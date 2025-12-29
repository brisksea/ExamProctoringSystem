# Gunicorn 配置文件 - 优化 500 人并发
import multiprocessing

# 绑定的IP和端口
bind = "0.0.0.0:5000"

# ===== 核心配置 (500人并发优化) =====
# CPU: 32 核，并发目标: 500 人
# 推荐配置（300人）：12 workers
# 高性能配置（500人）：16 workers
workers = 24                    # 24 个 worker 进程（支持480人并发）
# workers = 16                  # 16 个 worker 进程（基础配置）
worker_class = "gevent"        # 异步 IO 模式（必须使用 gevent）
worker_connections = 200       # 每个 worker 支持 200 并发连接
                               # 总并发能力: 24 × 200 = 4,800 连接

# 超时配置（视频上传需要较长时间）
timeout = 600                  # 10 分钟超时（支持300人并发上传大文件）
graceful_timeout = 120         # 优雅关闭超时
keepalive = 5                  # 保持连接（心跳请求复用连接）

# 性能优化
worker_tmp_dir = "/dev/shm"    # 使用内存临时目录（提升性能）
preload_app = False            # 不预加载（避免连接池 fork 问题）

# Worker 进程管理
max_requests = 5000            # 每个 worker 处理 5000 请求后重启（防内存泄漏）
max_requests_jitter = 500      # 随机抖动，避免所有 worker 同时重启

# 日志配置
accesslog = "logs/gunicorn_access.log"
errorlog = "logs/gunicorn_error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# 进程名称
proc_name = "exam_monitor"

# 后台运行
daemon = False

# ==================== 配置说明 ====================
# 当前配置支持:
# - 并发连接: 1,600 (workers × worker_connections)
# - MySQL 连接: 160 (workers × pool_size=20)
# - Redis 连接: ~100
#
# 如需支持更多并发，可以调整:
# 1. 增加 workers 到 12-16
# 2. 增加 worker_connections 到 300
# 3. 相应增加 MySQL max_connections (见 PERFORMANCE_TUNING.md)


