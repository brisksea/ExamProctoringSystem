# 500 人并发场景配置指南

## 服务器硬件信息
- **CPU 核心数**: 32 核

## 负载分析

### 1. 请求类型和频率

**稳态负载** (考试进行中):
- **心跳请求**: 500 人 × 1次/30秒 = **16.7 QPS**
- **视频上传**: 500 人 × 1次/120秒 = **4.2 QPS** (但每次耗时长，15-20MB)
- **状态查询**: 偶尔发生，可忽略
- **总稳态 QPS**: ~20-25 QPS

**峰值负载** (登录/退出时):
- **登录峰值**: 500 人在 1-2 分钟内登录 = **100-250 QPS**
- **退出峰值**: 500 人同时退出 = **200-500 QPS** (短时间)

### 2. 并发连接数

- **长连接**: 500 个学生保持心跳连接
- **上传连接**: ~4-10 个并发上传（每次上传耗时 5-30 秒）
- **总并发连接**: ~500-600

---

## 推荐配置

### 1. Gunicorn Worker 配置

#### 方案 A: 保守配置（推荐）
```python
workers = 8              # 8 个 worker 进程
worker_class = "gevent"  # 使用 gevent 异步模式
worker_connections = 200 # 每个 worker 支持 200 并发连接
```

**总并发能力**: 8 × 200 = **1600 并发连接**

**适用场景**:
- ✅ 500 人并发绰绰有余
- ✅ 留有 3 倍余量应对峰值

#### 方案 B: 激进配置（高性能）
```python
workers = 12             # 12 个 worker 进程
worker_class = "gevent"
worker_connections = 300
```

**总并发能力**: 12 × 300 = **3600 并发连接**

**适用场景**:
- ✅ 支持 1000+ 人并发
- ✅ 视频上传密集时性能更好

---

### 2. MySQL 连接池配置

#### 计算公式
```
总 MySQL 连接数 = (Gunicorn Workers × 每个 Worker 的 pool_size) + (Celery Workers × 每个 Worker 的连接数)
```

#### 方案 A: 8 个 Gunicorn Worker
```python
# data_access.py
pool_size = 20  # 每个 Gunicorn Worker 的连接池大小

# 总连接数计算：
# - Gunicorn: 8 workers × 20 = 160 连接
# - Celery: 3 workers × 5 = 15 连接
# - 总计: 175 连接
```

**MySQL 配置要求**:
```sql
SET GLOBAL max_connections = 250;  -- 至少 250，建议 300
```

#### 方案 B: 12 个 Gunicorn Worker
```python
pool_size = 15  # 每个 Worker 减少连接池

# 总连接数：
# - Gunicorn: 12 × 15 = 180
# - Celery: 3 × 5 = 15
# - 总计: 195 连接
```

**MySQL 配置要求**:
```sql
SET GLOBAL max_connections = 300;
```

---

### 3. Redis 连接池配置

```python
# redis_helper.py
max_connections = 150  # 增加到 150

# 连接分配：
# - Gunicorn Workers: ~100 连接
# - Celery Workers: ~20 连接
# - 数据库实时状态查询: ~30 连接
```

---

## 具体配置文件

### gunicorn_config.py (推荐方案 A)

```python
import multiprocessing

# 绑定的IP和端口
bind = "0.0.0.0:5001"

# ===== 核心配置 (500人并发优化) =====
workers = 8                    # 8 个 worker 进程
worker_class = "gevent"        # 异步 IO 模式
worker_connections = 200       # 每个 worker 200 并发

# 超时配置
timeout = 300                  # 5 分钟（视频上传需要时间）
graceful_timeout = 120
keepalive = 5                  # 心跳保持连接

# 性能优化
worker_tmp_dir = "/dev/shm"    # 使用内存临时目录（提升性能）
preload_app = False            # 不预加载（避免连接池 fork 问题）

# 日志
accesslog = "logs/gunicorn_access.log"
errorlog = "logs/gunicorn_error.log"
loglevel = "info"

# 进程管理
proc_name = "exam_monitor"
max_requests = 5000            # 每个 worker 处理 5000 请求后重启（防内存泄漏）
max_requests_jitter = 500      # 随机抖动避免同时重启
```

