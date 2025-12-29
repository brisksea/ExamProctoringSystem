#!/usr/bin/env python3
"""
真实场景的负载测试 - 模拟480个学生并发上传录屏
两阶段测试：
- 阶段1：所有用户完成登录
- 阶段2：统一开始上传视频

基于实际录屏参数:
- 录屏间隔: 60秒
- 上传间隔: 60秒 + 随机0-10秒
- 文件大小: 6-10MB (平均8MB，模拟 1536x864, 2fps, quality=2, 60秒)
- 上传超时: 120秒
"""

import os
import io
import time
import random
import threading
from datetime import datetime
from locust import HttpUser, task, between, events

# 全局配置
# TOTAL_USERS 仅用于限制学生ID范围，不用于等待同步
TOTAL_USERS = int(os.getenv('TOTAL_USERS', '480'))  # 学生ID范围上限

class RealisticExamStudent(HttpUser):
    """
    模拟真实的考试学生行为

    分布式部署说明：
    - 每个 Worker 需要设置环境变量 WORKER_OFFSET 以避免学生ID冲突
    - Worker1: WORKER_OFFSET=0   (学生ID: 1-100)
    - Worker2: WORKER_OFFSET=100 (学生ID: 101-200)
    - Worker3: WORKER_OFFSET=200 (学生ID: 201-300)
    """
    # 上传间隔: 60秒 + 随机0-10秒
    wait_time = between(60, 70)

    # Worker 偏移量（从环境变量读取，避免分布式环境下学生ID冲突）
    _worker_offset = int(os.getenv('WORKER_OFFSET', '0'))
    _student_counter = 0
    _counter_lock = None

    # 两阶段同步：等待所有用户登录完成
    _login_count = 0
    _login_complete_event = None
    _all_logged_in = False

    def on_start(self):
        """初始化学生信息"""
        # 初始化共享锁和事件
        if RealisticExamStudent._counter_lock is None:
            RealisticExamStudent._counter_lock = threading.Lock()
        if RealisticExamStudent._login_complete_event is None:
            RealisticExamStudent._login_complete_event = threading.Event()

        with RealisticExamStudent._counter_lock:
            RealisticExamStudent._student_counter += 1
            # 加上 Worker 偏移量，避免不同 Worker 产生相同学生ID
            student_num = RealisticExamStudent._worker_offset + RealisticExamStudent._student_counter

            # 限制学生ID在1-480范围内（480用户测试）
            if student_num > TOTAL_USERS:
                print(f"⚠ 警告: 学生编号 {student_num} 超过{TOTAL_USERS}，重置为 {(student_num - 1) % TOTAL_USERS + 1}")
                student_num = (student_num - 1) % TOTAL_USERS + 1

        # 学生ID: test_00001 到 test_00500
        self.student_id = f"test_{student_num:05d}"
        self.student_name = f"测试学生{student_num:03d}"

        # 模拟不同网段的IP (连续IP): 192.168.1.1-255, 192.168.2.1-245
        if student_num <= 255:
            self.simulated_ip = f"192.168.1.{student_num}"
        else:
            self.simulated_ip = f"192.168.2.{student_num - 255}"

        self.login_success = False
        self.exam_id = None
        self.video_sequence = 0  # 视频序号计数器

        # ========== 阶段1: 登录 ==========
        self._login()

        # 登录成功后，增加登录计数
        if self.login_success:
            with RealisticExamStudent._counter_lock:
                RealisticExamStudent._login_count += 1
                current_count = RealisticExamStudent._login_count

                # 不再等待所有用户，直接允许开始上传
                # （实际用户数可能与TOTAL_USERS不同，由Web UI动态设置）
                if current_count % 50 == 0:  # 每50个用户打印一次进度
                    print(f"📊 登录进度: {current_count} 个用户已登录")

            # 登录成功后启动后台心跳线程（每30秒发送一次）
            try:
                if not hasattr(self, '_hb_thread') or not getattr(self, '_hb_thread'):
                    self._hb_running = True
                    hb_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
                    hb_thread.start()
                    self._hb_thread = hb_thread
            except Exception:
                pass

        # 不再等待同步，登录成功后直接开始上传
        # 添加随机延迟 (模拟学生不是同时开始考试)
        time.sleep(random.uniform(0, 30))

    def _login(self):
        """学生登录"""
        try:
            with self.client.post("/api/login",
                json={
                    "student_id": self.student_id,
                    "student_name": self.student_name
                },
                catch_response=True,
                timeout=10) as response:

                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "success":
                        self.exam_id = data.get("exam_id")
                        if self.exam_id:
                            self.login_success = True
                            response.success()
                            print(f"✓ {self.student_id} 登录成功, exam_id={self.exam_id}, IP={self.simulated_ip}")
                            # 登录成功，不再延迟（由统一等待机制控制）
                        else:
                            print(f"✗ {self.student_id} 登录响应中缺少 exam_id")
                            self.environment.runner.quit()  # 停止测试
                    else:
                        response.failure(f"登录失败: {data.get('message')}")
                        print(f"✗ {self.student_id} 登录失败: {data.get('message')}")
                else:
                    response.failure(f"HTTP {response.status_code}")
                    print(f"✗ {self.student_id} 登录HTTP错误: {response.status_code}")
        except Exception as e:
            print(f"✗ {self.student_id} 登录异常: {e}")
            # 登录异常不停止测试，允许重试

    @task(10)
    def upload_video(self):
        """
        上传录屏视频 (高权重任务)
        模拟真实场景:
        - 文件大小: 6-10MB (平均8MB)
        - 上传超时: 120秒
        - 使用X-Test-Client-IP header
        - 文件名包含序号便于检测丢失
        """
        # 检查登录状态（所有用户已在on_start中完成登录等待）
        if not self.login_success or not self.exam_id:
            return

        # 递增视频序号
        self.video_sequence += 1
        seq = self.video_sequence

        # 生成6-10MB的视频数据 (模拟 1536x864, 2fps, quality=2, 60秒录屏)
        video_size = random.randint(6, 10) * 1024 * 1024  # 6-10 MB
        video_data = os.urandom(video_size)
        video_file = io.BytesIO(video_data)

        # 文件名包含序号: recording_seq_0001.mp4
        filename = f"recording_seq_{seq:04d}.mp4"
        video_file.name = filename

        # 高精度时间戳 (避免文件名冲突)
        timestamp = datetime.now().isoformat() + f".{int(time.time() * 1000000) % 1000:03d}"

        try:
            # 使用streaming upload, 超时600秒 (与真实客户端一致)
            # 添加重传机制
            max_retries = 3
            for attempt in range(max_retries):
                response = self.client.post("/api/screen_recording",
                    files={"video": (filename, io.BytesIO(video_data), "video/mp4")},
                    data={
                        "student_id": self.student_id,
                        "exam_id": str(self.exam_id),
                        "timestamp": timestamp,
                        "sequence": str(seq),  # 添加序号信息
                        "fps": "2",
                        "quality": "2"
                    },
                    headers={"X-Test-Client-IP": self.simulated_ip},
                    name="/api/screen_recording",
                    timeout=120,  # 2分钟超时
                    stream=True)  # 流式上传

                if response.status_code == 200:
                    print(f"✓ {self.student_id} 上传第 {seq} 个视频: {filename}")
                    break
                elif response.status_code == 0:
                    # 状态码0表示连接失败
                    error_msg = getattr(response, 'error', '连接失败')
                    print(f"⚠ {self.student_id} 上传第 {seq} 个视频连接失败: {error_msg}，重试 {attempt + 2}/{max_retries}")
                    time.sleep(2)  # 连接失败等待更长时间
                elif attempt < max_retries - 1:
                    print(f"⚠ {self.student_id} 上传第 {seq} 个视频失败 (状态码:{response.status_code})，重试 {attempt + 2}/{max_retries}")
                    time.sleep(1)  # 等待1秒后重试
                else:
                    print(f"✗ {self.student_id} 上传第 {seq} 个视频失败: 状态码 {response.status_code}")
        except Exception as e:
            print(f"✗ {self.student_id} 上传第 {seq} 个视频异常: {e}")

    #@task(10)  # 权重10：与上传视频相同频率，每60-70秒发一次
    def _send_heartbeat(self):
        """单次发送心跳请求（内部使用）。"""
        if not self.login_success or not self.exam_id:
            return
        try:
            self.client.post("/api/heartbeat",
                json={
                    "student_id": self.student_id,
                    "exam_id": self.exam_id
                },
                name="/api/heartbeat",
                timeout=5)
        except Exception:
            pass  # 忽略心跳异常以减少日志噪声

    def _heartbeat_loop(self):
        """后台循环线程：每30秒发送一次心跳，直到用户停止。"""
        import time
        self._hb_running = True
        while getattr(self, '_hb_running', False):
            # 发送心跳并等待30秒
            self._send_heartbeat()
            for _ in range(30):
                if not getattr(self, '_hb_running', False):
                    break
                time.sleep(1)

    def on_stop(self):
        # 停止后台心跳线程
        self._hb_running = False


