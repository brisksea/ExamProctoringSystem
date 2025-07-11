#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import sys
import argparse
import requests
import time


class ConfigManager:
    """
    配置管理器类，负责管理考试监控客户端的配置
    """

    def __init__(self, config_file=None, api_client=None):
        """
        初始化配置管理器

        Args:
            config_file: 配置文件路径，如果为None则使用默认路径
            api_client: 获取配置接口
        """
        if config_file:
            # 默认配置文件路径
            self.config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

        # 服务器URL
        self.api_client = api_client

        # 配置来源标志
        self.config_from_server = False

        # 默认配置
        self.default_config = {
            "allowed_apps": [
                {"exe": "chrome.exe", "name": "谷歌浏览器"},
                {"exe": "msedge.exe", "name": "Edge浏览器"},
                {"exe": "notepad.exe", "name": "记事本"},
                {"exe": "calc.exe", "name": "计算器"},
                {"exe": "devcpp.exe", "name": "Dev-C++"},
                {"exe": "cursor.exe", "name": "Cursor"},
                {"exe": "mspaint.exe", "name": "画图"},
                {"exe": "evcapture.exe", "name": "录屏"},
                {"exe": "ConsolePauser.exe", "name": "Dev-C++"}
            ],

            "allowed_executables": [
                {"path": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe", "name": "谷歌浏览器"},
            ], 

            "allowed_apps1": [
                {"exe": "chrome.exe", "name": "谷歌浏览器"},
                {"exe": "msedge.exe", "name": "Edge浏览器"},
                {"exe": "firefox.exe", "name": "火狐浏览器"},
                {"exe": "notepad.exe", "name": "记事本"},
                {"exe": "notepad++.exe", "name": "Notepad++"},
                {"exe": "code.exe", "name": "VS Code"},
                {"exe": "devenv.exe", "name": "Visual Studio"},
                {"exe": "idea64.exe", "name": "IntelliJ IDEA"},
                {"exe": "pycharm64.exe", "name": "PyCharm"},
                {"exe": "eclipse.exe", "name": "Eclipse"},
                {"exe": "sublime_text.exe", "name": "Sublime Text"},
                {"exe": "atom.exe", "name": "Atom"},
                {"exe": "calc.exe", "name": "计算器"},
                {"exe": "AcroRd32.exe", "name": "Adobe Reader"},
                {"exe": "SumatraPDF.exe", "name": "Sumatra PDF"},
                {"exe": "winword.exe", "name": "Word"},
                {"exe": "excel.exe", "name": "Excel"},
                {"exe": "powerpnt.exe", "name": "PowerPoint"},
                {"exe": "explorer.exe", "name": "资源管理器"},
                {"exe": "cmd.exe", "name": "命令提示符"},
                {"exe": "powershell.exe", "name": "PowerShell"},
                {"exe": "WindowsTerminal.exe", "name": "Windows Terminal"}
            ],
            "allowed_executables1": [
                {"path": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe", "name": "谷歌浏览器"},
                {"path": "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe", "name": "谷歌浏览器(32位)"},
                {"path": "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe", "name": "Edge浏览器"},
                {"path": "C:\\Program Files\\Mozilla Firefox\\firefox.exe", "name": "火狐浏览器"},
                {"path": "C:\\Windows\\System32\\notepad.exe", "name": "记事本"},
                {"path": "C:\\Windows\\System32\\calc.exe", "name": "计算器"},
                {"path": "C:\\Windows\\explorer.exe", "name": "资源管理器"},
                {"path": "C:\\Windows\\System32\\cmd.exe", "name": "命令提示符"},
                {"path": "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe", "name": "PowerShell"},
                {"path": "C:\\Program Files\\Notepad++\\notepad++.exe", "name": "Notepad++"},
                {"path": "C:\\Program Files\\Microsoft VS Code\\Code.exe", "name": "VS Code"},
                {"path": "C:\\Program Files (x86)\\Microsoft Visual Studio\\2019\\Community\\Common7\\IDE\\devenv.exe", "name": "Visual Studio"},
                {"path": "C:\\Program Files\\JetBrains\\IntelliJ IDEA*\\bin\\idea64.exe", "name": "IntelliJ IDEA"},
                {"path": "C:\\Program Files\\JetBrains\\PyCharm*\\bin\\pycharm64.exe", "name": "PyCharm"},
                {"path": "C:\\Program Files (x86)\\Adobe\\Acrobat Reader DC\\Reader\\AcroRd32.exe", "name": "Adobe Reader"},
                {"path": "C:\\Program Files\\SumatraPDF\\SumatraPDF.exe", "name": "Sumatra PDF"},
                {"path": "C:\\Program Files\\Microsoft Office\\root\\Office16\\WINWORD.EXE", "name": "Word"},
                {"path": "C:\\Program Files\\Microsoft Office\\root\\Office16\\EXCEL.EXE", "name": "Excel"},
                {"path": "C:\\Program Files\\Microsoft Office\\root\\Office16\\POWERPNT.EXE", "name": "PowerPoint"}
            ],
            "allowed_urls": [
                "https://pintia.cn"
            ],
            "allowed_url_patterns": [
                "^https://pintia\\.cn/.*$"
            ],
            "default_url": "https://pintia.cn",  # 浏览器启动后自动导航到的网址
            "exam_time_limit": 120,  # 考试时间限制（分钟）
            "chrome_settings": {
                "disable_extensions": True,
                "disable_dev_tools": True,
                "disable_downloads": False,  # 允许下载，方便获取考试资料
                "disable_printing": False,   # 允许打印
                "disable_new_tabs": False    # 允许新标签页
            },
            "only_monitor_foreground": True,  # 只监控前台窗口，忽略后台进程

            "enable_server_reporting": True,  # 是否启用服务器报告功能
            "screenshot_on_violation": True,   # 是否在违规时截图
            "end_violation_foreground_process": False  # 是否结束违规前台进程
        }

        # 如果提供了服务器URL，尝试从服务器获取配置
        if self.api_client:
            server_config = self.api_client.fetch_config()
            if server_config:
                self.config = server_config
                self.config_from_server = True
                print(f"已从服务器 {self.api_client.server_url} 获取配置")
                return
            else:
                print(f"无法从服务器获取配置，使用本地配置")
                # 加载配置
        
        self.config = self.load_config()

    def load_config(self):
        """
        从配置文件加载配置

        Returns:
            dict: 配置字典
        """
        # 如果配置文件不存在，创建默认配置文件
        if not self.config_file or not os.path.exists(self.config_file):
            return self.default_config.copy()

        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            return config
        except Exception as e:
            print(f"加载配置文件时出错: {str(e)}")
            # 出错时重新创建默认配置
            #self.save_default_config()
            return self.default_config.copy()

    def get_allowed_apps(self):
        """
        获取允许的应用程序对象列表
        Returns:
            list: 允许的应用程序对象列表（含 exe 和 name）
        """
        apps = self.config.get("allowed_apps", self.default_config["allowed_apps"])
        filtered_apps = [app for app in apps if isinstance(app, dict) and 'exe' in app]
        return filtered_apps

    def get_allowed_executables(self):
        """
        获取允许的可执行文件对象列表
        Returns:
            list: 允许的可执行文件对象列表（含 path 和 name）
        """
        exes = self.config.get("allowed_executables", self.default_config["allowed_executables"])
        filtered_exes = [exe for exe in exes if isinstance(exe, dict) and 'path' in exe]
        return filtered_exes

    def get_allowed_urls(self):
        """
        获取允许访问的URL列表

        Returns:
            list: 允许访问的URL列表
        """
        return self.config.get("allowed_urls", self.default_config["allowed_urls"])

    def get_allowed_url_patterns(self):
        """
        获取允许访问的URL正则表达式模式列表

        Returns:
            list: 允许访问的URL正则表达式模式列表
        """
        return self.config.get("allowed_url_patterns", self.default_config["allowed_url_patterns"])

    def get_url_patterns(self):
        """
        获取允许访问的URL正则表达式模式列表
        与get_allowed_url_patterns方法功能相同，为保持兼容性添加

        Returns:
            list: 允许访问的URL正则表达式模式列表
        """
        return self.get_allowed_url_patterns()

    def get_exam_time_limit(self):
        """
        获取考试时间限制（分钟）

        Returns:
            int: 考试时间限制
        """
        return self.config.get("exam_time_limit", self.default_config["exam_time_limit"])

    def get_chrome_settings(self):
        """
        获取Chrome浏览器设置

        Returns:
            dict: Chrome浏览器设置
        """
        return self.config.get("chrome_settings", self.default_config["chrome_settings"])


    def is_foreground_only_monitoring(self):
        """
        获取是否只监控前台程序

        Returns:
            bool: 是否只监控前台程序
        """
        return self.config.get("only_monitor_foreground", self.default_config["only_monitor_foreground"])

    def is_server_reporting_enabled(self):
        """
        获取是否启用服务器报告

        Returns:
            bool: 是否启用服务器报告
        """
        return self.config.get("enable_server_reporting", self.default_config["enable_server_reporting"])

    def is_screenshot_on_violation_enabled(self):
        """
        获取是否在违规时截图

        Returns:
            bool: 是否在违规时截图
        """
        return self.config.get("screenshot_on_violation", self.default_config["screenshot_on_violation"])

    def get_default_url(self):
        """
        获取浏览器启动后自动导航到的网址

        Returns:
            str: 默认网址
        """
        return self.config.get("default_url", self.default_config["default_url"])
    
    def get_delay_min(self):
        """
        获取延迟时间

        Returns:
            int: 延迟时间
        """
        return self.config.get("delay_min", self.default_config.get("delay_min", 0))

    def is_config_from_server(self):
        """
        检查配置是否来自服务器

        Returns:
            bool: 配置是否来自服务器
        """
        return self.config_from_server

    def refresh_config_from_server(self):
        """
        从服务器刷新配置

        Returns:
            bool: 是否成功刷新
        """
        if not self.api_client:
            return False

        server_config = self.api_client.fetch_config()
        if server_config:
            self.config = server_config
            self.config_from_server = True
            print(f"已从服务器刷新配置")
            return True
        else:
            print(f"无法从服务器刷新配置")
            return False

    def is_end_violation_foreground_process_enabled(self):
        """是否结束违规前台进程"""
        return self.config.get("end_violation_foreground_process", False)