import json
from datetime import datetime
import os
from redis.connection import ConnectionPool
import redis

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server_data")

# Redis连接池配置（500人并发优化）
REDIS_CONFIG = {
    'host': 'localhost',
    'port': 6379,
    'db': 0,
    'decode_responses': True,
    'max_connections': 150,  # 增加到 150 以支持 500 人并发
                             # 分配：Gunicorn ~100 + Celery ~20 + 状态查询 ~30
    'socket_timeout': 5,    # 连接超时时间
    'socket_connect_timeout': 5,  # 建立连接超时时间
    'retry_on_timeout': True,     # 超时时重试
}

EXAM_CONFIG_KEY = "exam_configs"  # Redis中存储考试配置的key

# 创建Redis连接池
redis_pool = ConnectionPool(**REDIS_CONFIG)

def get_redis():
    """获取Redis连接"""
    try:
        client = redis.Redis(connection_pool=redis_pool)
        # 测试连接
        client.ping()
        return client
    except redis.ConnectionError as e:
        print(f"Redis连接错误: {str(e)}")
        raise

# 配置Redis持久化
def configure_redis_persistence():
    """配置Redis持久化选项"""
    try:
        client = get_redis()
        # 配置RDB持久化
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
        client.config_set('save', '900 1 300 10 60 10000')
        client.config_set('dir', DATA_DIR)
        client.config_set('dbfilename', 'exam_monitor.rdb')

        # 配置AOF持久化
        client.config_set('appendonly', 'yes')
        client.config_set('appendfilename', 'exam_monitor.aof')
        client.config_set('appendfsync', 'everysec')

        print(f"进程 {os.getpid()}: Redis持久化配置完成")
    except redis.RedisError as e:
        print(f"进程 {os.getpid()}: Redis持久化配置失败: {str(e)}")

def save_redis_data():
    """保存Redis数据"""
    try:
        client = get_redis()
        print(f"进程 {os.getpid()}: 正在保存Redis数据...")
        client.save()
        print(f"进程 {os.getpid()}: Redis数据保存完成")
    except redis.RedisError as e:
        print(f"进程 {os.getpid()}: Redis数据保存失败: {str(e)}")

def get_all_exams():
    client = get_redis()
    exams = client.hgetall(EXAM_CONFIG_KEY)
    return [json.loads(exam_data) for exam_data in exams.values()]

def get_exam_students(exam_id):
    """获取指定考试的所有学生"""
    students = {}
    client = get_redis()
    keys = client.keys(f'exam:{exam_id}:student:*')
    for key in keys:
        if key.endswith(":screenshots") or key.endswith(":logins"):
            continue
        student_data = client.hgetall(key)
        if student_data:
            student_id = key.split(':')[-1]
            students[student_id] = student_data
    return students

def get_violations():
    """获取所有违规记录"""
    client = get_redis()
    violations = []
    violation_count = client.llen('violations')
    if violation_count > 0:
        violations_data = client.lrange('violations', 0, -1)
        violations = [json.loads(v) for v in violations_data]
    return violations

def create_exam(exam_data):
    """创建新考试"""
    client = get_redis()
    exam_id = client.incr('exam_id_counter')

    exam_config = {
        'id': exam_id,
        'name': exam_data['name'],
        'start_time': exam_data['start_time'],
        'end_time': exam_data['end_time'],
        'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'status': 'pending',  # pending, active, completed
        'default_url': exam_data['default_url']
    }

    # 存储考试配置
    client.hset(EXAM_CONFIG_KEY, exam_id, json.dumps(exam_config))
    return exam_config

def get_exam(exam_id):
    """获取考试信息"""
    client = get_redis()
    exam_data = client.hget(EXAM_CONFIG_KEY, exam_id)
    return json.loads(exam_data) if exam_data else None

def get_all_exams():
    """获取所有考试信息"""
    client = get_redis()
    exams = client.hgetall(EXAM_CONFIG_KEY)
    return [json.loads(exam_data) for exam_data in exams.values()]

def update_exam_status():
    """更新所有考试的状态"""
    client = get_redis()
    now = datetime.now()
    exams = get_all_exams()
    updated_count = 0

    for exam in exams:
        exam_id = exam['id']
        current_status = exam['status']
        start_time = datetime.strptime(exam['start_time'], "%Y-%m-%dT%H:%M")
        end_time = datetime.strptime(exam['end_time'], "%Y-%m-%dT%H:%M")

        # 确定考试应该处于的状态
        if now < start_time:
            new_status = 'pending'  # 未开始
        elif start_time <= now <= end_time:
            new_status = 'active'   # 进行中
        else:
            new_status = 'completed'  # 已结束

        # 如果状态需要更新
        if new_status != current_status:
            exam['status'] = new_status
            client.hset(EXAM_CONFIG_KEY, exam_id, json.dumps(exam))
            updated_count += 1
            print(f"考试状态更新: ID={exam_id}, 名称={exam['name']}, {current_status} -> {new_status}")

    return updated_count

def find_student_in_exams(username):
    """查找学生所在的所有考试"""
    active_exams = []
    student_exams = []

    # 获取所有考试
    exams = get_all_exams()

    # 先更新考试状态
    update_exam_status()

    # 筛选出正在进行中的考试
    for exam in exams:
        if exam['status'] == 'active':
            active_exams.append(exam)

    # 在每个正在进行的考试中查找学生
    for exam in active_exams:
        exam_id = exam['id']
        students = get_exam_students(exam_id)

        for student_id, student in students.items():
            if student['username'] == username:
                # 找到了学生
                student_exam = {
                    'exam_id': exam_id,
                    'student_id': student_id,
                    'exam_name': exam['name'],
                    'start_time': exam['start_time'],
                    'end_time': exam['end_time']
                }
                student_exams.append(student_exam)

    return student_exams

def get_exam_violations(exam_id, page=1, per_page=12):
    """获取指定考试的违规记录，支持分页"""
    client = get_redis()
    violation_key = f'exam:{exam_id}:violations'
    
    # 获取所有违规记录
    violations_data = client.lrange(violation_key, 0, -1)
    # 解析JSON并转换为列表
    violations = [json.loads(v) for v in violations_data]
    # 按时间戳倒序排序
    violations.sort(key=lambda x: x['timestamp'], reverse=True)
    
    # 计算分页范围
    start = (page - 1) * per_page
    end = start + per_page
    
    # 返回指定范围的记录
    return violations[start:end]

def cleanup_redis():
    """清理Redis连接并保存数据"""
    try:
        client = get_redis()
        # 将所有考试中的在线学生标记为离线
        exams = get_all_exams()
        for exam in exams:
            exam_id = exam['id']
            students = get_exam_students(exam_id)
            for student_id, student in students.items():
                if student.get('status') == 'online':
                    student_key = f'exam:{exam_id}:student:{student_id}'
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    client.hset(student_key, 'status', 'offline')
                    client.hset(student_key, 'logout_time', timestamp)
                    print(f"进程 {os.getpid()}: 学生 {student['username']} (考试: {exam_id}) 标记为离线")

        # 保存数据
        save_redis_data()

        # 关闭连接池
        redis_pool.disconnect()
        print(f"进程 {os.getpid()}: Redis连接已关闭")
    except Exception as e:
        print(f"进程 {os.getpid()}: 清理Redis时出错: {str(e)}")
