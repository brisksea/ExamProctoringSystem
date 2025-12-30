# 监控密码功能完整实现总结

## 📋 功能清单

### ✅ 已完成的功能

1. **统一登录入口**
   - 访问首页 `/` 自动显示登录弹窗
   - 支持管理口令：`gdufskaoshi` → 进入完整管理后台
   - 支持监控密码：自动跳转到对应考试的监控页面

2. **监控密码管理**
   - 创建考试时设置监控密码
   - 编辑考试时修改监控密码
   - 监控密码可重复使用（仅需在同时进行的考试间唯一）
   - 自动冲突检测（创建/编辑时检查）

3. **监控页面**
   - 简化版界面（仅查看权限）
   - 实时学生状态
   - 异常记录查看
   - 截图/录屏查看
   - 自动刷新（15秒）
   - 新增异常提示

## 🔍 密码重复使用规则

### 核心原则
**监控密码只需在时间重叠的考试之间保持唯一**

### 允许的情况 ✅
- 已结束考试的密码可以被新考试使用
- 不同时间段（不重叠）的考试可用相同密码
- 考试时间完全错开的可以使用相同密码

### 不允许的情况 ❌
- 两个时间重叠的考试使用相同密码（无论状态是 pending/active/completed）

### 示例场景
```
时间线：
  09:00-11:00  考试A   密码: exam123
  14:00-16:00  考试B   密码: exam123  ← ✓ 可以（时间不重叠）
  14:00-16:00  考试C   密码: exam123  ← ✗ 冲突（与考试B时间重叠）
  15:00-17:00  考试D   密码: exam123  ← ✗ 冲突（与考试B、C时间重叠）
  19:00-21:00  考试E   密码: exam123  ← ✓ 可以（时间不重叠）
```

## 💻 技术实现

### 数据库变更
```sql
ALTER TABLE exams
ADD COLUMN monitor_password VARCHAR(255) DEFAULT NULL
AFTER disable_new_tabs;
```

### 后端API (server.py)

#### 1. 统一登录入口
- 修改首页登录逻辑：先验证管理口令，再验证监控密码

#### 2. 冲突检测 - 创建考试
```python
# 检查是否与时间重叠的考试冲突
# 时间重叠判断：start_time < other_end_time AND end_time > other_start_time
SELECT id, name, start_time, end_time FROM exams
WHERE monitor_password = %s
AND %s < end_time
AND %s > start_time
LIMIT 1
```

#### 3. 冲突检测 - 编辑考试
```python
# 检查是否与时间重叠的考试冲突（排除当前考试）
SELECT id, name, start_time, end_time FROM exams
WHERE monitor_password = %s
AND %s < end_time
AND %s > start_time
AND id != %s  # 排除当前考试
LIMIT 1
```

#### 4. 监控登录验证
```python
# 只匹配status='active'的考试（登录时才需要检查状态）
SELECT id, name FROM exams
WHERE monitor_password = %s
AND status = 'active'
LIMIT 1
```

### 前端修改 (templates/)

#### index.html
1. **登录弹窗** (lines 1839-1907)
   - 统一入口：管理口令 + 监控密码
   - 先检查管理口令，再尝试监控密码
   - 显示加载状态和错误提示

2. **创建考试表单** (lines 443-450)
   - 监控密码输入框
   - 友好提示：密码重复使用规则

3. **编辑考试表单** (lines 559-566)
   - 监控密码输入框
   - 同样的提示信息

#### monitor.html
- 简化版监控页面
- 仅查看权限
- 退出按钮跳转回首页

#### monitor_login.html
- 专用监控登录页（备用）
- 仅支持监控密码

## 📊 测试工具

### 1. add_monitor_password_field.py
- 数据库迁移脚本
- 添加monitor_password字段
- 显示表结构

### 2. test_monitor_password_reuse.py
- 测试密码重复使用
- 显示当前考试及密码使用情况
- 检测密码冲突
- 演示规则说明

### 3. test_monitor_password.py
- 显示所有设置了监控密码的考试
- 使用说明

## 🎯 使用流程

### 管理员创建考试
1. 登录管理后台（口令：`gdufskaoshi`）
2. 创建考试，设置监控密码（如：`monitor2025`）
3. 系统检查密码是否与其他active考试冲突
4. 无冲突则保存成功

### 监考员登录
1. 访问 `http://服务器IP:5000/`
2. 输入监控密码（如：`monitor2025`）
3. 系统验证密码是否匹配某个active考试
4. 匹配成功则自动跳转到该考试的监控页面

### 考试结束后
1. 考试状态变为 `completed`
2. 该监控密码自动"释放"
3. 新考试可以重复使用该密码

## 🔒 安全考虑

1. **密码存储**
   - 当前明文存储（适用于内部系统）
   - 可升级为哈希存储（需要时）

2. **访问控制**
   - 监控密码仅对active考试有效
   - 考试结束后密码自动失效

3. **权限隔离**
   - 监控页面完全无管理功能
   - 只读访问
   - 无法修改任何数据

## 📝 文件清单

### 新增文件
- `templates/monitor_login.html` - 监控登录页
- `templates/monitor.html` - 监控页面
- `add_monitor_password_field.py` - 数据库迁移
- `test_monitor_password_reuse.py` - 测试脚本
- `test_monitor_password.py` - 测试脚本
- `MONITOR_PASSWORD_FEATURE.md` - 功能文档

### 修改文件
- `server.py` - 添加路由和冲突检测
- `data_access.py` - 添加monitor_password字段支持
- `templates/index.html` - 统一登录 + 表单字段

## ✨ 优势

1. **简化管理**
   - 密码可重复使用，减少记忆负担
   - 只需确保同时进行的考试密码不同

2. **自动验证**
   - 系统自动检测冲突
   - 友好错误提示

3. **统一入口**
   - 一个页面支持两种角色
   - 自动识别，智能跳转

4. **安全可控**
   - 密码仅对进行中的考试有效
   - 考试结束自动失效

## 🚀 测试建议

1. **创建两个同时进行的考试，设置相同密码**
   - 应该提示冲突

2. **创建一个未开始的考试，使用已结束考试的密码**
   - 应该允许

3. **用监控密码登录**
   - 应该只能看到对应考试
   - 没有管理按钮

4. **用管理口令登录**
   - 应该看到完整管理后台
   - 可以管理所有考试

## 📞 支持

如有问题，请检查：
1. 数据库字段是否正确添加
2. 考试状态是否为 'active'
3. 监控密码是否与其他active考试冲突
4. 浏览器控制台是否有错误信息
