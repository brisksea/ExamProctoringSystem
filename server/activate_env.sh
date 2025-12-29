#!/bin/bash
echo "正在激活考试监控系统环境..."
source "venv/bin/activate"
echo "环境已激活，可以运行考试监控系统"
exec $SHELL