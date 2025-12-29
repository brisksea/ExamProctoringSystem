#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Redis优化方案
针对400个并发客户端的性能优化
"""

import redis
import json
import time
import threading
from datetime import datetime
from redis.connection import ConnectionPool
import psutil

class OptimizedRedisManager:
    def __init__(self):
        # 优化后的Redis配置
        self.redis_config = {
            'host': 'localhost',
            'port': 6379,
            'db': 0,
            'decode_responses': True,
            'max_connections': 100,  # 增加连接池大小
            'socket_timeout': 3,     # 减少超时时间
            'socket_connect_timeout': 3,
            'retry_on_timeout': True,
            'health_check_interval': 30,  # 连接健康检查
        }
        
        # 创建连接池
        self.pool = ConnectionPool(**self.redis_config)
        self.client = redis.Redis(connection_pool=self.pool)
        
        # 性能监控
        self.stats = {
            'operations': 0,
            'errors': 0,
            'start_time': time.time()
        }
    
    def optimize_redis_config(self):
        """优化Redis服务器配置"""
        try:
            # 设置内存策略
            self.client.config_set('maxmemory-policy', 'allkeys-lru')
            
            # 设置最大内存（根据服务器内存调整）
            memory_gb = psutil.virtual_memory().total / (1024**3)
            max_memory = int(memory_gb * 0.7 * 1024 * 1024 * 1024)  # 使用70%内存
            self.client.config_set('maxmemory', max_memory)
            
            # 优化持久化配置
            self.client.config_set('save', '900 1 300 10 60 10000')
            self.client.config_set('appendonly', 'yes')
            self.client.config_set('appendfsync', 'everysec')
            
            # 优化网络配置
            self.client.config_set('tcp-keepalive', '300')
            self.client.config_set('timeout', '0')
            
            print(f"Redis配置优化完成，最大内存: {max_memory / (1024**3):.1f}GB")
            
        except Exception as e:
            print(f"Redis配置优化失败: {str(e)}")
    
    def batch_operations(self, operations):
        """批量操作优化"""
        try:
            with self.client.pipeline() as pipe:
                for op in operations:
                    if op['type'] == 'hset':
                        pipe.hset(op['key'], op['field'], op['value'])
                    elif op['type'] == 'set':
                        pipe.set(op['key'], op['value'])
                    elif op['type'] == 'expire':
                        pipe.expire(op['key'], op['seconds'])
                
                results = pipe.execute()
                self.stats['operations'] += len(operations)
                return results
                
        except Exception as e:
            self.stats['errors'] += 1
            print(f"批量操作失败: {str(e)}")
            return None
    
    def optimized_student_login(self, student_data):
        """优化的学生登录操作"""
        try:
            exam_id = student_data['exam_id']
            student_id = student_data['student_id']
            
            # 使用批量操作
            operations = [
                {
                    'type': 'hset',
                    'key': f'exam:{exam_id}:student:{student_id}',
                    'field': 'last_active',
                    'value': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                },
                {
                    'type': 'hset',
                    'key': f'exam:{exam_id}:student:{student_id}',
                    'field': 'status',
                    'value': 'online'
                },
                {
                    'type': 'expire',
                    'key': f'exam:{exam_id}:student:{student_id}',
                    'seconds': 3600  # 1小时过期
                }
            ]
            
            self.batch_operations(operations)
            return True
            
        except Exception as e:
            self.stats['errors'] += 1
            print(f"学生登录操作失败: {str(e)}")
            return False
    
    def optimized_heartbeat(self, exam_id, student_id):
        """优化的心跳操作"""
        try:
            # 使用更高效的更新方式
            key = f'exam:{exam_id}:student:{student_id}'
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 使用pipeline减少网络往返
            with self.client.pipeline() as pipe:
                pipe.hset(key, 'last_active', timestamp)
                pipe.expire(key, 3600)
                pipe.execute()
            
            self.stats['operations'] += 1
            return True
            
        except Exception as e:
            self.stats['errors'] += 1
            print(f"心跳操作失败: {str(e)}")
            return False
    
    def optimized_screenshot_upload(self, exam_id, student_id, filename):
        """优化的截图上传记录"""
        try:
            # 使用列表存储截图记录，限制数量
            key = f'exam:{exam_id}:student:{student_id}:screenshots'
            
            with self.client.pipeline() as pipe:
                # 添加新截图
                pipe.lpush(key, filename)
                # 限制列表长度，只保留最近100张
                pipe.ltrim(key, 0, 99)
                # 设置过期时间
                pipe.expire(key, 86400)  # 24小时
                pipe.execute()
            
            self.stats['operations'] += 1
            return True
            
        except Exception as e:
            self.stats['errors'] += 1
            print(f"截图上传记录失败: {str(e)}")
            return False
    
    def get_performance_stats(self):
        """获取性能统计"""
        uptime = time.time() - self.stats['start_time']
        ops_per_sec = self.stats['operations'] / uptime if uptime > 0 else 0
        error_rate = self.stats['errors'] / self.stats['operations'] if self.stats['operations'] > 0 else 0
        
        return {
            'total_operations': self.stats['operations'],
            'total_errors': self.stats['errors'],
            'operations_per_second': ops_per_sec,
            'error_rate': error_rate,
            'uptime_seconds': uptime
        }
    
    def cleanup_old_data(self):
        """清理过期数据"""
        try:
            # 清理过期的学生状态
            pattern = 'exam:*:student:*'
            keys = self.client.keys(pattern)
            
            current_time = datetime.now()
            expired_keys = []
            
            for key in keys:
                last_active = self.client.hget(key, 'last_active')
                if last_active:
                    try:
                        last_active_time = datetime.strptime(last_active, '%Y-%m-%d %H:%M:%S')
                        if (current_time - last_active_time).total_seconds() > 7200:  # 2小时
                            expired_keys.append(key)
                    except:
                        pass
            
            if expired_keys:
                self.client.delete(*expired_keys)
                print(f"清理了 {len(expired_keys)} 个过期键")
                
        except Exception as e:
            print(f"清理过期数据失败: {str(e)}")

def performance_test():
    """性能测试"""
    print("开始Redis性能测试...")
    
    manager = OptimizedRedisManager()
    manager.optimize_redis_config()
    
    # 模拟400个客户端并发操作
    def client_simulation(client_id):
        exam_id = 1
        student_id = client_id
        
        for i in range(100):  # 每个客户端100次操作
            # 模拟心跳
            manager.optimized_heartbeat(exam_id, student_id)
            time.sleep(0.1)  # 100ms间隔
    
    # 启动多个线程模拟并发
    threads = []
    start_time = time.time()
    
    for i in range(40):  # 40个线程，每个模拟10个客户端
        thread = threading.Thread(target=client_simulation, args=(i,))
        threads.append(thread)
        thread.start()
    
    # 等待所有线程完成
    for thread in threads:
        thread.join()
    
    end_time = time.time()
    
    # 输出性能统计
    stats = manager.get_performance_stats()
    print(f"\n性能测试结果:")
    print(f"总操作数: {stats['total_operations']}")
    print(f"总错误数: {stats['total_errors']}")
    print(f"操作速率: {stats['operations_per_second']:.2f} ops/sec")
    print(f"错误率: {stats['error_rate']:.4f}")
    print(f"总耗时: {end_time - start_time:.2f} 秒")

if __name__ == '__main__':
    performance_test() 