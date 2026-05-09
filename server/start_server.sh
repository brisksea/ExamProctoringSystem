#!/bin/bash

# 考试监控服务器管理脚本
# 用法: ./start_server.sh {start|stop|restart|status}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# PID文件和日志
GUNICORN_PIDFILE="$SCRIPT_DIR/logs/gunicorn.pid"
SCHEDULER_PIDFILE="$SCRIPT_DIR/logs/exam_scheduler.pid"

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
    if [ -f "$GUNICORN_PIDFILE" ]; then
        PID=$(cat "$GUNICORN_PIDFILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            kill -TERM "$PID" 2>/dev/null
            for i in {1..10}; do
                if ! ps -p "$PID" > /dev/null 2>&1; then
                    break
                fi
                sleep 1
            done
            if ps -p "$PID" > /dev/null 2>&1; then
                kill -9 "$PID" 2>/dev/null
                sleep 1
            fi
        fi
        rm -f "$GUNICORN_PIDFILE"
    fi

    pkill -9 -f "gunicorn.*exam_monitor" 2>/dev/null
    pkill -9 -f "gunicorn.*server:app" 2>/dev/null
    sleep 1

    if pgrep -f "gunicorn.*exam_monitor" > /dev/null 2>&1; then
        echo "⚠ 警告: 仍有 gunicorn 进程残留"
        pgrep -af "gunicorn.*exam_monitor"
    fi

    echo "✓ Gunicorn 已停止"
}

start_scheduler() {
    if [ -f "$SCHEDULER_PIDFILE" ] && ps -p $(cat "$SCHEDULER_PIDFILE") > /dev/null 2>&1; then
        echo "考试调度服务已在运行"
        return 0
    fi
    rm -f "$SCHEDULER_PIDFILE"

    echo "启动考试调度服务..."
    python "$SCRIPT_DIR/exam_scheduler.py" >> "$SCRIPT_DIR/logs/exam_scheduler.log" 2>&1 &
    SCHEDULER_PID=$!
    echo $SCHEDULER_PID > "$SCHEDULER_PIDFILE"
    sleep 2

    if ps -p "$SCHEDULER_PID" > /dev/null 2>&1; then
        echo "✓ 考试调度服务启动成功 (PID: $SCHEDULER_PID)"
    else
        echo "✗ 考试调度服务启动失败，请检查 logs/exam_scheduler.log"
        rm -f "$SCHEDULER_PIDFILE"
        return 1
    fi
}

stop_scheduler() {
    if [ -f "$SCHEDULER_PIDFILE" ]; then
        PID=$(cat "$SCHEDULER_PIDFILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            kill -TERM "$PID" 2>/dev/null
            for i in {1..10}; do
                if ! ps -p "$PID" > /dev/null 2>&1; then
                    break
                fi
                sleep 1
            done
            if ps -p "$PID" > /dev/null 2>&1; then
                kill -9 "$PID" 2>/dev/null
                sleep 1
            fi
        fi
        rm -f "$SCHEDULER_PIDFILE"
    fi

    pkill -9 -f "exam_scheduler.py" 2>/dev/null
    sleep 1

    echo "✓ 考试调度服务已停止"
}

show_status() {
    echo "========== 服务状态 =========="
    for name in Gunicorn "考试调度服务"; do
        case "$name" in
            Gunicorn) pidfile="$GUNICORN_PIDFILE" ;;
            "考试调度服务") pidfile="$SCHEDULER_PIDFILE" ;;
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
        start_scheduler
        ;;
    stop)
        echo "========== 停止服务 =========="
        stop_scheduler
        stop_gunicorn
        ;;
    restart)
        echo "========== 重启服务 =========="
        stop_scheduler
        stop_gunicorn
        sleep 1
        start_gunicorn
        start_scheduler
        ;;
    status)
        show_status
        ;;
    *)
        echo "用法: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
