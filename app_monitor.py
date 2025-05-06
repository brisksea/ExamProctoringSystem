#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import psutil
import win32process
import win32api
import win32con
import win32gui
import time
import sys
from datetime import datetime

class AppMonitor:
    """
    监控应用程序的类，检测正在运行的应用程序并与允许列表比较
    """

    def __init__(self, config_manager, chrome_controller, exam_client):
        """
        初始化应用监控器

        Args:
            config_manager: 配置管理器实例
            chrome_controller: Chrome控制器实例
        """
        self.config_manager = config_manager
        self.chrome_controller = chrome_controller
        self.last_check_time = 0
        self.check_interval = 2  # 检查间隔时间（秒）
        self.foreground_window_pid = None
        self.foreground_window_title = ""
        self.exam_client = exam_client

    def isnewer(self, filepath):
        ctime = os.path.getctime(filepath)
        ctime_str = datetime.fromtimestamp(ctime).strftime("%Y-%m-%d %H:%M:%S")
        print(f"当前打开文件: {filepath}，创建日期: {ctime_str}") 
        exam_start_time_dt = datetime.fromisoformat(self.exam_client.exam_start_time)
        if ctime < exam_start_time_dt.timestamp():
            warn_msg = f"当前打开文件: {filepath} 的创建日期({ctime_str})早于考试开始时间({exam_start_time_dt.strftime('%Y-%m-%d %H:%M:%S')})，请注意是否为考试前准备的代码文件"
            return warn_msg

    def islater(self, filepath):
        ctime = os.path.getctime(filepath)
        mtime = os.path.getmtime(filepath)
        mtime_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
        print(f"当前打开文件: {filepath}，修改日期: {mtime_str}")
        exam_start_time_dt = datetime.fromisoformat(self.exam_client.exam_start_time)
        if mtime > exam_start_time_dt.timestamp(): return None

    def check_devcpp(self, window_title):
        # 通常Dev-C++窗口标题格式为 "xxx.cpp - Dev-C++"
        if window_title and " - Dev-C" in window_title:
            filename = window_title.split("- Dev-C")[0].strip()
            if os.path.exists(filename):
                try:
                    return self.isnewer(filename)
                except Exception as e:
                    print(f"无法获取文件创建日期: {filename}, 错误: {e}")                                            
            else:
                print(f"Dev-C++ 当前窗口文件未找到: {filename}")
        
        return None 
    
    def check_running_apps(self):
        """检查当前运行的应用程序"""
        try:
            # 获取当前前台窗口
            foreground_hwnd = win32gui.GetForegroundWindow()
            if foreground_hwnd == 0:
                return None

            # 获取前台窗口的进程ID和标题
            _, pid = win32process.GetWindowThreadProcessId(foreground_hwnd)
            window_title = win32gui.GetWindowText(foreground_hwnd)

            # 获取进程信息
            proc = psutil.Process(pid)
            process_name = proc.name()
            process_exe = proc.exe()

            # 获取允许的应用列表
            allowed_apps = [ app['exe'] for app in self.config_manager.get_allowed_apps() ]
            allowed_exes = [ exe['path'] for exe in self.config_manager.get_allowed_executables() ]
           
            '''
            print("允许的应用列表:", allowed_apps)
            print("允许的可执行文件:", allowed_exes)
            print("当前前台窗口进程ID:", pid)
            print("当前窗口标题:", window_title)
            print("进程名称:", process_name)
            print("可执行文件路径:", process_exe)
            '''
            
            
            # 如果是devcpp.exe，则根据它的标题推断出目前打开的文件，打印这个文件的创建日期
            if process_name.lower() == "devcpp.exe":
                return self.check_devcpp(window_title)


            # 如果是Chrome浏览器
            if process_name.lower() == "chrome.exe":
                return self.chrome_controller.check(pid, window_title)


            # 跳过系统进程和自身
            if self._is_system_process(process_name):
                print("跳过系统进程:", process_name)
                return None

            if self._is_self_process(process_exe):
                print("跳过自身进程:", process_exe)
                return None

            # 检查进程是否在允许列表中
            if not self._is_allowed_process(process_name, process_exe, allowed_apps, allowed_exes):
                # 使用窗口标题作为应用名称
                app_name = window_title if window_title else process_name
                print("发现未授权应用:", app_name, process_exe)
                if self.islater(process_exe): return None
                return f"未授权的前台应用: {app_name}，切换到允许的应用进行考试"
            


        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
            print("获取进程信息时出错:", str(e))
            # 如果无法获取进程信息，返回窗口标题
            if window_title:
                print("无法获取进程信息，但发现可能的未授权应用:", window_title)
                return f"未授权的前台应用: {window_title}，切换到允许的应用进行考试"
            
        

        # 更新最后检查时间
        self.last_check_time = time.time()

        return None  # 如果是授权应用则返回None

    def _is_system_process(self, process_name):
        """
        检查是否为系统进程

        Args:
            process_name: 进程名称

        Returns:
            bool: 是否为系统进程
        """
        system_processes = [
            'svchost.exe', 'explorer.exe', 'csrss.exe', 'services.exe',
            'smss.exe', 'winlogon.exe', 'lsass.exe', 'spoolsv.exe',
            'dwm.exe', 'taskhostw.exe', 'conhost.exe', 'dllhost.exe',
            'fontdrvhost.exe', 'wininit.exe', 'sihost.exe', 'ctfmon.exe',
            'searchindexer.exe', 'ShellExperienceHost.exe', 'RuntimeBroker.exe',
            'SgrmBroker.exe', 'wmiprvse.exe', 'searchui.exe', 'textInputHost.exe',
            'SearchApp.exe'
        ]
        return process_name.lower() in [ proc.lower() for proc in system_processes ]

    def _is_self_process(self, process_exe):
        """
        检查是否为自身进程

        Args:
            process_exe: 进程可执行文件路径

        Returns:
            bool: 是否为自身进程
        """
        if not process_exe:
            return False

        # 当前python解释器
        if process_exe.lower() == sys.executable.lower():
            return True

        # python相关进程
        if os.path.basename(process_exe).lower() in ('python.exe', 'pythonw.exe'):
            return True

        return False

    def _is_allowed_process(self, process_name, process_exe, allowed_apps, allowed_exes):
        """
        检查进程是否在允许的应用列表中

        Args:
            process_name: 进程名称
            process_exe: 进程可执行文件路径
            allowed_apps: 允许的应用名称列表
            allowed_exes: 允许的可执行文件列表

        Returns:
            bool: 是否在允许的应用列表中
        """
        # 检查进程名
        if process_name.lower() in (app.lower() for app in allowed_apps):
            return True

        # 检查可执行文件路径
        if process_exe:
            # 完整路径匹配
            if process_exe.lower() in (exe.lower() for exe in allowed_exes):
                return True


        return False

    def get_foreground_window_info(self):
        """
        获取当前前台窗口信息

        Returns:
            tuple: (窗口标题, 进程ID)
        """
        # 获取当前前台窗口
        foreground_hwnd = win32gui.GetForegroundWindow()
        if foreground_hwnd == 0:
            # 没有前台窗口，返回当前存储的值
            return (self.foreground_window_title, self.foreground_window_pid)

        # 获取前台窗口的进程ID
        _, pid = win32process.GetWindowThreadProcessId(foreground_hwnd)
        self.foreground_window_pid = pid

        # 获取前台窗口标题
        window_title = win32gui.GetWindowText(foreground_hwnd)
        self.foreground_window_title = window_title

        return (self.foreground_window_title, self.foreground_window_pid)
