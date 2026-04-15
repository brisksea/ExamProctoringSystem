#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
考试数据归档工具
将已结束的考试从主目录（SSD）移动到备份目录（大容量存储），释放主目录空间
"""

import os
import sys
import json
import shutil
import argparse
import pymysql
from pathlib import Path

# 全局配置
DATA_DIR = None
BACKUP_DATA_DIR = None
DB_CONFIG = None


def load_config():
    """加载配置文件"""
    global DATA_DIR, BACKUP_DATA_DIR, DB_CONFIG

    config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # 读取主数据目录
        config_data_dir = config.get('data_dir', './server_data')
        if not os.path.isabs(config_data_dir):
            DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), config_data_dir)
        else:
            DATA_DIR = config_data_dir

        # 读取备份数据目录
        backup_dir = config.get('backup_data_dir')
        if backup_dir:
            if not os.path.isabs(backup_dir):
                BACKUP_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), backup_dir)
            else:
                BACKUP_DATA_DIR = backup_dir

        # 读取MySQL配置
        DB_CONFIG = config.get('mysql', {})

        return True
    except Exception as e:
        print(f"加载配置文件失败: {e}")
        return False


def get_db_connection():
    """获取数据库连接"""
    return pymysql.connect(
        host=DB_CONFIG.get('host', 'localhost'),
        port=DB_CONFIG.get('port', 3306),
        user=DB_CONFIG.get('user'),
        password=DB_CONFIG.get('password'),
        database=DB_CONFIG.get('database'),
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )


def get_exam(exam_id):
    """从数据库获取考试信息"""
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM exams WHERE id = %s", (exam_id,))
            exam = cursor.fetchone()
        conn.close()
        return exam
    except Exception as e:
        print(f"查询考试信息失败: {e}")
        return None


def get_all_exams():
    """获取所有考试"""
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM exams ORDER BY id DESC")
            exams = cursor.fetchall()
        conn.close()
        return exams
    except Exception as e:
        print(f"查询考试列表失败: {e}")
        return []


def get_exam_size(exam_dir):
    """计算考试目录大小"""
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(exam_dir):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            try:
                total_size += os.path.getsize(fp)
            except Exception as e:
                pass
    return total_size


def format_size(size_bytes):
    """格式化文件大小显示"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def archive_exam(exam_id, dry_run=False, force=False):
    """
    归档指定考试到备份目录

    Args:
        exam_id: 考试ID
        dry_run: 是否为演练模式（不实际移动文件）
        force: 是否强制覆盖已存在的备份目录

    Returns:
        (success, message)
    """
    if not BACKUP_DATA_DIR:
        return False, "未配置备份数据目录，无法归档"

    # 检查主目录中的考试
    primary_exam_dir = os.path.join(DATA_DIR, str(exam_id))
    if not os.path.exists(primary_exam_dir):
        # 检查是否已经在备份目录
        backup_exam_dir = os.path.join(BACKUP_DATA_DIR, str(exam_id))
        if os.path.exists(backup_exam_dir):
            return False, f"考试 {exam_id} 已在备份目录中"
        else:
            return False, f"考试 {exam_id} 不存在"

    # 检查考试状态
    exam = get_exam(exam_id)
    if not exam:
        return False, f"数据库中未找到考试 {exam_id}"

    if exam['status'] == 'active':
        return False, f"考试 {exam_id} 正在进行中，无法归档"

    # 计算大小
    exam_size = get_exam_size(primary_exam_dir)

    # 备份目录路径
    backup_exam_dir = os.path.join(BACKUP_DATA_DIR, str(exam_id))

    print(f"\n{'='*60}")
    print(f"考试 ID: {exam_id}")
    print(f"考试名称: {exam['name']}")
    print(f"考试状态: {exam['status']}")
    print(f"数据大小: {format_size(exam_size)}")
    print(f"源目录: {primary_exam_dir}")
    print(f"目标目录: {backup_exam_dir}")
    print(f"{'='*60}")

    # 先检查备份目录是否已存在（在用户确认之前）
    if os.path.exists(backup_exam_dir):
        if not force:
            print(f"\n⚠️  错误: 备份目录已存在")
            print(f"   路径: {backup_exam_dir}")

            # 计算备份目录的大小
            backup_size = get_exam_size(backup_exam_dir)
            print(f"   现有大小: {format_size(backup_size)}")

            print(f"\n可能的原因:")
            print(f"  1. 该考试已经归档过")
            print(f"  2. 存在旧的备份数据")
            print(f"\n建议操作:")
            print(f"  1. 检查备份目录内容是否为该考试的数据")
            print(f"  2. 如果确认可以覆盖，使用 --force 选项强制归档:")
            print(f"     python3 archive_exam.py --exam {exam_id} --force")
            print(f"  3. 或手动删除备份目录后重新归档:")
            print(f"     rm -rf {backup_exam_dir}")
            print(f"  4. 如果需要保留备份，先重命名备份目录:")
            print(f"     mv {backup_exam_dir} {backup_exam_dir}.bak")

            return False, f"备份目录已存在，请先处理后再归档"

    if dry_run:
        print("[演练模式] 将执行以下操作:")
        print(f"  1. 将 {primary_exam_dir} 移动到 {backup_exam_dir}")
        print(f"  2. 释放主目录空间: {format_size(exam_size)}")
        return True, "演练模式完成"

    # 确认操作
    response = input("\n确认归档? (yes/no): ")
    if response.lower() not in ['yes', 'y']:
        return False, "用户取消归档"

    try:
        # 强制模式：删除已存在的备份目录
        if os.path.exists(backup_exam_dir) and force:
            print(f"\n⚠️  强制模式: 将删除已存在的备份目录")
            backup_size = get_exam_size(backup_exam_dir)
            print(f"   路径: {backup_exam_dir}")
            print(f"   大小: {format_size(backup_size)}")

            confirm = input("\n确认删除已存在的备份目录? (yes/no): ")
            if confirm.lower() not in ['yes', 'y']:
                return False, "用户取消删除备份目录"

            print(f"正在删除已存在的备份目录...")
            shutil.rmtree(backup_exam_dir)
            print(f"✓ 已删除旧备份")

        # 移动目录
        print(f"\n正在移动目录...")
        shutil.move(primary_exam_dir, backup_exam_dir)

        # 验证移动成功
        if os.path.exists(backup_exam_dir) and not os.path.exists(primary_exam_dir):
            print(f"✓ 归档成功!")
            print(f"✓ 已释放主目录空间: {format_size(exam_size)}")
            return True, f"考试 {exam_id} 已归档到备份目录"
        else:
            return False, "目录移动后验证失败"

    except Exception as e:
        return False, f"归档失败: {str(e)}"


