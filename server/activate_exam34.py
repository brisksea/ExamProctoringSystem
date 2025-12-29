#!/usr/bin/env python3
"""
检查并激活考试34
"""

import sys
import os
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data_access import DataAccess

EXAM_ID = 34

data_access = DataAccess()

# 获取考试信息
with data_access.get_connection() as conn:
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM exams WHERE id = %s", (EXAM_ID,))
        exam = cursor.fetchone()

if not exam:
    print(f"考试 {EXAM_ID} 不存在")
    sys.exit(1)

print(f"考试 {EXAM_ID} 信息:")
print(f"  名称: {exam['name']}")
print(f"  状态: {exam['status']}")
print(f"  开始时间: {exam['start_time']}")
print(f"  结束时间: {exam['end_time']}")
print()

# 如果不是active状态，更新为active
if exam['status'] != 'active':
    print(f"考试状态为 '{exam['status']}'，正在更新为 'active'...")

    # 设置开始时间为1小时前，结束时间为1小时后
    now = datetime.now()
    start_time = now - timedelta(hours=1)
    end_time = now + timedelta(hours=1)

    with data_access.get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE exams SET status = 'active', start_time = %s, end_time = %s WHERE id = %s",
                (start_time, end_time, EXAM_ID)
            )
        conn.commit()

    print(f"✓ 考试已激活")
    print(f"  开始时间: {start_time}")
    print(f"  结束时间: {end_time}")
else:
    print("✓ 考试已是active状态")
