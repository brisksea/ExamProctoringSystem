# 主备双目录架构使用说明

## 概述

考试监控系统现在支持**主备双目录架构**，用于优化存储空间使用：

- **主目录（SSD）**：考试进行时存储数据，写入速度快，空间有限
- **备份目录（大容量存储）**：考试结束后归档，容量大但速度较慢

## 配置方式

在 `config.json` 中配置：

```json
{
  "data_dir": "/home/zq/project/supervise/server/server_data",
  "backup_data_dir": "/data/supervise/server_data"
}
```

- `data_dir`: 主数据目录（SSD，考试进行中使用）
- `backup_data_dir`: 备份数据目录（大容量存储，归档用）

## 工作原理

### 1. 数据写入（考试进行中）

所有新数据（截图、录屏、违规记录）都写入**主目录**：
- `/home/zq/project/supervise/server/server_data/{exam_id}/`

### 2. 数据读取（查询考试数据）

系统自动按以下顺序查找：
1. 先查主目录：`/home/zq/project/supervise/server/server_data/{exam_id}/`
2. 如果主目录不存在，再查备份目录：`/data/supervise/server_data/{exam_id}/`
3. 如果都不存在，则使用主目录路径（用于新建考试）

### 3. 数据归档（考试结束后）

使用 `archive_exam.py` 脚本将已结束考试从主目录移动到备份目录。

## 归档工具使用

### 查看可归档的考试

```bash
python3 archive_exam.py --list
```

输出示例：
```
可归档的考试列表（已结束且在主目录中）:
================================================================================
ID     名称                             状态         大小              结束时间
================================================================================
48     数据爬取与分析(2025)152班小测2           completed  7.19 GB         2025-12-25 19:50:00
49     数据爬取与分析(2025)134班期末考试          completed  100.71 GB       2025-12-24 19:50:00
50     Python 与大数据分析-小测               completed  2.89 GB         2025-12-25 09:20:00
51     Python数据可视化与分析（2025）期末考试       completed  11.64 GB        2025-12-28 18:30:00
================================================================================
总计: 4 个考试，可释放空间: 122.43 GB
```

### 演练归档（不实际移动文件）

```bash
python3 archive_exam.py --exam 48 --dry-run
```

### 实际归档单个考试

```bash
python3 archive_exam.py --exam 48
```

系统会显示考试信息，并**先检查备份目录是否已存在**：

**情况1：备份目录不存在（正常归档）**
```
============================================================
考试 ID: 48
考试名称: 数据爬取与分析(2025)152班小测2
考试状态: completed
数据大小: 7.19 GB
源目录: /home/zq/project/supervise/server/server_data/48
目标目录: /data/supervise/server_data/48
============================================================

确认归档? (yes/no):
```

输入 `yes` 后开始归档。

**情况2：备份目录已存在（拒绝归档）**
```
============================================================
考试 ID: 48
...
============================================================

⚠️  错误: 备份目录已存在
   路径: /data/supervise/server_data/48
   现有大小: 3.07 GB

可能的原因:
  1. 该考试已经归档过
  2. 存在旧的备份数据

建议操作:
  1. 检查备份目录内容是否为该考试的数据
  2. 如果确认可以覆盖，使用 --force 选项强制归档:
     python3 archive_exam.py --exam 48 --force
  3. 或手动删除备份目录后重新归档:
     rm -rf /data/supervise/server_data/48
  4. 如果需要保留备份，先重命名备份目录:
     mv /data/supervise/server_data/48 /data/supervise/server_data/48.bak

✗ 备份目录已存在，请先处理后再归档
```

**情况3：强制覆盖已存在的备份**

如果确认需要覆盖旧备份，使用 `--force` 选项：

```bash
python3 archive_exam.py --exam 48 --force
```

系统会要求二次确认：
```
确认归档? (yes/no): yes

⚠️  强制模式: 将删除已存在的备份目录
   路径: /data/supervise/server_data/48
   大小: 3.07 GB

确认删除已存在的备份目录? (yes/no): yes

正在删除已存在的备份目录...
✓ 已删除旧备份

正在移动目录...
✓ 归档成功!
✓ 已释放主目录空间: 7.19 GB
```

