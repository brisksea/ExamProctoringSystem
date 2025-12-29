#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
全局日志配置（供 client/ 下模块导入以初始化日志）

行为：
- 在打包后（frozen）使用 exe 所在目录作为基准路径，否则使用项目根目录
- 在 `logs/` 下创建 `client.log`，使用 RotatingFileHandler 和控制台输出
"""
import os
import sys
import logging
from logging.handlers import RotatingFileHandler

try:
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        # client/ 的上级目录被视为项目根
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    logs_dir = os.path.join(base_dir, 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    log_path = os.path.join(logs_dir, 'client.log')

    handler = RotatingFileHandler(log_path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    # 避免重复添加 handlers（如果被多次导入）
    existing_paths = set()
    for h in root_logger.handlers:
        try:
            if hasattr(h, 'baseFilename'):
                existing_paths.add(getattr(h, 'baseFilename'))
        except Exception:
            continue

    if log_path not in existing_paths:
        root_logger.setLevel(logging.INFO)
        root_logger.addHandler(handler)
        root_logger.addHandler(console_handler)

    logging.info(f"Initialized client logging. Log file: {log_path}")
except Exception as e:
    # 初始化失败时不要中断主程序
    print("Failed to initialize client logging:", e)
