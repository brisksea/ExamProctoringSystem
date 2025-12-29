#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
import time
import threading
import uuid
import json
from PIL import ImageGrab
from io import BytesIO
import socket
import hashlib
import traceback
from datetime import datetime, timezone
from tkinter import messagebox
import psutil
import tkinter as tk


from app_monitor import AppMonitor
from chrome_controller import ChromeController
from config_manager import ConfigManager
from api_client import ApiClient

class LoginWindow:
    """登录窗口类，用于用户登录"""

    def __init__(self, root, on_login_success):
        """
        初始化登录窗口

        Args:
            root: 父窗口
            on_login_success: 登录成功回调函数
        """
        self.root = root
        self.on_login_success = on_login_success
        self.server_ip = '10.188.2.252'
        #self.server_ip = '127.0.0.1'

        # 设置窗口属性
        self.root.title("考试监控系统 - 登录")
        self.root.geometry("400x350")  # 增加高度以适应新的输入框
        self.root.resizable(False, False)

        # 居中窗口
        self.center_window()

        # 创建界面
        self.create_widgets()

        # 绑定关闭事件，确保关闭登录窗口时退出整个程序
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def center_window(self):
        """将窗口居中显示"""
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry('{}x{}+{}+{}'.format(width, height, x, y))

    def create_widgets(self):
        """创建登录界面控件"""
        try:
            # 创建主框架
            main_frame = tk.Frame(self.root, padx=30, pady=20)
            main_frame.pack(fill=tk.BOTH, expand=True)

            # 标题
            title_label = tk.Label(main_frame, text="考试监控系统登录", font=("Arial", 18, "bold"))
            title_label.pack(pady=10)

            # 说明文本
            info_label = tk.Label(main_frame, text="请输入您的信息以继续", font=("Arial", 10))
            info_label.pack(pady=5)

            # 学号输入框架
            student_id_frame = tk.Frame(main_frame)
            student_id_frame.pack(fill=tk.X, pady=8)

            student_id_label = tk.Label(student_id_frame, text="学号:", width=8)
            student_id_label.pack(side=tk.LEFT, padx=5)

            self.student_id_entry = tk.Entry(student_id_frame, width=25)
            self.student_id_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
            self.student_id_entry.focus_set()  # 设置焦点

            # 姓名显示框架
            name_frame = tk.Frame(main_frame)
            name_frame.pack(fill=tk.X, pady=8)

            name_label = tk.Label(name_frame, text="姓名:", width=8)
            name_label.pack(side=tk.LEFT, padx=5)

            self.name_entry = tk.Entry(name_frame, width=25, state='readonly')
            self.name_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

            # 服务器地址输入框架
            server_frame = tk.Frame(main_frame)
            server_frame.pack(fill=tk.X, pady=8)

            server_label = tk.Label(server_frame, text="服务器:", width=8)
            server_label.pack(side=tk.LEFT, padx=5)

            # 获取默认服务器地址
            default_server = self.server_ip

            self.server_entry = tk.Entry(server_frame, width=25)
            self.server_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
            self.server_entry.insert(0, default_server)  # 设置默认值

            # 服务器提示
            server_info = tk.Label(main_frame, text="服务器IP地址",
                               font=("Arial", 8), fg="#555555", justify=tk.CENTER)
            server_info.pack(pady=5)

            # 状态提示
            self.status_label = tk.Label(main_frame, text="请输入学号后按回车键或点击查询姓名",
                                        font=("Arial", 9), fg="#555555", justify=tk.CENTER)
            self.status_label.pack(pady=5)

            # 按钮框架
            button_frame = tk.Frame(main_frame)
            button_frame.pack(pady=10)

            # 查询姓名按钮
            self.query_button = tk.Button(button_frame, text="查询姓名", command=self.query_student_name, width=12, height=2)
            self.query_button.pack(side=tk.LEFT, padx=(0, 10))

            # 登录按钮
            self.login_button = tk.Button(button_frame, text="登录", command=self.login, width=12, height=2, state='disabled')
            self.login_button.pack(side=tk.LEFT)

            # 登录状态标记
            self.login_step = 1  # 1: 查询姓名, 2: 确认登录
            self.current_student_id = ""
            self.current_student_name = ""

            # 绑定事件
            #self.student_id_entry.bind('<Return>', lambda _: self.query_student_name())
            self.student_id_entry.bind('<KeyRelease>', self.on_student_id_change)
            self.root.bind('<Return>', self.on_enter_key)
        except Exception as e:
            messagebox.showerror("界面初始化失败", f"错误信息: {e}")
            raise

    def on_student_id_change(self, event):
        """学号输入框内容变化时的处理"""
        student_id = self.student_id_entry.get().strip()
        if not student_id:
            # 清空姓名和重置状态
            self.name_entry.config(state='normal')
            self.name_entry.delete(0, tk.END)
            self.name_entry.config(state='readonly')
            self.login_button.config(state='disabled')
            self.query_button.config(state='normal')
            self.status_label.config(text="请输入学号后按回车键或点击查询姓名")
            self.login_step = 1
            self.current_student_id = ""
            self.current_student_name = ""

    def on_enter_key(self, event):
        """处理回车键事件"""
        if self.login_step == 1:
            self.query_student_name()
        elif self.login_step == 2:
            self.login()

    def query_student_name(self):
        """查询学生姓名"""
        student_id = self.student_id_entry.get().strip()
        server_ip = self.server_entry.get().strip()

        if not student_id:
            messagebox.showwarning("警告", "请输入学号")
            return

        if not server_ip:
            messagebox.showwarning("警告", "请输入服务器地址")
            return
        else:
            import re
            pattern = r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$'
            match = re.match(pattern, server_ip)
            if not match:
                messagebox.showwarning("警告", "请输入有效的服务器IP地址")
                return

        # 创建API客户端
        self.api_client = ApiClient(server_ip)

        # 查询学生姓名
        self.status_label.config(text="正在查询学生信息...")
        self.query_button.config(state='disabled')

        try:
            success, student_name, error_message = self.api_client.get_student_name_by_id(student_id)

            if success:
                # 显示姓名
                self.name_entry.config(state='normal')
                self.name_entry.delete(0, tk.END)
                self.name_entry.insert(0, student_name)
                self.name_entry.config(state='readonly')

                # 更新状态
                self.current_student_id = student_id
                self.current_student_name = student_name
                self.login_step = 2
                self.login_button.config(state='normal')
                self.query_button.config(state='disabled')
                self.status_label.config(text="请确认姓名无误后点击登录按钮")
            else:
                # 查询失败
                messagebox.showerror("查询失败", error_message)
                self.query_button.config(state='normal')
                self.status_label.config(text="查询失败，请检查学号或网络连接")
                # 让主窗口重新获得焦点
                self.root.focus_force()
                # 将光标定位到学号输入框
                self.student_id_entry.delete(0, tk.END)
                self.student_id_entry.focus_set()
        except Exception as e:
            messagebox.showerror("查询错误", f"查询过程中发生错误: {str(e)}")
            self.query_button.config(state='normal')
            self.status_label.config(text="查询失败，请重试")

    def login(self):
        """处理登录"""
        if self.login_step != 2:
            messagebox.showwarning("警告", "请先查询学生姓名")
            return

        if not self.current_student_id or not self.current_student_name:
            messagebox.showwarning("警告", "学生信息不完整，请重新查询")
            return

        # 使用学号和姓名进行登录
        self.status_label.config(text="正在登录...")
        self.login_button.config(state='disabled')

        try:
            success, login_data, error_message = self.api_client.login(
                self.current_student_id, self.current_student_name
            )

            if success:
                # 登录成功
                self.on_login_success(self.current_student_name, self.api_client, login_data)
            elif success is None and error_message == "choice_required":
                # 需要选择考试
                self.show_exam_selection_with_student_info(login_data)
            else:
                # 登录失败
                messagebox.showerror("登录失败", error_message)
                self.login_button.config(state='normal')
                self.status_label.config(text="登录失败，请重试")
        except Exception as e:
            messagebox.showerror("登录错误", f"登录过程中发生错误: {str(e)}")
            self.login_button.config(state='normal')
            self.status_label.config(text="登录失败，请重试")


    def on_close(self):
        self.root.destroy()
        import sys
        sys.exit(0)

