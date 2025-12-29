#!/bin/bash
# 负载测试监控脚本
# 实时显示系统关键指标

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================"
echo "考试系统负载测试监控"
echo "========================================"
echo ""

while true; do
    clear
    echo -e "${GREEN}========================================"
    echo "系统资源监控 - $(date '+%Y-%m-%d %H:%M:%S')"
    echo -e "========================================${NC}"
    echo ""

    # CPU使用率
    echo -e "${YELLOW}[CPU使用率]${NC}"
    cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1)
    echo "当前CPU: ${cpu_usage}%"
    if (( $(echo "$cpu_usage > 80" | bc -l) )); then
        echo -e "${RED}⚠ 警告：CPU使用率过高${NC}"
    fi
    echo ""

    # 内存使用
    echo -e "${YELLOW}[内存使用]${NC}"
    free -h | grep -E "Mem|Swap"
    mem_available=$(free -m | awk '/^Mem:/{print $7}')
    if [ "$mem_available" -lt 1024 ]; then
        echo -e "${RED}⚠ 警告：可用内存不足1GB${NC}"
    fi
    echo ""

    # Gunicorn进程
    echo -e "${YELLOW}[Gunicorn进程]${NC}"
    gunicorn_count=$(pgrep -f "gunicorn.*server:app" | wc -l)
    echo "进程数: $gunicorn_count"
    if [ "$gunicorn_count" -gt 10 ]; then
        echo -e "${RED}⚠ 警告：Gunicorn进程数过多${NC}"
    elif [ "$gunicorn_count" -eq 0 ]; then
        echo -e "${RED}✗ 错误：Gunicorn未运行${NC}"
    fi
    echo ""

    # MySQL连接数
    echo -e "${YELLOW}[MySQL连接数]${NC}"
    mysql_conn=$(mysql -u debian-sys-maint -pbGEtT3EfFKGLhYRS -s -N -e "SHOW STATUS LIKE 'Threads_connected';" 2>/dev/null | awk '{print $2}')
    mysql_max=$(mysql -u debian-sys-maint -pbGEtT3EfFKGLhYRS -s -N -e "SHOW STATUS LIKE 'Max_used_connections';" 2>/dev/null | awk '{print $2}')

    if [ -n "$mysql_conn" ]; then
        echo "当前连接: $mysql_conn"
        echo "峰值连接: $mysql_max"
        if [ "$mysql_conn" -gt 85 ]; then
            echo -e "${RED}⚠ 警告：MySQL连接数接近上限${NC}"
        fi
    else
        echo -e "${YELLOW}无法获取MySQL状态（可能需要sudo权限）${NC}"
    fi
    echo ""

    # 网络流量
    echo -e "${YELLOW}[网络流量]${NC}"
    # 获取主网卡名称（ens33或其他）
    main_interface=$(ip route | grep default | awk '{print $5}' | head -1)
    if [ -n "$main_interface" ]; then
        rx_bytes=$(cat /sys/class/net/$main_interface/statistics/rx_bytes 2>/dev/null)
        tx_bytes=$(cat /sys/class/net/$main_interface/statistics/tx_bytes 2>/dev/null)

        if [ -n "$rx_bytes" ] && [ -n "$tx_bytes" ]; then
            rx_mb=$(echo "scale=2; $rx_bytes / 1024 / 1024" | bc)
            tx_mb=$(echo "scale=2; $tx_bytes / 1024 / 1024" | bc)
            echo "接口: $main_interface"
            echo "接收: ${rx_mb} MB"
            echo "发送: ${tx_mb} MB"
        fi
    fi
    echo ""

    # Redis状态
    echo -e "${YELLOW}[Redis状态]${NC}"
    redis_status=$(systemctl is-active redis 2>/dev/null)
    if [ "$redis_status" == "active" ]; then
        echo "✓ Redis运行正常"
        redis_clients=$(redis-cli info clients 2>/dev/null | grep connected_clients | cut -d: -f2 | tr -d '\r')
        if [ -n "$redis_clients" ]; then
            echo "连接数: $redis_clients"
        fi
    else
        echo -e "${RED}✗ Redis未运行${NC}"
    fi
    echo ""

    # 磁盘IO
    echo -e "${YELLOW}[磁盘使用]${NC}"
    df -h | grep -E "Filesystem|/dev/sd|/dev/nvme" | head -5
    echo ""

    # 负载平均值
    echo -e "${YELLOW}[系统负载]${NC}"
    uptime | awk -F'load average:' '{print "负载平均值:" $2}'
    echo ""

    echo -e "${GREEN}========================================"
    echo "按 Ctrl+C 退出监控"
    echo -e "========================================${NC}"

    # 每2秒刷新一次
    sleep 2
done
