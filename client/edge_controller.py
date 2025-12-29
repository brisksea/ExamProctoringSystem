#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import psutil
from selenium import webdriver
from selenium.webdriver.edge.service import Service
from browser_controller import BaseBrowserController
from edge_driver_manager import (
    get_edge_version, 
    get_edgedriver_path, 
    download_edgedriver_from_web
)

class EdgeController(BaseBrowserController):
    def __init__(self, config_manager=None, default_url=None, disable_new_tabs=False):
        super().__init__(config_manager, default_url, disable_new_tabs)

    def start(self, url=None):
        """启动受控的Edge浏览器"""
        try:
            options = webdriver.EdgeOptions()
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--start-maximized')
            options.add_argument('--disable-gpu')
            
            # Edge specific, similar to Chrome but for Edge
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)

            if self.disable_new_tabs:
                options.add_argument('--disable-popup-blocking')

            edge_version = get_edge_version()
            if not edge_version:
                raise Exception("无法检测到Edge浏览器版本")

            driver_path = get_edgedriver_path(edge_version)
            
            # 如果本地没有驱动，尝试下载 (优先从服务器下载)
            if not driver_path:
                if self.config_manager and hasattr(self.config_manager, 'api_client'):
                    try:
                        print("尝试从考试服务器下载 EdgeDriver...")
                        driver_path = self.config_manager.api_client.download_driver('edge', edge_version)
                    except Exception as e:
                        print(f"从服务器下载 EdgeDriver 失败: {e}")
                        driver_path = None
            
            # 如果服务器下载也失败，尝试从官网下载
            if not driver_path:
                try:
                    driver_path = download_edgedriver_from_web(edge_version)
                except Exception as e:
                    print(f"从官网下载 EdgeDriver 失败: {e}")
                    driver_path = None
            
            service = Service(driver_path) if driver_path else Service()
            self.driver = webdriver.Edge(service=service, options=options)

            initial_url = url if url else self.default_url
            self.driver.get(initial_url)
            
            # 获取 PID
            self.chrome_pid = None # 还是用这个变量名以保持基类兼容
            driver_pid = self.driver.service.process.pid
            
            try:
                parent = psutil.Process(driver_pid)
                children = parent.children(recursive=True)
                for child in children:
                    if child.name().lower() == 'msedge.exe':
                        self.chrome_pid = child.pid
                        break
            except Exception:
                pass
                
            if not self.chrome_pid:
                for proc in psutil.process_iter(['pid', 'name', 'ppid']):
                   try:
                       if proc.info['name'].lower() == 'msedge.exe' and proc.info['ppid'] == driver_pid:
                           self.chrome_pid = proc.info['pid']
                           break
                   except Exception:
                       continue

        except Exception as e:
            print(f"启动Edge浏览器时出错: {str(e)}")
            self.stop()
            raise
