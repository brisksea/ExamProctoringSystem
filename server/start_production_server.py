#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
生产环境服务器启动脚本
使用Gunicorn + gevent处理高并发
"""

import os
import sys
import subprocess
import signal
import atexit

def signal_handler(signum, frame):
    """信号处理函数"""
    print(f"\n进程 {os.getpid()}: 接收到信号 {signum}")
    # 清理工作已移至MySQL，无需Redis清理
    sys.exit(0)

def start_production_server():
    """启动生产环境服务器"""
    try:
        # 注册信号处理器
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # MySQL数据库无需特殊持久化配置
        
        # 确保日志目录存在
        os.makedirs("logs", exist_ok=True)
        
        # 启动Gunicorn服务器
        cmd = [
            "gunicorn",
            "--config", "gunicorn_config.py",
            "--worker-class", "gevent",
            "--worker-connections", "2000",
            "--max-requests", "1000",
            "--max-requests-jitter", "100",
            "--preload",
            "server:app"
        ]
        
        print(f"进程 {os.getpid()}: 启动生产环境服务器...")
        print(f"命令: {' '.join(cmd)}")
        
        # 启动服务器
        subprocess.run(cmd)
        
    except KeyboardInterrupt:
        print("\n服务器被用户中断")
    except Exception as e:
        print(f"服务器启动失败: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    start_production_server() 