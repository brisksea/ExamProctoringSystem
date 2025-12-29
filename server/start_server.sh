#!/bin/bash

# 考试监控服务器管理脚本
# 用法: ./start_server.sh {start|stop|restart|status}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# PID文件和日志
GUNICORN_PIDFILE="$SCRIPT_DIR/logs/gunicorn.pid"
CELERY_WORKER_PIDFILE="$SCRIPT_DIR/logs/celery_worker.pid"
CELERY_BEAT_PIDFILE="$SCRIPT_DIR/logs/celery_beat.pid"

mkdir -p "$SCRIPT_DIR/logs"

start_gunicorn() {
    if [ -f "$GUNICORN_PIDFILE" ] && ps -p $(cat "$GUNICORN_PIDFILE") > /dev/null 2>&1; then
        echo "Gunicorn 已在运行"
        return 0
    fi
    rm -f "$GUNICORN_PIDFILE"

    echo "启动 Gunicorn..."
    gunicorn -c gunicorn_config.py --daemon --pid "$GUNICORN_PIDFILE" server:app
    sleep 2

    if [ -f "$GUNICORN_PIDFILE" ] && ps -p $(cat "$GUNICORN_PIDFILE") > /dev/null 2>&1; then
        WORKERS=$(grep "^workers" gunicorn_config.py | grep -o '[0-9]*')
        echo "✓ Gunicorn 启动成功 (Workers: $WORKERS)"
    else
        echo "✗ Gunicorn 启动失败"
        return 1
    fi
}

