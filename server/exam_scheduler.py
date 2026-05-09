"""
考试调度服务 - 替代 Celery Beat + Worker

- 动态按考试生命周期调度任务（只在有考试时运行）
- 通过 Redis pub/sub 响应考试创建/修改/删除事件
- 视频合并使用 ThreadPoolExecutor + FFmpeg subprocess
"""

import os
import sys
import json
import time
import signal
import logging
import threading
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor

from apscheduler.schedulers.background import BackgroundScheduler

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data_access import DataAccess
from video_merger import merge_student_videos

# 日志配置（只用 stdout，由 start_server.sh 重定向到文件）
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

REDIS_CHANNEL = 'exam:schedule_changes'
DATA_DIR = 'server_data'

scheduler = BackgroundScheduler(timezone='Asia/Shanghai')
merge_executor = ThreadPoolExecutor(max_workers=2)
data_access = DataAccess()


# ========== APScheduler 任务函数 ==========

def check_offline_students(exam_id):
    """检测超过60秒未发心跳的学生，标记为离线"""
    try:
        now = datetime.now()
        inactive_ids = data_access.get_inactive_students(exam_id, timeout_seconds=60)
        if not inactive_ids:
            return

        students = data_access.get_exam_students(exam_id)
        students_dict = {s['student_id']: s for s in students}

        for student_id in inactive_ids:
            student = students_dict.get(student_id)
            if not student or student['status'] == 'logout':
                continue
            rt = data_access.get_student_realtime_status(exam_id, student_id)
            current_status = rt.get('status') or student['status']
            if current_status != 'online':
                continue

            data_access.update_student_status(student_id, exam_id, 'offline')
            try:
                student_exam = data_access.get_student_exam(student_id, exam_id)
                if student_exam:
                    data_access.add_login_history(
                        student_exam['id'], 'offline',
                        now.strftime("%Y-%m-%d %H:%M:%S"), 'system'
                    )
            except Exception as e:
                logger.warning(f"[掉线检测] 写入历史失败: {e}")

            data_access.set_student_realtime_status(
                exam_id, student_id, status='offline',
                last_seen=now.strftime("%Y-%m-%d %H:%M:%S")
            )
            logger.info(f"[掉线检测] 学生离线: {student.get('student_name')} (ID={student_id}, exam={exam_id})")

    except Exception as e:
        logger.error(f"[掉线检测] 出错 (exam={exam_id}): {e}")


def start_offline_check(exam_id):
    """考试开始时启动离线检测 interval job"""
    job_id = f'offline_{exam_id}'
    if scheduler.get_job(job_id):
        return
    scheduler.add_job(
        check_offline_students, 'interval', seconds=30,
        id=job_id, args=[exam_id], replace_existing=True
    )
    logger.info(f"[调度] 离线检测已启动: exam={exam_id}")


def handle_exam_end(exam_id):
    """考试结束：自动登出所有在线学生，停止离线检测"""
    logger.info(f"[考试结束] 处理: exam={exam_id}")
    try:
        job_id = f'offline_{exam_id}'
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)

        students = data_access.get_exam_students(exam_id)
        for student in students:
            if student['status'] == 'online':
                student_id = student['student_id']
                data_access.update_student_status(student_id, exam_id, 'logout')
                data_access.set_student_realtime_status(exam_id, student_id, status='logout')
                logger.info(f"[考试结束] 自动登出: {student.get('student_name')} (ID={student_id})")
    except Exception as e:
        logger.error(f"[考试结束] 处理失败 (exam={exam_id}): {e}")


def trigger_video_merge(exam_id):
    """考试结束30分钟后触发视频合并"""
    logger.info(f"[视频合并] 触发: exam={exam_id}")
    try:
        students = data_access.get_exam_students(exam_id)
        for student in students:
            student_id = student['student_id']
            student_dir = os.path.join(DATA_DIR, str(exam_id), "recordings", str(student_id))
            if os.path.exists(student_dir):
                logger.info(f"[视频合并] 提交: exam={exam_id}, student={student_id}")
                merge_executor.submit(
                    merge_student_videos,
                    exam_id, student_id,
                    student.get('student_name', f'student_{student_id}'),
                    DATA_DIR
                )
    except Exception as e:
        logger.error(f"[视频合并] 触发失败 (exam={exam_id}): {e}")


# ========== 调度管理 ==========

def _parse_time(t):
    if isinstance(t, datetime):
        return t
    if isinstance(t, str):
        return datetime.strptime(t, "%Y-%m-%d %H:%M:%S")
    raise ValueError(f"无法解析时间类型: {type(t)}")


