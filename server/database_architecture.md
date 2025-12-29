# 考试监控系统数据库架构设计

## 当前架构分析

### Redis使用场景（保持）
**高频读写操作 - 适合Redis**
1. **实时状态管理**
   - 学生在线状态
   - 心跳检测
   - 连接会话

2. **缓存层**
   - 考试配置缓存
   - 用户会话缓存
   - 热点数据缓存

3. **队列和计数器**
   - 违规ID计数器
   - 考试ID计数器
   - 临时任务队列

### PostgreSQL使用场景（新增）
**结构化数据存储 - 适合PostgreSQL**
1. **考试管理**
   - 考试基本信息
   - 考试历史记录
   - 考试配置变更日志

2. **学生管理**
   - 学生基本信息
   - 学生考试历史
   - 学生成绩记录

3. **违规记录**
   - 详细违规信息
   - 违规统计分析
   - 违规处理记录

4. **系统日志**
   - 操作日志
   - 系统事件
   - 性能监控数据

## 混合架构设计

### 数据流向
```
客户端请求 → Redis缓存 → PostgreSQL持久化
                ↓
            实时数据    历史数据
```

### 具体实现方案

#### 1. 实时数据（Redis）
```python
# 学生在线状态
exam:{exam_id}:student:{student_id} = {
    'id': '123',
    'username': '张三',
    'status': 'online',
    'last_active': '2024-01-01 10:00:00',
    'ip': '192.168.1.100'
}

# 考试配置缓存
exam_config:{exam_id} = {
    'name': '期末考试',
    'start_time': '2024-01-01 09:00:00',
    'end_time': '2024-01-01 11:00:00'
}
```

#### 2. 持久化数据（PostgreSQL）
```sql
-- 考试表
CREATE TABLE exams (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 学生表
CREATE TABLE students (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL,
    exam_id INTEGER REFERENCES exams(id),
    login_time TIMESTAMP,
    logout_time TIMESTAMP,
    status VARCHAR(20) DEFAULT 'inactive'
);

-- 违规记录表
CREATE TABLE violations (
    id SERIAL PRIMARY KEY,
    student_id INTEGER REFERENCES students(id),
    exam_id INTEGER REFERENCES exams(id),
    reason TEXT NOT NULL,
    screenshot_path VARCHAR(255),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 性能优化策略

### 1. 缓存策略
```python
# 读取数据流程
def get_exam_info(exam_id):
    # 1. 先查Redis缓存
    cached_data = redis_client.get(f'exam_config:{exam_id}')
    if cached_data:
        return json.loads(cached_data)
    
    # 2. 缓存未命中，查PostgreSQL
    exam_data = db.query("SELECT * FROM exams WHERE id = %s", exam_id)
    
    # 3. 写入Redis缓存
    redis_client.setex(f'exam_config:{exam_id}', 3600, json.dumps(exam_data))
    
    return exam_data
```

### 2. 异步持久化
```python
# 高频操作只写Redis，异步同步到PostgreSQL
def update_student_status(student_id, status):
    # 立即更新Redis
    redis_client.hset(f'student:{student_id}', 'status', status)
    
    # 异步更新PostgreSQL
    async_task.delay('sync_student_status', student_id, status)
```

### 3. 数据同步策略
```python
# 定时同步Redis数据到PostgreSQL
def sync_redis_to_postgres():
    # 同步学生状态
    students = redis_client.keys('exam:*:student:*')
    for student_key in students:
        student_data = redis_client.hgetall(student_key)
        # 批量更新PostgreSQL
        batch_update_student(student_data)
```

## 性能对比

### Redis优势场景
- **心跳检测**: 400客户端 × 每30秒 = 13.3次/秒
- **状态更新**: 实时状态变更
- **会话管理**: 用户登录状态

### PostgreSQL优势场景
- **历史查询**: 考试记录查询
- **统计分析**: 违规统计报表
- **复杂查询**: 多表关联查询

## 实施建议

### 阶段1：保持Redis，优化配置
1. 增加Redis连接池
2. 优化Redis数据结构
3. 添加Redis集群支持

### 阶段2：引入PostgreSQL
1. 设计数据库schema
2. 实现数据同步机制
3. 迁移历史数据

### 阶段3：混合架构优化
1. 实现智能缓存策略
2. 优化查询性能
3. 监控和调优

## 结论

对于400个并发客户端的考试监控系统：
- **Redis**: 处理实时高频操作（心跳、状态更新）
- **PostgreSQL**: 存储结构化历史数据（考试记录、违规统计）
- **混合架构**: 结合两者优势，提供最佳性能 