stop_gunicorn() {
    # 先尝试优雅关闭主进程（会自动关闭所有worker）
    if [ -f "$GUNICORN_PIDFILE" ]; then
        PID=$(cat "$GUNICORN_PIDFILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            kill -TERM "$PID" 2>/dev/null
            # 等待优雅关闭
            for i in {1..10}; do
                if ! ps -p "$PID" > /dev/null 2>&1; then
                    break
                fi
                sleep 1
            done
            # 如果还活着，强制杀掉
            if ps -p "$PID" > /dev/null 2>&1; then
                kill -9 "$PID" 2>/dev/null
                sleep 1
            fi
        fi
        rm -f "$GUNICORN_PIDFILE"
    fi

    # 清理所有可能残留的 gunicorn 进程
    # 使用 exam_monitor 进程名来匹配，因为 worker 进程的 cmdline 会被改写
    pkill -9 -f "gunicorn.*exam_monitor" 2>/dev/null
    # 也尝试匹配原始启动命令
    pkill -9 -f "gunicorn.*server:app" 2>/dev/null
    sleep 1

    # 再次确认清理完毕
    if pgrep -f "gunicorn.*exam_monitor" > /dev/null 2>&1; then
        echo "⚠ 警告: 仍有 gunicorn 进程残留"
        pgrep -af "gunicorn.*exam_monitor"
    fi

    echo "✓ Gunicorn 已停止"
}

start_celery_worker() {
    if [ -f "$CELERY_WORKER_PIDFILE" ] && ps -p $(cat "$CELERY_WORKER_PIDFILE") > /dev/null 2>&1; then
        echo "Celery Worker 已在运行"
        return 0
    fi
    rm -f "$CELERY_WORKER_PIDFILE"

    echo "启动 Celery Worker..."
    celery -A celery_config worker --loglevel=info --concurrency=4 \
        --pidfile="$CELERY_WORKER_PIDFILE" \
        --logfile="$SCRIPT_DIR/logs/celery_worker.log" \
        --detach
    sleep 2

    if [ -f "$CELERY_WORKER_PIDFILE" ] && ps -p $(cat "$CELERY_WORKER_PIDFILE") > /dev/null 2>&1; then
        echo "✓ Celery Worker 启动成功"
    else
        echo "✗ Celery Worker 启动失败"
        return 1
    fi
}

stop_celery_worker() {
    # 先尝试优雅关闭主进程
    if [ -f "$CELERY_WORKER_PIDFILE" ]; then
        PID=$(cat "$CELERY_WORKER_PIDFILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            kill -TERM "$PID" 2>/dev/null
            # 等待优雅关闭
            for i in {1..15}; do
                if ! ps -p "$PID" > /dev/null 2>&1; then
                    break
                fi
                sleep 1
            done
            # 如果还活着，强制杀掉
            if ps -p "$PID" > /dev/null 2>&1; then
                kill -9 "$PID" 2>/dev/null
                sleep 1
            fi
        fi
        rm -f "$CELERY_WORKER_PIDFILE"
    fi

    # 清理所有可能残留的 celery worker 进程（包括子进程）
    pkill -9 -f "celery.*worker" 2>/dev/null
    # 也清理可能的 celeryd 进程
    pkill -9 -f "celeryd.*celery_config" 2>/dev/null
    sleep 1

    # 再次确认清理完毕
    if pgrep -f "celery.*worker" > /dev/null 2>&1; then
        echo "⚠ 警告: 仍有 celery worker 进程残留"
        pgrep -af "celery.*worker"
    fi

    echo "✓ Celery Worker 已停止"
}

start_celery_beat() {
    if [ -f "$CELERY_BEAT_PIDFILE" ] && ps -p $(cat "$CELERY_BEAT_PIDFILE") > /dev/null 2>&1; then
        echo "Celery Beat 已在运行"
        return 0
    fi
    rm -f "$CELERY_BEAT_PIDFILE"

    echo "启动 Celery Beat..."
    celery -A celery_config beat --loglevel=info \
        --pidfile="$CELERY_BEAT_PIDFILE" \
        --logfile="$SCRIPT_DIR/logs/celery_beat.log" \
        --detach
    sleep 2

    if [ -f "$CELERY_BEAT_PIDFILE" ] && ps -p $(cat "$CELERY_BEAT_PIDFILE") > /dev/null 2>&1; then
        echo "✓ Celery Beat 启动成功"
    else
        echo "✗ Celery Beat 启动失败"
        return 1
    fi
}

stop_celery_beat() {
    # 先尝试优雅关闭主进程
    if [ -f "$CELERY_BEAT_PIDFILE" ]; then
        PID=$(cat "$CELERY_BEAT_PIDFILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            kill -TERM "$PID" 2>/dev/null
            # 等待优雅关闭
            for i in {1..10}; do
                if ! ps -p "$PID" > /dev/null 2>&1; then
                    break
                fi
                sleep 1
            done
            # 如果还活着，强制杀掉
            if ps -p "$PID" > /dev/null 2>&1; then
                kill -9 "$PID" 2>/dev/null
                sleep 1
            fi
        fi
        rm -f "$CELERY_BEAT_PIDFILE"
    fi

    # 清理所有可能残留的 celery beat 进程
    pkill -9 -f "celery.*beat" 2>/dev/null
    sleep 1

    # 再次确认清理完毕
    if pgrep -f "celery.*beat" > /dev/null 2>&1; then
        echo "⚠ 警告: 仍有 celery beat 进程残留"
        pgrep -af "celery.*beat"
    fi

    echo "✓ Celery Beat 已停止"
}

show_status() {
    echo "========== 服务状态 =========="
    for name in Gunicorn "Celery Worker" "Celery Beat"; do
        case "$name" in
            Gunicorn) pidfile="$GUNICORN_PIDFILE" ;;
            "Celery Worker") pidfile="$CELERY_WORKER_PIDFILE" ;;
            "Celery Beat") pidfile="$CELERY_BEAT_PIDFILE" ;;
        esac
        if [ -f "$pidfile" ] && ps -p $(cat "$pidfile") > /dev/null 2>&1; then
            echo "$name: 运行中 (PID: $(cat $pidfile))"
        else
            echo "$name: 已停止"
        fi
    done
}

case "$1" in
    start)
        echo "========== 启动服务 =========="
        start_gunicorn
        start_celery_worker
        start_celery_beat
        ;;
    stop)
        echo "========== 停止服务 =========="
        stop_celery_beat
        stop_celery_worker
        stop_gunicorn
        ;;
    restart)
        echo "========== 重启服务 =========="
        stop_celery_beat
        stop_celery_worker
        stop_gunicorn
        sleep 1
        start_gunicorn
        start_celery_worker
        start_celery_beat
        ;;
    status)
        show_status
        ;;
    *)
        echo "用法: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
