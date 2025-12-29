#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
考试系统负载测试脚本
模拟400个学生并发考试，包括登录、心跳、截图、视频上传等操作
"""

from locust import HttpUser, task, between, events
import random
import io
import os
from datetime import datetime
from PIL import Image

class ExamStudent(HttpUser):
    """模拟考试学生的行为

    分布式部署说明：
    - 每个 Worker 需要设置环境变量 WORKER_OFFSET 以避免学生ID冲突
    - Worker1: WORKER_OFFSET=0   (学生ID: 1-100)
    - Worker2: WORKER_OFFSET=100 (学生ID: 101-200)
    - Worker3: WORKER_OFFSET=200 (学生ID: 201-300)
    """

    # 任务之间等待时间：25-35秒（模拟心跳间隔30秒，带随机抖动）
    wait_time = between(25, 35)

    # Worker 偏移量（从环境变量读取，避免分布式环境下学生ID冲突）
    import os
    _worker_offset = int(os.getenv('WORKER_OFFSET', '0'))
    _student_counter = 0
    _counter_lock = None

    def on_start(self):
        """学生登录"""
        # 使用类级别的计数器分配学号，确保与数据库中导入的学生一致
        # test_00001, test_00002, ... test_00500
        if ExamStudent._counter_lock is None:
            import threading
            ExamStudent._counter_lock = threading.Lock()

        with ExamStudent._counter_lock:
            ExamStudent._student_counter += 1
            # 加上 Worker 偏移量，避免不同 Worker 产生相同学生ID
            student_num = ExamStudent._worker_offset + ExamStudent._student_counter

        # 生成与generate_students.sh一致的学号格式
        self.student_id = f"test_{student_num:05d}"
        self.student_name = f"测试学生{student_num:03d}"
        self.exam_id = None
        self.login_success = False

        # 为每个学生分配一个相近的IP地址（模拟同一实验室的学生）
        # 192.168.1.1, 192.168.1.2, 192.168.1.3, ...
        self.simulated_ip = f"192.168.1.{student_num}"

        # 设置自定义headers，包含模拟的客户端IP
        self.client.headers = {
            "X-Test-Client-IP": self.simulated_ip
        }

        # 执行登录
        with self.client.post("/api/login", json={
            "student_id": self.student_id,
            "student_name": self.student_name
        }, catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    self.exam_id = data.get("exam_id")
                    self.login_success = True
                    print(f"✓ 学生 {self.student_name} 登录成功，考试ID: {self.exam_id}")
                    response.success()
                else:
                    print(f"✗ 学生 {self.student_name} 登录失败: {data.get('message')}")
                    response.failure(f"登录失败: {data.get('message')}")
                    self.login_success = False
            else:
                print(f"✗ 学生 {self.student_name} 登录HTTP错误: {response.status_code}")
                print(f"  响应内容: {response.text}")
                response.failure(f"HTTP {response.status_code}")
                self.login_success = False

    @task(10)
    def heartbeat(self):
        """发送心跳（高频任务，权重10）"""
        if not self.login_success or not self.exam_id:
            return

        self.client.post("/api/heartbeat", json={
            "student_id": self.student_id,
            "exam_id": self.exam_id
        }, name="/api/heartbeat")

    @task(3)
    def upload_screenshot(self):
        """上传截图（中频任务，权重3）"""
        if not self.login_success or not self.exam_id:
            return

        # 生成一个小的测试图片（800x600，减少带宽占用）
        img = Image.new('RGB', (800, 600), color=(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)))
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.client.post("/api/screenshot", files={
            "screenshot": ("screenshot.png", img_bytes, "image/png")
        }, data={
            "student_id": self.student_id,
            "exam_id": str(self.exam_id),
            "username": self.student_name,
            "timestamp": timestamp
        }, name="/api/screenshot")

    @task(1)
    def upload_video(self):
        """上传视频片段（低频任务，权重1）"""
        if not self.login_success or not self.exam_id:
            return

        # 生成一个小的测试视频文件（模拟15MB的1分钟录屏）
        # 为了测试性能，我们使用较小的文件（1MB）以避免网络成为瓶颈
        video_size = 1 * 1024 * 1024  # 1MB
        video_data = os.urandom(video_size)
        video_file = io.BytesIO(video_data)

        # 使用高精度timestamp，避免测试时多个用户同时上传导致文件名冲突
        # 真实环境中客户端每60秒上传一次，不会有此问题
        import time
        timestamp = datetime.now().isoformat() + f".{int(time.time() * 1000000) % 1000:03d}"

        # 显式传递模拟IP的header（确保分流生效）
        self.client.post("/api/screen_recording",
            files={
                "video": ("recording.mp4", video_file, "video/mp4")
            },
            data={
                "student_id": self.student_id,
                "exam_id": str(self.exam_id),
                "timestamp": timestamp,
                "fps": "10",
                "quality": "80"
            },
            headers={"X-Test-Client-IP": self.simulated_ip},
            name="/api/screen_recording",
            timeout=30)

    def on_stop(self):
        """学生退出"""
        if self.login_success and self.exam_id:
            self.client.post("/api/logout", json={
                "student_id": self.student_id,
                "exam_id": self.exam_id,
                "username": self.student_name
            }, name="/api/logout")
            print(f"✓ 学生 {self.student_name} 已退出")


@events.init_command_line_parser.add_listener
def _(parser):
    """添加自定义命令行参数"""
    parser.add_argument("--exam-id", type=int, help="指定考试ID（需要预先创建）")


# 全局事件监听器 - 统计信息
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print("\n" + "="*60)
    print("开始负载测试")
    print("="*60)
    print(f"目标服务器: {environment.host}")
    print("测试场景: 模拟学生考试（登录、心跳、截图、视频上传）")
    print("="*60 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    print("\n" + "="*60)
    print("负载测试结束")
    print("="*60)
    print("请检查 Locust Web UI 查看详细统计信息")
    print("="*60 + "\n")
