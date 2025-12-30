# 分布式500用户并发测试指南

## 为什么需要分布式测试？

单台机器模拟500个并发客户端上传大文件的限制：

### 带宽瓶颈
```
计算: 500用户 × 17.5MB/文件 / 30秒间隔 = 291MB/s ≈ 2.3Gbps
问题: 单台机器通常只有1Gbps网卡
```

### 其他限制
- **CPU/内存**: Locust需要为每个用户维护状态
- **文件描述符**: 500个并发连接需要大量FD
- **端口数**: 客户端端口范围有限
- **操作系统限制**: 单进程的并发限制

## 解决方案: Locust分布式模式

使用**Master-Worker架构**:
- **1个Master节点**: 协调测试，收集统计，提供Web界面
- **多个Worker节点**: 实际执行测试，发送请求

### 推荐配置

| 总用户数 | Worker数量 | 每个Worker负载 | 总带宽需求 |
|---------|-----------|---------------|-----------|
| 500     | 3-4       | 125-167用户   | ~2.3Gbps  |
| 1000    | 6-8       | 125-167用户   | ~4.6Gbps  |

**原则**: 每个Worker不超过200个并发用户

## 快速部署指南

### 方案A: 自动部署 (推荐)

#### 1. 准备机器

准备3-4台Linux机器:

```
机器1 (Master): 172.16.229.162
机器2 (Worker): 10.188.2.252
机器3 (Worker): 10.188.2.253
机器4 (Worker): 10.188.2.254
```

#### 2. 配置SSH免密登录

在Master机器上:

```bash
# 生成SSH密钥 (如果没有)
ssh-keygen -t rsa -b 4096 -N "" -f ~/.ssh/id_rsa

# 复制公钥到所有Worker
ssh-copy-id zq@10.188.2.252
ssh-copy-id zq@10.188.2.253
ssh-copy-id zq@10.188.2.254

# 测试连接
ssh zq@10.188.2.252 "hostname"
```

#### 3. 修改Worker列表

编辑 `deploy_workers.sh`:

```bash
WORKER_HOSTS=(
    "10.188.2.252"
    "10.188.2.253"
    "10.188.2.254"
)
```

同样修改 `stop_all_workers.sh` 的WORKER_HOSTS数组。

#### 4. 自动部署Worker

```bash
cd /home/zq/project/supervise
chmod +x *.sh

# 部署并启动所有Workers
./deploy_workers.sh
```

脚本会自动:
- ✓ 检查SSH连接
- ✓ 部署测试脚本
- ✓ 检查/安装依赖 (Python, Locust)
- ✓ 启动所有Workers

#### 5. 启动Master并开始测试

```bash
./distributed_test_master.sh
```

然后在浏览器打开: `http://172.16.229.162:8089`

在Web界面中:
1. 确认Worker数量 (应该显示3-4个)
2. 设置用户数: 500
3. 启动速率: 10 users/s
4. 点击 "Start swarming"

#### 6. 停止测试

```bash
# 在Master上按 Ctrl+C 停止

# 停止所有Workers
./stop_all_workers.sh
```

### 方案B: 手动部署

#### 1. 在每台Worker机器上安装依赖

```bash
# 在所有Worker机器上执行
sudo apt update
sudo apt install python3 python3-pip -y
pip3 install locust requests
```

#### 2. 复制测试脚本到所有Worker

```bash
# 在Master机器上
for host in 10.188.2.252 10.188.2.253 10.188.2.254; do
    scp load_test_realistic.py zq@$host:/home/zq/project/supervise/
    scp distributed_test_worker.sh zq@$host:/home/zq/project/supervise/
done
```

#### 3. 在Master上启动

```bash
cd /home/zq/project/supervise
./distributed_test_master.sh
```

#### 4. 在每个Worker上启动

```bash
# 在Worker机器1 (10.188.2.252)
cd /home/zq/project/supervise
./distributed_test_worker.sh 172.16.229.162

# 在Worker机器2 (10.188.2.253)
cd /home/zq/project/supervise
./distributed_test_worker.sh 172.16.229.162

# 在Worker机器3 (10.188.2.254)
cd /home/zq/project/supervise
./distributed_test_worker.sh 172.16.229.162
```

#### 5. 检查Master Web界面

浏览器打开: `http://172.16.229.162:8089`

应该看到 "3 workers connected" 或类似提示。

## 网络配置

### 防火墙规则

Master机器需要开放端口:

```bash
# Master端口
sudo ufw allow 5557/tcp  # Locust Master通信端口
sudo ufw allow 8089/tcp  # Web界面端口

# 或使用iptables
sudo iptables -A INPUT -p tcp --dport 5557 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 8089 -j ACCEPT
```

