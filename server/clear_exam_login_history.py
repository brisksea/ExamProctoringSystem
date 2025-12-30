#!/usr/bin/env python3
"""
删除指定考试的所有登录历史记录
用法: python3 clear_exam_login_history.py <exam_id>
"""
import sys
import pymysql

def clear_login_history(exam_id):
    """删除指定考试的所有登录历史记录"""
    conn = pymysql.connect(
        host='10.188.2.252',
        port=3306,
        user='debian-sys-maint',
        password='bGEtT3EfFKGLhYRS',
        database='monitoring',
        cursorclass=pymysql.cursors.DictCursor
    )

    try:
        with conn.cursor() as cursor:
            # 先查询要删除的记录数
            count_sql = """
            SELECT COUNT(*) as total
            FROM student_login_history lh
            JOIN exam_students es ON lh.student_exam_id = es.id
            WHERE es.exam_id = %s
            """
            cursor.execute(count_sql, (exam_id,))
            result = cursor.fetchone()
            total_records = result['total']

            if total_records == 0:
                print(f"考试 {exam_id} 没有登录历史记录")
                return

            print(f"发现 {total_records} 条登录历史记录")

            # 询问用户确认
            confirm = input(f"确认删除考试 {exam_id} 的所有 {total_records} 条登录历史记录？(yes/no): ")
            if confirm.lower() != 'yes':
                print("已取消删除操作")
                return

            # 执行删除
            delete_sql = """
            DELETE lh FROM student_login_history lh
            JOIN exam_students es ON lh.student_exam_id = es.id
            WHERE es.exam_id = %s
            """
            cursor.execute(delete_sql, (exam_id,))
            conn.commit()

            deleted_count = cursor.rowcount
            print(f"✓ 成功删除 {deleted_count} 条登录历史记录")

    except Exception as e:
        print(f"✗ 删除失败: {e}")
        conn.rollback()
    finally:
        conn.close()


def main():
    if len(sys.argv) < 2:
        print("用法: python3 clear_exam_login_history.py <exam_id>")
        print("示例: python3 clear_exam_login_history.py 34")
        sys.exit(1)

    try:
        exam_id = int(sys.argv[1])
    except ValueError:
        print("错误: exam_id 必须是数字")
        sys.exit(1)

    print(f"准备清理考试 {exam_id} 的登录历史记录...")
    clear_login_history(exam_id)


if __name__ == "__main__":
    main()
