#!/usr/bin/env python3
"""
为考试34添加50个测试学生
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data_access import DataAccess

EXAM_ID = 34
TOTAL_USERS = 50

data_access = DataAccess()

print(f"开始为考试 {EXAM_ID} 添加学生...")
print(f"学生数量: {TOTAL_USERS} (test_00001 ~ test_{TOTAL_USERS:05d})")
print("=" * 80)

added_count = 0
skipped_count = 0

for i in range(1, TOTAL_USERS + 1):
    student_id = f"test_{i:05d}"
    student_name = f"测试学生{i:03d}"

    # 检查学生是否已存在
    existing = data_access.get_student_exam(student_id, EXAM_ID)

    if existing:
        print(f"⊘ {student_id} ({student_name}): 已存在，跳过")
        skipped_count += 1
        continue

    # 添加学生
    try:
        with data_access.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO exam_students (exam_id, student_id, student_name) VALUES (%s, %s, %s)",
                    (EXAM_ID, student_id, student_name)
                )
            conn.commit()
            added_count += 1
            print(f"✓ {student_id} ({student_name}): 添加成功")
    except Exception as e:
        print(f"✗ {student_id} ({student_name}): 添加失败 - {e}")

print("=" * 80)
print(f"完成！新增 {added_count} 个学生，跳过 {skipped_count} 个学生")