class ExamClient:
    def __init__(self, root):
        self.root = root
        self.root.withdraw()  # 隐藏主窗口，等待登录

        # 生成唯一学生ID
        self.student_id = None

        # 首先显示登录窗口
        self.login_window = LoginWindow(tk.Toplevel(root), self.on_login_success)

        # 用户信息
        self.username = ""

        # 服务器连接配置
        self.server_ip = None  # 由登录界面提供
        self.connected_to_server = False
        self.heartbeat_thread = None

        # 截图上传相关
        self.screenshot_thread = None
        self.screenshot_interval = self.get_screenshot_interval_from_config()
        self.screenshot_uploading = False

        # 日志目录和文件初始化
        self.log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

        # 默认日志文件名，登录后会更新
        self.log_file = os.path.join(self.log_dir, f"client_{time.strftime('%Y-%m-%d')}.log")

        # 其他属性初始化将在登录成功后进行

    def get_screenshot_interval_from_config(self):
        # 优先从 config_manager.config 获取
        interval = None
        if hasattr(self, 'config_manager') and hasattr(self.config_manager, 'config'):
            interval = self.config_manager.config.get('screenshot_interval')
        if interval is None:
            # 兼容旧配置，或未获取到时默认30秒
            interval = 30
        return interval

    def on_login_success(self, username, api_client, login_data=None):
        """
        登录成功的回调

        Args:
            username: 用户名
            api_client: 服务器API接口
            login_data: 登录返回的详细信息
        """
        # 关闭登录窗口
        self.login_window.root.destroy()

        # 记录用户名
        self.username = username

        # 解析并保存登录返回的关键信息
        self.exam_id = login_data.get("exam_id") if login_data else None
        self.student_id = login_data.get("student_id") if login_data else None
        self.exam_name = login_data.get("exam_name") if login_data else None
        self.exam_start_time = login_data.get("start_time") if login_data else None
        self.exam_end_time = login_data.get("end_time") if login_data else None
        self.exam_default_url = login_data.get("default_url", "about:blank") if login_data else None
        self.disable_new_tabs = login_data.get("disable_new_tabs", False) if login_data else False
        self.delay_min = login_data.get("delay_min", 0) if login_data else 0

        print(f"[DEBUG][on_login_success] login_data: {login_data}")

        # 检查关键信息
        if not self.exam_id or not self.student_id:
            messagebox.showerror("登录失败", "未获取到考试ID或学生ID，无法进入考试系统。请确认您的信息或联系管理员。")
            return

        # 生成学生ID (基于用户名和机器信息)（如未从服务器获取到student_id时备用）
        if not self.student_id:
            user_info = f"{username}_{socket.gethostname()}_{uuid.getnode()}"
            self.student_id = hashlib.md5(user_info.encode()).hexdigest()

        # 日志文件名格式: user_姓名_yyyy-mm-dd.log
        log_date = time.strftime("%Y-%m-%d", time.localtime())
        self.log_file = os.path.join(self.log_dir, f"user_{username}_{log_date}.log")

        # 记录用户登录
        self.write_log(f"用户 '{username}' 登录系统")

        # 显示主窗口
        self.root.deiconify()
        self.root.title(f"考试监控客户端 - 用户: {self.username}")
        self.root.geometry("1024x768")
        #screen_width = self.root.winfo_screenwidth()
        #screen_height = self.root.winfo_screenheight()
        #self.root.geometry(f"{int(screen_width*0.8)}x{int(screen_height*0.8)}")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # 禁止用户调整窗口大小
        self.root.resizable(False, False)


        # 创建API客户端
        self.api_client = api_client
        # 创建配置管理器，传入服务器URL以从服务器获取配置
        self.config_manager = ConfigManager(api_client = self.api_client)

        # 创建界面
        self.create_widgets()


        # 刷新截图间隔
        self.screenshot_interval = self.get_screenshot_interval_from_config()

        if not self.exam_default_url and self.config_manager:
            self.exam_default_url = self.config_manager.get_default_url()


        # 设置本场考试专用 default_url 和 allowed_urls（不写入配置文件，只在内存中用）
        if self.exam_default_url:
            # 合并 default_url 到 allowed_urls，仅在内存中生效
            allowed_urls = self.config_manager.get_allowed_urls()
            if self.exam_default_url not in allowed_urls:
                allowed_urls = [self.exam_default_url] + allowed_urls
            self._exam_allowed_urls = allowed_urls
        else:
            self._exam_allowed_urls = self.config_manager.get_allowed_urls()


        # 启动Chrome浏览器
        try:
            print(f"[DEBUG][on_login_success] chrome_start_url: {self.exam_default_url}")
            chrome_start_url = self.exam_default_url if self.exam_default_url else None
            self.chrome_controller = ChromeController(
                config_manager=self.config_manager,
                default_url=chrome_start_url,
                disable_new_tabs=self.disable_new_tabs
            )
            self.chrome_controller.start()
            self.browser_status.set("已启动 (受控模式)")
            self.log("Chrome浏览器已启动，插件已被禁用")
        except Exception as e:
            self.log(f"启动Chrome浏览器失败: {str(e)}")
            messagebox.showerror("错误", f"启动Chrome浏览器失败: {str(e)}")

        # 创建应用监控器
        self.app_monitor = AppMonitor(self.config_manager, self.chrome_controller, self)

        # 前台应用状态
        self.foreground_app = ""

        # 异常检测延时
        self.last_warning_time = 0
        self.warning_cooldown = 10  # 异常检测后的冷却时间（秒）


        # 监控线程
        self.monitoring = False
        self.monitor_thread = None

        # 日志目录
        self.log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

        # 记录用户登录
        self.write_log(f"用户 '{username}' 登录系统")

        # 登录成功后设置为已连接
        self.connected_to_server = True

        # 开始心跳线程, 用定时发送截屏取代心跳
        self.start_heartbeat()

        # 初始化停止按钮状态
        self.stop_button_initialized = False

        # 获取服务器时间并与本地时间比较
        check_time_sync(self.api_client, self.log)

        # 启动考试结束时间检查
        self.start_exam_end_time_check()


        # 登录成功后自动启动考试模式
        self.root.after(1000, self.start_monitoring)  # 延迟1秒启动，确保界面已完全加载

    def start_heartbeat(self):
        """开始心跳线程"""
        if self.heartbeat_thread is None:
            self.heartbeat_thread = threading.Thread(target=self.heartbeat_loop)
            self.heartbeat_thread.daemon = True
            self.heartbeat_thread.start()

    def heartbeat_loop(self):
        """心跳循环，定期向服务器发送心跳"""
        while True:
            #print(f"[DEBUG][heartbeat_loop] before: connected_to_server={self.connected_to_server}, server_url={self.server_url}")
            if self.api_client:
                # print(f"[DEBUG][heartbeat_loop] send_heartbeat: success={success}, error_message={error_message}")
                success, error_message = self.api_client.send_heartbeat(self.student_id, self.exam_id)
                # print(f"[DEBUG][heartbeat_loop] after: connected_to_server={self.connected_to_server}")
                if not success:
                    self.log(error_message)
                    self.connected_to_server = False
                else:
                    self.connected_to_server = True
            else:
                pass
            # print(f"[DEBUG][heartbeat_loop] after: connected_to_server={self.connected_to_server}")

            # 30秒发送一次心跳
            time.sleep(30)

    def send_logout(self):
        """向服务器发送登出信息"""
        # print(self.student_id, self.exam_id, self.server_url)
        if self.student_id and self.exam_id:
            # 使用API客户端发送登出请求
            success, error_message = self.api_client.send_logout(self.student_id, self.exam_id)

            if success:
                self.log("已向服务器发送登出信息")
            else:
                self.log(error_message)

    def take_screenshot(self):
        """捕获当前屏幕截图"""
        try:
            # 捕获全屏
            screenshot = ImageGrab.grab()

            # 转换为字节流
            img_byte_arr = BytesIO()
            screenshot.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)

            return img_byte_arr

        except Exception as e:
            self.log(f"截图错误: {str(e)}")
            return None

    def report_violation(self, reason, screenshot_path=None):
        """
        向服务器报告违规

        Args:
            reason: 违规原因
            screenshot_path: 可选的截图文件路径
        """
        # 检查是否启用服务器报告
        if not self.config_manager.is_server_reporting_enabled():
            return False

        # 检查是否连接到服务器
        if not self.connected_to_server:
            self.log("未连接到服务器，无法报告违规")
            return False

        # 检查是否启用截图
        screenshot_enabled = self.config_manager.is_screenshot_on_violation_enabled()

        # 准备截图
        screenshot = None
        if screenshot_enabled:
            # 如果提供了截图路径，使用该文件
            if screenshot_path and os.path.exists(screenshot_path):
                screenshot = screenshot_path
            else:
                # 否则尝试实时截图
                screenshot = self.take_screenshot()
                if screenshot is None:
                    self.log("无法获取屏幕截图，但仍将报告违规")

        # 使用API客户端发送违规报告
        success, error_message = self.api_client.report_violation(
            self.student_id,
            self.username,
            reason,
            self.exam_id,
            screenshot=screenshot
        )

        if success:
            self.log(f"已向服务器报告违规: {reason}")
            return True
        else:
            self.log(error_message)
            return False

    def create_widgets(self):
        """创建主界面控件"""
        try:
            # 创建主框架
            main_frame = tk.Frame(self.root)
            main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

            # 标题和用户信息框架
            header_frame = tk.Frame(main_frame)
            header_frame.pack(fill=tk.X, pady=5)

            # 标题
            title_label = tk.Label(header_frame, text="考试监控系统", font=("Arial", 18, "bold"))
            title_label.pack(side=tk.LEFT, pady=10)

            # 美观的考试信息显示（单独一行，居中，加粗）
            exam_info_frame = tk.Frame(main_frame)
            exam_info_frame.pack(fill=tk.X, pady=(0, 10))
            exam_name_label = tk.Label(exam_info_frame, text=f"考试名称: {self.exam_name or ''}", font=("Arial", 12, "bold"), fg="#1a237e")
            exam_name_label.pack(side=tk.TOP, pady=(0, 2))
            exam_time_str = ""
            if self.exam_start_time:
                dt = datetime.fromisoformat(self.exam_start_time)
                exam_time_str += f"开始: {dt.strftime("%Y-%m-%d %H:%M:%S")}  "
            if self.exam_end_time:
                dt = datetime.fromisoformat(self.exam_end_time)
                exam_time_str += f"结束: {dt.strftime("%Y-%m-%d %H:%M:%S")}"
            if exam_time_str:
                exam_time_label = tk.Label(exam_info_frame, text=exam_time_str, font=("Arial", 11), fg="#37474f")
                exam_time_label.pack(side=tk.TOP)

            # 用户信息
            user_frame = tk.Frame(header_frame)
            user_frame.pack(side=tk.RIGHT, pady=10)

            user_label = tk.Label(user_frame, text=f"当前用户: {self.username}", font=("Arial", 10))
            user_label.pack()

            # 服务器状态显示 (添加到用户信息框架)
            self.server_status_var = tk.StringVar()
            self.server_status_var.set("服务器: 未连接")
            self.server_status_label = tk.Label(user_frame, textvariable=self.server_status_var,
                                   font=("Arial", 10), fg="red")
            self.server_status_label.pack()

            # 定期更新服务器状态显示
            self.update_server_status()

            # 信息框架
            info_frame = tk.Frame(main_frame)
            info_frame.pack(fill=tk.BOTH, expand=True, pady=10)

            # 应用监控信息
            app_frame = tk.LabelFrame(info_frame, text="应用监控", padx=10, pady=10)
            app_frame.pack(fill=tk.BOTH, expand=True, side=tk.LEFT, padx=5)

            # 允许的应用列表
            allowed_label = tk.Label(app_frame, text="允许的应用:")
            allowed_label.pack(anchor=tk.W)

            self.allowed_apps_text = tk.Text(app_frame, height=10, width=30)
            self.allowed_apps_text.pack(fill=tk.BOTH, expand=True)

            # 填充允许的应用
            allowed_apps = self.config_manager.get_allowed_apps()
            display_names = [app.get("name", app.get("exe", "")) for app in allowed_apps]
            self.allowed_apps_text.insert(tk.END, "\n".join(display_names))
            self.allowed_apps_text.config(state=tk.DISABLED)

            # 浏览器控制信息
            browser_frame = tk.LabelFrame(info_frame, text="浏览器控制", padx=10, pady=10)
            browser_frame.pack(fill=tk.BOTH, expand=True, side=tk.RIGHT, padx=5)

            # 浏览器控制信息
            browser_info = tk.Label(browser_frame, text="浏览器控制状态:")
            browser_info.pack(anchor=tk.W)

            self.browser_status = tk.StringVar()
            self.browser_status.set("未启动")
            status_label = tk.Label(browser_frame, textvariable=self.browser_status)
            status_label.pack(anchor=tk.W)

            # 浏览器设置
            settings_label = tk.Label(browser_frame, text="浏览器设置:")
            settings_label.pack(anchor=tk.W, pady=(10, 0))

            settings_text = "• 禁用所有插件\n• 禁用开发者工具\n• 限制访问网址\n• 禁止多窗口"
            settings_info = tk.Label(browser_frame, text=settings_text, justify=tk.LEFT)
            settings_info.pack(anchor=tk.W)

            # 前台应用状态框架
            foreground_frame = tk.LabelFrame(main_frame, text="前台应用监控", padx=10, pady=10)
            foreground_frame.pack(fill=tk.X, pady=10)

            # 前台应用标签
            foreground_label = tk.Label(foreground_frame, text="当前前台应用:")
            foreground_label.pack(anchor=tk.W)

            self.foreground_app_var = tk.StringVar()
            self.foreground_app_var.set("未监控")
            self.foreground_app_label = tk.Label(foreground_frame, textvariable=self.foreground_app_var,
                                                 font=("Arial", 11))
            self.foreground_app_label.pack(anchor=tk.W, pady=5)

            self.foreground_status_var = tk.StringVar()
            self.foreground_status_var.set("状态: 未监控")
            self.foreground_status = tk.Label(foreground_frame, textvariable=self.foreground_status_var,
                                              font=("Arial", 10))
            self.foreground_status.pack(anchor=tk.W)

            # 状态显示框架
            status_frame = tk.Frame(main_frame)
            status_frame.pack(fill=tk.X, pady=10)

            self.status_var = tk.StringVar()
            self.status_var.set("考试监控已自动启动")
            status_label = tk.Label(status_frame, textvariable=self.status_var,
                                   font=("Arial", 11, "bold"), fg="#006600", pady=5)
            status_label.pack()

            # 结束考试按钮框架
            end_exam_frame = tk.Frame(main_frame)
            end_exam_frame.pack(fill=tk.X, pady=10)

            # 结束考试按钮
            self.end_exam_button = tk.Button(end_exam_frame, text="结束考试",
                                        command=self.end_exam, width=20, height=2)
            self.end_exam_button.pack(pady=10)
            self.end_exam_button.config(bg="#4a86e8", fg="white", font=("Arial", 11, "bold"))

            # 监控说明标签
            monitor_info = tk.Label(end_exam_frame,
                                  text="点击上方按钮结束考试并退出监控程序",
                                  font=("Arial", 9), fg="#555555")
            monitor_info.pack(pady=5)

            '''
            # 日志框架
            log_frame = tk.LabelFrame(main_frame, text="监控日志")
            log_frame.pack(fill=tk.BOTH, expand=True, pady=10)

            self.log_text = tk.Text(log_frame, height=8)
            self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

            scrollbar = tk.Scrollbar(self.log_text)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

            self.log_text.config(yscrollcommand=scrollbar.set)
            scrollbar.config(command=self.log_text.yview)
            '''
        except Exception as e:
            messagebox.showerror("界面初始化失败", f"错误信息: {e}")
            raise

    def log(self, message):
        """添加日志消息到UI"""
        timestamp = time.strftime("%H:%M:%S", time.localtime())
        log_message = f"[{timestamp}] [用户: {self.username}] {message}"
        #self.log_text.insert(tk.END, log_message + "\n")
        #self.log_text.see(tk.END)

        print(log_message)

        # 同时写入日志文件
        self.write_log(message)

    def write_log(self, message):
        """
        将日志写入文件

        Args:
            message: 日志消息
        """
        try:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

            # 确保日志目录存在
            if not hasattr(self, 'log_dir') or not self.log_dir:
                self.log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
                if not os.path.exists(self.log_dir):
                    os.makedirs(self.log_dir)

            # 确保日志文件名存在
            if not hasattr(self, 'log_file') or not self.log_file:
                # 如果有用户名，使用用户名创建日志文件
                if hasattr(self, 'username') and self.username:
                    log_date = time.strftime("%Y-%m-%d", time.localtime())
                    self.log_file = os.path.join(self.log_dir, f"user_{self.username}_{log_date}.log")
                else:
                    # 否则使用默认名称
                    self.log_file = os.path.join(self.log_dir, f"client_{time.strftime('%Y-%m-%d')}.log")

            # 写入日志
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {message}\n")
        except Exception as e:
            print(f"写入日志失败: {str(e)}")
            # 尝试写入备用日志文件
            try:
                backup_log = os.path.join(os.path.dirname(os.path.abspath(__file__)), "error.log")
                with open(backup_log, "a", encoding="utf-8") as f:
                    f.write(f"[{timestamp}] 原始日志写入失败: {str(e)}, 原始消息: {message}\n")
            except:
                pass  # 如果备用日志也失败，只能忽略

    def start_monitoring(self):
        """启动考试模式"""
        # 如果已经在监控中，不要重复启动
        if self.monitoring:
            return

        self.monitoring = True

        # 更新状态文本
        if hasattr(self, 'status_var'):
            self.status_var.set("考试监控运行中，全程受监控")

        # 记录用户启动监控
        self.log(f"考试监控已自动启动")

        # 启动监控线程
        self.monitor_thread = threading.Thread(target=self.monitor_apps)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()


        # 初始化录屏管理器
        try:
            enable_screen_recording = self.config_manager.config.get("enable_screen_recording", True)
            if enable_screen_recording:
                from screen_recorder import ScreenRecorderManager
                server_url = f"http://{self.api_client.server_ip}:5000"
                self.screen_recorder = ScreenRecorderManager(
                    server_url, 
                    self.student_id, 
                    self.exam_id,
                    self.config_manager
                )
                self.screen_recorder.start()
                self.log("录屏功能已启动（从服务器获取配置）")
            else:
                self.screen_recorder = None
                self.log("服务器配置禁用了录屏功能")
        except Exception as e:
            self.log(f"启动录屏功能失败: {str(e)}")
            self.screen_recorder = None

        # 启动截图上传线程（根据服务器配置）
        if self.config_manager.config.get("enable_screenshot_upload", True):
            self.screenshot_uploading = True
            self.screenshot_thread = threading.Thread(target=self.screenshot_loop)
            self.screenshot_thread.daemon = True
            self.screenshot_thread.start()
        else:
            self.screenshot_uploading = False
            self.log("服务器配置禁用了定时截图上传")

    def stop_monitoring(self):
        """停止监控"""
        if not self.monitoring:
            return

        self.monitoring = False

        # 停止录屏
        if hasattr(self, 'screen_recorder') and self.screen_recorder:
            self.screen_recorder.stop()
            self.log("录屏功能已停止")

        # 停止Chrome浏览器
        try:
            self.chrome_controller.stop()
            self.browser_status.set("未启动")
            self.log("Chrome浏览器已关闭")
        except Exception as e:
            self.log(f"关闭Chrome浏览器失败: {str(e)}")

        # 停止截图上传线程
        self.screenshot_uploading = False

        # 记录用户停止监控
        self.log("考试监控已自动停止")

    def monitor_apps(self):
        """统一的应用程序监控线程"""
        # 从配置中获取检查间隔
        check_interval = self.config_manager.config.get("check_interval", 10)  # 默认10秒
        print(f"应用检查间隔: {check_interval}秒")
        if self.delay_min:
            delay_min = self.delay_min
        else:
            delay_min = 0
        print(f"检测延时：{delay_min}分")
        pass_second = 0

        while self.monitoring:
            if pass_second >= delay_min * 60:
                try:
                    # 使用check_running_apps函数检测未授权的应用程序
                    err_msg = self.app_monitor.check_running_apps()

                    # 获取前台窗口信息（用于UI显示和Chrome检查）
                    window_info = self.app_monitor.get_foreground_window_info()
                    if window_info is None:
                        foreground_title, foreground_process = "未知窗口", None
                    else:
                        foreground_title, foreground_process = window_info

                    #print(f"前台窗口: {foreground_title}, 进程: {foreground_process}")

                    # 更新UI状态
                    self.update_status(foreground_title, foreground_process, err_msg)

                    # 如果有未授权的应用程序
                    if err_msg:
                        # 捕获屏幕截图
                        screenshot_path = self.capture_screenshot()

                        # 发送违规报告
                        violation_reason = err_msg
                        self.report_violation(violation_reason, screenshot_path)
                        # 记录到日志
                        self.log(f"警告：{err_msg}")

                        # 根据配置决定是否显示警告窗口
                        if self.config_manager.is_show_violation_warning_enabled():
                            self.show_warning("警告", err_msg, 5)

                        if "未授权的URL" in err_msg:
                            self.chrome_controller.to_default_url()
                        elif "多个标签页" in err_msg:
                            self.chrome_controller.handle_multiple_tabs_when_disabled()
                        elif "未授权的前台应用" in err_msg:
                            if self.config_manager.is_end_violation_foreground_process_enabled() and foreground_process:
                                try:
                                    proc = psutil.Process(foreground_process)
                                    process_name = proc.name()
                                    proc.terminate()
                                    print(f"已结束未授权前台进程: {process_name} (PID: {foreground_process})")
                                except Exception as e:
                                    print(f"结束未授权前台进程时出错: {str(e)}")
                        elif "获取标签页句柄时出错" in err_msg:
                            self.show_warning("警告", "获取标签页句柄时出错，浏览器将重新启动", 5)
                            self.chrome_controller.restart()
                            
                            
                except Exception as e:
                    # print(f"监控过程出错: {str(e)}")
                    traceback.print_exc()  # 添加这行来打印详细的错误信息

            pass_second += check_interval
            status = self.chrome_controller.check_and_restart_if_needed()
            if status == 'restart':
                pass_second = 0
            time.sleep(check_interval)

    def capture_screenshot(self):
        """捕获屏幕截图并保存到文件"""
        try:
            from PIL import ImageGrab
            import datetime

            # 创建截图文件名
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_path = os.path.join(self.log_dir, f"violation_{timestamp}.png")

            # 捕获屏幕截图
            screenshot = ImageGrab.grab()
            screenshot.save(screenshot_path)

            return screenshot_path
        except Exception as e:
            # print(f"捕获屏幕截图时出错: {str(e)}")
            return None

    def take_screenshot(self):
        """捕获屏幕截图并返回字节流"""
        try:
            from PIL import ImageGrab
            import io

            # 捕获屏幕截图
            screenshot = ImageGrab.grab()

            # 将图像转换为字节流
            img_byte_arr = io.BytesIO()
            screenshot.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)  # 将指针移回开始位置

            return img_byte_arr
        except Exception as e:
            # print(f"捕获屏幕截图时出错: {str(e)}")
            return None

    def update_status(self, foreground_title, foreground_process, err_msg):
        """更新UI状态显示"""
        try:
            # 更新前台应用显示
            self.foreground_app_var.set(foreground_title)

            # 检查前台应用是否在未授权列表中
            # 直接使用传入的前台窗口信息进行检查，避免重复调用check_running_apps
            # 这样可以确保UI状态与监控线程的检测结果一致
            #unauthorized_apps = self.app_monitor.check_running_apps()

            # 更新状态显示
            if err_msg:
                self.foreground_status_var.set("状态: 未授权应用 (禁止使用)")
                self.foreground_status.config(fg="red")

                # 高亮显示前台应用名称，使其更加醒目
                self.foreground_app_label.config(fg="red", font=("Arial", 11, "bold"))
            else:
                self.foreground_status_var.set("状态: 授权应用 (允许使用)")
                self.foreground_status.config(fg="green")

                # 恢复正常显示
                self.foreground_app_label.config(fg="black", font=("Arial", 11))

            # 更新Chrome状态
            if foreground_process and "chrome" in str(foreground_process).lower():
                if self.chrome_controller.is_controlled(foreground_process):
                    self.browser_status.set("已启动 (受控模式)")
                    # 重置警告标志
                    self._chrome_warning_logged = False
                else:
                    self.browser_status.set("警告: 未受控Chrome")
                    # 记录未受控Chrome到日志
                    if not hasattr(self, '_chrome_warning_logged') or not self._chrome_warning_logged:
                        self.log("警告：检测到未受控的Chrome浏览器")
                        self._chrome_warning_logged = True

        except Exception as e:
            # print(f"更新状态显示时出错: {str(e)}")
            pass

    def end_exam(self):
        """结束考试"""
        # 确认是否结束考试
        if self.show_confirmation("确认", "您确定要结束考试并退出监控系统吗？"):
            self.log("用户选择结束考试")

            # 停止录屏
            if hasattr(self, 'screen_recorder') and self.screen_recorder:
                self.screen_recorder.stop()
                self.log("录屏功能已停止")

            # 停止监控
            if self.monitoring:
                self.stop_monitoring()

            # 发送登出信息
            self.send_logout()

            # 记录用户退出
            self.write_log(f"用户 '{self.username}' 主动结束考试并退出系统")

            # 销毁窗口
            self.root.destroy()

    def on_close(self):
        """窗口关闭事件"""
        # 提示用户使用结束考试按钮
        if self.show_confirmation("确认", "您确定要结束考试并退出监控系统吗？"):

            # 如果监控正在运行，先停止监控
            if hasattr(self, 'monitoring') and self.monitoring:
                self.stop_monitoring()

            # 发送登出信息
            self.send_logout()

            # 记录用户退出
            self.write_log(f"用户 '{self.username}' 通过关闭窗口退出系统")

            # 销毁窗口
            self.root.destroy()
        return "break"  # 如果用户选择"否"，阻止关闭操作

    def update_allowed_apps_display(self):
        """更新UI中的允许应用列表显示"""
        if hasattr(self, 'allowed_apps_text'):
            # 获取最新的允许应用列表
            allowed_apps = self.config_manager.get_allowed_apps()

            # 更新文本框
            self.allowed_apps_text.config(state=tk.NORMAL)  # 先解除只读状态
            self.allowed_apps_text.delete(1.0, tk.END)  # 清空当前内容
            self.allowed_apps_text.insert(tk.END, "\n".join(allowed_apps))  # 插入新内容
            self.allowed_apps_text.config(state=tk.DISABLED)  # 恢复只读状态

    def update_server_status(self):
        """更新服务器状态显示"""
        if self.connected_to_server:
            config_source = "服务器" if self.config_manager.is_config_from_server() else "本地"
            self.server_status_var.set(f"服务器: 已连接 ({self.api_client.server_url}))")
            self.server_status_label.config(fg="green")
        else:
            self.server_status_var.set("服务器: 未连接\n")
            self.server_status_label.config(fg="red")
        # 2秒后再次更新
        self.root.after(2000, self.update_server_status)

    def show_warning(self, title, message, seconds=5):
        """
        显示始终在最前端的警告对话框

        Args:
            title: 对话框标题
            message: 对话框内容
        """
        # 创建一个新的顶层窗口
        warning_window = tk.Toplevel(self.root)
        warning_window.title(title)
        warning_window.geometry("450x260")  # 稍微调大尺寸
        warning_window.resizable(False, False)

        # 设置为始终在最前端
        warning_window.attributes('-topmost', True)

        # 设置为模态窗口
        warning_window.grab_set()

        # 设置背景色为浅红色
        warning_window.configure(background="#FFF0F0")

        # 立即居中显示
        width = 450
        height = 260
        x = (warning_window.winfo_screenwidth() // 2) - (width // 2)
        y = (warning_window.winfo_screenheight() // 2) - (height // 2)
        warning_window.geometry(f"{width}x{height}+{x}+{y}")

        # 创建一个顶部装饰条，使用红色渐变
        top_frame = tk.Frame(warning_window, height=8, background="#D32F2F")
        top_frame.pack(side=tk.TOP, fill=tk.X, padx=0, pady=0)

        # 创建主内容框架
        content_frame = tk.Frame(warning_window, background="#FFF0F0")
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=15)

        # 创建标题
        title_label = tk.Label(content_frame, text=title, font=("Arial", 16, "bold"),
                           fg="#D32F2F", background="#FFF0F0")
        title_label.pack(pady=(0, 15))

        # 创建警告图标和消息的水平框架
        message_frame = tk.Frame(content_frame, background="#FFF0F0")
        message_frame.pack(fill=tk.X, padx=10)

        # 创建警告图标
        icon_label = tk.Label(message_frame, text="!", font=("Arial", 24, "bold"),
                          fg="#D32F2F", background="#FFF0F0", width=2)
        icon_label.pack(side=tk.LEFT, padx=(0, 10))

        # 创建消息文本
        message_label = tk.Label(message_frame, text=message, wraplength=340,
                             justify="left", background="#FFF0F0",
                             font=("Arial", 11))
        message_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 创建分隔线
        separator = tk.Frame(warning_window, height=1, background="#E0E0E0")
        separator.pack(fill=tk.X, padx=10, pady=15)

        # 用户点击确认
        def on_confirm():
            if warning_window.winfo_exists():
                warning_window.destroy()

        # 自定义按钮样式类
        class HoverButton(tk.Button):
            def __init__(self, master, **kw):
                tk.Button.__init__(self, master=master, **kw)
                self.defaultBackground = self["background"]
                self.defaultForeground = self["foreground"]
                self.bind("<Enter>", self.on_enter)
                self.bind("<Leave>", self.on_leave)

            def on_enter(self, e):
                if self["state"] != "disabled":
                    self["background"] = self["activebackground"]
                    self["foreground"] = self["activeforeground"]

            def on_leave(self, e):
                if self["state"] != "disabled":
                    self["background"] = self.defaultBackground
                    self["foreground"] = self.defaultForeground

        # 创建按钮框架
        button_frame = tk.Frame(warning_window, background="#FFF0F0")
        button_frame.pack(side=tk.BOTTOM, pady=(0, 20))

        # 创建确认按钮
        confirm_button = HoverButton(
            button_frame, text="确定", width=10, command=on_confirm,
            font=("Arial", 10, "bold"), background="#D32F2F", foreground="white",
            activebackground="#B71C1C", activeforeground="white", bd=0,
            padx=15, pady=8, cursor="hand2"
        )
        confirm_button.pack()

        # 绑定回车键和Escape键
        warning_window.bind("<Return>", lambda event: on_confirm())
        warning_window.bind("<Escape>", lambda event: on_confirm())

        # 确保窗口总是在最前端
        warning_window.lift()

        # 添加小延迟再设置焦点，确保窗口已完全显示
        warning_window.after(100, lambda: confirm_button.focus_set())

        # 为窗口添加阴影效果（视觉暗示）
        warning_window.update_idletasks()

        # 再次确保窗口位置居中
        x = (warning_window.winfo_screenwidth() // 2) - (warning_window.winfo_width() // 2)
        y = (warning_window.winfo_screenheight() // 2) - (warning_window.winfo_height() // 2)
        warning_window.geometry(f"+{x}+{y}")

        # 添加倒计时标签
        countdown_var = tk.StringVar(value="5")
        countdown_label = tk.Label(button_frame, textvariable=countdown_var,
                                  font=("Arial", 9), fg="#888888", background="#FFF0F0")
        countdown_label.pack(pady=(5, 0))

        # 倒计时函数
        def countdown(count):
            if count > 0 and warning_window.winfo_exists():
                countdown_var.set(str(count))
                warning_window.after(1000, countdown, count-1)
            elif warning_window.winfo_exists():
                on_confirm()

        # 启动倒计时
        warning_window.after(0, countdown, seconds)

        # 等待窗口关闭
        self.root.wait_window(warning_window)

    def show_confirmation(self, title, message):
        """
        显示始终在最前端的确认对话框

        Args:
            title: 对话框标题
            message: 对话框内容

        Returns:
            bool: 用户是否确认
        """
        # 创建一个新的顶层窗口
        confirm_window = tk.Toplevel(self.root)
        confirm_window.title(title)
        confirm_window.geometry("450x260")  # 稍微调大尺寸
        confirm_window.resizable(False, False)

        # 设置为始终在最前端
        confirm_window.attributes('-topmost', True)

        # 设置为模态窗口
        confirm_window.grab_set()

        # 设置背景色为浅金色
        confirm_window.configure(background="#FFF8E1")

        # 立即居中显示
        width = 450
        height = 260
        x = (confirm_window.winfo_screenwidth() // 2) - (width // 2)
        y = (confirm_window.winfo_screenheight() // 2) - (height // 2)
        confirm_window.geometry(f"{width}x{height}+{x}+{y}")

        # 创建一个顶部装饰条，使用蓝色渐变
        top_frame = tk.Frame(confirm_window, height=8, background="#0078D7")
        top_frame.pack(side=tk.TOP, fill=tk.X, padx=0, pady=0)

        # 创建主内容框架
        content_frame = tk.Frame(confirm_window, background="#FFF8E1")
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=15)

        # 创建标题
        title_label = tk.Label(content_frame, text=title, font=("Arial", 16, "bold"),
                           fg="#0078D7", background="#FFF8E1")
        title_label.pack(pady=(0, 15))

        # 创建问题图标和消息的水平框架
        message_frame = tk.Frame(content_frame, background="#FFF8E1")
        message_frame.pack(fill=tk.X, padx=10)

        # 创建问题图标
        icon_label = tk.Label(message_frame, text="?", font=("Arial", 24, "bold"),
                          fg="#0078D7", background="#FFF8E1", width=2)
        icon_label.pack(side=tk.LEFT, padx=(0, 10))

        # 创建消息文本
        message_label = tk.Label(message_frame, text=message, wraplength=340,
                             justify="left", background="#FFF8E1",
                             font=("Arial", 11))
        message_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 创建分隔线
        separator = tk.Frame(confirm_window, height=1, background="#E0E0E0")
        separator.pack(fill=tk.X, padx=10, pady=15)

        # 创建用户响应变量
        user_response = tk.BooleanVar(value=False)

        # 用户点击是
        def on_yes():
            user_response.set(True)
            confirm_window.destroy()

        # 用户点击否
        def on_no():
            user_response.set(False)
            confirm_window.destroy()

        # 自定义按钮样式类
        class HoverButton(tk.Button):
            def __init__(self, master, **kw):
                tk.Button.__init__(self, master=master, **kw)
                self.defaultBackground = self["background"]
                self.defaultForeground = self["foreground"]
                self.bind("<Enter>", self.on_enter)
                self.bind("<Leave>", self.on_leave)

            def on_enter(self, e):
                if self["state"] != "disabled":
                    self["background"] = self["activebackground"]
                    self["foreground"] = self["activeforeground"]

            def on_leave(self, e):
                if self["state"] != "disabled":
                    self["background"] = self.defaultBackground
                    self["foreground"] = self.defaultForeground

        # 创建按钮框架
        button_frame = tk.Frame(confirm_window, background="#FFF8E1")
        button_frame.pack(side=tk.BOTTOM, pady=(0, 20))

        # 创建是/否按钮
        yes_button = HoverButton(
            button_frame, text="是", width=8, command=on_yes,
            font=("Arial", 10, "bold"), background="#0078D7", foreground="white",
            activebackground="#005FA3", activeforeground="white", bd=0,
            padx=15, pady=8, cursor="hand2"
        )
        yes_button.pack(side=tk.LEFT, padx=10)

        no_button = HoverButton(
            button_frame, text="否", width=8, command=on_no,
            font=("Arial", 10), background="#E5E5E5", foreground="#333333",
            activebackground="#D5D5D5", activeforeground="#333333", bd=0,
            padx=15, pady=8, cursor="hand2"
        )
        no_button.pack(side=tk.LEFT, padx=10)

        # 绑定回车键和Escape键
        confirm_window.bind("<Return>", lambda event: on_yes())
        confirm_window.bind("<Escape>", lambda event: on_no())

        # 确保窗口总是在最前端
        confirm_window.lift()

        # 添加小延迟再设置焦点，确保窗口已完全显示
        confirm_window.after(100, lambda: yes_button.focus_set())

        # 为窗口添加阴影效果（视觉暗示）
        confirm_window.update_idletasks()

        # 再次确保窗口位置居中
        x = (confirm_window.winfo_screenwidth() // 2) - (confirm_window.winfo_width() // 2)
        y = (confirm_window.winfo_screenheight() // 2) - (confirm_window.winfo_height() // 2)
        confirm_window.geometry(f"+{x}+{y}")

        # 等待窗口关闭
        self.root.wait_window(confirm_window)

        # 返回用户响应
        return user_response.get()

    def screenshot_loop(self):
        """定时上传屏幕截图到服务器"""
        while self.screenshot_uploading:
            try:
                screenshot = self.take_screenshot()
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                success, error_message = self.api_client.upload_screenshot(
                    self.student_id,
                    self.username,
                    self.exam_id,
                    screenshot,
                    timestamp=timestamp
                )
                if success:
                    self.connected_to_server = True
                    self.log("已自动上传屏幕截图")
                else:
                    self.log(f"自动上传截图失败: {error_message}")
                    self.connected_to_server = False
            except Exception as e:
                self.log(f"截图上传线程异常: {str(e)}")
            time.sleep(self.screenshot_interval)

    def start_exam_end_time_check(self):
        """启动考试结束时间检查"""
        if not self.exam_end_time:
            self.log("未设置考试结束时间，无法自动结束考试")
            return

        try:
            # 解析考试结束时间
            end_time = datetime.fromisoformat(self.exam_end_time)

            # 计算当前时间到考试结束时间的毫秒数
            now = datetime.now()
            time_diff = (end_time - now).total_seconds() * 1000
            print(f"考试结束时间: {end_time}: now : {now}")
            print(f"当前时间到考试结束时间的毫秒数: {time_diff}")

            if time_diff <= 0:
                # 考试已经结束
                self.log("考试已结束，系统将自动退出")
                self.root.after(1000, self.auto_end_exam)
            else:
                # 设置定时器，在考试结束时自动退出
                self.log(f"系统将在考试结束时间 {end_time.strftime('%Y-%m-%d %H:%M:%S')} 自动退出")
                self.root.after(int(time_diff), self.auto_end_exam)

                # 设置提前5分钟的提醒
                pre_min = 5
                if time_diff > pre_min * 60 * 1000:
                    self.root.after(int(time_diff - pre_min * 60 * 1000), 
                                    lambda: self.show_warning("考试即将结束", "注意：考试将在5分钟后结束，请及时保存您的工作。系统将在考试结束时自动关闭。", 5)
                      ) 

        except Exception as e:
            self.log(f"设置考试结束自动退出时出错: {str(e)}")
            print(f"设置考试结束自动退出时出错: {str(e)}")
            traceback.print_exc()

    def auto_end_exam(self):
        """考试结束时自动退出"""
        try:
            # 记录日志
            self.log("考试时间已到，系统自动退出")

            # 显示考试结束消息（自定义对话框，10秒后自动关闭）
            self.show_warning(
                "考试已结束",
                "考试时间已到，系统将自动关闭。\n\n感谢您的参与！",
                10  # 10秒后自动关闭
            )

            # 停止监控
            if self.monitoring:
                self.stop_monitoring()

            # 发送登出信息
            self.send_logout()

            # 记录用户退出
            self.write_log(f"用户 '{self.username}' 考试时间到，系统自动退出")

            # 销毁窗口
            self.root.destroy()

            # 确保程序完全退出
            import sys
            sys.exit(0)
        except Exception as e:
            self.log(f"自动结束考试时出错: {str(e)}")
            print(f"自动结束考试时出错: {str(e)}")
            traceback.print_exc()

            # 尝试强制退出
            try:
                self.root.destroy()
                import sys
                sys.exit(0)
            except:
                pass

def check_time_sync(api_client, log_func):
    """检测本地时间与服务器时间差异，超2分钟弹窗警告"""
    try:
        status, server_time_str, errmsg = api_client.get_server_time()
        if status and server_time_str:
            server_time = datetime.strptime(server_time_str, "%Y-%m-%d %H:%M:%S")
            local_time = datetime.now()
            diff = abs((local_time - server_time).total_seconds())
            if diff > 120:
                messagebox.showwarning(
                    "时间不同步",
                    "检测到您的电脑时间与服务器时间相差超过2分钟。\n"
                    "请检查并校准本机时间，否则可能影响考试记录的准确性。"
                )
    except Exception as e:
        print(f"获取服务器时间失败: {e}")
        log_func(f"获取服务器时间失败: {e}")

def main():
    root = tk.Tk()
    # 创建应用实例并保持引用，防止被垃圾回收
    _ = ExamClient(root)
    root.mainloop()

if __name__ == "__main__":
    main()



