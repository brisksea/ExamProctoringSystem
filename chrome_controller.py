#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import time
import psutil
import subprocess
import re
import logging
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import functools
import win32gui
import win32process

# 导入Chrome驱动管理模块（集成了版本检测和驱动管理功能）
from chrome_driver_manager import get_chrome_version, get_major_version, get_chromedriver_path, download_chromedriver_from_server

class ChromeController:
    def __init__(self, config_manager=None, default_url=None, disable_new_tabs=False):
        """
        初始化Chrome控制器

        Args:
            config_manager: 配置管理器实例
            default_url: 默认URL
            disable_new_tabs: 是否禁用新标签页
        """
        self.config_manager = config_manager
        self.disable_new_tabs = disable_new_tabs
        self.driver = None
        self.default_url = default_url
        self.window_title = None
        self.tab_title = None
        

        # 编译URL匹配模式
        self.url_restriction_enabled = True
        self.compiled_patterns = []
        self.allowed_urls = []
        if config_manager:
            self.default_url = config_manager.get_default_url()
            patterns = config_manager.get_url_patterns()
            self.compiled_patterns = [re.compile(pattern) for pattern in patterns]
            self.allowed_urls = config_manager.get_allowed_urls() or []
            if self.default_url and self.default_url not in self.allowed_urls:
                self.allowed_urls.append(self.default_url)

    def start(self, url=None):
        """启动受控的Chrome浏览器"""
        try:
            options = webdriver.ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--start-maximized')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-software-rasterizer')

            if self.disable_new_tabs:
                options.add_argument('--disable-popup-blocking')

            # 获取Chrome版本
            chrome_version = get_chrome_version()

            # 获取适用于当前Chrome版本的ChromeDriver路径
            driver_path = get_chromedriver_path(chrome_version)

            # 如果找到了兼容的ChromeDriver，使用它
            if not driver_path:
                driver_path = self.config_manager.api_client.download_chromedriver(chrome_version)
            service = Service(driver_path)
            self.driver = webdriver.Chrome(service=service, options=options)

            # 导航到初始URL或空白页
            initial_url = url if url else self.default_url
            self.driver.get(initial_url)
            

            #print("Chrome浏览器已启动")

            # 获取真正的Chrome浏览器PID
            self.chrome_pid = None
            chromedriver_pid = self.driver.service.process.pid
            #print(f"ChromeDriver PID: {chromedriver_pid}")
            
            for proc in psutil.process_iter(['pid', 'name', 'ppid']):
                try:
                    # 找到名称为chrome.exe且父进程为chromedriver的进程
                    if proc.info['name'].lower() == 'chrome.exe' and proc.info['ppid'] == chromedriver_pid:
                        self.chrome_pid = proc.info['pid']
                        #print(f"Chrome浏览器 PID: {self.chrome_pid}")
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue


        except Exception as e:
            print(f"启动Chrome浏览器时出错: {str(e)}")
            self.stop()
            raise

    def stop(self):
        """停止Chrome浏览器"""
        try:
            if self.driver:
                self.driver.quit()
                self.driver = None
                print("Chrome浏览器已关闭")
                self.chrome_pid = None
        except Exception as e:
            print(f"关闭Chrome浏览器时出错: {str(e)}")

    def is_running(self):
        """检查Chrome浏览器是否正在运行"""
        return self.chrome_pid is not None and psutil.pid_exists(self.chrome_pid)

    def is_controlled(self, pid):
        """检查当前Chrome实例是否是受控的"""
        if self.chrome_pid is None:
            return False
        return self.chrome_pid == pid


    def _strip_protocol(self, url):
        if url.startswith('http://'):
            return url[len('http://'):]
        elif url.startswith('https://'):
            return url[len('https://'):]
        return url

    def _is_url_allowed(self, url):
        """
        检查URL是否允许访问

        Args:
            url: 要检查的URL

        Returns:
            bool: 是否允许访问
        """
        if not self.url_restriction_enabled:
            return True

        # 处理 None 或空URL
        if not url:
            return True

        # 特殊页面总是允许
        if (url.startswith("about:") or
            url.startswith("chrome://") or
            url.startswith("chrome-error://") or
            url.startswith("data:text/html") or
            url.startswith("chrome-extension://") or
            url == "about:blank" or
            "chrome-search://" in url):
            return True

        # 检查是否匹配任何允许的URL模式
        try:
            for pattern in self.compiled_patterns:
                if pattern.match(url):
                    return True
        except Exception as e:
            print(f"正则表达式匹配错误: {str(e)}")
            return True
        
        try:
            url_no_proto = self._strip_protocol(url)
            for allowed_url in self.allowed_urls:
                allowed_url_no_proto = self._strip_protocol(allowed_url)
                if url_no_proto.startswith(allowed_url_no_proto):
                    return True
        except Exception as e:
            print(f"URL前缀匹配错误: {str(e)}")
            return True

        return False
    

    def to_default_url(self):
        if self.default_url:
            self.driver.execute_script(f"window.location.href = '{self.default_url}';")
        else:
            self.driver.execute_script("window.location.href = 'about:blank';")

    def check(self, pid, window_title):
        
        if not self.is_controlled(pid):
            return "未受控的Chrome浏览器，请切换到允许的浏览器进行考试"
        
        handles = self.driver.window_handles
        if self.disable_new_tabs and len(handles) > 1:
            error_msg = f"检测到多个标签页，请关闭多余标签页"
            print(error_msg)
            # 处理多标签页情况
            #self._handle_multiple_tabs_when_disabled()
            return error_msg
 
        #print("比较：",self.window_title, "， ", window_title)
        
        #如果chrome的链接没有发生变化不检查
        if self.window_title == window_title:
            return None
        
        title = window_title.split(" - G")[0]
        try:
            # 获取所有标签页句柄           
            current_handle = handles[0]
            for handle in handles:
                self.driver.switch_to.window(handle)
                url = self.driver.current_url
                if not self._is_url_allowed(url):
                    error_msg = f"未授权的URL: {url}，切换到允许的URL进行考试"
                    return error_msg
                #通过标题判断为当前标签
                #print(self.driver.title)
                if title == self.driver.title:
                    current_handle = handle
            self.driver.switch_to.window(current_handle)           
        except Exception as e:
            error_msg = f"获取标签页句柄时出错: {str(e)}"
            #print(error_msg)
            return error_msg
        self.window_title = window_title
        return None

    def handle_multiple_tabs_when_disabled(self):
        """处理禁用新标签页时的多标签页情况"""
        try:
            # 获取所有标签页句柄
            handles = self.driver.window_handles

            if len(handles) <= 1:
                return

            # 保留第一个标签页，关闭其他标签页
            first_handle = handles[0]
            for handle in handles[1:]:
                try:
                    self.driver.switch_to.window(handle)
                    self.driver.close()
                except Exception as e:
                    print(f"关闭多余标签页时出错: {str(e)}")

            # 切换回第一个标签页
            try:
                self.driver.switch_to.window(first_handle)
            except Exception as e:
                print(f"切换回第一个标签页时出错: {str(e)}")

        except Exception as e:
            print(f"处理多标签页时出错: {str(e)}")
        

    def check_and_restart_if_needed(self):
        """
        检查Chrome浏览器是否需要重启，如果需要则重启

        Returns:
            str: 成功状态
        """
        try:
            # 如果Chrome浏览器已经在运行，不需要重启
            if self.is_running():
                return 'running'

            # 尝试启动Chrome浏览器
            print("Chrome浏览器未运行或未受控，尝试重启...")

            # 启动浏览器
            self.driver.quit()
            self.driver = None
            self.start()

            return "restart"

        except Exception as e:
            print(f"重启Chrome浏览器时出错: {str(e)}")
            return "error"




