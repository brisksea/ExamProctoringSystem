#!/usr/bin/env python3
"""检测并清理无效的MySQL数据库连接"""
import pymysql
from datetime import datetime

DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 3306,
    'user': 'debian-sys-maint',
    'password': 'bGEtT3EfFKGLhYRS',
    'database': 'monitoring'
}

def check_and_clean_connections(idle_threshold_seconds=300, dry_run=True):
    """
    检测并清理无效的数据库连接

    Args:
        idle_threshold_seconds: 空闲时间阈值（秒），超过此时间的连接将被标记为无效
        dry_run: True表示仅检测不删除，False表示实际删除
    """
    conn = pymysql.connect(**DB_CONFIG)

    try:
        with conn.cursor() as cursor:
            # 获取当前所有连接
            cursor.execute("""
                SELECT Id, User, Host, db, Command, Time, State, Info
                FROM information_schema.PROCESSLIST
                ORDER BY Time DESC
            """)
            all_connections = cursor.fetchall()

            print(f"\n{'='*80}")
            print(f"数据库连接检测报告 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*80}\n")

            # 统计信息
            total_count = len(all_connections)
            sleep_connections = [c for c in all_connections if c[4] == 'Sleep']
            idle_connections = [c for c in sleep_connections if c[5] > idle_threshold_seconds]

            print(f"总连接数: {total_count}")
            print(f"Sleep状态连接: {len(sleep_connections)}")
            print(f"空闲超过{idle_threshold_seconds}秒的连接: {len(idle_connections)}\n")

            # 获取最大连接数
            cursor.execute("SHOW VARIABLES LIKE 'max_connections'")
            max_conn = int(cursor.fetchone()[1])
            usage_percent = (total_count / max_conn) * 100
            print(f"最大连接数: {max_conn}")
            print(f"连接使用率: {usage_percent:.1f}%\n")

            if idle_connections:
                print(f"{'ID':<10} {'用户':<20} {'主机':<30} {'数据库':<15} {'空闲时间(秒)':<15} {'状态'}")
                print("-" * 110)

                kill_ids = []
                for conn_info in idle_connections:
                    conn_id, user, host, db, command, time, state, info = conn_info
                    # 跳过系统进程和当前连接
                    if user == 'system user' or user == DB_CONFIG['user']:
                        continue

                    print(f"{conn_id:<10} {user:<20} {host:<30} {str(db):<15} {time:<15} {state}")
                    kill_ids.append(conn_id)

                print()

                if kill_ids:
                    if dry_run:
                        print(f"⚠️  检测模式：发现 {len(kill_ids)} 个可清理的无效连接")
                        print(f"   使用 --execute 参数执行实际清理操作")
                    else:
                        print(f"🔧 执行模式：正在清理 {len(kill_ids)} 个无效连接...")

                        success_count = 0
                        fail_count = 0

                        for conn_id in kill_ids:
                            try:
                                cursor.execute(f"KILL {conn_id}")
                                success_count += 1
                                print(f"   ✓ 已终止连接 {conn_id}")
                            except Exception as e:
                                fail_count += 1
                                print(f"   ✗ 终止连接 {conn_id} 失败: {e}")

                        print(f"\n✅ 清理完成：成功 {success_count} 个，失败 {fail_count} 个")

                        # 清理后再次检查
                        cursor.execute("SELECT COUNT(*) FROM information_schema.PROCESSLIST")
                        new_count = cursor.fetchone()[0]
                        print(f"   清理前连接数: {total_count}")
                        print(f"   清理后连接数: {new_count}")
                        print(f"   减少: {total_count - new_count} 个连接")
                else:
                    print("✅ 所有空闲连接都是系统连接或当前用户连接，无需清理")
            else:
                print("✅ 没有发现超过阈值的空闲连接\n")

            # 显示连接状态分布
            print(f"\n{'='*80}")
            print("连接状态分布:")
            print(f"{'='*80}")

            status_count = {}
            for conn_info in all_connections:
                status = conn_info[4]  # Command字段
                status_count[status] = status_count.get(status, 0) + 1

            for status, count in sorted(status_count.items(), key=lambda x: x[1], reverse=True):
                print(f"  {status:<20} {count:>5} 个")

            print()

    finally:
        conn.close()

if __name__ == '__main__':
    import sys

    # 解析命令行参数
    dry_run = True
    idle_threshold = 300  # 默认5分钟

    if '--execute' in sys.argv or '-e' in sys.argv:
        dry_run = False

    if '--threshold' in sys.argv or '-t' in sys.argv:
        try:
            idx = sys.argv.index('--threshold') if '--threshold' in sys.argv else sys.argv.index('-t')
            idle_threshold = int(sys.argv[idx + 1])
        except (IndexError, ValueError):
            print("❌ 错误：--threshold 参数需要一个整数值（秒）")
            sys.exit(1)

    if '--help' in sys.argv or '-h' in sys.argv:
        print("数据库连接检测和清理工具")
        print("\n用法:")
        print("  python3 check_db_connections.py [选项]")
        print("\n选项:")
        print("  -h, --help              显示帮助信息")
        print("  -e, --execute           执行实际清理操作（默认仅检测）")
        print("  -t, --threshold <秒>    设置空闲时间阈值（默认300秒）")
        print("\n示例:")
        print("  # 仅检测，不清理（默认）")
        print("  python3 check_db_connections.py")
        print()
        print("  # 检测并清理空闲超过5分钟的连接")
        print("  python3 check_db_connections.py --execute")
        print()
        print("  # 检测并清理空闲超过10分钟的连接")
        print("  python3 check_db_connections.py --execute --threshold 600")
        sys.exit(0)

    check_and_clean_connections(idle_threshold_seconds=idle_threshold, dry_run=dry_run)
