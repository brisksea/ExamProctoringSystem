#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import psutil
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from browser_controller import BaseBrowserController
from chrome_driver_manager import get_chrome_version, get_chromedriver_path

class ChromeController(BaseBrowserController):
    def __init__(self, config_manager=None, default_url=None, disable_new_tabs=False):
        super().__init__(config_manager, default_url, disable_new_tabs)

    def start(self, url=None):
        """启动受控的Chrome浏览器"""
        try:
            options = webdriver.ChromeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--start-maximized')
            options.add_argument('--disable-gpu')
            options.add_argument('--disable-software-rasterizer')
            
            # 标记为被自动化控制，有些场景下可能需要隐藏这个标记，但在考试场景可能不强制
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)

            if self.disable_new_tabs:
                options.add_argument('--disable-popup-blocking')

            # 获取Chrome版本
            chrome_version = get_chrome_version()
            if not chrome_version:
                raise Exception("无法检测到Chrome浏览器版本，请确保Chrome已正确安装")

            # 获取适用于当前Chrome版本的ChromeDriver路径
            try:
                # 尝试普通获取
                driver_path = get_chromedriver_path(chrome_version)
            except Exception:
                driver_path = None
            
            if not driver_path:
                # 如果没有本地驱动，尝试下载
                # 注意：chrome_driver_manager.py 必须确保有 api_client 或者独立可用的下载逻辑
                # 原逻辑引用了 self.config_manager.api_client.download_chromedriver 
                # 但 chrome_driver_manager 实际上提供了 download_chromedriver_from_server
                # 这里我们保持原有的逻辑，如果 config_manager 提供了 api_client
                if self.config_manager and hasattr(self.config_manager, 'api_client'):
                    driver_path = self.config_manager.api_client.download_driver('chrome', chrome_version)
                else: 
                     # 如果没有 config_manager 或 api_client，可能无法下载，除非 logic 在 get_chromedriver_path 内部
                     # 原 main.py 中逻辑是: if not driver_path: driver_path = self.config_manager.api_client.download_chromedriver(chrome_version)
                     # 所以这里我们必须保留对 api_client 的调用
                     pass

            if not driver_path:
                 # 最后尝试直接 Service() 让 selenium 自己去找（通常不靠谱如果版本不一）
                 # 或者抛出异常
                 pass

            service = Service(driver_path) if driver_path else Service()
            self.driver = webdriver.Chrome(service=service, options=options)

            # 导航到初始URL或空白页
            initial_url = url if url else self.default_url
            self.driver.get(initial_url)
            
            # 获取真正的Chrome浏览器PID
            self.chrome_pid = None
            chromedriver_pid = self.driver.service.process.pid
            
            try:
                parent = psutil.Process(chromedriver_pid)
                children = parent.children(recursive=True)
                for child in children:
                    if child.name().lower() == 'chrome.exe':
                        self.chrome_pid = child.pid
                        break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            
            if not self.chrome_pid:
                for proc in psutil.process_iter(['pid', 'name', 'ppid']):
                    try:
                        if proc.info['name'].lower() == 'chrome.exe' and proc.info['ppid'] == chromedriver_pid:
                            self.chrome_pid = proc.info['pid']
                            break
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue

        except Exception as e:
            print(f"启动Chrome浏览器时出错: {str(e)}")
            self.stop()
            raise
