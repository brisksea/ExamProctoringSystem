# Celery 后台任务系统使用说明

## 架构概述

本系统使用 **Celery + Redis** 实现后台任务处理，完全替代了原来的 `StatusChecker` 和 `MergeManager`。

```
┌─────────────────────────────────────────────┐
│     Gunicorn/Flask (Web 服务)                │
│  - 接收 HTTP 请求                            │
│  - 提交任务到 Celery                         │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│          Redis (消息队列 + 结果存储)          │
│  Queue 1: status_check (状态检测)            │
│  Queue 2: video_merge  (视频合并)            │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│          Celery Workers (任务执行器)         │
│  Worker 1: 处理状态检测任务                  │
│  Worker 2-3: 处理视频合并任务 (CPU密集)      │
└─────────────────────────────────────────────┘
                    ↑
┌─────────────────────────────────────────────┐
│       Celery Beat (定时任务调度器)           │
│  每30秒触发: status_check_task               │
└─────────────────────────────────────────────┘
```

## 任务类型

### 1. 状态检测任务 (status_check_task)
- **触发方式**: Celery Beat 定时触发（每30秒）
- **队列**: `status_check`
- **功能**:
  - 检查考试状态（pending/active/completed）
  - 检测学生掉线（超过60秒无心跳）
  - 更新数据库和 Redis
- **原代码**: `status_checker.py` (已废弃)

### 2. 视频合并任务 (merge_videos_task)
- **触发方式**: 学生考试结束时由 server.py 提交
- **队列**: `video_merge`
- **功能**:
  - 使用 FFmpeg 合并录屏片段
  - 支持序号排序（优先）和时间戳排序
  - 自动重试（最多3次）
  - 合并成功后删除片段
- **原代码**: `merge_manager.py` (已废弃)

## 安装依赖

### 1. 安装 Redis

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install redis-server
sudo systemctl start redis
sudo systemctl enable redis
```

**CentOS/RHEL:**
```bash
sudo yum install redis
sudo systemctl start redis
sudo systemctl enable redis
```

**验证 Redis:**
```bash
redis-cli ping
# 应该返回: PONG
```

### 2. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

核心依赖：
- `celery>=5.2.0` - 任务队列框架
- `redis>=4.3.0` - Redis 客户端

## 启动服务

### 方式1: 一键启动（推荐）

```bash
bash start_all_celery.sh
```

这会依次启动：
1. Celery Beat (定时任务调度器)
2. Celery Worker (状态检测队列)
3. Celery Worker (视频合并队列)

### 方式2: 分别启动

```bash
# 1. 启动定时任务调度器
bash start_celery_beat.sh

# 2. 启动状态检测 Worker
bash start_celery_status_worker.sh

# 3. 启动视频合并 Worker
bash start_celery_worker.sh
```

## 停止服务

```bash
bash stop_celery.sh
```

## 查看运行状态

### 1. 查看进程

```bash
ps aux | grep celery
```

### 2. 查看日志

```bash
# 定时任务调度器日志
tail -f logs/celery_beat.log

# 状态检测 Worker 日志
tail -f logs/celery_worker_status.log

# 视频合并 Worker 日志
tail -f logs/celery_worker_merge.log
```

### 3. 监控 Redis 队列

```bash
# 连接 Redis
redis-cli

# 查看队列长度
LLEN status_check
LLEN video_merge

# 查看队列内容（不删除）
LRANGE status_check 0 -1
LRANGE video_merge 0 -1
```

## 完整部署流程

### 1. 启动 Redis

```bash
sudo systemctl start redis
```

### 2. 启动 Celery 服务

```bash
bash start_all_celery.sh
```

### 3. 启动 Web 服务

**开发环境:**
```bash
python server.py
```

**生产环境 (Gunicorn):**
```bash
gunicorn -c gunicorn_config.py server:app
```

### 4. 验证系统

```bash
# 检查 Celery 进程
ps aux | grep celery

# 检查日志
tail -f logs/celery_beat.log
tail -f logs/celery_worker_status.log
tail -f logs/celery_worker_merge.log

# 检查 Redis 连接
redis-cli ping
```

## 配置说明

### celery_config.py

主要配置项：
```python
# Redis 连接
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_DB = 0

# 任务超时
task_time_limit = 1800  # 30分钟硬超时
task_soft_time_limit = 1500  # 25分钟软超时