### 批量归档多个考试

```bash
python3 archive_exam.py --exam 48 49 50
```

## 注意事项

1. **考试进行中无法归档**：只能归档状态为 `completed` 的考试
2. **自动查找机制**：归档后，查询该考试数据时系统会自动从备份目录读取
3. **空间释放**：归档后主目录空间立即释放
4. **数据安全**：归档使用 `shutil.move()`，数据不会丢失
5. **恢复数据**：如需将考试移回主目录，手动 `mv` 即可：
   ```bash
   mv /data/supervise/server_data/48 /home/zq/project/supervise/server/server_data/
   ```

## 存储空间管理建议

### 定期归档策略

建议在以下情况进行归档：

1. **考试结束后 1-2 天**：确认无需回查后立即归档
2. **主目录空间不足时**：优先归档最早结束的考试
3. **考试高峰期前**：提前归档旧考试，为新考试腾出空间

### 监控主目录空间

```bash
df -h /home/zq/project/supervise/server/server_data
```

当主目录使用率超过 80% 时，应该进行归档。

### 快速释放大量空间

```bash
# 1. 查看可归档考试
python3 archive_exam.py --list

# 2. 按大小排序，优先归档最大的考试
# 例如：归档考试49（100.71 GB）可立即释放最多空间
python3 archive_exam.py --exam 49
```

## 技术实现细节

### 核心函数

```python
def get_exam_data_dir(exam_id):
    """
    获取指定考试的数据目录路径
    优先查找主目录，如果不存在则查找备份目录
    """
    # 优先检查主目录
    primary_exam_dir = os.path.join(DATA_DIR, str(exam_id))
    if os.path.exists(primary_exam_dir):
        return primary_exam_dir

    # 如果配置了备份目录，检查备份目录
    if BACKUP_DATA_DIR:
        backup_exam_dir = os.path.join(BACKUP_DATA_DIR, str(exam_id))
        if os.path.exists(backup_exam_dir):
            return backup_exam_dir

    # 都不存在，返回主目录路径（用于新建考试）
    return primary_exam_dir
```

### 修改的关键API

以下API已支持主备目录：

- `GET /{exam_id}/screenshots/{filename}` - 提供截图文件
- `GET /{exam_id}/screenshots/{student_id}/{filename}` - 提供学生截图
- `GET /{exam_id}/violations/{filename}` - 提供违规截图
- `GET /api/exams/{exam_id}/students/{student_id}/screenshots` - 获取截图列表
- `GET /api/exams/{exam_id}/students/{student_id}/recordings` - 获取录屏列表
- `GET /recordings/{exam_id}/{filename}` - 提供录屏文件
- `GET /recordings/{exam_id}/{student_id}/{filename}` - 提供学生录屏
- `DELETE /api/exams/{exam_id}/students/{student_id}` - 删除学生数据

### 数据写入仍使用主目录

以下操作仍然直接写入主目录（考试进行中）：

- 学生登录创建目录
- 上传截图
- 上传录屏
- 上传违规记录

## 常见问题

### Q: 归档后能否继续访问考试数据？
A: 可以。系统会自动从备份目录读取，Web界面完全透明，无需任何修改。

### Q: 归档过程中服务器需要停机吗？
A: 不需要。归档过程不影响服务器运行，但建议在考试结束且确认无人访问时进行。

### Q: 归档失败会丢失数据吗？
A: 不会。归档使用 `shutil.move()`，是原子操作。如果失败，数据仍在原位置。

### Q: 如何恢复误归档的考试？
A: 手动移动回主目录即可：
```bash
mv /data/supervise/server_data/{exam_id} /home/zq/project/supervise/server/server_data/
```

### Q: 备份目录满了怎么办？
A: 可以删除很早之前的考试数据，或者扩容备份目录存储。删除前建议先做好数据备份。
