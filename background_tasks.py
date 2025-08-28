import json
import threading
from data_access import DataAccess
import time, os
from datetime import datetime, timedelta

# 创建数据访问实例
data_access = DataAccess()

# 长时间不活跃的学生清理任务
def cleanup_inactive_students():
    """清理长时间不活跃的学生（自动掉线）"""
    while True:
        time.sleep(60)  # 每分钟检查一次
        try:
            now = datetime.now()
            # 获取所有活跃的考试
            exams = [exam for exam in data_access.get_all_exams() if exam.get('status') == 'active']

            for exam in exams:
                exam_id = exam['id']
                students = data_access.get_exam_students(exam_id)
                for student in students:  # students is now a list
                    student_id = student['student_id']
                    if student['status'] == 'online' and student.get('last_active'):
                        try:
                            last_active = datetime.strptime(str(student['last_active']), "%Y-%m-%d %H:%M:%S")
                            inactive_minutes = (now - last_active).total_seconds() / 60
                            # 超过2分钟没有收到截屏认为掉线
                            if inactive_minutes > 2:
                                timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
                                # 更新学生状态为离线
                                data_access.update_student_status(student_id, exam_id, 'offline')

                                # 添加离线记录到登录历史
                                student_exam = data_access.get_student_exam(student_id, exam_id)
                                if student_exam:
                                    data_access.add_login_history(student_exam['id'], 'offline', timestamp, 'system')

                                print(f"进程 {os.getpid()}: 学生 {student['student_name']} (ID: {student_id}, 考试: {exam_id}) 长时间无心跳，自动掉线")
                        except ValueError as e:
                            print(f"解析学生最后活跃时间出错: {student.get('last_active')}, 错误: {str(e)}")
        except Exception as e:
            print(f"进程 {os.getpid()}: 清理不活跃学生时出错: {str(e)}")

# 考试状态更新任务
def update_exam_status_task():
    """定期更新考试状态的任务"""
    while True:
        time.sleep(30)  # 每30秒检查一次
        try:
            updated_count = 0
            now = datetime.now()
            exams = data_access.get_all_exams()

            for exam in exams:
                exam_id = exam['id']
                current_status = exam['status']

                # 检查考试时间状态
                start_time = datetime.strptime(str(exam['start_time']), "%Y-%m-%d %H:%M:%S")
                end_time = datetime.strptime(str(exam['end_time']), "%Y-%m-%d %H:%M:%S")

                new_status = current_status
                if now < start_time and current_status != 'pending':
                    new_status = 'pending'
                elif start_time <= now <= end_time and current_status != 'active':
                    new_status = 'active'
                elif now > end_time and current_status != 'completed':
                    new_status = 'completed'

                # 如果状态发生变化，更新考试状态
                if current_status != new_status:
                    data_access.update_exam_status(exam_id, new_status)
                    updated_count += 1
                    print(f"考试状态更新: {exam['name']} (ID: {exam_id}) {current_status} -> {new_status}")

            if updated_count > 0:
                print(f"进程 {os.getpid()}: 已更新 {updated_count} 个考试的状态")
        except Exception as e:
            print(f"进程 {os.getpid()}: 更新考试状态时出错: {str(e)}")

# 启动后台任务线程
def start_background_tasks():
    """启动所有后台任务线程"""
    # 启动学生清理线程
    inactive_thread = threading.Thread(target=cleanup_inactive_students)
    inactive_thread.daemon = True
    inactive_thread.start()
    print(f"进程 {os.getpid()}: 学生清理线程已启动")

    # 启动考试状态更新线程
    exam_status_thread = threading.Thread(target=update_exam_status_task)
    exam_status_thread.daemon = True
    exam_status_thread.start()
    print(f"进程 {os.getpid()}: 考试状态更新线程已启动")

if __name__ == '__main__':
    start_background_tasks()
    print("后台定时任务已启动")
    while True:
        time.sleep(60)