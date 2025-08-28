# Gunicorn 配置文件
import multiprocessing

# 绑定的IP和端口
bind = "0.0.0.0:5000"

# 工作进程数 - 根据CPU核心数优化
workers = min(multiprocessing.cpu_count() + 1, 4)  # 限制最大4个进程

# 工作模式 - 使用异步工作模式提高并发性能
worker_class = "gevent"

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
preload_app = False

# 工作进程超时时间
graceful_timeout = 120

# 最大客户端并发数量 - 每个worker支持更多连接
worker_connections = 1000

# 添加gevent配置
worker_tmp_dir = "/dev/shm"  # 使用内存临时目录
keepalive = 2
