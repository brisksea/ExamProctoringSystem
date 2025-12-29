import multiprocessing

bind = "0.0.0.0:5000"
workers = min(multiprocessing.cpu_count() + 1, 32)                    # 4个进程
worker_class = "gevent"        # 异步模式
worker_connections = 1000      # 每个worker支持1000连接
preload_app = False           # 避免fork问题
max_requests = 1000           # 请求后重启worker
max_requests_jitter = 100     # 随机抖动
timeout = 120
keepalive = 2
