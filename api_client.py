#!/usr/bin/env python
# -*- coding: utf-8 -*-

import requests
import json
import logging
import os
from typing import Dict, Any, Optional, Tuple, Union
import time

class ApiClient:
    """
    API客户端类，负责处理与服务器的所有通信
    """

    def __init__(self, server_url: str = None):
        """
        初始化API客户端

        Args:
            server_url: 服务器URL，如果为None则需要在调用方法时提供
        """
        self.server_url = server_url
        self.headers = {
            'Content-Type': 'application/json'
        }
        self.timeout = 5  # 默认超时时间（秒）

    def set_server_url(self, server_url: str) -> None:
        """
        设置服务器URL

        Args:
            server_url: 服务器URL
        """
        self.server_url = server_url

    def login(self, username: str, server_url: str = None) -> Tuple[Optional[bool], Dict[str, Any], str]:
        """
        用户初始登录 - 用于用户首次登录系统，只需提供用户名

        Args:
            username: 用户名
            server_url: 服务器URL，如果为None则使用实例的server_url

        Returns:
            Tuple[Optional[bool], Dict[str, Any], str]:
                - 是否成功 (True/False/None)
                - 响应数据（如果成功或需要选择）或空字典
                - 错误消息（如果失败）或"choice_required"或空字符串
        """
        url = server_url
        if not url:
            return False, {}, "未指定服务器URL"

        # 验证服务器URL格式
        if not (url.startswith("http://") or url.startswith("https://")):
            url = "http://" + url

        # 设置实例的服务器URL
        self.server_url = url

        # 准备登录数据
        login_data = {
            "username": username
        }

        try:
            # 发送登录请求
            response = requests.post(
                f"{url}/api/login",
                json=login_data,
                headers=self.headers,
                timeout=self.timeout
            )

            #print(response.text)

            # 解析响应
            if response.status_code == 200:
                login_response = response.json()
                status = login_response.get("status")
                #print("login:",status)
                if status == "success":
                    # 保存考试和学生信息
                    data = {
                        "exam_id": login_response.get("exam_id"),
                        "student_id": login_response.get("student_id"),
                        "exam_name": login_response.get("exam_name"),
                        "start_time": login_response.get("start_time"),
                        "end_time": login_response.get("end_time"),
                        "message": login_response.get("message", ""),
                        "default_url": login_response.get("default_url", "about:blank"),
                        "delay_min": login_response.get('delay_min', 0)
                    }
                    return True, data, ""
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


    def send_heartbeat(self, student_id: str, exam_id: str) -> Tuple[bool, str]:
        """
        发送心跳请求

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

        try:
            heartbeat_data = {
                "student_id": student_id,
                "exam_id": exam_id
            }
            response = requests.post(
                f"{self.server_url}/api/heartbeat",
                json=heartbeat_data,
                timeout=self.timeout
            )
            if response.status_code == 200:
                return True, ""
            else:
                return False, f"服务器心跳失败: {response.text}"
        except Exception as e:
            return False, f"服务器心跳错误: {str(e)}"

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
