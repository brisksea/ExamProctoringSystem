# 400人并发负载测试指南

## 一、测试准备

### 1. 安装测试工具

```bash
# 激活虚拟环境
source /home/zq/project/venv/bin/activate

# 安装 locust 和依赖
pip install locust pillow
```

### 2. 创建测试考试

在开始负载测试前，需要先创建一个测试用的考试：

```bash
# 访问 http://172.16.229.162:5000/
# 创建考试，设置：
# - 考试名称：负载测试考试
# - 开始时间：当前时间
# - 结束时间：当前时间+2小时
# - 状态会自动设置为 active
```

记下创建的考试ID（例如：23）

### 3. 导入测试学生名单

为了模拟真实场景，需要预先导入400个学生到考试中：

```bash
# 生成400个学生名单
for i in {1..400}; do
    student_id=$(printf "test_%05d" $i)
    echo "$student_id 测试学生$i"
done > test_students.txt

# 通过Web界面导入，或使用API：
curl -X POST http://172.16.229.162:5000/api/students/import \
  -F "exam_id=23" \
  -F "import_type=file" \
  -F "student_list_file=@test_students.txt"
```

## 二、测试策略

### 渐进式压力测试（推荐）

不要直接测试400人，而是逐步增加负载：

**阶段1：50人并发（5分钟）**
- 目的：验证基本功能
- 预期：所有请求成功，响应时间 < 1秒

**阶段2：100人并发（10分钟）**
- 目的：检测系统在中等负载下的表现
- 预期：成功率 > 99%，响应时间 < 2秒

**阶段3：200人并发（10分钟）**
- 目的：接近实际负载
- 预期：成功率 > 98%，响应时间 < 3秒

**阶段4：400人并发（15分钟）**
- 目的：峰值压力测试
- 预期：成功率 > 95%，响应时间 < 5秒

## 三、执行测试

### 方法1：使用 Locust Web UI（推荐）

```bash
# 进入项目目录
cd /home/zq/project/supervise

# 启动 Locust Web UI
locust -f load_test.py --host=http://172.16.229.162:5000

# 在浏览器中访问 http://localhost:8089
# 设置：
# - Number of users: 50 (先从50开始)
# - Spawn rate: 5 (每秒增加5个用户)
# - Host: http://172.16.229.162:5000
```

**优点**：
- 实时图表展示
- 可以动态调整并发数
- 详细的请求统计

### 方法2：命令行模式（无界面）

```bash
# 50人并发，持续5分钟
locust -f load_test.py \
  --host=http://172.16.229.162:5000 \
  --users 50 \
  --spawn-rate 5 \
  --run-time 5m \
  --headless \
  --html report_50users.html

# 100人并发，持续10分钟
locust -f load_test.py \
  --host=http://172.16.229.162:5000 \
  --users 100 \
  --spawn-rate 10 \
  --run-time 10m \
  --headless \
  --html report_100users.html

# 200人并发，持续10分钟
locust -f load_test.py \
  --host=http://172.16.229.162:5000 \
  --users 200 \
  --spawn-rate 10 \
  --run-time 10m \
  --headless \
  --html report_200users.html

# 400人并发，持续15分钟
locust -f load_test.py \
  --host=http://172.16.229.162:5000 \
  --users 400 \
  --spawn-rate 20 \
  --run-time 15m \
  --headless \
  --html report_400users.html
```

## 四、监控指标

### 1. 在测试机器上监控

**终端1：监控 CPU 和内存**
```bash
watch -n 2 'ps aux | grep -E "(gunicorn|redis|mysql|merge)" | grep -v grep | head -20'
```

**终端2：监控网络流量**
```bash
watch -n 2 'ifconfig ens33 | grep "RX packets\|TX packets"'
```

**终端3：监控 MySQL 连接**
```bash
watch -n 2 'mysql -u debian-sys-maint -pbGEtT3EfFKGLhYRS -e "SHOW STATUS LIKE \"Threads_connected\"; SHOW STATUS LIKE \"Max_used_connections\";"'
```

**终端4：监控 Gunicorn 进程**
```bash
watch -n 2 'pgrep -a gunicorn | wc -l'
```

### 2. 监控服务器资源

**CPU使用率**
```bash
top -b -n 1 | grep "Cpu(s)"
# 期望：< 80%
```

**内存使用**
```bash
free -h
# 期望：至少保留 2GB 可用内存
```

**磁盘IO**
```bash
iostat -x 2 5
# 期望：%util < 80%
```

**网络带宽**
```bash
iftop -i ens33
# 期望：< 800 Mbps（千兆网卡的80%）
```

### 3. 应用层指标（从 Locust Web UI 查看）

- **请求成功率**：应该 > 95%
- **响应时间（P95）**：应该 < 5秒
- **RPS（每秒请求数）**：期望 > 100
- **失败类型**：如果有失败，查看具体原因

## 五、关键性能指标基准

### 正常范围

| 指标 | 50人 | 100人 | 200人 | 400人 |
|------|------|-------|-------|-------|
| CPU使用率 | < 30% | < 50% | < 70% | < 85% |
| 内存使用 | < 4GB | < 6GB | < 8GB | < 10GB |
| MySQL连接数 | < 20 | < 40 | < 60 | < 85 |
| 响应时间(P95) | < 1s | < 2s | < 3s | < 5s |
| 请求成功率 | > 99% | > 99% | > 98% | > 95% |
| 网络流量 | < 100Mbps | < 200Mbps | < 400Mbps | < 700Mbps |