# 定时任务
beat_schedule = {
    'status-check-every-30-seconds': {
        'task': 'celery_tasks.status_check_task',
        'schedule': 30.0,  # 每30秒
    },
}
```

### Worker 并发配置

**状态检测 Worker:**
- 并发数: 1 (不需要并发)
- 队列: `status_check`

**视频合并 Worker:**
- 并发数: 2 (CPU密集型)
- 队列: `video_merge`

## 故障排查

### 1. Celery Beat 没有触发任务

**检查:**
```bash
# 查看 Beat 日志
tail -f logs/celery_beat.log

# 确认 Beat 进程在运行
ps aux | grep "celery.*beat"
```

**解决:**
```bash
# 重启 Celery Beat
bash stop_celery.sh
bash start_celery_beat.sh
```

### 2. Worker 没有处理任务

**检查:**
```bash
# 查看 Worker 日志
tail -f logs/celery_worker_merge.log

# 检查队列是否有积压
redis-cli
LLEN video_merge
```

**解决:**
```bash
# 重启 Worker
bash stop_celery.sh
bash start_celery_worker.sh
```

### 3. Redis 连接失败

**检查:**
```bash
# Redis 是否运行
sudo systemctl status redis

# 测试连接
redis-cli ping
```

**解决:**
```bash
# 启动 Redis
sudo systemctl start redis
```

### 4. 视频合并失败

**检查:**
```bash
# 查看 FFmpeg 是否安装
ffmpeg -version

# 查看合并 Worker 日志
tail -f logs/celery_worker_merge.log
```

**解决:**
```bash
# 安装 FFmpeg
sudo apt install ffmpeg  # Ubuntu/Debian
sudo yum install ffmpeg  # CentOS/RHEL
```

## 性能优化

### 1. 增加视频合并并发数

编辑 `start_celery_worker.sh`:
```bash
--concurrency=4  # 增加到4个并发
```

### 2. 使用多个 Worker 节点

在多台机器上运行 Worker:
```bash
# 机器A
bash start_celery_worker.sh

# 机器B
bash start_celery_worker.sh
```

### 3. 调整任务超时时间

编辑 `celery_config.py`:
```python
task_time_limit = 3600  # 增加到60分钟
```

## 监控 (可选)

### 使用 Flower 监控 Celery

安装:
```bash
pip install flower
```

启动:
```bash
celery -A celery_config.celery_app flower --port=5555
```

访问: http://localhost:5555

## 与旧系统对比

| 功能 | 旧系统 | 新系统 (Celery) |
|------|--------|----------------|
| 状态检测 | `status_checker.py` (独立进程) | Celery Beat + Worker |
| 视频合并 | `merge_manager.py` (线程) | Celery Worker |
| 任务持久化 | ❌ 内存队列，重启丢失 | ✅ Redis 持久化 |
| 任务重试 | ❌ 不支持 | ✅ 自动重试3次 |
| 水平扩展 | ❌ 单进程 | ✅ 多 Worker |
| 监控 | ❌ 无 | ✅ Flower |
| 任务优先级 | ❌ 无 | ✅ 支持队列优先级 |

## 迁移说明

### 已废弃文件

以下文件已被 Celery 替代，可以删除（但建议保留备份）:
- `status_checker.py` → `celery_tasks.status_check_task`
- `merge_manager.py` → `celery_tasks.merge_videos_task`

### gunicorn_config.py 变更

已移除 `post_fork` 和 `worker_exit` 钩子，MergeManager 不再需要在每个 worker 中启动。

### server.py 变更

- 移除 `from merge_manager import MergeManager`
- 移除 `app.merge_manager = MergeManager()`
- 修改 `current_app.merge_manager.add_merge_task(...)` 为 `merge_videos_task.delay(...)`

## 常见问题

### Q: 为什么状态检测也要用 Celery？
A: 虽然 `status_checker.py` 作为独立进程也能工作，但使用 Celery 有以下优势：
- 统一管理所有后台任务
- Celery Beat 提供更可靠的定时调度
- 便于监控和日志管理

### Q: 可以只用 Celery 处理视频合并，保留 status_checker.py 吗？
A: 可以。只需：
1. 不启动 `start_celery_beat.sh` 和 `start_celery_status_worker.sh`
2. 继续运行 `python status_checker.py`
3. 只启动 `start_celery_worker.sh` (视频合并)

### Q: Redis 崩溃会影响系统吗？
A: 会。Redis 崩溃会导致：
- 任务无法提交（视频合并）
- 定时任务无法执行（状态检测）
- 建议配置 Redis 持久化和主从复制

## 总结

采用 Celery + Redis 方案后：
- ✅ 任务持久化，不怕进程崩溃
- ✅ 支持任务重试和超时控制
- ✅ 可水平扩展（多 Worker）
- ✅ 统一监控和日志管理
- ✅ 业界标准方案，易于维护
