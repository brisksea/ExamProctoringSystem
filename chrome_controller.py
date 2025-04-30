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
from chrome_driver_manager import get_chrome_version, get_major_version, get_chromedriver_path

class ChromeController:
    def __init__(self, config_manager=None, default_url=None, disable_new_tabs=True):
        """
        初始化Chrome控制器

        Args:
            config_manager: 配置管理器实例
            disable_new_tabs: 是否禁用新标签页
        """
        self.config_manager = config_manager
        self.disable_new_tabs = disable_new_tabs
        self.driver = None
        self.default_url = default_url
        

        # 编译URL匹配模式
        self.url_restriction_enabled = True
        self.compiled_patterns = []
        self.allowed_urls = []
        if config_manager:
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

            if self.disable_new_tabs:
                options.add_argument('--disable-popup-blocking')

            # 获取Chrome版本
            chrome_version = get_chrome_version()

            # 获取适用于当前Chrome版本的ChromeDriver路径
            driver_path = get_chromedriver_path(chrome_version)

            # 如果找到了兼容的ChromeDriver，使用它
            if driver_path:
                service = Service(driver_path)
                self.driver = webdriver.Chrome(service=service, options=options)
            else:
                # 否则使用webdriver_manager自动下载
                from webdriver_manager.chrome import ChromeDriverManager
                service = Service(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=options)


            # 导航到初始URL或空白页
            initial_url = url if url else self.default_url


            # 如果配置管理器存在且未提供URL，使用默认URL
            if not initial_url and self.config_manager:
                default_url = self.config_manager.get_default_url()
                if default_url:
                    initial_url = default_url
            self.driver.get(initial_url)

            # 注入限制脚本
            self._inject_tab_restrictions()

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


    def _inject_tab_restrictions(self):
        """注入JavaScript脚本禁用标签页和右键菜单"""
        try:
            # 基本限制脚本 - 禁用右键菜单和新窗口快捷键
            restriction_script = """
            // 禁用右键菜单
            document.addEventListener('contextmenu', function(e) {
                e.preventDefault();
                return false;
            }, true);

            // 禁用新窗口和隐私窗口快捷键
            document.addEventListener('keydown', function(e) {
                // Ctrl+N (新窗口)
                if (e.ctrlKey && e.key === 'n') {
                    e.preventDefault();
                    return false;
                }

                // Ctrl+Shift+N (隐私窗口)
                if (e.ctrlKey && e.shiftKey && e.key === 'n') {
                    e.preventDefault();
                    return false;
                }

                // Alt+F4 (关闭窗口)
                if (e.altKey && e.key === 'F4') {
                    e.preventDefault();
                    return false;
                }
            """

            # 如果配置为禁用新标签页，添加相应的限制
            if self.disable_new_tabs:
                restriction_script += """
                // Ctrl+T (新标签页)
                if (e.ctrlKey && e.key === 't') {
                    e.preventDefault();
                    return false;
                }

                // Ctrl+W (关闭标签页)
                if (e.ctrlKey && e.key === 'w') {
                    e.preventDefault();
                    return false;
                }
                """

            # 完成事件监听器
            restriction_script += """
            }, true);
            """

            # 添加MutationObserver部分
            restriction_script += """
            // 在每个页面载入后自动注入限制
            function setupMutationObserver() {
                // 创建一个新的MutationObserver
                const observer = new MutationObserver(function() {
            """

            # 如果配置为禁用新标签页，添加隐藏新标签页按钮的代码
            if self.disable_new_tabs:
                restriction_script += """
                    // 禁用标签页相关元素
                    try {
                        // 隐藏新标签按钮
                        const newTabButtons = document.querySelectorAll('[title="新建标签页"], [title="New tab"]');
                        newTabButtons.forEach(btn => {
                            if(btn) btn.style.display = 'none';
                        });

                        // 隐藏标签栏中的加号按钮
                        const plusButtons = document.querySelectorAll('.new-tab-button');
                        plusButtons.forEach(btn => {
                            if(btn) btn.style.display = 'none';
                        });
                    } catch(e) {
                        console.log('禁用标签页元素时出错:', e);
                    }
                """

            # 完成MutationObserver部分
            restriction_script += """
                });

                // 开始观察document.body的变化
                observer.observe(document.body, {
                    childList: true,
                    subtree: true
                });
            }

            // 当DOM内容加载完成后执行设置
            if(document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', setupMutationObserver);
            } else {
                setupMutationObserver();
            }
            """

            # 执行脚本
            self.driver.execute_script(restriction_script)

            # 处理window.open函数
            if self.disable_new_tabs:
                # 如果禁用新标签页，阻止window.open
                self.driver.execute_script("""
                // 保存原始的window.open函数
                if (!window._originalOpen) {
                    window._originalOpen = window.open;
                }

                // 重写window.open，阻止打开
                window.open = function() {
                    console.log('阻止新窗口打开');
                    return null;
                };
                """)
            else:
                # 如果允许新标签页，只记录但不阻止
                self.driver.execute_script("""
                // 保存原始的window.open函数
                if (!window._originalOpen) {
                    window._originalOpen = window.open;
                }

                // 重写window.open，允许打开但记录
                window.open = function(url, name, specs) {
                    console.log('打开新窗口/标签页:', url);
                    // 确保我们不会重复包装window.open
                    return window._originalOpen(url, name, specs);
                };
                """)

            print("已注入标签页限制脚本")
        except Exception as e:
            print(f"注入标签页限制脚本时出错: {str(e)}")

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


    def check_tabs_and_urls(self):
        """
        检查Chrome标签页数量和URL

        Returns:
            tuple: (是否符合要求, 错误信息)
        """

        try:
            # 获取所有标签页句柄
            handles = self.driver.window_handles

            # 检查标签页数量
            if self.disable_new_tabs and len(handles) > 1:
                error_msg = f"检测到多个标签页，请关闭多余标签页"
                print(error_msg)
                # 处理多标签页情况
                #self._handle_multiple_tabs_when_disabled()
                return False, error_msg

            # 检查当前标签页URL
            try:
                current_url = self.driver.current_url

                # 跳过特殊页面
                if (current_url == "about:blank" or
                    current_url.startswith("chrome://") or
                    current_url.startswith("chrome-extension://") or
                    "data:text/html" in current_url):
                    return True, None

                # 检查URL是否允许
                if not self._is_url_allowed(current_url):
                    error_msg = f"未授权的URL: {current_url}，切换到允许的URL进行考试"
                    print(error_msg)

                    return False, error_msg

            except Exception as e:
                error_msg = f"检查URL时出错: {str(e)}"
                print(error_msg)
                return False, error_msg
            
        except Exception as e:
            error_msg = f"获取标签页句柄时出错: {str(e)}"
            print(error_msg)
            return False, error_msg
        
        return True, None

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


