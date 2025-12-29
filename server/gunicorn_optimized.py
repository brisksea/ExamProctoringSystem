import multiprocessing
import os

bind = "0.0.0.0:5000" # 绑定的IP和端口
workers = min(multiprocessing.cpu_count(), 2) # 减少worker数量，避免内存不足
worker_class = "gevent"        # 异步模式
worker_connections = 500       # 减少连接数，降低内存使用
preload_app = False           # 避免fork问题
max_requests = 500            # 减少请求数，更频繁重启worker
max_requests_jitter = 50      # 随机抖动
timeout = 600                 # 增加超时时间到10分钟，处理大文件上传
graceful_timeout = 600        # 优雅关闭超时时间
keepalive = 2
accesslog = "logs/gunicorn_access.log" # 访问日志格式
errorlog = "logs/gunicorn_error.log"   # 访问日志格式

# 内存优化配置
max_requests_jitter = 50      # 随机抖动
worker_tmp_dir = "/tmp"       # 使用普通临时目录，避免内存不足
limit_request_line = 4096     # 限制请求行长度
limit_request_fields = 100    # 限制请求字段数
limit_request_field_size = 8190  # 限制字段大小

# 内存监控
def worker_int(worker):
    """Worker进程中断时的处理"""
    worker.log.info("worker received INT or QUIT signal")
    
def pre_fork(server, worker):
    """Fork前的处理"""
    server.log.info("Worker spawned (pid: %s)", worker.pid)
    
def post_fork(server, worker):
    """Fork后的处理"""
    server.log.info("Worker spawned (pid: %s)", worker.pid)
    
def worker_abort(worker):
    """Worker异常退出时的处理"""
    worker.log.info("Worker aborted (pid: %s)", worker.pid)
