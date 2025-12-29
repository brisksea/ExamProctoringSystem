"""
Celery 配置文件
使用 Redis 作为消息中间件和结果后端
"""
from celery import Celery
from celery.schedules import crontab

# Redis 配置
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_DB = 0
REDIS_URL = f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}'

# 创建 Celery 实例
celery_app = Celery(
    'exam_monitor',
    broker=REDIS_URL,        # 消息队列
    backend=REDIS_URL        # 结果存储
)

# Celery 配置
celery_app.conf.update(
    # 任务序列化方式
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Shanghai',
    enable_utc=False,

    # 任务结果过期时间（秒）
    result_expires=3600,

    # 任务超时时间（秒）
    task_time_limit=1800,  # 30分钟硬超时
    task_soft_time_limit=1500,  # 25分钟软超时

    # 任务确认机制
    task_acks_late=True,  # 任务执行完成后才确认
    worker_prefetch_multiplier=1,  # 每次只预取1个任务

    # Worker 配置
    worker_max_tasks_per_child=100,  # 每个 worker 执行100个任务后重启（防止内存泄漏）

    # 任务路由
    task_routes={
        'celery_tasks.status_check_task': {'queue': 'status_check'},
        'celery_tasks.merge_videos_task': {'queue': 'video_merge'},
    },

    # 定时任务配置（Celery Beat）
    beat_schedule={
        'status-check-every-30-seconds': {
            'task': 'celery_tasks.status_check_task',
            'schedule': 30.0,  # 每30秒执行一次
            'options': {'queue': 'status_check'}
        },
    },

    # 日志配置
    worker_log_format='[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
    worker_task_log_format='[%(asctime)s: %(levelname)s/%(processName)s] [%(task_name)s(%(task_id)s)] %(message)s',
)

# 直接导入任务模块（celery_tasks.py 是单文件模块，不能用 autodiscover）
import celery_tasks