# Locust事件处理器
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """测试开始时的处理"""
    print("\n" + "="*60)
    print("开始真实场景负载测试")
    print("="*60)
    print(f"目标用户数: 500")
    print(f"视频大小: 15-20 MB")
    print(f"上传间隔: 20-40秒 (模拟实际的120±60秒)")
    print(f"上传超时: 600秒")
    print(f"IP范围: 192.168.1.1-255, 192.168.2.1-245")
    print("="*60 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """测试结束时的处理"""
    print("\n" + "="*60)
    print("负载测试结束")
    print("="*60)

    # 输出统计信息
    stats = environment.stats
    print(f"\n请求统计:")
    print(f"  总请求数: {stats.total.num_requests}")
    print(f"  失败请求数: {stats.total.num_failures}")
    print(f"  成功率: {(1 - stats.total.fail_ratio) * 100:.2f}%")
    print(f"  平均响应时间: {stats.total.avg_response_time:.0f}ms")
    print(f"  中位数响应时间: {stats.total.median_response_time:.0f}ms")
    print(f"  RPS: {stats.total.total_rps:.2f}")

    print("\n各接口统计:")
    for name, entry in stats.entries.items():
        print(f"\n  {name}:")
        print(f"    请求数: {entry.num_requests}")
        print(f"    失败数: {entry.num_failures}")
        print(f"    平均响应时间: {entry.avg_response_time:.0f}ms")
        print(f"    中位数: {entry.median_response_time:.0f}ms")
        print(f"    95%: {entry.get_response_time_percentile(0.95):.0f}ms")
        print(f"    99%: {entry.get_response_time_percentile(0.99):.0f}ms")

    print("\n" + "="*60 + "\n")
