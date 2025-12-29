#!/bin/bash
# Locust Worker节点启动脚本
# 在负载机器上运行，连接到master并执行实际测试

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 从命令行参数获取master地址，或使用默认值
MASTER_HOST=${1:-"172.16.229.162"}
MASTER_PORT=5557

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Locust Worker 节点${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}配置信息:${NC}"
echo "  Master地址: $MASTER_HOST:$MASTER_PORT"
echo "  本机IP: $(hostname -I | awk '{print $1}')"
echo ""

# 检查是否能连接到master
echo -e "${YELLOW}检查Master连接...${NC}"
if ! timeout 5 bash -c "cat < /dev/null > /dev/tcp/$MASTER_HOST/$MASTER_PORT" 2>/dev/null; then
    echo -e "${RED}错误: 无法连接到 Master ($MASTER_HOST:$MASTER_PORT)${NC}"
    echo ""
    echo "请确保:"
    echo "  1. Master已启动"
    echo "  2. 网络连通 (ping $MASTER_HOST)"
    echo "  3. 防火墙允许端口 $MASTER_PORT"
    exit 1
fi
echo -e "${GREEN}✓ Master连接正常${NC}"
echo ""

# 检查load_test_realistic.py是否存在
if [ ! -f "load_test_realistic.py" ]; then
    echo -e "${RED}错误: 找不到 load_test_realistic.py${NC}"
    echo "请确保在正确的目录下运行此脚本"
    exit 1
fi

# 启动worker
echo -e "${YELLOW}启动Locust Worker...${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${GREEN}已连接到 Master: $MASTER_HOST${NC}"
echo ""
echo "按 Ctrl+C 停止Worker"
echo ""
echo -e "${BLUE}========================================${NC}"
echo ""

# 启动worker
locust -f load_test_realistic.py \
    --worker \
    --master-host=$MASTER_HOST \
    --master-port=$MASTER_PORT

echo ""
echo -e "${YELLOW}Worker已停止${NC}"
