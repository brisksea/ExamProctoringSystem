# Gunicorn 配置文件
import multiprocessing

# 绑定的IP和端口
bind = "0.0.0.0:5000"

# 工作进程数
workers = multiprocessing.cpu_count() * 2 + 1

# 工作模式
worker_class = "sync"

# 超时时间
timeout = 120

# 访问日志格式
accesslog = "logs/gunicorn_access.log"
errorlog = "logs/gunicorn_error.log"

# 进程名称
proc_name = "exam_monitor"

# 后台运行
daemon = False

# 重启时关闭旧进程
preload_app = True

# 工作进程超时时间
graceful_timeout = 120

# 最大客户端并发数量
worker_connections = 1000