def remove_exam_jobs(exam_id):
    """移除指定考试的所有调度任务"""
    for prefix in ('offline_', 'start_', 'end_', 'merge_'):
        job_id = f'{prefix}{exam_id}'
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
            logger.info(f"[调度] 移除 job: {job_id}")


def schedule_exam_jobs(exam):
    """为考试注册所有调度任务（已结束的考试跳过）"""
    exam_id = exam['id']
    now = datetime.now()

    try:
        start_time = _parse_time(exam['start_time'])
        end_time = _parse_time(exam['end_time'])
    except Exception as e:
        logger.error(f"[调度] 时间解析失败 (exam={exam_id}): {e}")
        return

    if now >= end_time:
        logger.info(f"[调度] 考试已结束，跳过注册: exam={exam_id}")
        return

    remove_exam_jobs(exam_id)

    if now >= start_time:
        # 考试进行中，立即启动离线检测
        scheduler.add_job(
            check_offline_students, 'interval', seconds=30,
            id=f'offline_{exam_id}', args=[exam_id], replace_existing=True
        )
        logger.info(f"[调度] 离线检测已启动: exam={exam_id}")
    else:
        # 考试未开始，在开考时启动离线检测
        scheduler.add_job(
            start_offline_check, 'date', run_date=start_time,
            id=f'start_{exam_id}', args=[exam_id], replace_existing=True
        )
        logger.info(f"[调度] 已注册开考任务: exam={exam_id}, start={start_time}")

    scheduler.add_job(
        handle_exam_end, 'date', run_date=end_time,
        id=f'end_{exam_id}', args=[exam_id], replace_existing=True
    )
    logger.info(f"[调度] 已注册结束任务: exam={exam_id}, end={end_time}")

    merge_time = end_time + timedelta(minutes=30)
    scheduler.add_job(
        trigger_video_merge, 'date', run_date=merge_time,
        id=f'merge_{exam_id}', args=[exam_id], replace_existing=True
    )
    logger.info(f"[调度] 已注册合并任务: exam={exam_id}, merge_at={merge_time}")


def init_from_db():
    """启动时扫描数据库，为 pending/active 考试注册任务"""
    logger.info("[启动] 扫描数据库中的考试...")
    try:
        exams = data_access.get_all_exams()
        scheduled = 0
        for exam in exams:
            if exam.get('status') in ('pending', 'active'):
                schedule_exam_jobs(exam)
                scheduled += 1
        logger.info(f"[启动] 完成，共调度 {scheduled} 场考试")
    except Exception as e:
        logger.error(f"[启动] 扫描失败: {e}")


def listen_redis_pubsub():
    """后台线程：监听 Redis pub/sub 消息，动态更新调度任务"""
    while True:
        try:
            r = data_access._get_redis()
            if not r:
                logger.error("[PubSub] Redis 不可用，5秒后重试")
                time.sleep(5)
                continue

            pubsub = r.pubsub()
            pubsub.subscribe(REDIS_CHANNEL)
            logger.info(f"[PubSub] 已订阅频道: {REDIS_CHANNEL}")

            for message in pubsub.listen():
                if message['type'] != 'message':
                    continue
                try:
                    data = json.loads(message['data'])
                    action = data.get('action')
                    exam_id = data.get('exam_id')
                    logger.info(f"[PubSub] 收到: action={action}, exam_id={exam_id}")

                    if action == 'delete':
                        remove_exam_jobs(exam_id)
                    elif action in ('create', 'update'):
                        exam = data_access.get_exam(exam_id)
                        if exam:
                            schedule_exam_jobs(exam)
                        else:
                            logger.warning(f"[PubSub] 考试不存在: exam={exam_id}")
                except Exception as e:
                    logger.error(f"[PubSub] 处理消息失败: {e}")

        except Exception as e:
            logger.error(f"[PubSub] 连接断开: {e}，5秒后重试")
            time.sleep(5)


def main():
    logger.info("考试调度服务启动")

    scheduler.start()
    init_from_db()

    pubsub_thread = threading.Thread(target=listen_redis_pubsub, daemon=True)
    pubsub_thread.start()

    def shutdown(signum, frame):
        logger.info("收到退出信号，正在关闭...")
        scheduler.shutdown(wait=False)
        merge_executor.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    logger.info("考试调度服务就绪")
    while True:
        time.sleep(60)


if __name__ == '__main__':
    main()
