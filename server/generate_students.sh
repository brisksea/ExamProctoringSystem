#!/bin/bash
# 生成测试学生名单并导入到指定考试

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}========================================"
echo "生成测试学生名单"
echo -e "========================================${NC}"
echo ""

# 获取考试ID
read -p "请输入考试ID: " EXAM_ID

if [ -z "$EXAM_ID" ]; then
    echo -e "${RED}✗ 考试ID不能为空${NC}"
    exit 1
fi

# 获取学生数量
read -p "请输入要生成的学生数量 (默认400): " STUDENT_COUNT
STUDENT_COUNT=${STUDENT_COUNT:-400}

echo ""
echo -e "${YELLOW}正在生成 $STUDENT_COUNT 个测试学生...${NC}"

# 生成学生名单文件
STUDENT_FILE="test_students_${EXAM_ID}.txt"
> "$STUDENT_FILE"

for i in $(seq 1 $STUDENT_COUNT); do
    student_id=$(printf "test_%05d" $i)
    student_name="测试学生$(printf "%03d" $i)"
    echo "$student_id $student_name" >> "$STUDENT_FILE"
done

echo -e "${GREEN}✓ 学生名单已生成: $STUDENT_FILE${NC}"
echo ""

# 询问是否导入
read -p "是否立即导入到考试 $EXAM_ID ? (y/n): " IMPORT

if [ "$IMPORT" = "y" ] || [ "$IMPORT" = "Y" ]; then
    echo ""
    echo -e "${YELLOW}正在导入学生到考试 $EXAM_ID...${NC}"

    # 使用API导入
    response=$(curl -s -X POST http://172.16.229.162:5000/api/students/import \
        -F "exam_id=$EXAM_ID" \
        -F "import_type=file" \
        -F "student_list_file=@$STUDENT_FILE")

    # 检查响应
    if echo "$response" | grep -q '"status":"success"'; then
        imported_count=$(echo "$response" | grep -o '"imported_count":[0-9]*' | cut -d: -f2)
        echo -e "${GREEN}✓ 成功导入 $imported_count 名学生${NC}"
    else
        echo -e "${RED}✗ 导入失败${NC}"
        echo "响应: $response"
        exit 1
    fi

    echo ""
    echo -e "${GREEN}完成！可以开始负载测试了${NC}"
    echo ""
    echo "下一步："
    echo "1. 运行测试: ./run_test.sh"
    echo "2. 或直接启动 Locust: locust -f load_test.py --host=http://172.16.229.162:5000"
else
    echo ""
    echo "学生名单已保存到: $STUDENT_FILE"
    echo "稍后可以通过Web界面手动导入"
fi

echo ""
