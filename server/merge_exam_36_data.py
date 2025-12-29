#!/usr/bin/env python3
"""
合并考试36的数据文件
从 /data/36_1 合并到 /data/supervise/server_data/36

规则：
1. 如果文件名和大小都相同，跳过
2. 如果文件名相同但大小不同，记录到日志
3. 如果文件不存在于目标目录，复制过去
"""

import os
import shutil
from pathlib import Path
from datetime import datetime

# 目录配置
SOURCE_DIR = Path("/data/38")
TARGET_DIR = Path("/data/supervise/server_data/38")
LOG_FILE = Path("/home/zq/project/supervise/logs/merge_exam_38.log")

# 统计信息
stats = {
    'total_files': 0,
    'skipped_same': 0,
    'copied_new': 0,
    'size_mismatch': 0,
    'errors': 0,
    'copied_bytes': 0
}

def get_relative_path(file_path, base_dir):
    """获取相对路径"""
    return file_path.relative_to(base_dir)

def format_size(size_bytes):
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f}{unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f}TB"

def log_message(message, to_console=True):
    """记录日志"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {message}\n"

    # 写入日志文件
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(log_line)

    # 打印到控制台
    if to_console:
        print(message)

def merge_files():
    """合并文件"""
    log_message("="*80)
    log_message(f"开始合并任务")
    log_message(f"源目录: {SOURCE_DIR}")
    log_message(f"目标目录: {TARGET_DIR}")
    log_message("="*80)

    # 确保日志目录存在
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    # 遍历源目录的所有文件
    for source_file in SOURCE_DIR.rglob('*'):
        if not source_file.is_file():
            continue

        stats['total_files'] += 1

        # 计算相对路径
        rel_path = get_relative_path(source_file, SOURCE_DIR)
        target_file = TARGET_DIR / rel_path

        # 获取源文件大小
        source_size = source_file.stat().st_size

        try:
            # 检查目标文件是否存在
            if target_file.exists():
                target_size = target_file.stat().st_size

                # 文件名和大小都相同，跳过
                if source_size == target_size:
                    stats['skipped_same'] += 1
                    if stats['total_files'] % 100 == 0:
                        log_message(f"进度: {stats['total_files']} 文件已处理 "
                                  f"(跳过: {stats['skipped_same']}, "
                                  f"复制: {stats['copied_new']}, "
                                  f"冲突: {stats['size_mismatch']})")
                    continue
                else:
                    # 文件名相同但大小不同
                    stats['size_mismatch'] += 1
                    log_message(f"⚠️  大小冲突: {rel_path}")
                    log_message(f"   源文件: {format_size(source_size)}")
                    log_message(f"   目标文件: {format_size(target_size)}")
                    log_message(f"   保留目标文件，跳过复制")
                    continue

            # 文件不存在，需要复制
            # 确保目标目录存在
            target_file.parent.mkdir(parents=True, exist_ok=True)

            # 复制文件
            shutil.copy2(source_file, target_file)
            stats['copied_new'] += 1
            stats['copied_bytes'] += source_size

            if stats['copied_new'] % 50 == 0:
                log_message(f"✓ 已复制 {stats['copied_new']} 个新文件 "
                          f"(总大小: {format_size(stats['copied_bytes'])})")

        except Exception as e:
            stats['errors'] += 1
            log_message(f"❌ 错误处理文件 {rel_path}: {e}")

    # 打印最终统计
    log_message("="*80)
    log_message("合并完成！")
    log_message("="*80)
    log_message(f"总文件数: {stats['total_files']}")
    log_message(f"跳过(相同): {stats['skipped_same']}")
    log_message(f"复制(新文件): {stats['copied_new']}")
    log_message(f"大小冲突: {stats['size_mismatch']}")
    log_message(f"错误: {stats['errors']}")
    log_message(f"复制数据量: {format_size(stats['copied_bytes'])}")
    log_message("="*80)

if __name__ == "__main__":
    try:
        merge_files()
    except KeyboardInterrupt:
        log_message("\n任务被用户中断")
        log_message(f"已处理: {stats['total_files']} 文件")
        log_message(f"已复制: {stats['copied_new']} 文件")
    except Exception as e:
        log_message(f"致命错误: {e}")
        raise
