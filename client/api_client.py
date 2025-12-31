#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import json
import logging
import os
import sys
import time
import shutil
from typing import Dict, Any, Optional, Tuple, Union

class ApiClient:
    """
    API客户端类，负责处理与服务器的所有通信
    """

    def __init__(self, server_ip):
        """
        初始化API客户端

        Args:
            server_url: 服务器URL，如果为None则需要在调用方法时提供
        """
        self.server_ip = server_ip
        self.server_url = f'http://{server_ip}:5000'
        self.headers = {
            'Content-Type': 'application/json'
        }
        self.timeout = 30  # 增加超时时间到30秒，提高网络容错性
        self.heartbeat_timeout = 20  # 心跳专用超时时间
        self.max_retries = 3  # 最大重试次数
        
        # 连接质量监控
        self.heartbeat_stats = {
            'total_attempts': 0,
            'successful_attempts': 0,
            'timeout_count': 0,
            'connection_error_count': 0,
            'last_success_time': None,
            'avg_response_time': 0
        }

    def set_server_url(self, server_ip: str) -> None:
        """
        设置服务器URL

        Args:
            server_ip: 服务器IP
        """
        self.server_url =  f'http://{server_ip}:5000'

    def login(self, username: str) -> Tuple[Optional[bool], Dict[str, Any], str]:
        """
        用户初始登录 - 用于用户首次登录系统，只需提供用户名

        Args:
            username: 用户名

        Returns:
            Tuple[Optional[bool], Dict[str, Any], str]:
                - 是否成功 (True/False/None)
                - 响应数据（如果成功或需要选择）或空字典
                - 错误消息（如果失败）或"choice_required"或空字符串
        """

        # 准备登录数据
        login_data = {
            "username": username
        }

        print("login")
        try:
            # 发送登录请求
            response = requests.post(
                f"{self.server_url}/api/login",
                json=login_data,
                headers=self.headers,
                timeout=self.timeout
            )

            print(response.text)

            # 解析响应
            if response.status_code == 200:
                login_response = response.json()
                status = login_response.get("status")
                #print("login:",status)
                if status == "success":
                    # 保存考试和学生信息
                    return True, login_response, ""
                elif status == "choice_required":
                    # 需要用户选择考试
                    data = {
                        "exams": login_response.get("exams", []),
                        "message": login_response.get("message", "")
                    }
                    return None, data, "choice_required"
                else:
                    error_message = login_response.get("message", "登录失败，请重试")
                    return False, {}, error_message
            else:
                # 尝试解析服务器返回的详细错误信息
                try:
                    error_detail = response.json().get("message", "")
                except Exception:
                    error_detail = response.text
                return False, {}, f"服务器返回错误: {error_detail}"

        except requests.exceptions.RequestException as e:
            return False, {}, f"无法连接到服务器: {str(e)}"

    def select_exam_login(self, username: str, exam_id: int) -> Tuple[bool, Dict[str, Any], str]:
        """
        用户选择考试后的登录

        Args:
            username: 用户名
            exam_id: 选择的考试ID

        Returns:
            Tuple[bool, Dict[str, Any], str]: 是否成功, 响应数据, 错误消息
        """
        login_data = {
            "username": username,
            "exam_id": exam_id
        }

        try:
            response = requests.post(
                f"{self.server_url}/api/login/select_exam",
                json=login_data,
                headers=self.headers,
                timeout=self.timeout
            )

            if response.status_code == 200:
                login_response = response.json()
                if login_response.get("status") == "success":
                    return True, login_response, ""
                else:
                    error_message = login_response.get("message", "登录失败，请重试")
                    return False, {}, error_message
            else:
                try:
                    error_detail = response.json().get("message", "")
                except Exception:
                    error_detail = response.text
                return False, {}, f"服务器返回错误: {error_detail}"

        except requests.exceptions.RequestException as e:
            return False, {}, f"无法连接到服务器: {str(e)}"

    def get_student_name_by_id(self, student_id: str) -> Tuple[bool, str, str]:
        """
        通过学号获取学生姓名

        Args:
            student_id: 学号

        Returns:
            Tuple[bool, str, str]: 是否成功, 学生姓名, 错误消息
        """
        try:
            response = requests.get(
                f"{self.server_url}/api/students/{student_id}",
                headers=self.headers,
                timeout=self.timeout
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("status") == "success":
                    student_name = result.get("student_name", "")
                    return True, student_name, ""
                else:
                    error_message = result.get("message", "未找到该学号对应的学生")
                    return False, "", error_message
            elif response.status_code == 404:
                return False, "", "未找到该学号对应的学生"
            else:
                try:
                    error_detail = response.json().get("message", "")
                except Exception:
                    error_detail = response.text
                return False, "", f"服务器返回错误: {error_detail}"

        except requests.exceptions.RequestException as e:
            return False, "", f"无法连接到服务器: {str(e)}"

    def login(self, student_id: str, student_name: str) -> Tuple[Optional[bool], Dict[str, Any], str]:
        """
        使用学号和姓名进行登录

        Args:
            student_id: 学号
            student_name: 学生姓名

        Returns:
            Tuple[Optional[bool], Dict[str, Any], str]: 是否成功, 响应数据, 错误消息
        """
        login_data = {
            "student_id": student_id,
            "student_name": student_name
        }

        try:
            response = requests.post(
                f"{self.server_url}/api/login",
                json=login_data,
                headers=self.headers,
                timeout=self.timeout
            )

            if response.status_code == 200:
                login_response = response.json()
                status = login_response.get("status")

                if status == "success":
                    return True, login_response, ""
                elif status == "choice_required":
                    data = {
                        "exams": login_response.get("exams", []),
                        "message": login_response.get("message", "")
                    }
                    return None, data, "choice_required"
                else:
                    error_message = login_response.get("message", "登录失败，请重试")
                    return False, {}, error_message
            else:
                try:
                    error_detail = response.json().get("message", "")
                except Exception:
                    error_detail = response.text
                return False, {}, f"服务器返回错误: {error_detail}"

        except requests.exceptions.RequestException as e:
            return False, {}, f"无法连接到服务器: {str(e)}"

    def send_heartbeat(self, student_id: str, exam_id: str) -> Tuple[bool, str]:
        """
        发送心跳请求，带重试机制

        Args:
            student_id: 学生ID
            exam_id: 考试ID

        Returns:
            Tuple[bool, str]: 是否成功, 错误消息（如果失败）
        """
        if not self.server_url:
            return False, "未指定服务器URL"

        if not student_id or not exam_id:
            return False, "心跳请求缺少student_id或exam_id"

        heartbeat_data = {
            "student_id": student_id,
            "exam_id": exam_id
        }

        # 重试机制
        last_error = ""
        self.heartbeat_stats['total_attempts'] += 1
        
        for attempt in range(self.max_retries):
            try:
                start_time = time.time()
                response = requests.post(
                    f"{self.server_url}/api/heartbeat",
                    json=heartbeat_data,
                    timeout=self.heartbeat_timeout
                )
                response_time = time.time() - start_time
                
                if response.status_code == 200:
                    # 更新成功统计
                    self.heartbeat_stats['successful_attempts'] += 1
                    self.heartbeat_stats['last_success_time'] = time.time()
                    
                    # 更新平均响应时间
                    if self.heartbeat_stats['avg_response_time'] == 0:
                        self.heartbeat_stats['avg_response_time'] = response_time
                    else:
                        self.heartbeat_stats['avg_response_time'] = (
                            self.heartbeat_stats['avg_response_time'] * 0.8 + response_time * 0.2
                        )
                    
                    try:
                        data = response.json()
                        return True, data
                    except Exception:
                        return True, {}
                else:
                    last_error = f"服务器心跳失败: HTTP {response.status_code}"
                    if attempt < self.max_retries - 1:
                        time.sleep(1)  # 重试前等待1秒
                        continue
            except requests.exceptions.Timeout:
                self.heartbeat_stats['timeout_count'] += 1
                last_error = f"心跳请求超时 (尝试 {attempt + 1}/{self.max_retries})"
                if attempt < self.max_retries - 1:
                    time.sleep(2)  # 超时后等待更长时间
                    continue
            except requests.exceptions.ConnectionError:
                self.heartbeat_stats['connection_error_count'] += 1
                last_error = f"网络连接错误 (尝试 {attempt + 1}/{self.max_retries})"
                if attempt < self.max_retries - 1:
                    time.sleep(3)  # 连接错误等待更长时间
                    continue
            except Exception as e:
                last_error = f"心跳请求异常: {str(e)}"
                if attempt < self.max_retries - 1:
                    time.sleep(1)
                    continue

        return False, last_error

    def get_connection_stats(self) -> Dict[str, Any]:
        """
        获取连接质量统计信息
        
        Returns:
            Dict[str, Any]: 包含连接统计信息的字典
        """
        stats = self.heartbeat_stats.copy()
        
        # 计算成功率
        if stats['total_attempts'] > 0:
            stats['success_rate'] = stats['successful_attempts'] / stats['total_attempts']
        else:
            stats['success_rate'] = 0
            
        # 计算距离上次成功的时间
        if stats['last_success_time']:
            stats['seconds_since_last_success'] = time.time() - stats['last_success_time']
        else:
            stats['seconds_since_last_success'] = None
            
        return stats

    def send_logout(self, student_id: str, exam_id: str) -> Tuple[bool, str]:
        """
        发送登出请求

        Args:
            student_id: 学生ID
            exam_id: 考试ID

        Returns:
            Tuple[bool, str]: 是否成功, 错误消息（如果失败）
        """
        if not self.server_url:
            return False, "未指定服务器URL"
        if not student_id or not exam_id:
            return False, "登出请求缺少student_id或exam_id"
        try:
            logout_data = {
                "student_id": student_id,
                "exam_id": exam_id
            }
            response = requests.post(
                f"{self.server_url}/api/logout",
                json=logout_data,
                timeout=self.timeout
            )
            if response.status_code == 200:
                return True, ""
            else:
                return False, f"服务器登出失败: {response.text}"
        except Exception as e:
            return False, f"服务器登出错误: {str(e)}"

    def report_violation(self, student_id: str, username: str, reason: str,
                         exam_id: str, screenshot=None, timestamp=None) -> Tuple[bool, str]:
        """
        报告违规

        Args:
            student_id: 学生ID
            username: 用户名
            reason: 违规原因
            exam_id: 考试ID
            screenshot: 截图文件或字节流（可选）
            timestamp: 违规时间（可选）

        Returns:
            Tuple[bool, str]: 是否成功, 错误消息（如果失败）
        """
        if not self.server_url:
            return False, "未指定服务器URL"
        if not student_id or not exam_id or not username or not reason:
            return False, "违规报告缺少必要参数"
        try:
            # 准备表单数据
            form_data = {
                "student_id": student_id,
                "exam_id": exam_id,
                "username": username,
                "reason": reason
            }
            if timestamp:
                form_data["timestamp"] = timestamp
            # 准备文件
            files = {}
            if screenshot:
                if hasattr(screenshot, 'read'):
                    files["screenshot"] = ("screenshot.png", screenshot, "image/png")
                elif isinstance(screenshot, str):
                    try:
                        with open(screenshot, 'rb') as f:
                            screenshot_data = f.read()
                        files["screenshot"] = (os.path.basename(screenshot), screenshot_data, "image/png")
                    except Exception as e:
                        return False, f"读取截图文件时出错: {str(e)}"
            response = requests.post(
                f"{self.server_url}/api/violation",
                data=form_data,
                files=files,
                timeout=10
            )
            if response.status_code == 200:
                return True, ""
            else:
                return False, f"违规报告失败: {response.text}"
        except Exception as e:
            return False, f"违规报告错误: {str(e)}"

    def fetch_config(self) -> Tuple[bool, Dict[str, Any], str]:
        """
        从服务器获取配置

        Returns:
            Tuple[bool, Dict[str, Any], str]:
                - 是否成功
                - 配置数据（如果成功）或空字典
                - 错误消息（如果失败）或空字符串
        """
        if not self.server_url:
            return False, {}, "未指定服务器URL"

        try:
            # 发送请求获取配置
            response = requests.get(
                f"{self.server_url}/api/config",
                timeout=self.timeout
            )

            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success" and "config" in data:
                    return True, data["config"], ""
                else:
                    return False, {}, "服务器返回的配置数据格式不正确"
            else:
                # 尝试解析服务器返回的详细错误信息
                try:
                    error_detail = response.json().get("message", "")
                except Exception:
                    error_detail = response.text
                return False, {}, f"服务器返回错误: {response.status_code} {error_detail}"

        except Exception as e:
            return False, {}, f"从服务器获取配置时出错: {str(e)}"

    def screenshot_loop(self):
        while self.monitoring and self.connected_to_server:
            screenshot = self.take_screenshot()
            self.api_client.upload_screenshot(self.student_id, self.username, self.exam_id, screenshot)
            time.sleep(self.screenshot_interval)  # 例如30秒

    def upload_screenshot(self, student_id, username, exam_id, screenshot, timestamp=None):
        """
        上传定时截图到服务器
        Args:
            student_id: 学生ID
            username: 用户名
            exam_id: 考试ID
            screenshot: 截图文件或字节流
            timestamp: 时间戳（可选）
        Returns:
            Tuple[bool, str]: 是否成功, 错误消息（如果失败）
        """
        if not self.server_url:
            return False, "未指定服务器URL"
        if not student_id or not exam_id or not username or not screenshot:
            return False, "截图上传缺少必要参数"
        try:
            form_data = {
                "student_id": student_id,
                "exam_id": exam_id,
                "username": username
            }
            if timestamp:
                form_data["timestamp"] = timestamp
            files = {}
            if hasattr(screenshot, 'read'):
                files["screenshot"] = ("screenshot.png", screenshot, "image/png")
            elif isinstance(screenshot, str):
                try:
                    with open(screenshot, 'rb') as f:
                        screenshot_data = f.read()
                    files["screenshot"] = (os.path.basename(screenshot), screenshot_data, "image/png")
                except Exception as e:
                    return False, f"读取截图文件时出错: {str(e)}"
            else:
                return False, "无效的截图数据"
            response = requests.post(
                f"{self.server_url}/api/screenshot",
                data=form_data,
                files=files,
                timeout=10
            )
            if response.status_code == 200:
                return True, ""
            else:
                try:
                    error_detail = response.json().get("message", "")
                except Exception:
                    error_detail = response.text
                return False, f"截图上传失败: {response.status_code} {error_detail}"
        except Exception as e:
            return False, f"截图上传错误: {str(e)}"
        
    def get_server_time(self) -> Tuple[bool, Optional[str], str]:
        """
        获取服务器时间

        Returns:
            Tuple[bool, Optional[str], str]:
                - 是否成功
                - 服务器时间字符串（如成功）或None
                - 错误消息（如失败）或空字符串
        """
        if not self.server_url:
            return False, None, "未指定服务器URL"
        try:
            response = requests.get(
                f"{self.server_url}/api/server_time",
                timeout=self.timeout
            )
            if response.status_code == 200:
                data = response.json()
                if "server_time" in data:
                    return True, data["server_time"], ""
                else:
                    return False, None, "服务器返回的数据格式不正确"
            else:
                try:
                    error_detail = response.json().get("message", "")
                except Exception:
                    error_detail = response.text
                return False, None, f"服务器返回错误: {response.status_code} {error_detail}"
        except Exception as e:
            return False, None, f"获取服务器时间时出错: {str(e)}"
        
        
    def download_driver(self, browser_type: str, version: str) -> str:
        """
        根据浏览器类型和版本号从服务器下载对应的驱动程序

        Args:
            browser_type: 浏览器类型 ('chrome' 或 'edge')
            version: 浏览器版本号

        Returns:
            str: 下载后的本地驱动路径
        """
        if not self.server_url:
            raise RuntimeError("未指定服务器URL")
        if not version:
            raise ValueError(f"{browser_type} 版本号不能为空")

        major_version = version.split('.')[0]
        browser_type = browser_type.lower()
        
        # 根据类型确定文件名
        if browser_type == 'chrome':
            driver_name = "chromedriver.exe"
            server_filename = f"chromedriver_{major_version}.exe"
        elif browser_type == 'edge':
            driver_name = "msedgedriver.exe"
            server_filename = f"msedgedriver_{major_version}.exe"
        else:
            raise ValueError(f"不支持的浏览器类型: {browser_type}")

        download_url = f"{self.server_url}/driver/{server_filename}"
        
        # 确定本地保存路径
        if getattr(sys, 'frozen', False):
            # 打包后的 exe 运行
            local_path = os.path.join(os.path.dirname(sys.executable), driver_name)
        else:
            # 源码运行
            local_path = os.path.join(os.path.dirname(__file__), driver_name)

        print(f"尝试从 {download_url} 下载 {driver_name} ...")
        try:
            r = requests.get(download_url, stream=True, timeout=10)
            if r.status_code == 200:
                with open(local_path, "wb") as f:
                    shutil.copyfileobj(r.raw, f)
                print(f"{driver_name} 下载完成")
                return local_path
            else:
                raise RuntimeError(f"下载 {driver_name} 失败，服务器返回: {r.status_code}")
        except Exception as e:
            if isinstance(e, RuntimeError):
                raise
            raise RuntimeError(f"网络连接错误，无法从服务器下载驱动: {str(e)}")

    def download_chromedriver(self, chrome_version):
        """兼容性包装器：下载chromedriver"""
        return self.download_driver('chrome', chrome_version)

    def download_edgedriver(self, edge_version):
        """兼容性包装器：下载msedgedriver"""
        return self.download_driver('edge', edge_version)