### 网络要求

- Master与所有Workers之间网络延迟 < 50ms
- Master与目标服务器之间网络稳定
- 每个Worker至少500Mbps带宽 (167用户 × 3MB/s)

## 监控和调试

### 查看Worker日志

```bash
# 在Worker机器上
tail -f /tmp/locust_worker.log
```

### 查看Worker状态

在Master的Web界面可以看到:
- Worker数量
- 每个Worker的RPS
- 每个Worker的用户数

### 常见问题

#### 1. Worker无法连接到Master

检查:
```bash
# 在Worker机器上测试连接
telnet 172.16.229.162 5557

# 检查Master防火墙
sudo ufw status
```

#### 2. 部分Worker掉线

可能原因:
- 网络不稳定
- Worker机器资源耗尽
- Master-Worker版本不匹配

检查Worker机器资源:
```bash
ssh zq@10.188.2.252 "top -bn1 | head -20"
```

#### 3. 用户分布不均匀

Locust会自动平衡用户到各个Worker，如果不均匀:
- 重启Master和所有Workers
- 确保所有Worker配置相同

## 资源规划建议

### 每个Worker机器配置

**最小配置**:
- CPU: 4核
- 内存: 8GB
- 网络: 1Gbps
- 负载: 150用户

**推荐配置**:
- CPU: 8核
- 内存: 16GB
- 网络: 10Gbps
- 负载: 200用户

### Master机器配置

**最小配置**:
- CPU: 2核
- 内存: 4GB
- 网络: 100Mbps (只处理统计数据)

### 机器数量计算

```python
# 公式
workers_needed = ceil(total_users / users_per_worker)

# 示例
500用户 / 150用户per worker = 4个Workers
1000用户 / 150用户per worker = 7个Workers
```

## 测试结果验证

测试完成后:

```bash
# 1. 在Master上查看分布
./analyze_test_results.sh

# 2. 查看HTML报告
xdg-open /tmp/test_500_distributed_report.html

# 3. 检查视频分布
find /home/zq/project/supervise/server_data/30/recordings -name "test_*" -type d | wc -l
ssh zq@10.188.2.252 "find /home/zq/project/supervise/server_data/30/recordings -name 'test_*' -type d | wc -l"
```

## 文件清单

| 文件 | 用途 | 位置 |
|------|------|------|
| `load_test_realistic.py` | 测试脚本 | Master + 所有Workers |
| `distributed_test_master.sh` | 启动Master | 仅Master |
| `distributed_test_worker.sh` | 启动Worker | 所有Workers |
| `deploy_workers.sh` | 自动部署 | 仅Master |
| `stop_all_workers.sh` | 停止Workers | 仅Master |

## 高级配置

### 调整用户数分配

如果Worker机器配置不同，可以手动指定用户数:

```bash
# Worker 1 (高配置): 200用户
./distributed_test_worker.sh 172.16.229.162 --expect-workers-max-users=200

# Worker 2 (低配置): 150用户
./distributed_test_worker.sh 172.16.229.162 --expect-workers-max-users=150
```

### 使用Docker部署Worker

```dockerfile
# Dockerfile
FROM python:3.9-slim
RUN pip install locust requests
COPY load_test_realistic.py /app/
WORKDIR /app
CMD ["locust", "-f", "load_test_realistic.py", "--worker", "--master-host=master"]
```

```bash
# 启动Worker容器
docker run -d --name locust-worker1 locust-worker:latest
docker run -d --name locust-worker2 locust-worker:latest
```

## 性能基准

基于3个Worker (每个150用户):

| 指标 | 期望值 |
|------|--------|
| 总用户数 | 450-500 |
| 总RPS | 15-20 (上传+心跳) |
| 失败率 | < 5% |
| 平均响应时间 | < 5000ms |
| P95响应时间 | < 15000ms |
| Master CPU | < 30% |
| Worker CPU | 40-60% |

## 故障排查

### 日志位置

```bash
# Master日志
journalctl -f  # 如果用systemd运行

# Worker日志
ssh zq@10.188.2.252 "tail -f /tmp/locust_worker.log"

# 应用日志
journalctl -u gunicorn_exam -f
tail -f /var/log/nginx/error.log
```

### 性能问题排查

1. **Master CPU过高**: 减少统计频率，使用--csv而非Web界面
2. **Worker CPU过高**: 减少每个Worker的用户数
3. **网络带宽不足**: 增加Worker数量，分散负载
4. **目标服务器慢**: 检查服务器资源，数据库连接，磁盘IO

## 联系和支持

遇到问题时，收集以下信息:
- Master和Worker的日志
- 网络拓扑图
- 资源使用情况 (top, htop)
- Locust版本: `locust --version`
