#!/bin/bash
# 一键启动所有 Celery 服务

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "========================================="
echo "启动所有 Celery 服务"
echo "========================================="

# 1. 启动 Celery Beat (定时任务调度器)
bash start_celery_beat.sh
sleep 2

# 2. 启动 Celery Worker (状态检测队列)
bash start_celery_status_worker.sh
sleep 2

# 3. 启动 Celery Worker (视频合并队列)
bash start_celery_worker.sh
sleep 2

echo ""
echo "========================================="
echo "所有 Celery 服务已启动"
echo "========================================="
echo ""
echo "查看运行状态:"
echo "  ps aux | grep celery"
echo ""
echo "查看日志:"
echo "  tail -f logs/celery_beat.log"
echo "  tail -f logs/celery_worker_status.log"
echo "  tail -f logs/celery_worker_merge.log"
echo ""
echo "停止服务:"
echo "  bash stop_celery.sh"
echo ""
