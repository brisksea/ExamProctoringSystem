#!/bin/bash
# Locust Master节点启动脚本
# 在主控机器上运行，协调所有worker

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 配置
USERS=500
SPAWN_RATE=10
RUN_TIME=10m
HOST="http://172.16.229.162:5000"
MASTER_PORT=5557
WEB_PORT=8089

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Locust Master 节点${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}配置信息:${NC}"
echo "  总用户数: $USERS"
echo "  启动速率: $SPAWN_RATE 用户/秒"
echo "  运行时间: $RUN_TIME"
echo "  目标服务器: $HOST"
echo "  Master端口: $MASTER_PORT"
echo "  Web界面: http://$(hostname -I | awk '{print $1}'):$WEB_PORT"
echo ""

# 检查端口占用
if lsof -Pi :$MASTER_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${RED}错误: 端口 $MASTER_PORT 已被占用${NC}"
    echo "请先停止其他Locust进程"
    exit 1
fi

if lsof -Pi :$WEB_PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${RED}错误: 端口 $WEB_PORT 已被占用${NC}"
    echo "请先停止其他Locust进程"
    exit 1
fi

# 清理旧测试数据
echo -e "${YELLOW}清理旧测试数据...${NC}"
rm -rf /home/zq/project/supervise/server_data/30/recordings/test_* 2>/dev/null || true
ssh zq@10.188.2.252 "rm -rf /home/zq/project/supervise/server_data/30/recordings/test_*" 2>/dev/null || true
echo -e "${GREEN}✓ 清理完成${NC}"
echo ""

# 清空nginx日志
echo -e "${YELLOW}准备日志文件...${NC}"
sudo truncate -s 0 /var/log/nginx/hash_debug.log
sudo chmod 644 /var/log/nginx/hash_debug.log
echo -e "${GREEN}✓ 日志已清空${NC}"
echo ""

# 启动master
echo -e "${YELLOW}启动Locust Master...${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${GREEN}Web界面访问: http://$(hostname -I | awk '{print $1}'):$WEB_PORT${NC}"
echo ""
echo -e "${YELLOW}等待Worker连接...${NC}"
echo "Worker连接命令 (在其他机器上执行):"
echo -e "${CYAN}  locust -f load_test_realistic.py --worker --master-host=$(hostname -I | awk '{print $1}')${NC}"
echo ""
echo -e "${BLUE}========================================${NC}"
echo ""

# 启动master (带Web界面)
locust -f load_test_realistic.py \
    --master \
    --master-bind-port=$MASTER_PORT \
    --web-port=$WEB_PORT \
    --expect-workers=3 \
    --host=$HOST \
    --html /tmp/test_500_distributed_report.html \
    --csv /tmp/test_500_distributed

echo ""
echo -e "${GREEN}测试完成！${NC}"
echo ""
echo "查看报告:"
echo "  HTML: /tmp/test_500_distributed_report.html"
echo "  CSV: /tmp/test_500_distributed_stats.csv"
