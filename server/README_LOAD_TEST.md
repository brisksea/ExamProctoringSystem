# 负载测试快速入门

## 一、文件说明

- **load_test.py** - Locust 负载测试脚本（模拟学生考试行为）
- **run_test.sh** - 快速启动测试（交互式菜单）
- **monitor_test.sh** - 实时系统监控
- **generate_students.sh** - 生成并导入测试学生
- **LOAD_TEST_GUIDE.md** - 完整测试指南（详细文档）

## 二、快速开始（3步）

### 1. 创建测试考试

访问 http://172.16.229.162:5000/，创建一个测试考试，记下考试ID（例如：23）

### 2. 生成测试学生

```bash
cd /home/zq/project/supervise
./generate_students.sh
# 输入考试ID和学生数量（例如：400）
```

### 3. 运行负载测试

```bash
./run_test.sh
# 选择 1（Web UI模式，推荐）
# 或选择 2（命令行模式）
```

**同时在另一个终端监控系统：**
```bash
./monitor_test.sh
```

## 三、测试策略

**渐进式测试（推荐）：**
1. 50人 → 5分钟
2. 100人 → 10分钟
3. 200人 → 10分钟
4. 400人 → 15分钟

每个阶段结束后，检查系统资源是否正常，再进行下一阶段。

## 四、关键指标

### 正常范围（400人）
- CPU < 85%
- 内存 < 10GB
- MySQL连接 < 85
- 响应时间(P95) < 5秒
- 成功率 > 95%

### 警告阈值
- CPU > 90%
- 内存 < 1GB可用
- MySQL连接 = 90（上限）
- 成功率 < 90%

## 五、Web UI 使用

启动后访问 http://localhost:8089

**配置参数：**
- Number of users: 50（先从小开始）
- Spawn rate: 5（每秒增加5个用户）
- Host: http://172.16.229.162:5000

**实时查看：**
- Statistics：请求统计（成功率、响应时间）
- Charts：实时图表
- Failures：失败详情
- Download Data：导出测试报告

## 六、命令行模式

自动运行完整测试，生成HTML报告：

```bash
./run_test.sh
# 选择 2（命令行模式）
# 选择用户数（1-4或自定义）
```

报告保存在：`report_XXXusers_YYYYMMDD_HHMMSS.html`

## 七、常见问题

### Q1: 提示 "pool exhausted"
**A:** MySQL连接池不足，增加 pool_size：
```python
# data_access.py line 25
'pool_size': 20,  # 改大一些
```

### Q2: 大量连接失败
**A:** Gunicorn worker不足：
```bash
# 编辑 start_server.sh
WORKERS=8  # 增加worker数
./start_server.sh restart
```

### Q3: 响应时间过长
**A:** 可能是磁盘IO瓶颈，检查磁盘使用率：
```bash
iostat -x 2
# 如果 %util > 80%，考虑使用SSD
```

### Q4: 视频上传失败
**A:** 检查nginx配置：
```nginx
# /etc/nginx/sites-enabled/default
client_max_body_size 600M;
proxy_read_timeout 600s;
```

## 八、测试后清理

```bash
# 停止测试
pkill -f locust

# 删除测试考试（假设ID=23）
curl -X DELETE http://172.16.229.162:5000/api/exams/23

# 清理测试数据
rm -rf /home/zq/project/supervise/server_data/23/
rm test_students_*.txt
rm report_*.html report_*.csv
```

## 九、生产环境注意事项

1. **真实视频大小：** 测试用1MB，实际15MB/分钟
   - 400人 × 15MB/min = 6GB/min = 800Mbps
   - 建议降低FPS或增加上传间隔

2. **提前演练：** 真实考试前一周完整测试

3. **监控告警：** 设置CPU、内存、网络告警

4. **应急方案：** 准备禁用录屏的降级方案

5. **资源余量：** 确保有30%的资源余量

## 十、获取帮助

详细文档请查看：**LOAD_TEST_GUIDE.md**

遇到问题时：
1. 检查 ./monitor_test.sh 的系统状态
2. 查看服务器日志：`tail -f /home/zq/project/supervise/logs/*.log`
3. 查看 Locust 的 Failures 标签页
4. 检查 MySQL 错误日志：`tail -f /var/log/mysql/error.log`