### 警告阈值

如果出现以下情况，需要立即停止测试并排查：

- CPU持续 > 90%
- 内存不足（< 1GB可用）
- MySQL连接数达到上限（90个）
- 请求成功率 < 90%
- 响应时间 > 10秒
- 大量 "Connection refused" 或 "Timeout" 错误

## 六、测试场景说明

### 脚本模拟的学生行为

1. **登录阶段**（on_start）
   - 每个学生使用唯一ID登录
   - 获取考试ID

2. **考试阶段**（循环执行）
   - **心跳**：每30秒左右发送一次（权重10，最高频）
   - **截图上传**：约每2分钟一次（权重3）
   - **视频上传**：约每5分钟一次（权重1，使用1MB测试文件）

3. **退出阶段**（on_stop）
   - 发送logout请求
   - 触发视频合并

### 真实考试 vs 测试的差异

**测试配置（减少网络压力）：**
- 截图：800x600（约100KB）
- 视频：1MB/片段

**真实场景：**
- 截图：1920x1080（约500KB）
- 视频：15MB/分钟

**换算：**
- 测试时400人上传1MB = 真实场景约27人上传15MB
- 如果测试时网络占用300Mbps，真实场景会达到 300 * 15 = 4500Mbps
- **因此真实考试时建议：**
  - 降低视频质量（FPS降到5-8）
  - 或延长上传间隔（90-120秒）
  - 或准备更高带宽（万兆网卡）

## 七、常见问题排查

### 问题1：大量 "Connection refused"

**原因**：
- Gunicorn worker不足
- 端口达到最大连接数

**解决**：
```bash
# 增加worker数量
vim /home/zq/project/supervise/start_server.sh
# 修改 WORKERS=8

# 或增加系统连接限制
sudo sysctl -w net.core.somaxconn=65535
```

### 问题2：响应时间过长

**原因**：
- MySQL连接池耗尽
- 磁盘IO瓶颈

**解决**：
```python
# 调整 data_access.py 中的 pool_size
'pool_size': 20,  # 增加到20
```

### 问题3：视频上传失败

**原因**：
- nginx client_max_body_size限制
- 请求超时

**解决**：
```nginx
# /etc/nginx/sites-enabled/default
client_max_body_size 600M;
proxy_read_timeout 600s;

# 重启nginx
sudo nginx -s reload
```

### 问题4：Redis连接失败

**原因**：
- Redis最大连接数不足

**解决**：
```bash
# 修改redis配置
sudo vim /etc/redis/redis.conf
# 找到 maxclients，改为：
maxclients 10000

# 重启redis
sudo systemctl restart redis
```

## 八、测试后清理

### 1. 停止测试

```bash
# 如果使用Web UI，在浏览器中点击 "Stop"
# 如果使用命令行，Ctrl+C 停止

# 确保所有locust进程已停止
pkill -f locust
```

### 2. 清理测试数据

```bash
# 删除测试考试（假设ID为23）
curl -X DELETE http://172.16.229.162:5000/api/exams/23

# 清理测试上传的文件
rm -rf /home/zq/project/supervise/server_data/23/
```

### 3. 检查系统状态

```bash
# 检查gunicorn进程
pgrep -a gunicorn

# 检查MySQL连接
mysql -u debian-sys-maint -pbGEtT3EfFKGLhYRS -e "SHOW STATUS LIKE 'Threads_connected';"

# 应该恢复到正常水平（< 5个连接）
```

## 九、优化建议

根据测试结果，可能需要的优化：

### 如果CPU是瓶颈
- 增加Gunicorn worker数量
- 使用多台服务器负载均衡
- 优化代码中的CPU密集型操作

### 如果内存是瓶颈
- 减少每个worker的内存占用
- 使用对象池复用
- 升级服务器内存

### 如果数据库是瓶颈
- 增加连接池大小
- 添加数据库索引
- 使用读写分离

### 如果网络是瓶颈
- 升级到万兆网卡
- 降低视频质量/帧率
- 使用视频压缩

### 如果磁盘是瓶颈
- 全部使用SSD
- 使用RAID提升性能
- 分离录屏文件到专用存储

## 十、生产环境建议

基于测试结果，对于实际400人考试：

1. **提前演练**：在真实考试前一周进行完整压力测试
2. **监控告警**：设置 CPU、内存、磁盘、网络的告警阈值
3. **降级方案**：准备禁用录屏功能的应急方案
4. **资源预留**：确保系统资源有30%余量
5. **技术支持**：考试期间安排技术人员实时监控

## 测试报告模板

测试完成后，记录以下信息：

```
# 400人并发压力测试报告

## 测试环境
- 服务器IP: 172.16.229.162
- CPU: ___核
- 内存: ___GB
- 网卡: ___
- 磁盘: ___

## 测试结果

### 50人并发
- 持续时间: 5分钟
- 成功率: ___%
- 平均响应时间: ___ms
- P95响应时间: ___ms
- 峰值CPU: ___%
- 峰值内存: ___GB
- MySQL连接数: ___

### 100人并发
（同上）

### 200人并发
（同上）

### 400人并发
（同上）

## 问题记录
1. 问题描述
   - 出现时间
   - 错误信息
   - 解决方案

## 结论
- [ ] 系统可以支持400人并发
- [ ] 需要进行以下优化：___
- [ ] 建议实际考试人数不超过：___人
```
