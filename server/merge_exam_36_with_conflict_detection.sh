#!/bin/bash
# 合并考试36数据，并检测大小冲突

SOURCE_DIR="/data/38"
TARGET_DIR="/data/supervise/server_data/38"
LOG_DIR="/home/zq/project/supervise/logs"
CONFLICT_LOG="$LOG_DIR/merge_exam_36_conflicts.log"
RSYNC_LOG="$LOG_DIR/merge_exam_36_rsync.log"

mkdir -p "$LOG_DIR"

echo "========================================"
echo "开始合并考试36数据"
echo "========================================"
echo "源目录: $SOURCE_DIR"
echo "目标目录: $TARGET_DIR"
echo "冲突日志: $CONFLICT_LOG"
echo "rsync日志: $RSYNC_LOG"
echo ""

# 第一步：检测大小冲突的文件
echo "步骤1/2: 检测文件大小冲突..."
echo "======================================== 文件大小冲突检测 ========================================" > "$CONFLICT_LOG"
echo "检测时间: $(date)" >> "$CONFLICT_LOG"
echo "" >> "$CONFLICT_LOG"

conflict_count=0
checked_count=0

# 遍历源目录的所有文件
while IFS= read -r -d '' src_file; do
    # 获取相对路径
    rel_path="${src_file#$SOURCE_DIR/}"
    target_file="$TARGET_DIR/$rel_path"
    
    checked_count=$((checked_count + 1))
    
    # 每1000个文件显示一次进度
    if [ $((checked_count % 1000)) -eq 0 ]; then
        echo "  已检查 $checked_count 个文件，发现 $conflict_count 个冲突..."
    fi
    
    # 如果目标文件存在，比较大小
    if [ -f "$target_file" ]; then
        src_size=$(stat -c%s "$src_file")
        target_size=$(stat -c%s "$target_file")
        
        if [ "$src_size" -ne "$target_size" ]; then
            conflict_count=$((conflict_count + 1))
            echo "冲突 #$conflict_count: $rel_path" >> "$CONFLICT_LOG"
            echo "  源文件大小: $(numfmt --to=iec-i --suffix=B $src_size)" >> "$CONFLICT_LOG"
            echo "  目标文件大小: $(numfmt --to=iec-i --suffix=B $target_size)" >> "$CONFLICT_LOG"
            echo "" >> "$CONFLICT_LOG"
        fi
    fi
done < <(find "$SOURCE_DIR" -type f -print0)

echo ""
echo "✓ 冲突检测完成"
echo "  检查文件数: $checked_count"
echo "  发现冲突: $conflict_count"
if [ $conflict_count -gt 0 ]; then
    echo "  ⚠️  详细冲突信息请查看: $CONFLICT_LOG"
fi
echo ""

# 第二步：使用 rsync 复制新文件（跳过已存在的）
echo "步骤2/2: 复制新文件..."
rsync -avh \
    --progress \
    --stats \
    --log-file="$RSYNC_LOG" \
    --ignore-existing \
    "$SOURCE_DIR/" \
    "$TARGET_DIR/"

echo ""
echo "========================================"
echo "✓ 合并完成！"
echo "========================================"
echo "冲突记录: $CONFLICT_LOG"
echo "rsync日志: $RSYNC_LOG"
echo ""
