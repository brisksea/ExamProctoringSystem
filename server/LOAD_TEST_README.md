# 500用户并发测试指南

## 测试说明

这个测试模拟真实考试场景，500个学生同时录屏上传视频到服务器。

### 测试特点

基于真实客户端实现 (`screen_recorder.py`):

- **录屏间隔**: 30秒
- **上传间隔**: 120秒 + 随机0-60秒延迟
- **视频大小**: 15-20MB (模拟 1920×1080×0.8 scale, 10fps, 30秒录屏)
- **上传超时**: 600秒
- **IP范围**: 192.168.1.1-255, 192.168.2.1-245 (连续IP)

### 预期行为

- **负载分布**: 本地服务器 75%, 远程服务器 25% (weight=3:1)
- **IP一致性**: 同一IP的请求总是路由到同一服务器
- **并发处理**: 500个学生同时上传，测试系统承载能力

## 快速开始

### 1. 运行测试

```bash
cd /home/zq/project/supervise
./test_500_users.sh
```

测试将自动完成以下步骤:
1. 清理旧测试数据
2. 检查服务状态 (Flask, Nginx, MySQL, Redis)
3. 启动系统监控
4. 运行Locust负载测试 (500用户, 10分钟)
5. 收集和分析结果

### 2. 查看实时监控

测试过程中，可以查看监控日志:

```bash
tail -f /tmp/test_500_monitor.log
```

### 3. 分析结果

测试完成后，运行详细分析:

```bash
./analyze_test_results.sh
```

### 4. 查看HTML报告

```bash
# 在浏览器中打开
firefox /tmp/test_500_report.html

# 或使用默认浏览器
xdg-open /tmp/test_500_report.html
```

## 测试参数调整

编辑 `test_500_users.sh` 可以调整测试参数:

```bash
USERS=500          # 用户数量
SPAWN_RATE=10      # 每秒启动用户数
RUN_TIME=10m       # 测试持续时间
HOST="http://172.16.229.162:5000"  # 目标服务器
```

编辑 `load_test_realistic.py` 可以调整行为参数:

```python
# 上传间隔 (行50)
wait_time = between(20, 40)  # 秒

# 视频大小 (行85)
video_size = random.randint(15, 20) * 1024 * 1024  # MB

# 任务权重 (行67, 行116)
@task(10)  # 上传视频 (高权重)
@task(1)   # 心跳 (低权重)
```

## 输出文件

测试完成后，以下文件将包含测试结果:

| 文件 | 说明 |
|------|------|
| `/tmp/test_500_report.html` | Locust HTML报告 (可视化) |
| `/tmp/test_500_stats.csv` | 请求统计数据 (CSV格式) |
| `/tmp/test_500_monitor.log` | 系统监控日志 |
| `/var/log/nginx/hash_debug.log` | Nginx负载均衡调试日志 |

## 结果验证

### 1. 学生分布检查

```bash
# 本地服务器
find /home/zq/project/supervise/server_data/30/recordings -name "test_*" -type d | wc -l

# 远程服务器
ssh zq@10.188.2.252 "find /home/zq/project/supervise/server_data/30/recordings -name 'test_*' -type d | wc -l"
```

预期: 本地约375个, 远程约125个 (总计500)

### 2. IP分布检查

```bash
# 查看前20个请求的IP分布
head -20 /var/log/nginx/hash_debug.log
```

预期: 看到 192.168.1.x 和 192.168.2.x 的IP

### 3. 路由一致性检查

同一IP的所有请求应该路由到同一服务器。分析脚本会自动检查。

## 常见问题

### Q: 测试失败, 提示服务未运行

检查服务状态:
```bash
# Flask服务
curl http://127.0.0.1:5001/api/health
curl http://10.188.2.252:5000/api/health

# Nginx
curl http://172.16.229.162:5000/api/health

# MySQL
mysqladmin ping -h localhost -u exam_system -pexam2024

# Redis
redis-cli ping
```

### Q: 负载分布不均匀

可能原因:
1. 测试时间太短 (样本不足)
2. Nginx配置的weight比例错误
3. 某个服务器宕机

检查:
```bash
# 查看nginx配置
grep -A 5 "upstream upload_backend" /etc/nginx/sites-enabled/default

# 查看nginx错误日志
sudo tail -50 /var/log/nginx/error.log
```

### Q: MySQL连接耗尽

检查当前连接数:
```bash
mysql -u exam_system -pexam2024 -e "SHOW PROCESSLIST;" | wc -l
mysql -u exam_system -pexam2024 -e "SHOW VARIABLES LIKE 'max_connections';"
```

如果连接数接近max_connections, 需要:
1. 增加MySQL max_connections
2. 减少Flask pool_size
3. 减少worker数量

### Q: 磁盘空间不足

计算所需空间:
- 500个学生
- 平均每人上传10个视频 (10分钟测试)
- 每个视频15-20MB
- 总计: 500 × 10 × 17.5MB ≈ 87.5GB

检查磁盘空间:
```bash
df -h /home/zq/project/supervise/server_data
```

清理测试数据:
```bash
rm -rf /home/zq/project/supervise/server_data/30/recordings/test_*
ssh zq@10.188.2.252 "rm -rf /home/zq/project/supervise/server_data/30/recordings/test_*"
```

## 性能基准

参考数据 (基于类似系统):

| 指标 | 期望值 |
|------|--------|
| 并发用户 | 500 |
| 成功率 | > 95% |
| 平均响应时间 | < 5000ms |
| P95响应时间 | < 15000ms |
| CPU使用率 | < 80% |
| 内存使用 | < 70% |
| MySQL连接 | < 80 |

如果超出这些指标, 考虑:
- 增加服务器资源
- 优化数据库查询
- 增加缓存
- 调整负载均衡比例

## 其他测试脚本

| 脚本 | 说明 | 用途 |
|------|------|------|
| `test_load_balance.sh` | 简单负载均衡测试 | 验证nginx分流功能 |
| `test_20_serial.sh` | 20用户串行测试 | 调试和快速验证 |
| `test_continuous_ips.sh` | 50个连续IP测试 | 验证连续IP的分流 |
| `test_diverse_ips.sh` | 不同IP段测试 | 验证不同IP段的分流 |
| `monitor_test.sh` | 系统监控 | 实时监控系统状态 |

## 联系

如有问题, 检查:
1. `/var/log/nginx/error.log` - Nginx错误日志
2. `journalctl -u gunicorn_exam` - Flask应用日志
3. `/tmp/test_500_monitor.log` - 系统监控日志
