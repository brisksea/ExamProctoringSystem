#!/bin/bash
# Celery Beat 启动脚本 - 定时任务调度器（状态检测）

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

# 清理旧的 beat 调度文件（避免冲突）
rm -f celerybeat-schedule.db

# 启动 Celery Beat (定时任务调度器)
echo "正在启动 Celery Beat (定时任务调度器)..."
celery -A celery_config.celery_app beat \
    --loglevel=info \
    --logfile=logs/celery_beat.log \
    --pidfile=logs/celery_beat.pid \
    --detach

echo "Celery Beat 已启动"
echo "查看日志: tail -f logs/celery_beat.log"
