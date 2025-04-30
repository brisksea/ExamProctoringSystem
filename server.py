#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
考试监控服务器
用于接收和显示学生状态和异常信息
"""

import os
import json
import time
import signal
import atexit
import threading
from datetime import datetime, timedelta
import redis
from redis.connection import ConnectionPool
from flask import Flask, request, render_template, jsonify, send_from_directory

# 创建Flask应用
app = Flask(__name__)

# 数据存储目录
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server_data")
SCREENSHOTS_DIR = os.path.join(DATA_DIR, "screenshots")
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

# 确保目录存在
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)
if not os.path.exists(SCREENSHOTS_DIR):
    os.makedirs(SCREENSHOTS_DIR)

# Redis连接池配置
REDIS_CONFIG = {
    'host': 'localhost',
    'port': 6379,
    'db': 0,
    'decode_responses': True,
    'max_connections': 10,  # 每个进程的最大连接数
    'socket_timeout': 5,    # 连接超时时间
    'socket_connect_timeout': 5,  # 建立连接超时时间
    'retry_on_timeout': True,     # 超时时重试
}

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

def signal_handler(signum, frame):
    """信号处理函数"""
    print(f"\n进程 {os.getpid()}: 接收到信号 {signum}")
    cleanup_redis()
    os._exit(0)

# 注册信号处理器
signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
signal.signal(signal.SIGTERM, signal_handler)  # 终止信号

# 注册退出处理函数
atexit.register(cleanup_redis)



def get_violations():
    """获取所有违规记录"""
    client = get_redis()
    violations = []
    violation_count = client.llen('violations')
    if violation_count > 0:
        violations_data = client.lrange('violations', 0, -1)
        violations = [json.loads(v) for v in violations_data]
    return violations

EXAM_CONFIG_KEY = "exam_configs"  # Redis中存储考试配置的key

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

def get_exam_violations(exam_id):
    """获取指定考试的所有违规记录"""
    client = get_redis()
    violations = []
    violation_key = f'exam:{exam_id}:violations'
    violation_count = client.llen(violation_key)
    if violation_count > 0:
        violations_data = client.lrange(violation_key, 0, -1)
        violations = [json.loads(v) for v in violations_data]
    return violations

@app.route('/')
def index():
    """主页，显示考试列表"""
    return render_template('index.html')

@app.route('/api/students')
def get_students():
    """获取所有学生信息"""
    all_students = []

    # 获取所有考试
    exams = get_all_exams()

    # 获取每个考试的学生
    for exam in exams:
        exam_id = exam['id']
        students = get_exam_students(exam_id)

        for student_id, student in students.items():
            # 添加考试信息
            student['exam_name'] = exam['name']
            all_students.append(student)

    return jsonify(all_students)

@app.route('/api/students/import', methods=['POST'])
def import_students():
    """导入学生名单"""
    if 'student_list' not in request.files:
        return jsonify({"status": "error", "message": "未找到文件"}), 400

    file = request.files['student_list']
    exam_id = request.form.get('exam_id')

    if not file or not exam_id:
        return jsonify({"status": "error", "message": "参数不完整"}), 400

    try:
        # 获取Redis连接
        client = get_redis()

        # 读取文件内容
        content = file.read().decode('utf-8')
        # 按行分割并去除空行
        names = [name.strip() for name in content.splitlines() if name.strip()]
        imported_count = 0

        for name in names:
            # 生成学生ID
            student_id = client.incr(f'exam:{exam_id}:student_id_counter')
            student_key = f'exam:{exam_id}:student:{student_id}'

            # 检查学生是否已存在
            if not client.exists(student_key):
                # 创建新学生记录
                student_data = {
                    'id': str(student_id),
                    'username': name,
                    'exam_id': exam_id,
                    'status': 'offline',
                    'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }

                # 存储学生数据
                client.hmset(student_key, student_data)
                imported_count += 1

        return jsonify({
            "status": "success",
            "message": f"成功导入 {imported_count} 名学生",
            "imported_count": imported_count
        })

    except Exception as e:
        print(f"导入学生失败: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"导入失败：{str(e)}"
        }), 500

@app.route('/api/violations')
def get_violations_api():
    """获取所有异常记录"""
    return jsonify(get_violations())

@app.route('/api/login', methods=['POST'])
def student_login():
    """学生登录"""
    if not request.is_json:
        return jsonify({"status": "error", "message": "Invalid request format"}), 400

    client = get_redis()
    data = request.json
    username = data.get('username')
    ip = request.remote_addr
    exam_id = data.get('exam_id')  # 可选：考试ID
    student_id = data.get('id')    # 可选：学生ID（用于重连）

    if not username:
        return jsonify({"status": "error", "message": "Missing username"}), 400

    # 更新所有考试状态
    update_exam_status()

    # 如果提供了学生ID，尝试直接重连
    if student_id:
        # 查找该学生ID是否存在于任何考试中
        found = False
        exams = get_all_exams()
        for exam in exams:
            exam_id_check = exam['id']
            student_key = f'exam:{exam_id_check}:student:{student_id}'
            if client.exists(student_key):
                # 验证用户名是否匹配
                stored_username = client.hget(student_key, 'username')
                if stored_username and stored_username == username:
                    found = True
                    exam_id = exam_id_check
                    break

        if found:
            # 更新学生状态
            student_key = f'exam:{exam_id}:student:{student_id}'
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            student_data = {
                'ip': ip,
                'last_active': timestamp,
                'status': 'online'
            }
            client.hmset(student_key, student_data)

            # 获取考试信息
            exam = get_exam(exam_id)
            print(f"进程 {os.getpid()}: 学生重连: {username} (ID: {student_id}) 考试: {exam_id} ({exam['name']}) IP: {ip}")

            # 登录时记录
            login_record = {
                "type": "login",
                "timestamp": timestamp,
                "ip": ip
            }
            client.rpush(f"exam:{exam_id}:student:{student_id}:logins", json.dumps(login_record))

            return jsonify({
                "status": "success",
                "message": f"成功重连到考试: {exam['name']}",
                "exam_id": exam_id,
                "student_id": student_id,
                "exam_name": exam['name'],
                "start_time": exam['start_time'],
                "end_time": exam['end_time'],
                "default_url": exam.get('default_url', "about:blank"),
                'delay_min': exam.get('delay_min', 0) 
            })

    # 如果没有提供考试ID或重连失败，则查找学生所在的考试
    if not exam_id:
        student_exams = find_student_in_exams(username)

        if not student_exams:
            return jsonify({
                "status": "error",
                "message": "未找到您参加的考试，或考试尚未开始"
            }), 404

        # 如果找到多个考试，返回考试列表供选择
        if len(student_exams) > 1:
            return jsonify({
                "status": "choice_required",
                "message": "您有多个正在进行的考试，请选择一个",
                "exams": student_exams
            })

        # 如果只找到一个考试，自动选择
        exam_id = student_exams[0]['exam_id']
        student_id = student_exams[0]['student_id']
    else:
        # 验证考试是否存在且在进行中
        exam = get_exam(exam_id)
        if not exam:
            return jsonify({"status": "error", "message": "考试不存在"}), 404

        if exam['status'] != 'active':
            return jsonify({"status": "error", "message": "考试尚未开始或已结束"}), 403

        # 在考试中查找学生
        students = get_exam_students(exam_id)
        student_id = None

        for sid, student in students.items():
            if student['username'] == username:
                student_id = sid
                break

        if not student_id:
            return jsonify({"status": "error", "message": "您不在此考试的学生名单中"}), 403

    # 使用Redis事务确保原子性
    with client.pipeline() as pipe:
        try:
            student_key = f'exam:{exam_id}:student:{student_id}'
            pipe.watch(student_key)

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            student_data = {
                'id': student_id,
                'username': username,
                'ip': ip,
                'exam_id': exam_id,
                'login_time': timestamp,
                'last_active': timestamp,
                'status': 'online'
            }

            pipe.multi()
            pipe.hmset(student_key, student_data)
            pipe.execute()

            # 获取考试信息
            exam = get_exam(exam_id)

            print(f"进程 {os.getpid()}: 学生登录: {username} (ID: {student_id}) 考试: {exam_id} ({exam['name']}) IP: {ip}")

            # 登录时记录
            login_record = {
                "type": "login",
                "timestamp": timestamp,
                "ip": ip
            }
            client.rpush(f"exam:{exam_id}:student:{student_id}:logins", json.dumps(login_record))

            return jsonify({
                "status": "success",
                "message": f"成功登录考试: {exam['name']}",
                "exam_id": exam_id,
                "student_id": student_id,
                "exam_name": exam['name'],
                "start_time": exam['start_time'],
                "end_time": exam['end_time'],
                "default_url": exam.get('default_url', "about:blank"),
                'delay_min': exam.get('delay_min', 0) 
            })
        except redis.WatchError:
            return jsonify({"status": "error", "message": "登录冲突，请重试"}), 409
        except Exception as e:
            print(f"学生登录失败: {str(e)}")
            return jsonify({"status": "error", "message": f"登录失败: {str(e)}"}), 500

@app.route('/api/heartbeat', methods=['POST'])
def heartbeat():
    """客户端心跳"""
    if not request.is_json:
        return jsonify({"status": "error", "message": "Invalid request format"}), 400

    data = request.json
    student_id = data.get('student_id')
    exam_id = data.get('exam_id')

    if not student_id or not exam_id:
        return jsonify({"status": "error", "message": "Missing student_id or exam_id"}), 400

    client = get_redis()  # 获取Redis连接

    # 检查学生是否存在
    student_key = f'exam:{exam_id}:student:{student_id}'
    if not client.exists(student_key):
        return jsonify({"status": "error", "message": "Unknown student or exam"}), 404

    # 更新最后活跃时间
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    client.hset(student_key, 'last_active', timestamp)

    # 如果学生状态不是online，则更新为online
    student_status = client.hget(student_key, 'status')
    if student_status != 'online':
        client.hset(student_key, 'status', 'online')
        print(f"学生状态更新: ID={student_id}, 考试={exam_id}, {student_status} -> online")

    return jsonify({"status": "success"})

@app.route('/api/logout', methods=['POST'])
def student_logout():
    """学生登出"""
    if not request.is_json:
        return jsonify({"status": "error", "message": "Invalid request format"}), 400

    data = request.json
    student_id = data.get('student_id')
    exam_id = data.get('exam_id')

    if not student_id or not exam_id:
        return jsonify({"status": "error", "message": "Missing student_id or exam_id"}), 400

    client = get_redis()  # 获取Redis连接

    # 更新学生状态
    student_key = f'exam:{exam_id}:student:{student_id}'
    if client.exists(student_key):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        client.hset(student_key, 'status', 'offline')
        client.hset(student_key, 'logout_time', timestamp)

        student_data = client.hgetall(student_key)
        print(f"学生登出: {student_data['username']} (ID: {student_id}, 考试: {exam_id})")

        # 登出时记录
        logout_record = {
            "type": "logout",
            "timestamp": timestamp,
            "ip": request.remote_addr
        }
        client.rpush(f"exam:{exam_id}:student:{student_id}:logins", json.dumps(logout_record))

        return jsonify({
            "status": "success",
            "message": "成功退出考试"
        })
    else:
        return jsonify({
            "status": "error",
            "message": "未找到学生记录"
        }), 404

@app.route('/api/violation', methods=['POST'])
def report_violation():
    """报告异常"""
    # 接收文件和表单数据
    screenshot = request.files.get('screenshot')
    student_id = request.form.get('student_id')
    exam_id = request.form.get('exam_id')
    username = request.form.get('username')
    reason = request.form.get('reason')
    timestamp = request.form.get('timestamp')

    if not screenshot or not student_id or not exam_id or not username or not reason:
        return jsonify({"status": "error", "message": "Missing violation information"}), 400

    client = get_redis()  # 获取Redis连接

    # 保存截图
    filename = f"{username}-{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    screenshot_path = os.path.join(SCREENSHOTS_DIR, filename)
    screenshot.save(screenshot_path)

    # 记录异常
    violation_id = client.incr('violation_id_counter')
    violation = {
        'id': violation_id,
        'student_id': student_id,
        'exam_id': exam_id,
        'username': username,
        'reason': reason,
        'timestamp': timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'screenshot_url': f"/screenshots/{filename}",
        'ip': request.remote_addr
    }

    # 将违规记录添加到全局违规列表
    client.rpush('violations', json.dumps(violation))

    # 将违规记录添加到考试特定的违规列表
    violation_key = f'exam:{exam_id}:violations'
    client.rpush(violation_key, json.dumps(violation))

    print(f"异常记录: 学生 {username} (ID: {student_id}) 考试: {exam_id} - {reason}")
    return jsonify({
        "status": "success",
        "message": "违规记录已提交",
        "violation_id": violation_id
    })

@app.route('/screenshots/<filename>')
def serve_screenshot(filename):
    """提供截图文件"""
    return send_from_directory(SCREENSHOTS_DIR, filename)

@app.route('/api/config')
def get_config():
    """获取服务器配置信息"""
    try:
        # 检查配置文件是否存在
        if not os.path.exists(CONFIG_FILE):
            return jsonify({"status": "error", "message": "Configuration file not found"}), 404

        # 读取配置文件
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # 返回配置信息
        return jsonify({"status": "success", "config": config})
    except Exception as e:
        print(f"获取配置信息时出错: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# 新增考试管理API
@app.route('/api/exams', methods=['GET', 'POST'])
def manage_exams():
    """考试管理"""
    if request.method == 'GET':
        return jsonify(get_all_exams())

    if request.method == 'POST':
        try:
            # 打印请求信息，用于调试
            print(f"请求内容类型: {request.content_type}")
            print(f"表单数据: {request.form}")
            print(f"文件: {request.files}")

            # 获取表单数据
            name = request.form.get('name')
            start_time = request.form.get('start_time')
            end_time = request.form.get('end_time')
            default_url = request.form.get('default_url')
            delay_min = request.form.get('delay_min')

            print(f"获取到的参数: name={name}, start_time={start_time}, end_time={end_time}, default_url={default_url}, delay_min={delay_min}")

            if not all([name, start_time, end_time]):
                missing = []
                if not name: missing.append('name')
                if not start_time: missing.append('start_time')
                if not end_time: missing.append('end_time')
                error_msg = f"参数不完整，缺少: {', '.join(missing)}"
                print(error_msg)
                return jsonify({"status": "error", "message": error_msg}), 400

            # 获取Redis连接
            client = get_redis()

            # 创建考试记录
            exam_id = client.incr('exam_id_counter')
            exam_config = {
                'id': exam_id,
                'name': name,
                'start_time': start_time,
                'end_time': end_time,
                'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'status': 'pending'  # pending, active, completed
            }
            if default_url:
                exam_config['default_url'] = default_url
            if delay_min:
                try:
                    exam_config['delay_min'] = int(delay_min)
                except Exception:
                    exam_config['delay_min'] = 0  # 默认1分钟

            # 存储考试配置
            client.hset(EXAM_CONFIG_KEY, exam_id, json.dumps(exam_config))

            # 处理学生名单导入
            imported_count = 0
            if 'student_list' in request.files:
                file = request.files['student_list']
                if file:
                    # 读取文件内容
                    content = file.read().decode('utf-8')
                    # 按行分割并去除空行
                    names = [name.strip() for name in content.splitlines() if name.strip()]

                    for name in names:
                        # 生成学生ID
                        student_id = client.incr(f'exam:{exam_id}:student_id_counter')
                        student_key = f'exam:{exam_id}:student:{student_id}'

                        # 创建新学生记录
                        student_data = {
                            'id': str(student_id),
                            'username': name,
                            'exam_id': str(exam_id),
                            'status': 'offline',
                            'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }

                        # 存储学生数据
                        client.hmset(student_key, student_data)
                        imported_count += 1

            message = "考试创建成功"
            if imported_count > 0:
                message += f"，已导入 {imported_count} 名学生"

            return jsonify({
                "status": "success",
                "exam_id": exam_id,
                "message": message,
                "imported_count": imported_count
            }), 200  # 使用200而不是201

        except Exception as e:
            print(f"创建考试失败: {str(e)}")
            return jsonify({
                "status": "error",
                "message": f"创建失败：{str(e)}"
            }), 500

@app.route('/api/exams/<int:exam_id>/students')
def get_exam_students_api(exam_id):
    """获取指定考试的学生信息"""
    return jsonify(list(get_exam_students(exam_id).values()))

@app.route('/api/exams/<int:exam_id>/violations')
def get_exam_violations_api(exam_id):
    """获取指定考试的违规记录"""
    return jsonify(get_exam_violations(exam_id))

@app.route('/api/exams/<int:exam_id>', methods=['DELETE'])
def delete_exam(exam_id):
    """删除考试"""
    try:
        client = get_redis()

        # 检查考试是否存在
        if not client.hexists(EXAM_CONFIG_KEY, exam_id):
            return jsonify({"status": "error", "message": "考试不存在"}), 404

        # 获取考试信息
        exam_data = client.hget(EXAM_CONFIG_KEY, exam_id)
        exam = json.loads(exam_data) if exam_data else None

        # 如果考试正在进行中，不允许删除
        #if exam and exam['status'] == 'active':
        #    return jsonify({"status": "error", "message": "无法删除正在进行中的考试"}), 400

        # 删除考试配置
        client.hdel(EXAM_CONFIG_KEY, exam_id)

        # 删除考试相关的学生数据
        student_keys = client.keys(f'exam:{exam_id}:student:*')
        if student_keys:
            client.delete(*student_keys)

        # 删除考试相关的违规记录
        violation_key = f'exam:{exam_id}:violations'
        if client.exists(violation_key):
            client.delete(violation_key)

        # 删除考试相关的计数器
        counter_key = f'exam:{exam_id}:student_id_counter'
        if client.exists(counter_key):
            client.delete(counter_key)

        print(f"考试已删除: ID={exam_id}, 名称={exam['name'] if exam else '未知'}")
        return jsonify({"status": "success", "message": "考试已成功删除"})

    except Exception as e:
        print(f"删除考试失败: {str(e)}")
        return jsonify({"status": "error", "message": f"删除失败：{str(e)}"}), 500

# 长时间不活跃的学生清理任务
def cleanup_inactive_students():
    """清理长时间不活跃的学生（自动登出）"""
    while True:
        time.sleep(60)  # 每分钟检查一次
        try:
            client = get_redis()
            now = datetime.now()

            # 获取所有考试
            exams = get_all_exams()

            # 对每个考试的学生进行检查
            for exam in exams:
                exam_id = exam['id']
                students = get_exam_students(exam_id)

                for student_id, student in students.items():
                    if student['status'] == 'online' and 'last_active' in student:
                        last_active = datetime.strptime(student['last_active'], "%Y-%m-%d %H:%M:%S")
                        inactive_minutes = (now - last_active).total_seconds() / 60

                        # 如果超过5分钟没有活动，自动登出
                        if inactive_minutes > 5:
                            student_key = f'exam:{exam_id}:student:{student_id}'
                            timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
                            client.hset(student_key, 'status', 'offline')
                            client.hset(student_key, 'logout_time', timestamp)
                            # 写入logout历史
                            logout_record = {
                                "type": "logout",
                                "timestamp": timestamp,
                                "ip": student.get('ip', 'unknown')
                            }
                            client.rpush(f"exam:{exam_id}:student:{student_id}:logins", json.dumps(logout_record))
                            print(f"进程 {os.getpid()}: 学生 {student['username']} (ID: {student_id}, 考试: {exam_id}) 长时间无心跳，自动登出")
        except Exception as e:
            print(f"进程 {os.getpid()}: 清理不活跃学生时出错: {str(e)}")

# 考试状态更新任务
def update_exam_status_task():
    """定期更新考试状态的任务"""
    while True:
        time.sleep(30)  # 每30秒检查一次
        try:
            updated_count = update_exam_status()
            if updated_count > 0:
                print(f"进程 {os.getpid()}: 已更新 {updated_count} 个考试的状态")
        except Exception as e:
            print(f"进程 {os.getpid()}: 更新考试状态时出错: {str(e)}")

# 启动后台任务线程
def start_background_tasks():
    """启动所有后台任务线程"""
    # 启动学生清理线程
    inactive_thread = threading.Thread(target=cleanup_inactive_students)
    inactive_thread.daemon = True
    inactive_thread.start()
    print(f"进程 {os.getpid()}: 学生清理线程已启动")

    # 启动考试状态更新线程
    exam_status_thread = threading.Thread(target=update_exam_status_task)
    exam_status_thread.daemon = True
    exam_status_thread.start()
    print(f"进程 {os.getpid()}: 考试状态更新线程已启动")

@app.route('/api/screenshot', methods=['POST'])
def upload_screenshot():
    """接收客户端定时上传的屏幕截图"""
    screenshot = request.files.get('screenshot')
    student_id = request.form.get('student_id')
    exam_id = request.form.get('exam_id')
    username = request.form.get('username')
    timestamp = request.form.get('timestamp') or datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    if not screenshot or not student_id or not exam_id or not username:
        return jsonify({"status": "error", "message": "Missing screenshot information"}), 400

    # 保存截图文件
    filename = f"screenshot_{student_id}_{exam_id}_{timestamp.replace(' ', '_').replace(':', '-')}.png"
    screenshot_path = os.path.join(SCREENSHOTS_DIR, filename)
    screenshot.save(screenshot_path)

    # 记录到Redis
    client = get_redis()
    key = f"exam:{exam_id}:student:{student_id}:screenshots"
    client.rpush(key, filename)

    return jsonify({"status": "success", "message": "截图已上传", "filename": filename})

@app.route('/api/exams/<int:exam_id>/students/<student_id>/screenshots')
def get_student_screenshots(exam_id, student_id):
    """获取指定考生的所有截图文件URL"""
    client = get_redis()
    key = f"exam:{exam_id}:student:{student_id}:screenshots"
    files = client.lrange(key, 0, -1)
    urls = [f"/screenshots/{fname}" for fname in files]
    return jsonify({"screenshots": urls})

@app.route('/api/exams/<int:exam_id>/students/<student_id>/logins')
def get_student_logins(exam_id, student_id):
    client = get_redis()
    key = f"exam:{exam_id}:student:{student_id}:logins"
    records = client.lrange(key, 0, -1)
    return jsonify([json.loads(r) for r in records])

if __name__ == '__main__':
    try:
        # 配置Redis持久化
        configure_redis_persistence()

        # 启动后台任务线程
        start_background_tasks()

        # 启动服务器
        print(f"进程 {os.getpid()}: 考试监控服务器启动在 http://0.0.0.0:5000/")
        app.run(host='0.0.0.0', port=5000, debug=True)  # 启用debug模式以查看错误信息
    except Exception as e:
        print(f"进程 {os.getpid()}: 服务器启动失败: {str(e)}")
        cleanup_redis()