def list_archivable_exams():
    """列出可以归档的考试"""
    print("\n可归档的考试列表（已结束且在主目录中）:")
    print(f"{'='*80}")
    print(f"{'ID':<6} {'名称':<30} {'状态':<10} {'大小':<15} {'结束时间':<20}")
    print(f"{'='*80}")

    exams = get_all_exams()

    archivable_count = 0
    total_size = 0

    for exam in exams:
        exam_id = exam['id']
        primary_exam_dir = os.path.join(DATA_DIR, str(exam_id))

        # 只显示在主目录中且已结束的考试
        if os.path.exists(primary_exam_dir) and exam['status'] == 'completed':
            size = get_exam_size(primary_exam_dir)
            total_size += size
            archivable_count += 1

            print(f"{exam_id:<6} {exam['name'][:28]:<30} {exam['status']:<10} "
                  f"{format_size(size):<15} {str(exam.get('end_time', 'N/A'))[:19]:<20}")

    print(f"{'='*80}")
    print(f"总计: {archivable_count} 个考试，可释放空间: {format_size(total_size)}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description='考试数据归档工具 - 将已结束考试从主目录移动到备份目录',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 查看可归档的考试列表
  python archive_exam.py --list

  # 演练归档考试（不实际移动）
  python archive_exam.py --exam 48 --dry-run

  # 实际归档考试
  python archive_exam.py --exam 48

  # 强制归档（覆盖已存在的备份）
  python archive_exam.py --exam 48 --force

  # 批量归档多个考试
  python archive_exam.py --exam 48 49 50
        """
    )

    parser.add_argument('--list', action='store_true', help='列出可归档的考试')
    parser.add_argument('--exam', type=int, nargs='+', help='要归档的考试ID')
    parser.add_argument('--dry-run', action='store_true', help='演练模式（不实际移动文件）')
    parser.add_argument('--force', action='store_true', help='强制模式（覆盖已存在的备份目录）')

    args = parser.parse_args()

    # 加载配置
    if not load_config():
        print("错误: 无法加载配置文件")
        sys.exit(1)

    # 检查配置
    if not DATA_DIR or not BACKUP_DATA_DIR:
        print("错误: 未正确配置主数据目录或备份数据目录")
        sys.exit(1)

    print(f"主数据目录: {DATA_DIR}")
    print(f"备份数据目录: {BACKUP_DATA_DIR}")

    if args.list:
        list_archivable_exams()
        sys.exit(0)

    if not args.exam:
        parser.print_help()
        sys.exit(0)

    # 归档指定的考试
    success_count = 0
    fail_count = 0

    for exam_id in args.exam:
        success, message = archive_exam(exam_id, args.dry_run, args.force)
        if success:
            success_count += 1
            print(f"✓ {message}")
        else:
            fail_count += 1
            print(f"✗ {message}")

    print(f"\n归档完成: 成功 {success_count}, 失败 {fail_count}")


if __name__ == '__main__':
    main()
