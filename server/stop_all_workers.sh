#!/bin/bash
# 停止所有Worker节点

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Worker机器列表 (与deploy_workers.sh保持一致)
WORKER_HOSTS=(
    "10.188.2.252"
    # "10.188.2.253"
    # "10.188.2.254"
)

SSH_USER="zq"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  停止所有Locust Workers${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

for host in "${WORKER_HOSTS[@]}"; do
    echo -n "停止 $host 上的Worker ... "

    # 杀掉locust进程
    ssh $SSH_USER@$host "pkill -f 'locust.*--worker' || true" 2>/dev/null

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${YELLOW}(可能未运行)${NC}"
    fi
done

echo ""
echo -e "${GREEN}所有Workers已停止${NC}"