### data_access.py

```python
self.pool_config = {
    'pool_name': f'exam_monitor_pool_{os.getpid()}',
    'pool_size': 20,           # ⬆️ 从 10 增加到 20
    'pool_reset_session': True,
    'host': mysql_conf.get('host', 'localhost'),
    'port': mysql_conf.get('port', 3306),
    'user': mysql_conf.get('user', 'exam_system'),
    'password': mysql_conf.get('password', 'exam2024'),
    'database': mysql_conf.get('database', 'monitoring'),
    'autocommit': True,
    'charset': 'utf8mb4',
    'use_unicode': True,
    'connection_timeout': 10,
    'sql_mode': 'TRADITIONAL',
}
```

### redis_helper.py

```python
REDIS_CONFIG = {
    'host': 'localhost',
    'port': 6379,
    'db': 0,
    'decode_responses': True,
    'max_connections': 150,    # ⬆️ 从 50 增加到 150
    'socket_timeout': 5,
    'socket_connect_timeout': 5,
    'retry_on_timeout': True,
}
```

---

## MySQL 服务器配置

### 1. 检查当前 max_connections

```bash
mysql -u root -p -e "SHOW VARIABLES LIKE 'max_connections';"
```

### 2. 永久修改 max_connections

编辑 `/etc/mysql/mysql.conf.d/mysqld.cnf`:

```ini
[mysqld]
max_connections = 300
```

重启 MySQL:
```bash
sudo systemctl restart mysql
```

### 3. 临时修改（重启后失效）

```sql
SET GLOBAL max_connections = 300;
```

---

## 配置对比表

| 配置项 | 当前配置 | 推荐配置 (方案A) | 推荐配置 (方案B) |
|--------|----------|------------------|------------------|
| **Gunicorn Workers** | 4 | 8 | 12 |
| **Worker Connections** | 100 | 200 | 300 |
| **总并发能力** | 400 | 1,600 | 3,600 |
| **MySQL pool_size/worker** | 10 | 20 | 15 |
| **总 MySQL 连接** | 40 | 175 | 195 |
| **MySQL max_connections** | 151 (默认) | 250+ | 300+ |
| **Redis max_connections** | 50 | 150 | 200 |

---

## 性能测试验证

### 1. 启动优化后的服务

```bash
# 停止旧服务
pkill -f gunicorn

# 启动新配置
gunicorn -c gunicorn_config.py server:app
```

### 2. 运行负载测试

```bash
# 测试 500 用户
bash distributed_test_master.sh
```

### 3. 监控指标

**数据库连接数**:
```bash
watch -n 1 'mysql -u root -p -e "SHOW STATUS LIKE \"Threads_connected\";"'
```

**Gunicorn 进程状态**:
```bash
ps aux | grep gunicorn
```

**系统资源**:
```bash
htop
```

---

## 故障排查

### 问题 1: MySQL 连接数不足

**现象**: `Too many connections`

**解决**:
```sql
-- 临时解决
SET GLOBAL max_connections = 300;

-- 永久解决（修改配置文件后重启）
sudo vim /etc/mysql/mysql.conf.d/mysqld.cnf
# 添加: max_connections = 300
sudo systemctl restart mysql
```

### 问题 2: Worker 超时

**现象**: `Worker timeout`

**解决**:
```python
# gunicorn_config.py
timeout = 300  # 增加超时时间
```

### 问题 3: 内存不足

**现象**: `Cannot allocate memory`

**解决**:
1. 减少 workers 数量
2. 减少 worker_connections
3. 减少 MySQL pool_size

---

## 总结

### 推荐配置（500 人并发）

| 组件 | 配置 |
|------|------|
| **Gunicorn Workers** | 8 |
| **Worker Connections** | 200 |
| **MySQL Pool Size** | 20/worker |
| **MySQL max_connections** | 300 |
| **Redis max_connections** | 150 |

**理由**:
- ✅ 支持 1,600 并发连接（500 人 × 3 倍余量）
- ✅ MySQL 连接总数 175（在 300 限制内）
- ✅ CPU 利用率合理（8 workers on 32 cores = 25%）
- ✅ 内存占用可控（每个 worker ~200MB，总计 ~2GB）
