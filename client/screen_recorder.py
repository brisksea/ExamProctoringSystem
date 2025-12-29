#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
屏幕录制模块
用于录制学生屏幕并发送到服务器
"""

import os
import time
import threading
import cv2
import numpy as np
import mss
import mss.tools
from io import BytesIO
from PIL import Image
import json
import base64
from datetime import datetime
import requests
import logging

# Ensure global logging is initialized for client modules. Try package import first,
# fall back to direct module import to support different execution contexts.
try:
    import client.logging_config as logging_config
except Exception:
    try:
        import logging_config
    except Exception:
        pass

class ScreenRecorder:
    """屏幕录制器"""
    
    def __init__(self, server_url, student_id, exam_id, upload_queue=None, config_manager = {}):
        """
        初始化屏幕录制器
        
        Args:
            server_url: 服务器URL
            student_id: 学生ID
            exam_id: 考试ID
            fps: 录制帧率
            quality: 视频质量 (1-100)
            upload_queue: 上传队列（可选）
        """
        self.server_url = server_url
        self.student_id = student_id
        self.exam_id = exam_id
        self.upload_queue = upload_queue
        
        screen_config = config_manager.config.get("screen_recording", {})
        
        # 录制配置
        recording_config = screen_config.get("recording", {})
        self.fps = recording_config.get("fps", 10)
        self.quality = recording_config.get("quality", 80)
        self.codec = recording_config.get("codec", "mp4")
        self.scale_ratio = recording_config.get("scale_ratio", 0.8)
        self.bitrate = recording_config.get("bitrate", 200000)

        print(self.fps, self.scale_ratio, self.codec, self.bitrate)


        # 录制状态
        self.is_recording = False
        self.recording_thread = None
        self.stop_event = threading.Event()
        
        # 视频编码器
        self.video_writer = None
        self.temp_video_path = None
        self.video_sequence = 0  # 视频序号计数器
        self.current_sequence = 0  # 当前录制视频的序号
        
        # 帧缓冲
        self.frame_buffer = []
        self.max_buffer_size = 30  # 最大缓冲帧数
        
        # 日志
        self.logger = logging.getLogger(f"ScreenRecorder_{student_id}")
        
        # 创建临时目录
        self.temp_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp_videos")
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)
    
    def start_recording(self):
        """开始录制"""
        if self.is_recording:
            self.logger.warning("录制已在进行中")
            return False
        
        try:
            self.is_recording = True
            self.stop_event.clear()

            # 递增视频序号
            self.video_sequence += 1
            self.current_sequence = self.video_sequence

            # 创建临时视频文件 - 使用与服务器端一致的命名格式
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # 文件名格式：recording_{student_id}_{exam_id}_{timestamp}_seq_{序号}.{codec}
            self.temp_video_path = os.path.join(
                self.temp_dir,
                f"recording_{self.student_id}_{self.exam_id}_{timestamp}_seq_{self.current_sequence:04d}.{self.codec}"
            )
            
            # 启动录制线程
            self.recording_thread = threading.Thread(target=self._recording_loop)
            self.recording_thread.daemon = True
            self.recording_thread.start()
            
            self.logger.info(f"开始录制屏幕，保存到: {self.temp_video_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"启动录制失败: {e}")
            self.is_recording = False
            return False
    
    def stop_recording(self):
        """停止录制"""
        if not self.is_recording:
            return
        
        self.logger.info("正在停止录制...")
        self.is_recording = False
        self.stop_event.set()
        
        if self.recording_thread:
            self.recording_thread.join(timeout=5)
        
        if self.video_writer:
            self.video_writer.release()
            self.video_writer = None
        
        # 将录制的视频添加到上传队列（不立即上传）
        if self.temp_video_path and os.path.exists(self.temp_video_path):
            self._add_to_upload_queue()
    
    def _add_to_upload_queue(self):
        """将录制的视频添加到上传队列"""
        if hasattr(self, 'upload_queue'):
            video_info = {
                'path': self.temp_video_path,
                'timestamp': datetime.now().isoformat(),
                'fps': self.fps,
                'quality': self.quality,
                'sequence': self.current_sequence  # 添加序号信息
            }
            self.upload_queue.append(video_info)
            self.logger.info(f"视频已添加到上传队列 (序号 {self.current_sequence}): {os.path.basename(self.temp_video_path)}")
        else:
            # 如果没有上传队列，则立即上传（兼容旧版本）
            self._upload_video()
    
    def _recording_loop(self):
        """录制循环"""
        import mss
        sct = mss.mss()  # 在本线程创建
        monitor = sct.monitors[1]  # 主显示器
        width = int(monitor['width'] * self.scale_ratio)
        height = int(monitor['height'] * self.scale_ratio)
        
        # 根据文件扩展名选择合适的编码器
        output_ext = os.path.splitext(self.temp_video_path)[1].lower()
        
        # 编码器与容器格式的兼容性映射
        codec_container_map = {
            '.webm': ['VP90', 'VP80'],  # WebM容器支持的编码器
            '.mp4': ['avc1', 'H264', 'h264', 'X264', 'mp4v'],  # MP4容器支持的编码器，优先尝试H.264
            '.avi': ['XVID', 'MJPG', 'H264', 'avc1', 'DIVX']  # AVI容器支持的编码器
        }
        
        # 获取适合当前容器格式的编码器列表
        compatible_codecs = codec_container_map.get(output_ext, ['mp4v', 'MJPG'])
        
        self.video_writer = None
        selected_codec = None
        
        for codec in compatible_codecs:
            try:
                fourcc = cv2.VideoWriter_fourcc(*codec)
                self.video_writer = cv2.VideoWriter(
                    self.temp_video_path, 
                    fourcc, 
                    self.fps, 
                    (width, height)
                )
                if self.video_writer.isOpened():
                    selected_codec = codec
                    self.logger.info(f"使用编码器: {codec} (容器: {output_ext})")
                    break
                else:
                    self.video_writer.release()
                    self.video_writer = None
            except Exception as e:
                if codec in ['avc1', 'H264', 'h264', 'X264']:
                    self.logger.warning(f"H.264 编码器 {codec} 不可用，可能需要更新 openh264.dll: {e}")
                else:
                    self.logger.warning(f"编码器 {codec} 不可用: {e}")
                continue
        
        if not self.video_writer:
            # 如果所有编码器都失败，使用默认编码器
            self.logger.warning("主要编码器不可用，尝试基础编码器")
            try:
                if output_ext == '.mp4':
                    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                elif output_ext == '.avi':
                    fourcc = cv2.VideoWriter_fourcc(*'MJPG')
                else:
                    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                
                self.video_writer = cv2.VideoWriter(
                    self.temp_video_path, 
                    fourcc, 
                    self.fps, 
                    (width, height)
                )
                if self.video_writer.isOpened():
                    selected_codec = 'fallback'
                else:
                    self.logger.error("无法创建视频写入器")
                    return
            except Exception as e:
                self.logger.error(f"创建视频写入器失败: {e}")
                return

        frame_interval = 1.0 / self.fps
        last_frame_time = time.time()
        
        while self.is_recording and not self.stop_event.is_set():
            try:
                current_time = time.time()
                
                # 控制帧率
                if current_time - last_frame_time >= frame_interval:
                    # 捕获屏幕
                    screenshot = sct.grab(monitor)
                    
                    # 转换为OpenCV格式
                    frame = np.array(screenshot)
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                    frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
                    
                    # 写入视频
                    if self.video_writer and self.video_writer.isOpened():
                        self.video_writer.write(frame)
                    
                    last_frame_time = current_time
                
                # 短暂休眠
                time.sleep(0.01)
                
            except Exception as e:
                self.logger.error(f"录制过程中出错: {e}")
                time.sleep(0.1)
        # 释放mss
        sct.close()
    
    def _upload_video(self):
        """上传录制的视频到服务器"""
        try:
            if not os.path.exists(self.temp_video_path):
                self.logger.warning("视频文件不存在")
                return
            
            file_size = os.path.getsize(self.temp_video_path)
            if file_size == 0:
                self.logger.warning("视频文件为空")
                return
            
            self.logger.info(f"正在上传视频文件: {self.temp_video_path} ({file_size} bytes)")
            
            # 准备上传数据
            with open(self.temp_video_path, 'rb') as f:
                files = {'video': f}
                data = {
                    'student_id': self.student_id,
                    'exam_id': self.exam_id,
                    'timestamp': datetime.now().isoformat(),
                    'fps': self.fps,
                    'quality': self.quality
                }
                
                # 发送到服务器
                response = requests.post(
                    f"{self.server_url}/api/screen_recording",
                    files=files,
                    data=data,
                    timeout=60
                )
                
                if response.status_code == 200:
                    result = response.json()
                    self.logger.info(f"视频上传成功: {result.get('message', '')}")
                else:
                    self.logger.error(f"视频上传失败: {response.status_code} - {response.text}")
            
            # 删除临时文件
            try:
                os.remove(self.temp_video_path)
                self.logger.info("临时视频文件已删除")
            except Exception as e:
                self.logger.warning(f"删除临时文件失败: {e}")
            
        except Exception as e:
            self.logger.error(f"上传视频失败: {e}")
    
    def capture_single_frame(self):
        """捕获单帧并上传"""
        try:
            import mss
            sct = mss.mss()  # 在本线程创建
            monitor = sct.monitors[1]
            screenshot = sct.grab(monitor)
            sct.close()
            
            # 转换为PIL Image
            img = Image.frombytes('RGB', screenshot.size, screenshot.rgb)
            
            # 压缩图像
            buffer = BytesIO()
            img.save(buffer, format='JPEG', quality=self.quality)
            image_data = buffer.getvalue()
            
            # 编码为base64
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            # 准备数据
            data = {
                'student_id': self.student_id,
                'exam_id': self.exam_id,
                'timestamp': datetime.now().isoformat(),
                'image_data': image_base64,
                'type': 'single_frame'
            }
            
            # 发送到服务器
            response = requests.post(
                f"{self.server_url}/api/screen_frame",
                json=data,
                timeout=10
            )
            
            if response.status_code == 200:
                return True
            else:
                self.logger.error(f"单帧上传失败: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"捕获单帧失败: {e}")
            return False
    
    def cleanup(self):
        """清理资源"""
        self.stop_recording()
        # 不再需要self.sct
        # 清理临时文件
        if self.temp_video_path and os.path.exists(self.temp_video_path):
            try:
                os.remove(self.temp_video_path)
            except:
                pass


class ScreenRecorderManager:
    """屏幕录制管理器"""
    
    def __init__(self, server_url, student_id, exam_id, config_manager):
        """
        初始化录制管理器
        
        Args:
            server_url: 服务器URL
            student_id: 学生ID
            exam_id: 考试ID
            config_manager: 用于从服务器获取配置
        """
        self.server_url = server_url
        self.student_id = student_id
        self.exam_id = exam_id
        self.config_manager = config_manager
        self.logger = logging.getLogger(f"ScreenRecorderManager_{student_id}")
        
        # 录制器实例
        self.recorder = None
        
        # 从服务器获取配置
        self._load_config_from_server()
        
        # 定时器
        self.recording_timer = None
        self.upload_timer = None
        self.is_running = False
        
        # 上传队列
        self.upload_queue = []
        self.uploading = False
    
    def _load_config_from_server(self):
        """从服务器加载配置"""
        try:
            if self.config_manager:
                # 尝试从服务器获取配置
                    # 从服务器配置中提取录屏相关配置
                    screen_config = self.config_manager.config.get("screen_recording", {})
                    
                    # 录制配置
                    recording_config = screen_config.get("recording", {})
                    self.recording_enabled = recording_config.get("enabled", True)
                    self.recording_interval = recording_config.get("interval", 30)
                    
                    # 上传配置
                    upload_config = screen_config.get("upload", {})
                    self.upload_strategy = upload_config.get("strategy", "distributed")
                    self.upload_interval = upload_config.get("interval", 120)
                    self.max_upload_delay = upload_config.get("max_delay", 60)
                    
                    self.logger.info("已从服务器获取录屏配置")
                    return
            
            # 如果无法从服务器获取配置，使用默认配置
            self._load_default_config()
            self.logger.info("使用默认录屏配置")
            
        except Exception as e:
            self.logger.error(f"加载服务器配置失败: {e}")
            self._load_default_config()
            self.logger.info("使用默认录屏配置")
    
    def _load_default_config(self):
        """加载默认配置"""
        # 录制配置
        self.recording_enabled = True
        self.recording_fps = 2
        self.recording_quality = 80
        self.recording_interval = 30  # 录制间隔（秒）
        self.scale_ratio = 0.8
        
        # 分布式上传配置
        self.upload_strategy = "distributed"  # "distributed" 或 "end_only"
        self.upload_interval = 120  # 上传间隔（秒），默认2分钟
        self.max_upload_delay = 60  # 最大上传延迟（秒），用于随机化
    
    def start(self):
        """启动录制管理器"""
        if self.is_running:
            return
        
        self.is_running = True
        self.recorder = ScreenRecorder(
            self.server_url,
            self.student_id,
            self.exam_id,
            self.upload_queue,  # 传递上传队列,
            self.config_manager # 配置信息
        )
        
        # 启动定时录制
        self._schedule_recording()
        
        # 启动分布式上传
        if self.upload_strategy == "distributed":
            self._schedule_upload()
    
    def stop(self, fast_exit=False):
        """
        停止录制管理器
        
        Args:
            fast_exit: 如果为 True，快速退出模式，不等待视频上传完成，改为后台线程上传
        """
        # 如果已经在录制，先停止当前录制
        if self.recorder and self.recorder.is_recording:
            self.recorder.stop_recording()

        self.is_running = False
        
        if self.recording_timer:
            self.recording_timer.cancel()
        
        if self.upload_timer:
            self.upload_timer.cancel()
        
        # 上传剩余的视频文件
        if self.upload_strategy == "distributed" and self.upload_queue:
            if fast_exit:
                # 快速退出模式：在后台线程中上传，不阻塞主线程
                upload_thread = threading.Thread(target=self._upload_remaining_files, daemon=True)
                upload_thread.start()
                self.logger.info("快速退出模式：视频文件将在后台线程中继续上传")
            else:
                # 正常模式：同步上传
                self._upload_remaining_files()
        
        if self.recorder:
            self.recorder.cleanup()
            self.recorder = None
    
    def _schedule_recording(self):
        """安排定时录制"""
        if not self.is_running:
            return
        
        # 如果已经在录制，先停止当前录制
        if self.recorder and self.recorder.is_recording:
            self.recorder.stop_recording()
        
        # 开始新的录制
        if self.recording_enabled and self.recorder:
            self.recorder.start_recording()
        
        # 安排下次录制
        self.recording_timer = threading.Timer(
            self.recording_interval,
            self._schedule_recording
        )
        self.recording_timer.daemon = True
        self.recording_timer.start()
    
    def _schedule_upload(self):
        """安排分布式上传"""
        if not self.is_running:
            return
        
        # 上传队列中的视频文件
        self._upload_queued_files()
        
        # 计算下次上传时间（添加随机延迟以避免同时上传）
        import random
        random_delay = random.uniform(0, self.max_upload_delay)
        next_upload_time = self.upload_interval + random_delay
        
        # 安排下次上传
        self.upload_timer = threading.Timer(
            next_upload_time,
            self._schedule_upload
        )
        self.upload_timer.daemon = True
        self.upload_timer.start()
    
    def _upload_queued_files(self):
        """上传队列中的文件"""
        if self.uploading or not self.upload_queue:
            return

        self.uploading = True

        try:
            # 上传队列中的所有文件
            i = 0
            while i < len(self.upload_queue):
                video_info = self.upload_queue[i]
                upload_success = self._upload_single_file(video_info)

                if upload_success:
                    # 上传成功，从队列中删除
                    self.upload_queue.pop(i)
                    self.logger.info(f"文件上传成功并从队列中删除: {os.path.basename(video_info['path'])}")
                else:
                    # 上传失败，保留在队列中，继续下一个
                    i += 1
                    self.logger.warning(f"文件上传失败，保留在队列中: {os.path.basename(video_info['path'])}")

                # 短暂延迟，避免过快上传
                time.sleep(1)

        except Exception as e:
            self.logger.error(f"上传队列文件时出错: {e}")
        finally:
            self.uploading = False
    
    def _upload_single_file(self, video_info):
        """上传单个文件，返回是否上传成功"""
        try:
            video_path = video_info['path']
            if not os.path.exists(video_path):
                self.logger.warning(f"视频文件不存在: {video_path}")
                return False

            file_size = os.path.getsize(video_path)
            if file_size == 0:
                self.logger.warning(f"视频文件为空: {video_path}")
                # 空文件直接删除并返回成功
                try:
                    os.remove(video_path)
                    self.logger.info("空视频文件已删除")
                except Exception as e:
                    self.logger.warning(f"删除空文件失败: {e}")
                return True

            self.logger.info(f"正在上传视频文件: {os.path.basename(video_path)} ({file_size} bytes)")

            # 准备上传数据 - 使用真正的流式上传
            with open(video_path, 'rb') as f:
                # 使用requests的流式上传
                files = {'video': (os.path.basename(video_path), f, 'video/mp4')}
                data = {
                    'student_id': self.student_id,
                    'exam_id': self.exam_id,
                    'timestamp': video_info['timestamp'],
                    'sequence': str(video_info.get('sequence', 0)),  # 添加序号信息
                    'fps': video_info['fps'],
                    'quality': video_info['quality']
                }

                # 发送到服务器 - 使用流式上传和更长的超时时间
                response = requests.post(
                    f"{self.server_url}/api/screen_recording",
                    files=files,
                    data=data,
                    timeout=600,  # 10分钟超时，与服务器端保持一致
                    stream=True   # 启用流式传输
                )

            if response.status_code == 200:
                result = response.json()
                self.logger.info(f"视频上传成功: {result.get('message', '')}")

                # 上传成功，删除本地文件
                try:
                    os.remove(video_path)
                    self.logger.info("本地视频文件已删除")
                    return True
                except Exception as e:
                    self.logger.warning(f"删除本地文件失败: {e}")
                    # 即使删除失败，也认为上传成功
                    return True
            else:
                self.logger.error(f"视频上传失败: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            self.logger.error(f"上传单个文件失败: {e}")
            return False
    
    def _upload_remaining_files(self):
        """上传剩余的文件（考试结束时调用）"""
        if not self.upload_queue:
            return

        initial_count = len(self.upload_queue)
        self.logger.info(f"考试结束，上传剩余的 {initial_count} 个视频文件")

        # 最多重试3次
        max_retries = 3
        for retry in range(max_retries):
            if not self.upload_queue:
                break

            remaining_count = len(self.upload_queue)
            self.logger.info(f"第 {retry + 1} 次尝试上传，剩余 {remaining_count} 个文件")

            self._upload_queued_files()

            # 如果还有文件未上传成功，等待一段时间再重试
            if self.upload_queue and retry < max_retries - 1:
                self.logger.info("等待5秒后重试...")
                time.sleep(5)

        # 最终报告
        if self.upload_queue:
            failed_count = len(self.upload_queue)
            self.logger.warning(f"考试结束后仍有 {failed_count} 个文件上传失败")
        else:
            self.logger.info(f"所有 {initial_count} 个视频文件上传完成")
    
    def capture_frame(self):
        """捕获单帧"""
        if self.recorder:
            return self.recorder.capture_single_frame()
        return False
