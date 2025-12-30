# Locust 分布式负载测试指南

## 问题说明

**原问题**：分布式部署时，多个 Worker 会产生相同的学生ID，导致：
- 同一个学生ID被多个虚拟用户使用
- 视频序号混乱（有的有 seq_0001，有的没有）
- 无法准确模拟 500 个独立学生

**解决方案**：使用环境变量 `WORKER_OFFSET` 为每个 Worker 分配不同的学生ID范围。

---

## 单机测试（无需修改）

```bash
# Master + Worker 在同一台机器
locust -f load_test_realistic.py --master --web-host=0.0.0.0
```

默认 `WORKER_OFFSET=0`，学生ID范围：`test_00001` - `test_00500`

---

## 分布式测试（3台服务器）

### 架构

```
Server1 (Master)
  ├─ Server1 Worker (WORKER_OFFSET=0)   → test_00001 - test_00166
  ├─ Server2 Worker (WORKER_OFFSET=166) → test_00167 - test_00333
  └─ Server3 Worker (WORKER_OFFSET=333) → test_00334 - test_00500
```

### 部署步骤

#### Server1 (192.168.1.100) - Master + Worker

```bash
# 启动 Master
locust -f load_test_realistic.py --master --web-host=0.0.0.0 --web-port=8089

# 启动 Worker (学生ID: 1-166)
WORKER_OFFSET=0 locust -f load_test_realistic.py --worker --master-host=192.168.1.100
```

#### Server2 (192.168.1.101) - Worker

```bash
# 启动 Worker (学生ID: 167-333)
WORKER_OFFSET=166 locust -f load_test_realistic.py --worker --master-host=192.168.1.100
```

#### Server3 (192.168.1.102) - Worker

```bash
# 启动 Worker (学生ID: 334-500)
WORKER_OFFSET=333 locust -f load_test_realistic.py --worker --master-host=192.168.1.100
```

---

## 配置说明

### 学生ID分配规则

| Worker | WORKER_OFFSET | 学生ID范围 | 数量 |
|--------|--------------|------------|------|
| Worker1 | 0   | test_00001 - test_00166 | 166 |
| Worker2 | 166 | test_00167 - test_00333 | 167 |
| Worker3 | 333 | test_00334 - test_00500 | 167 |

**公式**：
```python
student_id = WORKER_OFFSET + local_counter
```

### 调整 Worker 数量

**2 个 Worker（每个负责 250 人）**：
- Worker1: `WORKER_OFFSET=0`   (1-250)
- Worker2: `WORKER_OFFSET=250` (251-500)

**5 个 Worker（每个负责 100 人）**：
- Worker1: `WORKER_OFFSET=0`   (1-100)
- Worker2: `WORKER_OFFSET=100` (101-200)
- Worker3: `WORKER_OFFSET=200` (201-300)
- Worker4: `WORKER_OFFSET=300` (301-400)
- Worker5: `WORKER_OFFSET=400` (401-500)

---

## 验证测试

### 1. 检查学生ID唯一性

```bash
# 查看服务器日志，确认学生ID无重复
tail -f /home/zq/project/supervise/logs/gunicorn_access.log | grep "登录成功"
```

### 2. 检查视频序号连续性

启动测试后，检查某个学生的视频文件：

```bash
ls -lh /home/zq/project/supervise/server_data/30/recordings/test_00100/
```

期望输出（序号连续）：
```
test_00100_20251123_180000_seq_0001.mp4
test_00100_20251123_180030_seq_0002.mp4
test_00100_20251123_180100_seq_0003.mp4
```

### 3. 通过 Web UI 监控

访问 Master 的 Web UI：`http://192.168.1.100:8089`
- 查看总用户数是否达到 500
- 查看 RPS（每秒请求数）
- 查看失败率

---

## 常见问题

### Q1: Worker 无法连接到 Master

**解决方案**：
1. 检查 Master 是否启动：`ps aux | grep locust`
2. 检查防火墙：`sudo ufw allow 5557` (Locust 默认端口)
3. 检查 `--master-host` IP 是否正确

### Q2: 学生ID仍然重复

**原因**：忘记设置 `WORKER_OFFSET` 环境变量

**检查**：
```bash
# 在 Worker 启动前确认环境变量
echo $WORKER_OFFSET
```

### Q3: 视频序号不连续

**原因**：
- 上传失败（网络问题）
- 客户端中途退出

**检查日志**：
```bash
tail -f /home/zq/project/supervise/logs/celery_worker_merge.log | grep "序号缺失"
```

---

## 性能建议

### 单 Worker 推荐并发数

- **测试目标**：500 人
- **Worker 数量**：3-5 个
- **每个 Worker 并发**：100-166 人
- **机器配置**：4 核 8GB RAM（每个 Worker）

### 网络带宽计算

- 每个学生上传视频：15-20 MB / 120 秒 ≈ 125-167 KB/s
- 500 人总带宽：500 × 150 KB/s ≈ **75 MB/s (600 Mbps)**

---

## 示例：启动 3 Worker 测试

```bash
# Server1 (Master + Worker1)
# Terminal 1
locust -f load_test_realistic.py --master --web-host=0.0.0.0

# Terminal 2
WORKER_OFFSET=0 locust -f load_test_realistic.py --worker --master-host=localhost

# Server2 (Worker2)
WORKER_OFFSET=166 locust -f load_test_realistic.py --worker --master-host=192.168.1.100

# Server3 (Worker3)
WORKER_OFFSET=333 locust -f load_test_realistic.py --worker --master-host=192.168.1.100
```

访问 Web UI: http://192.168.1.100:8089
- 设置用户数：500
- 设置生成速率：10 users/s
- 点击 "Start swarming"

---

## 监控命令

```bash
# 查看 Celery 状态检测日志
tail -f /home/zq/project/supervise/logs/celery_worker_status.log

# 查看视频合并日志
tail -f /home/zq/project/supervise/logs/celery_worker_merge.log

# 查看 Gunicorn 访问日志
tail -f /home/zq/project/supervise/logs/gunicorn_access.log

# 查看系统资源使用
htop
```
