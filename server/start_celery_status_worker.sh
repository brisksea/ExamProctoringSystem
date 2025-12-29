#!/bin/bash
# Celery Worker 启动脚本 - 处理状态检测任务（由 Beat 触发）

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# 激活虚拟环境（如果存在）
if [ -d "/home/zq/project/venv" ]; then
    source /home/zq/project/venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
fi

# 确保日志目录存在
mkdir -p logs

# 启动 Celery Worker (处理状态检测队列)
echo "正在启动 Celery Worker (状态检测队列)..."
celery -A celery_config.celery_app worker \
    --loglevel=info \
    --queues=status_check \
    --concurrency=1 \
    --max-tasks-per-child=1000 \
    --logfile=logs/celery_worker_status.log \
    --pidfile=logs/celery_worker_status.pid \
    --hostname=worker_status@%h \
    --detach

echo "Celery Worker (状态检测) 已启动"
echo "查看日志: tail -f logs/celery_worker_status.log"
