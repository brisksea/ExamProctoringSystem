#!/usr/bin/env python3
import sys
import os
import time
import signal
from datetime import datetime

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data_access import DataAccess

class StatusChecker:
    def __init__(self):
        self.data_access = DataAccess()
        self.running = True

        # 注册信号处理器
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)

    def signal_handler(self, signum, frame):
        print(f"收到信号 {signum}，准备退出...")
        self.running = False

    def check_status(self):
        """检查所有正在进行的考试状态和学生状态"""
        try:
            now = datetime.now()

            # 获取所有考试
            exams = self.data_access.get_all_exams()

            for exam in exams:
                exam_id = exam['id']

                # 检查考试状态
                try:
                    # 处理start_time，支持datetime对象和字符串
                    start_time = exam['start_time']
                    if isinstance(start_time, str):
                        start_time = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
                    elif not isinstance(start_time, datetime):
                        raise ValueError(f"Unsupported start_time type: {type(start_time)}")

                    # 处理end_time，支持datetime对象和字符串
                    end_time = exam['end_time']
                    if isinstance(end_time, str):
                        end_time = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
                    elif not isinstance(end_time, datetime):
                        raise ValueError(f"Unsupported end_time type: {type(end_time)}")

                    # 更新考试状态
                    if now < start_time:
                        new_status = 'pending'
                    elif start_time <= now <= end_time:
                        new_status = 'active'
                    else:
                        new_status = 'completed'

                    # 如果状态发生变化，更新考试状态
                    if exam['status'] != new_status:
                        self.data_access.update_exam_status(exam_id, new_status)
                        print(f"考试状态更新: {exam['name']} (ID: {exam_id}) {exam['status']} -> {new_status}")

                    # 只检查正在进行的考试的学生状态
                    if new_status == 'active':
                        students = self.data_access.get_exam_students(exam_id)

                        for student in students:
                            student_id = student['student_id']

                            # 跳过已经掉线或已结束考试的学生
                            if student['status'] in ['logout']:
                                continue

                            # 获取最后活跃时间
                            last_active = student.get('last_active')
                            if last_active:
                                try:
                                    # 处理last_active，支持datetime对象和字符串
                                    if isinstance(last_active, datetime):
                                        last_active_time = last_active
                                    elif isinstance(last_active, str):
                                        last_active_time = datetime.strptime(last_active, "%Y-%m-%d %H:%M:%S")
                                    else:
                                        # 尝试转换为字符串再解析
                                        last_active_time = datetime.strptime(str(last_active), "%Y-%m-%d %H:%M:%S")

                                    # 如果超过30秒没有活跃，并且学生状态是online，标记为掉线
                                    if (now - last_active_time).total_seconds() > 30 and student['status'] == 'online':
                                        self.data_access.update_student_status(student_id, exam_id, 'offline')
                                        self.data_access.add_login_history(student['id'], 'offline', now.strftime("%Y-%m-%d %H:%M:%S"), 'system')
                                        print(f"学生掉线: {student['student_name']} (ID: {student_id}, 考试: {exam_id})")
                                    # 如果学生状态是offline，并且30秒内活跃，则恢复为online
                                    elif (now - last_active_time).total_seconds() < 30 and student['status'] == 'offline':
                                        self.data_access.update_student_status(student_id, exam_id, 'online')
                                        self.data_access.add_login_history(student['id'], 'online', now.strftime("%Y-%m-%d %H:%M:%S"), 'system')
                                except (ValueError, TypeError) as e:
                                    print(f"解析学生最后活跃时间出错: {last_active} (类型: {type(last_active)}), 错误: {str(e)}")
                                    continue

                except Exception as e:
                    print(f"处理考试 {exam_id} 时出错: {str(e)}")
                    continue

        except Exception as e:
            print(f"状态检查出错: {str(e)}")

    def run(self):
        """主运行循环"""
        print(f"状态检查器启动，PID: {os.getpid()}")

        while self.running:
            try:
                self.check_status()
            except Exception as e:
                print(f"检查状态时出错: {e}")

            # 每10秒检查一次
            for _ in range(100):  # 10秒 = 100 × 0.1秒
                if not self.running:
                    break
                time.sleep(0.1)

        print("状态检查器正常退出")

if __name__ == '__main__':
    checker = StatusChecker()
    checker.run()