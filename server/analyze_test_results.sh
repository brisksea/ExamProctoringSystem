#!/bin/bash
# 分析500用户测试结果
# 提供详细的性能指标、负载分布、错误分析

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  测试结果详细分析${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# 1. 学生分布分析
echo -e "${CYAN}[1] 学生分布分析${NC}"
echo -e "${BLUE}----------------------------------------${NC}"

LOCAL_STUDENTS=$(find /home/zq/project/supervise/server_data/30/recordings -name "test_*" -type d 2>/dev/null | wc -l)
REMOTE_STUDENTS=$(ssh zq@10.188.2.252 "find /home/zq/project/supervise/server_data/30/recordings -name 'test_*' -type d 2>/dev/null | wc -l" 2>/dev/null || echo "0")
TOTAL_STUDENTS=$((LOCAL_STUDENTS + REMOTE_STUDENTS))

echo "总学生数: $TOTAL_STUDENTS"
echo "本地服务器: $LOCAL_STUDENTS 个学生"
echo "远程服务器: $REMOTE_STUDENTS 个学生"

if [ $TOTAL_STUDENTS -gt 0 ]; then
    LOCAL_PERCENT=$((LOCAL_STUDENTS * 100 / TOTAL_STUDENTS))
    REMOTE_PERCENT=$((REMOTE_STUDENTS * 100 / TOTAL_STUDENTS))

    echo ""
    echo "分布比例:"
    echo "  本地: ${LOCAL_PERCENT}%"
    echo "  远程: ${REMOTE_PERCENT}%"
    echo "  期望: 75% / 25%"

    # 计算偏差
    LOCAL_DIFF=$((LOCAL_PERCENT - 75))
    REMOTE_DIFF=$((REMOTE_PERCENT - 25))

    echo ""
    echo "偏差分析:"
    if [ $LOCAL_DIFF -lt 0 ]; then
        echo "  本地: ${LOCAL_DIFF}% (少于期望)"
    else
        echo "  本地: +${LOCAL_DIFF}% (多于期望)"
    fi

    if [ $REMOTE_DIFF -lt 0 ]; then
        echo "  远程: ${REMOTE_DIFF}% (少于期望)"
    else
        echo "  远程: +${REMOTE_DIFF}% (多于期望)"
    fi
fi
echo ""

# 2. 视频文件分析
echo -e "${CYAN}[2] 视频文件分析${NC}"
echo -e "${BLUE}----------------------------------------${NC}"

LOCAL_FILES=$(find /home/zq/project/supervise/server_data/30/recordings/test_* -name "*.mp4" 2>/dev/null | wc -l)
REMOTE_FILES=$(ssh zq@10.188.2.252 "find /home/zq/project/supervise/server_data/30/recordings/test_* -name '*.mp4' 2>/dev/null | wc -l" 2>/dev/null || echo "0")
TOTAL_FILES=$((LOCAL_FILES + REMOTE_FILES))

echo "总视频文件: $TOTAL_FILES 个"
echo "本地文件: $LOCAL_FILES 个"
echo "远程文件: $REMOTE_FILES 个"

if [ $TOTAL_STUDENTS -gt 0 ]; then
    AVG_FILES_PER_STUDENT=$((TOTAL_FILES * 100 / TOTAL_STUDENTS))
    echo "平均每学生: $((AVG_FILES_PER_STUDENT / 100)).$((AVG_FILES_PER_STUDENT % 100)) 个文件"
fi
echo ""

# 本地文件大小统计
if [ $LOCAL_FILES -gt 0 ]; then
    echo "本地文件大小统计:"
    LOCAL_SIZE=$(du -sh /home/zq/project/supervise/server_data/30/recordings/test_* 2>/dev/null | awk '{s+=$1} END {print s}' || echo "0")
    echo "  总大小: $(du -sh /home/zq/project/supervise/server_data/30/recordings/test_* 2>/dev/null | tail -1 | awk '{print $1}')"

    # 计算平均文件大小
    TOTAL_BYTES=$(find /home/zq/project/supervise/server_data/30/recordings/test_* -name "*.mp4" -exec stat -f%z {} + 2>/dev/null | awk '{s+=$1} END {print s}' || \
                  find /home/zq/project/supervise/server_data/30/recordings/test_* -name "*.mp4" -exec stat -c%s {} + 2>/dev/null | awk '{s+=$1} END {print s}')

    if [ ! -z "$TOTAL_BYTES" ] && [ "$TOTAL_BYTES" != "0" ]; then
        AVG_SIZE=$((TOTAL_BYTES / LOCAL_FILES / 1024 / 1024))
        echo "  平均文件大小: ${AVG_SIZE}MB"
    fi
fi
echo ""

# 3. Nginx日志分析
echo -e "${CYAN}[3] Nginx负载均衡日志分析${NC}"
echo -e "${BLUE}----------------------------------------${NC}"

if [ -f "/var/log/nginx/hash_debug.log" ]; then
    TOTAL_REQUESTS=$(wc -l < /var/log/nginx/hash_debug.log)
    echo "总请求数: $TOTAL_REQUESTS"

    if [ $TOTAL_REQUESTS -gt 0 ]; then
        # 统计唯一IP数量
        UNIQUE_IPS=$(awk '{print $5}' /var/log/nginx/hash_debug.log | sort -u | wc -l)
        echo "唯一客户端IP: $UNIQUE_IPS 个"

        # IP段分布
        echo ""
        echo "IP段分布:"
        awk '{print $5}' /var/log/nginx/hash_debug.log | sed 's/\.[0-9]*$//' | sort | uniq -c | sort -rn | head -10 | while read count subnet; do
            percent=$((count * 100 / TOTAL_REQUESTS))
            echo "  ${subnet}.x: $count 次 (${percent}%)"
        done

        # Top 10 IP
        echo ""
        echo "请求最多的10个IP:"
        awk '{print $5}' /var/log/nginx/hash_debug.log | sort | uniq -c | sort -rn | head -10 | while read count ip; do
            percent=$((count * 100 / TOTAL_REQUESTS))
            echo "  $ip: $count 次 (${percent}%)"
        done
    fi
else
    echo "未找到nginx日志文件"
fi
echo ""

# 4. IP分布一致性检查
echo -e "${CYAN}[4] IP分布一致性检查${NC}"
echo -e "${BLUE}----------------------------------------${NC}"
echo "检查同一IP是否总是路由到同一服务器..."

if [ -f "/var/log/nginx/hash_debug.log" ]; then
    # 分析每个IP的路由情况
    INCONSISTENT=0

    # 获取所有唯一IP
    UNIQUE_IPS=$(awk '{print $5}' /var/log/nginx/hash_debug.log | sort -u)

    for ip in $UNIQUE_IPS; do
        # 检查这个IP对应的学生目录
        student_dirs=$(grep "$ip" /var/log/nginx/hash_debug.log | head -1 | grep -o "test_[0-9]\{5\}" || echo "")

        if [ ! -z "$student_dirs" ]; then
            # 检查本地和远程是否都有这个学生
            local_has=$(find /home/zq/project/supervise/server_data/30/recordings -name "$student_dirs" -type d 2>/dev/null | wc -l)
            remote_has=$(ssh zq@10.188.2.252 "find /home/zq/project/supervise/server_data/30/recordings -name '$student_dirs' -type d 2>/dev/null | wc -l" 2>/dev/null || echo "0")

            if [ $local_has -gt 0 ] && [ $remote_has -gt 0 ]; then
                echo -e "${RED}  ✗ $ip ($student_dirs) 同时存在于本地和远程${NC}"
                INCONSISTENT=$((INCONSISTENT + 1))
            fi
        fi
    done

    if [ $INCONSISTENT -eq 0 ]; then
        echo -e "${GREEN}  ✓ 所有IP都保持一致性路由${NC}"
    else
        echo -e "${RED}  发现 $INCONSISTENT 个IP的路由不一致${NC}"
    fi
else
    echo "无法检查 (nginx日志不存在)"
fi
echo ""

# 5. Locust测试报告摘要
echo -e "${CYAN}[5] Locust测试报告摘要${NC}"
echo -e "${BLUE}----------------------------------------${NC}"

if [ -f "/tmp/test_500_stats.csv" ]; then
    echo "请求统计:"
    echo ""

    # 跳过标题行, 显示统计数据
    tail -n +2 /tmp/test_500_stats.csv | while IFS=',' read type name req_count fail_count median avg min max avg_size rps failures; do
        if [ "$type" != "None" ]; then
            success_rate=$(echo "scale=2; ($req_count - $fail_count) * 100 / $req_count" | bc 2>/dev/null || echo "100")
            echo "  $name"
            echo "    请求数: $req_count"
            echo "    失败数: $fail_count"
            echo "    成功率: ${success_rate}%"
            echo "    响应时间: avg=${avg}ms, median=${median}ms, max=${max}ms"
            echo "    RPS: $rps"
            echo ""
        fi
    done
else
    echo "未找到Locust CSV报告"
fi

if [ -f "/tmp/test_500_report.html" ]; then
    echo "HTML报告: /tmp/test_500_report.html"
    echo "浏览器打开: file:///tmp/test_500_report.html"
fi
echo ""

# 6. 系统资源使用情况
echo -e "${CYAN}[6] 系统资源使用情况${NC}"
echo -e "${BLUE}----------------------------------------${NC}"

if [ -f "/tmp/test_500_monitor.log" ]; then
    echo "从监控日志中提取资源使用峰值..."
    echo ""

    # 提取CPU峰值
    CPU_PEAK=$(grep "CPU使用" /tmp/test_500_monitor.log | awk '{print $2}' | sort -rn | head -1)
    echo "  CPU峰值: ${CPU_PEAK}"

    # 提取内存峰值
    MEM_PEAK=$(grep "内存使用" /tmp/test_500_monitor.log | awk '{print $2}' | sort -rn | head -1)
    echo "  内存峰值: ${MEM_PEAK}"

    # 提取MySQL连接峰值
    MYSQL_PEAK=$(grep "MySQL连接" /tmp/test_500_monitor.log | awk '{print $2}' | sort -rn | head -1)
    echo "  MySQL连接峰值: ${MYSQL_PEAK}"

    # 提取网络流量峰值
    NET_PEAK=$(grep "网络流量" /tmp/test_500_monitor.log | awk '{print $2}' | tail -1)
    echo "  网络流量: ${NET_PEAK}"

    echo ""
    echo "完整监控日志: /tmp/test_500_monitor.log"
else
    echo "未找到监控日志"
fi
echo ""

# 7. 总结和建议
echo -e "${CYAN}[7] 测试总结${NC}"
echo -e "${BLUE}========================================${NC}"

if [ $TOTAL_STUDENTS -ge 400 ]; then
    echo -e "${GREEN}✓ 测试成功: 有 $TOTAL_STUDENTS 个学生成功上传${NC}"
else
    echo -e "${YELLOW}⚠ 测试部分成功: 只有 $TOTAL_STUDENTS 个学生成功上传 (期望500)${NC}"
fi

if [ $TOTAL_STUDENTS -gt 0 ]; then
    if [ $LOCAL_PERCENT -ge 70 ] && [ $LOCAL_PERCENT -le 80 ]; then
        echo -e "${GREEN}✓ 负载分布合理: ${LOCAL_PERCENT}% / ${REMOTE_PERCENT}% (期望 75% / 25%)${NC}"
    else
        echo -e "${YELLOW}⚠ 负载分布偏离: ${LOCAL_PERCENT}% / ${REMOTE_PERCENT}% (期望 75% / 25%)${NC}"
    fi
fi

if [ $INCONSISTENT -eq 0 ]; then
    echo -e "${GREEN}✓ IP路由一致性: 所有IP保持一致性路由${NC}"
else
    echo -e "${RED}✗ IP路由一致性: 发现 $INCONSISTENT 个不一致${NC}"
fi

echo ""
echo -e "${BLUE}========================================${NC}"
