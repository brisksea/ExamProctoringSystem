#!/usr/bin/env python3
"""
清空考试30中test_00001~test_00050的所有登录历史
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data_access import DataAccess

EXAM_ID = 30
START_USER = 1
END_USER = 50

data_access = DataAccess()

print(f"开始清空考试 {EXAM_ID} 的学生登录历史...")
print(f"学生范围: test_{START_USER:05d} ~ test_{END_USER:05d}")
print("=" * 80)

deleted_count = 0

for i in range(START_USER, END_USER + 1):
    student_id = f"test_{i:05d}"

    # 获取 student_exam 记录
    student_exam = data_access.get_student_exam(student_id, EXAM_ID)

    if student_exam:
        exam_student_id = student_exam['id']

        # 删除该学生的所有登录历史
        with data_access.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM student_login_history WHERE student_exam_id = %s",
                    (exam_student_id,)
                )
                deleted = cursor.rowcount
                deleted_count += deleted

                if deleted > 0:
                    print(f"✓ {student_id}: 删除 {deleted} 条登录历史记录")
            conn.commit()

print("=" * 80)
print(f"清空完成！共删除 {deleted_count} 条登录历史记录")
