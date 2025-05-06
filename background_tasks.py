import json
import threading
from redis_helper import configure_redis_persistence, get_all_exams, get_exam_students, get_redis, update_exam_status
import time, os
from datetime import datetime, timedelta


# 长时间不活跃的学生清理任务
def cleanup_inactive_students():
    """清理长时间不活跃的学生（自动掉线）"""
    while True:
        time.sleep(60)  # 每分钟检查一次
        try:
            client = get_redis()
            now = datetime.now()
            exams = [exam for exam in get_all_exams() if exam.get('status') == 'active']

            for exam in exams:
                exam_id = exam['id']
                students = get_exam_students(exam_id)
                for student_id, student in students.items():
                    if student['status'] == 'online' and 'last_active' in student:
                        last_active = datetime.strptime(student['last_active'], "%Y-%m-%d %H:%M:%S")
                        inactive_minutes = (now - last_active).total_seconds() / 60
                        #超过2分钟没有收到截屏认为掉线
                        if inactive_minutes > 2:
                            student_key = f'exam:{exam_id}:student:{student_id}'
                            timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
                            client.hset(student_key, 'status', 'offline')
                            client.hset(student_key, 'offline_time', timestamp)
                            # 写入掉线历史
                            offline_record = {
                                "type": "offline",
                                "timestamp": timestamp,
                                "ip": student.get('ip', 'unknown')
                            }
                            client.rpush(f"exam:{exam_id}:student:{student_id}:logins", json.dumps(offline_record))
                            print(f"进程 {os.getpid()}: 学生 {student['username']} (ID: {student_id}, 考试: {exam_id}) 长时间无心跳，自动掉线")
        except Exception as e:
            print(f"进程 {os.getpid()}: 清理不活跃学生时出错: {str(e)}")

# 考试状态更新任务
def update_exam_status_task():
    """定期更新考试状态的任务"""
    while True:
        time.sleep(30)  # 每30秒检查一次
        try:
            updated_count = update_exam_status()
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
    #configure_redis_persistence()
    start_background_tasks()
    print("后台定时任务已启动")
    while True:
        time.sleep(60)