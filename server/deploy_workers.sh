#!/bin/bash
# 自动部署Worker到多台机器
# 使用SSH批量部署和启动worker

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Master地址 (当前机器)
MASTER_HOST=$(hostname -I | awk '{print $1}')

# Worker机器列表 (修改为你的实际机器)
WORKER_HOSTS=(
    "10.188.2.251"
    "172.16.229.136"
    # "10.188.2.253"
    # "10.188.2.254"
    # 添加更多worker机器...
)

# SSH用户名
SSH_USER="zq"

# 项目路径
PROJECT_DIR="/home/zq/project/supervise"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  批量部署Locust Worker${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}配置信息:${NC}"
echo "  Master地址: $MASTER_HOST"
echo "  Worker数量: ${#WORKER_HOSTS[@]}"
echo "  Worker列表:"
for host in "${WORKER_HOSTS[@]}"; do
    echo "    - $host"
done
echo ""

# 1. 检查SSH连接
echo -e "${CYAN}[1/4] 检查SSH连接...${NC}"
REACHABLE_HOSTS=()
for host in "${WORKER_HOSTS[@]}"; do
    echo -n "  检查 $host ... "
    if ssh -o ConnectTimeout=5 -o BatchMode=yes $SSH_USER@$host "echo ok" >/dev/null 2>&1; then
        echo -e "${GREEN}✓${NC}"
        REACHABLE_HOSTS+=("$host")
    else
        echo -e "${RED}✗ 无法连接${NC}"
    fi
done

if [ ${#REACHABLE_HOSTS[@]} -eq 0 ]; then
    echo -e "${RED}错误: 没有可用的worker机器${NC}"
    exit 1
fi

echo -e "${GREEN}可用Worker: ${#REACHABLE_HOSTS[@]} 台${NC}"
echo ""

# 2. 部署测试脚本
echo -e "${CYAN}[2/4] 部署测试脚本到Worker...${NC}"
for host in "${REACHABLE_HOSTS[@]}"; do
    echo "  部署到 $host ..."

    # 创建目录
    ssh $SSH_USER@$host "mkdir -p $PROJECT_DIR" 2>/dev/null || true

    # 复制必要文件
    scp -q load_test_realistic.py $SSH_USER@$host:$PROJECT_DIR/
    scp -q distributed_test_worker.sh $SSH_USER@$host:$PROJECT_DIR/

    # 添加执行权限
    ssh $SSH_USER@$host "chmod +x $PROJECT_DIR/distributed_test_worker.sh"

    echo -e "    ${GREEN}✓ 完成${NC}"
done
echo ""

# 3. 检查Worker环境
echo -e "${CYAN}[3/4] 检查Worker环境...${NC}"
for host in "${REACHABLE_HOSTS[@]}"; do
    echo "  检查 $host ..."

    # 检查Python
    if ! ssh $SSH_USER@$host "python3 --version" >/dev/null 2>&1; then
        echo -e "    ${RED}✗ Python3未安装${NC}"
        continue
    fi

    # 检查Locust
    if ! ssh $SSH_USER@$host "python3 -c 'import locust'" >/dev/null 2>&1; then
        echo -e "    ${YELLOW}⚠ Locust未安装，正在安装...${NC}"
        ssh $SSH_USER@$host "pip3 install locust requests" >/dev/null 2>&1
        if [ $? -eq 0 ]; then
            echo -e "    ${GREEN}✓ Locust安装成功${NC}"
        else
            echo -e "    ${RED}✗ Locust安装失败${NC}"
            continue
        fi
    else
        echo -e "    ${GREEN}✓ 环境检查通过${NC}"
    fi
done
echo ""

# 4. 启动Workers
echo -e "${CYAN}[4/4] 启动Workers...${NC}"
echo ""
echo -e "${YELLOW}准备启动 ${#REACHABLE_HOSTS[@]} 个Worker节点${NC}"
echo -e "${YELLOW}Master地址: $MASTER_HOST${NC}"
echo ""

# 创建启动脚本
WORKER_PIDS=()
for i in "${!REACHABLE_HOSTS[@]}"; do
    host="${REACHABLE_HOSTS[$i]}"
    echo -e "${BLUE}启动Worker $((i+1))/${#REACHABLE_HOSTS[@]}: $host${NC}"

    # 后台启动worker
    ssh $SSH_USER@$host "cd $PROJECT_DIR && nohup ./distributed_test_worker.sh $MASTER_HOST > /tmp/locust_worker.log 2>&1 &" &
    WORKER_PIDS+=($!)

    sleep 2
done

# 等待所有ssh命令完成
for pid in "${WORKER_PIDS[@]}"; do
    wait $pid 2>/dev/null || true
done

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  所有Worker已启动${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Worker列表:"
for host in "${REACHABLE_HOSTS[@]}"; do
    echo "  - $host"
done
echo ""
echo "现在可以在Master上开始测试了！"
echo ""
echo "查看Worker日志:"
for host in "${REACHABLE_HOSTS[@]}"; do
    echo "  ssh $SSH_USER@$host tail -f /tmp/locust_worker.log"
done
echo ""
echo "停止所有Workers:"
echo "  ./stop_all_workers.sh"
echo ""
