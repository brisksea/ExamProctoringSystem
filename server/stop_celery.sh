#!/bin/bash
# 停止所有 Celery 进程

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "正在停止所有 Celery 进程..."

# 停止 Celery Workers
if [ -f "logs/celery_worker_merge.pid" ]; then
    PID=$(cat logs/celery_worker_merge.pid)
    if ps -p $PID > /dev/null 2>&1; then
        kill $PID
        echo "Celery Worker (视频合并) 已停止 (PID: $PID)"
    fi
    rm -f logs/celery_worker_merge.pid
fi

if [ -f "logs/celery_worker_status.pid" ]; then
    PID=$(cat logs/celery_worker_status.pid)
    if ps -p $PID > /dev/null 2>&1; then
        kill $PID
        echo "Celery Worker (状态检测) 已停止 (PID: $PID)"
    fi
    rm -f logs/celery_worker_status.pid
fi

# 停止 Celery Beat
if [ -f "logs/celery_beat.pid" ]; then
    PID=$(cat logs/celery_beat.pid)
    if ps -p $PID > /dev/null 2>&1; then
        kill $PID
        echo "Celery Beat 已停止 (PID: $PID)"
    fi
    rm -f logs/celery_beat.pid
fi

# 强制杀死残留的 celery 进程
pkill -f "celery.*celery_config" || true

echo "所有 Celery 进程已停止"
