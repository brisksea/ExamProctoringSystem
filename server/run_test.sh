#!/bin/bash
# 快速启动负载测试

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}========================================"
echo "考试系统负载测试 - 快速启动"
echo -e "========================================${NC}"
echo ""

# 检查虚拟环境
if [ ! -d "/home/zq/project/venv" ]; then
    echo -e "${RED}✗ 虚拟环境不存在${NC}"
    exit 1
fi

# 激活虚拟环境
source /home/zq/project/venv/bin/activate

# 检查locust是否安装
if ! python -c "import locust" 2>/dev/null; then
    echo -e "${YELLOW}正在安装 locust...${NC}"
    pip install locust pillow -q
fi

echo ""
echo "请选择测试模式："
echo ""
echo "1) Web UI 模式（推荐） - 可视化界面，实时图表"
echo "2) 命令行模式 - 自动化测试"
echo "3) 仅启动监控（不运行测试）"
echo ""
read -p "请输入选择 (1-3): " choice

case $choice in
    1)
        echo ""
        echo -e "${GREEN}启动 Locust Web UI...${NC}"
        echo ""
        echo "1. 访问 http://localhost:8089"
        echo "2. 配置参数："
        echo "   - Number of users: 50 (建议从小开始)"
        echo "   - Spawn rate: 5"
        echo "   - Host: http://172.16.229.162:5000"
        echo ""
        echo "3. 点击 Start Swarming"
        echo ""
        echo "4. 在另一个终端运行监控："
        echo "   cd $SCRIPT_DIR && ./monitor_test.sh"
        echo ""
        read -p "按回车键继续..."

        locust -f load_test.py --host=http://172.16.229.162:5000
        ;;

    2)
        echo ""
        echo "请选择并发用户数："
        echo "1) 50 用户 (5分钟)"
        echo "2) 100 用户 (10分钟)"
        echo "3) 200 用户 (10分钟)"
        echo "4) 400 用户 (15分钟)"
        echo "5) 自定义"
        echo ""
        read -p "请输入选择 (1-5): " test_choice

        case $test_choice in
            1)
                USERS=50
                SPAWN_RATE=5
                RUN_TIME="5m"
                ;;
            2)
                USERS=100
                SPAWN_RATE=10
                RUN_TIME="10m"
                ;;
            3)
                USERS=200
                SPAWN_RATE=10
                RUN_TIME="10m"
                ;;
            4)
                USERS=400
                SPAWN_RATE=20
                RUN_TIME="15m"
                ;;
            5)
                read -p "用户数: " USERS
                read -p "启动速率(users/sec): " SPAWN_RATE
                read -p "运行时间(如: 10m): " RUN_TIME
                ;;
            *)
                echo -e "${RED}无效选择${NC}"
                exit 1
                ;;
        esac

        REPORT_FILE="report_${USERS}users_$(date +%Y%m%d_%H%M%S).html"

        echo ""
        echo -e "${GREEN}开始测试...${NC}"
        echo "参数: $USERS 用户, 启动速率 $SPAWN_RATE/秒, 持续 $RUN_TIME"
        echo "报告将保存到: $REPORT_FILE"
        echo ""
        echo -e "${YELLOW}建议：在另一个终端运行监控脚本${NC}"
        echo "  cd $SCRIPT_DIR && ./monitor_test.sh"
        echo ""
        read -p "按回车键开始测试..."

        locust -f load_test.py \
            --host=http://172.16.229.162:5000 \
            --users $USERS \
            --spawn-rate $SPAWN_RATE \
            --run-time $RUN_TIME \
            --headless \
            --html $REPORT_FILE \
            --csv report_${USERS}users

        echo ""
        echo -e "${GREEN}测试完成！${NC}"
        echo "HTML报告: $REPORT_FILE"
        echo "CSV数据: report_${USERS}users_*.csv"
        ;;

    3)
        echo ""
        echo -e "${GREEN}启动系统监控...${NC}"
        ./monitor_test.sh
        ;;

    *)
        echo -e "${RED}无效选择${NC}"
        exit 1
        ;;
esac
