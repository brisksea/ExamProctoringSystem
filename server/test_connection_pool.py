#!/usr/bin/env python3
"""
测试数据库连接池的脚本
用于诊断连接池问题
"""

import sys
import os
import time
import threading
from datetime import datetime

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data_access import DataAccess

def test_connection_pool():
    """测试连接池基本功能"""
    print("=== 数据库连接池测试 ===")
    
    try:
        # 创建DataAccess实例
        da = DataAccess()
        print("✓ DataAccess实例创建成功")
        
        # 获取连接池状态
        pool_status = da.get_pool_status()
        print(f"✓ 连接池状态: {pool_status}")
        
        # 测试基本查询
        with da.with_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT 1 as test")
                result = cursor.fetchone()
                print(f"✓ 基本查询测试成功: {result}")
        
        # 测试获取考试列表
        exams = da.get_all_exams()
        print(f"✓ 获取考试列表成功，共 {len(exams)} 个考试")
        
        return True
        
    except Exception as e:
        print(f"✗ 连接池测试失败: {e}")
        return False

def test_concurrent_connections():
    """测试并发连接"""
    print("\n=== 并发连接测试 ===")
    
    da = DataAccess()
    results = []
    errors = []
    
    def worker(worker_id):
        try:
            with da.with_connection() as conn:
                with conn.cursor(dictionary=True) as cursor:
                    cursor.execute("SELECT %s as worker_id, NOW() as timestamp", (worker_id,))
                    result = cursor.fetchone()
                    results.append(result)
                    print(f"✓ Worker {worker_id} 连接成功")
        except Exception as e:
            errors.append(f"Worker {worker_id}: {e}")
            print(f"✗ Worker {worker_id} 连接失败: {e}")
    
    # 创建10个并发线程
    threads = []
    for i in range(10):
        thread = threading.Thread(target=worker, args=(i,))
        threads.append(thread)
        thread.start()
    
    # 等待所有线程完成
    for thread in threads:
        thread.join()
    
    print(f"✓ 并发测试完成: 成功 {len(results)}, 失败 {len(errors)}")
    if errors:
        print("错误详情:")
        for error in errors:
            print(f"  - {error}")
    
    return len(errors) == 0

def test_connection_pool_exhaustion():
    """测试连接池耗尽情况"""
    print("\n=== 连接池耗尽测试 ===")
    
    da = DataAccess()
    pool_status = da.get_pool_status()
    pool_size = pool_status.get('pool_size', 15)
    
    print(f"连接池大小: {pool_size}")
    
    # 尝试获取超过池大小的连接
    connections = []
    try:
        for i in range(pool_size + 5):
            try:
                conn = da.get_connection()
                connections.append(conn)
                print(f"✓ 获取连接 {i+1} 成功")
            except Exception as e:
                print(f"✗ 获取连接 {i+1} 失败: {e}")
                break
        
        print(f"成功获取 {len(connections)} 个连接")
        
    finally:
        # 关闭所有连接
        for conn in connections:
            try:
                conn.close()
            except:
                pass
        print("✓ 所有连接已关闭")

def main():
    """主测试函数"""
    print(f"测试开始时间: {datetime.now()}")
    
    # 基本功能测试
    if not test_connection_pool():
        print("基本功能测试失败，退出")
        return
    
    # 并发连接测试
    if not test_concurrent_connections():
        print("并发连接测试失败")
    
    # 连接池耗尽测试
    test_connection_pool_exhaustion()
    
    print(f"\n测试完成时间: {datetime.now()}")

if __name__ == '__main__':
    main()
