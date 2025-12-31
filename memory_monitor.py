#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
内存监控脚本
监控服务器内存使用情况，防止内存不足导致进程被杀死
"""

import os
import psutil
import time
import logging
import signal
import sys
from datetime import datetime

class MemoryMonitor:
    """内存监控器"""
    
    def __init__(self, threshold_percent=80, check_interval=30):
        """
        初始化内存监控器
        
        Args:
            threshold_percent: 内存使用率阈值（百分比）
            check_interval: 检查间隔（秒）
        """
        self.threshold_percent = threshold_percent
        self.check_interval = check_interval
        self.is_running = False
        
        # 设置日志
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('logs/memory_monitor.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
        # 确保日志目录存在
        if not os.path.exists('logs'):
            os.makedirs('logs')
    
    def get_memory_info(self):
        """获取内存信息"""
        memory = psutil.virtual_memory()
        return {
            'total': memory.total,
            'available': memory.available,
            'used': memory.used,
            'percent': memory.percent,
            'free': memory.free
        }
    
    def get_disk_info(self):
        """获取磁盘信息"""
        disk = psutil.disk_usage('/')
        return {
            'total': disk.total,
            'used': disk.used,
            'free': disk.free,
            'percent': (disk.used / disk.total) * 100
        }
    
    def get_process_info(self):
        """获取进程信息"""
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'memory_percent', 'memory_info']):
            try:
                if proc.info['memory_percent'] > 1.0:  # 只显示内存使用超过1%的进程
                    processes.append({
                        'pid': proc.info['pid'],
                        'name': proc.info['name'],
                        'memory_percent': proc.info['memory_percent'],
                        'memory_mb': proc.info['memory_info'].rss / 1024 / 1024
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # 按内存使用率排序
        processes.sort(key=lambda x: x['memory_percent'], reverse=True)
        return processes[:10]  # 返回前10个最耗内存的进程
    
    def check_memory_usage(self):
        """检查内存使用情况"""
        memory_info = self.get_memory_info()
        disk_info = self.get_disk_info()
        
        # 记录内存使用情况
        self.logger.info(
            f"内存使用: {memory_info['percent']:.1f}% "
            f"({memory_info['used']/1024/1024/1024:.1f}GB / {memory_info['total']/1024/1024/1024:.1f}GB)"
        )
        
        # 记录磁盘使用情况
        self.logger.info(
            f"磁盘使用: {disk_info['percent']:.1f}% "
            f"({disk_info['used']/1024/1024/1024:.1f}GB / {disk_info['total']/1024/1024/1024:.1f}GB)"
        )
        
        # 检查内存使用是否超过阈值
        if memory_info['percent'] > self.threshold_percent:
            self.logger.warning(f"内存使用率过高: {memory_info['percent']:.1f}%")
            
            # 获取高内存使用进程
            top_processes = self.get_process_info()
            self.logger.warning("高内存使用进程:")
            for proc in top_processes:
                self.logger.warning(
                    f"  PID {proc['pid']}: {proc['name']} - "
                    f"{proc['memory_percent']:.1f}% ({proc['memory_mb']:.1f}MB)"
                )
            
            # 建议重启gunicorn worker
            self.logger.warning("建议重启gunicorn worker以释放内存")
        
        # 检查磁盘空间
        if disk_info['percent'] > 90:
            self.logger.error(f"磁盘空间不足: {disk_info['percent']:.1f}%")
            self.logger.error("建议清理临时文件和日志文件")
    
    def start_monitoring(self):
        """开始监控"""
        self.is_running = True
        self.logger.info(f"开始内存监控，阈值: {self.threshold_percent}%，检查间隔: {self.check_interval}秒")
        
        try:
            while self.is_running:
                self.check_memory_usage()
                time.sleep(self.check_interval)
        except KeyboardInterrupt:
            self.logger.info("收到中断信号，停止监控")
        except Exception as e:
            self.logger.error(f"监控过程中发生错误: {e}")
        finally:
            self.is_running = False
    
    def stop_monitoring(self):
        """停止监控"""
        self.is_running = False

def signal_handler(signum, frame):
    """信号处理器"""
    print(f"\n收到信号 {signum}，正在停止监控...")
    sys.exit(0)

def main():
    """主函数"""
    # 设置信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 创建监控器
    monitor = MemoryMonitor(threshold_percent=80, check_interval=30)
    
    # 开始监控
    monitor.start_monitoring()

if __name__ == "__main__":
    main()
