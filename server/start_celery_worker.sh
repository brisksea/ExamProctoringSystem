#!/bin/bash
# Celery Worker 启动脚本 - 处理视频合并任务

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

# 启动 Celery Worker (处理视频合并队列)
echo "正在启动 Celery Worker (视频合并队列)..."
celery -A celery_config.celery_app worker \
    --loglevel=info \
    --queues=video_merge \
    --concurrency=2 \
    --max-tasks-per-child=50 \
    --logfile=logs/celery_worker_merge.log \
    --pidfile=logs/celery_worker_merge.pid \
    --hostname=worker_merge@%h \
    --detach

echo "Celery Worker (视频合并) 已启动"
echo "查看日志: tail -f logs/celery_worker_merge.log"
