#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
考试监控服务器
用于接收和显示学生状态和异常信息

数据持久化策略:
- 学生实时状态（online/offline/logout 等）保存在 Redis，用于快速查询与心跳更新。
- 学生的登录、掉线(offline)、上线(online)、退出(logout) 等活动事件写入数据库，形成可审计的历史记录。
"""

import os
import json
import time
import signal
import atexit
import threading
from datetime import datetime, timedelta
from flask import Flask, request, render_template, jsonify, send_from_directory, send_file, current_app
from flask_cors import CORS
from data_access import DataAccess
from celery_tasks import merge_videos_task

# 配置文件路径
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

# 全局变量，将在 create_app() 中初始化
DATA_DIR = None


def get_real_ip():
    """
    获取客户端真实IP地址
    优先从nginx反向代理头部获取，回退到remote_addr
    """
    # 1. 优先从 X-Real-IP 获取（nginx单层代理推荐）
    real_ip = request.headers.get('X-Real-IP')
    if real_ip:
        return real_ip

    # 2. 从 X-Forwarded-For 获取（多层代理场景）
    forwarded_for = request.headers.get('X-Forwarded-For')
    if forwarded_for:
        # X-Forwarded-For: client, proxy1, proxy2
        # 取第一个IP（客户端IP）
        return forwarded_for.split(',')[0].strip()

    # 3. 回退到直连IP
    return request.remote_addr


# 创建Flask应用
def create_app():
    global DATA_DIR
    
    app = Flask(__name__)

    # 初始化 DATA_DIR（从配置文件读取，支持相对/绝对路径）
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
        config_data_dir = config.get('data_dir', './server_data')
        # 如果是相对路径，转换为绝对路径（相对于脚本目录）
        if not os.path.isabs(config_data_dir):
            DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), config_data_dir)
        else:
            DATA_DIR = config_data_dir
    except Exception as e:
        print(f"读取配置文件失败，使用默认路径: {e}")
        DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server_data")

    # 确保数据目录存在
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        print(f"已创建数据目录: {DATA_DIR}")
    else:
        print(f"数据目录: {DATA_DIR}")

    # 设置文件上传配置
    app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB 最大文件大小
    app.config['UPLOAD_FOLDER'] = DATA_DIR

    # 禁用模板和静态文件缓存（方便开发调试）
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

    # 启用 CORS 支持，允许跨域请求
    CORS(app, resources={
        r"/api/*": {
            "origins": "*",  # 允许所有来源，生产环境建议指定具体域名
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })

    app.data_access = DataAccess()
    # MergeManager 已迁移到 Celery 任务，不再需要在这里创建
    return app

app = create_app()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/student_management')
def student_management():
    return render_template('student_management.html')

@app.route('/monitor_login')
def monitor_login():
    """监控登录页面"""
    return render_template('monitor_login.html')

@app.route('/monitor/<int:exam_id>')
def monitor_page(exam_id):
    """监控页面（仅查看权限）"""
    # 验证考试是否存在
    exam = current_app.data_access.get_exam(exam_id)
    if not exam:
        return "考试不存在", 404

    return render_template('monitor.html', exam_id=exam_id)

@app.route('/api/monitor/login', methods=['POST'])
def monitor_login_api():
    """监控密码验证API"""
    if not request.is_json:
        return jsonify({"status": "error", "message": "Invalid request format"}), 400

    data = request.json
    password = data.get('monitor_password')

    if not password:
        return jsonify({"status": "error", "message": "Missing password"}), 400

    # 查找具有该密码的考试
    conn = current_app.data_access.get_connection()
    try:
        with conn.cursor(dictionary=True) as cursor:
            cursor.execute(
                "SELECT id, name FROM exams WHERE monitor_password = %s AND status = 'active' LIMIT 1",
                (password,)
            )
            exam = cursor.fetchone()

            if exam:
                return jsonify({
                    "status": "success",
                    "exam_id": exam['id'],
                    "exam_name": exam['name']
                })
            else:
                return jsonify({
                    "status": "error",
                    "message": "密码错误或考试未在进行中"
                }), 401
    finally:
        conn.close()

@app.route('/api/students/import', methods=['POST'])
def import_students():
    """导入学生到指定考试，支持文本输入和文件上传两种方式"""
    exam_id = request.form.get('exam_id')
    import_type = request.form.get('import_type', 'file')  # 默认为文件方式

    if not exam_id:
        return jsonify({"status": "error", "message": "缺少考试ID"}), 400

    try:
        students = []

        if import_type == 'text':
            # 文本输入方式
            student_list_text = request.form.get('student_list_text', '').strip()
            if not student_list_text:
                return jsonify({"status": "error", "message": "学生名单不能为空"}), 400

            # 解析文本，格式：学号 姓名
            for line in student_list_text.splitlines():
                parts = line.strip().split()
                if len(parts) >= 2:
                    student_id, student_name = parts[0], ' '.join(parts[1:])
                    students.append({'student_id': student_id, 'student_name': student_name})
                elif len(parts) == 1:
                    # 只有姓名，自动生成学号
                    student_name = parts[0]
                    students.append({'student_id': None, 'student_name': student_name})

        elif import_type == 'file':
            # 文件上传方式
            if 'student_list_file' not in request.files:
                return jsonify({"status": "error", "message": "未找到文件"}), 400

            file = request.files['student_list_file']
            if not file:
                return jsonify({"status": "error", "message": "文件不能为空"}), 400

            # 读取文件内容
            file_content = file.read().decode('utf-8').strip()
            if not file_content:
                return jsonify({"status": "error", "message": "文件内容为空"}), 400

            # 解析文件内容，格式：学号 姓名
            for line in file_content.splitlines():
                parts = line.strip().split()
                if len(parts) >= 2:
                    student_id, student_name = parts[0], ' '.join(parts[1:])
                    students.append({'student_id': student_id, 'student_name': student_name})
                elif len(parts) == 1:
                    # 只有姓名，自动生成学号
                    student_name = parts[0]
                    students.append({'student_id': None, 'student_name': student_name})

        else:
            return jsonify({"status": "error", "message": "不支持的导入类型"}), 400

        if not students:
            return jsonify({"status": "error", "message": "没有找到有效的学生数据"}), 400

        # 导入学生到考试
        imported_count = import_students_to_exam(exam_id, students)

        return jsonify({
            "status": "success",
            "message": f"成功导入 {imported_count} 名学生",
            "imported_count": imported_count,
            "total_parsed": len(students)
        })

    except Exception as e:
        print(f"导入学生失败: {str(e)}")
        return jsonify({"status": "error", "message": f"导入失败：{str(e)}"}), 500


@app.route('/api/students', methods=['GET'])
def get_all_students():
    """获取所有学生列表"""
    try:
        students = current_app.data_access.get_all_students_from_table()
        return jsonify({"status": "success", "students": students})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/students/batch', methods=['POST'])
def batch_create_students():
    """批量创建学生"""
    if not request.is_json:
        return jsonify({"status": "error", "message": "Invalid request format"}), 400

    data = request.json
    students = data.get('students', [])

    if not students:
        return jsonify({"status": "error", "message": "Missing students data"}), 400

    try:
        created_students = []
        errors = []

        for student_data in students:
            student_name = student_data.get('student_name')
            student_id = student_data.get('student_id')

            if not student_name or student_id:
                errors.append(f"学生姓名不能为空: {student_data}")
                continue

            try:
                created_id = current_app.data_access.create_student(student_name, student_id)
                created_students.append({
                    "student_id": created_id,
                    "student_name": student_name
                })
            except Exception as e:
                errors.append(f"创建学生 {student_name} 失败: {str(e)}")

        return jsonify({
            "status": "success",
            "message": f"批量创建完成，成功: {len(created_students)}, 失败: {len(errors)}",
            "created_students": created_students,
            "errors": errors
        })
    except Exception as e:
        return jsonify({"status": "error", "message": f"批量创建失败: {str(e)}"}), 500

@app.route('/api/students/<student_id>', methods=['GET'])
def get_student_by_id(student_id):
    """根据学号获取学生信息"""
    try:

        # 通过get_student_name_by_id方法查找（包含兼容性处理）
        student_name = current_app.data_access.get_student_name_by_id(student_id)
        if student_name:
            return jsonify({
                "status": "success",
                "student_id": student_id,
                "student_name": student_name
            })
        else:
            return jsonify({
                "status": "error",
                "message": "未找到该学号对应的学生"
            }), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/login', methods=['POST'])
def login():
    """使用学号和姓名进行登录"""
    if not request.is_json:
        return jsonify({"status": "error", "message": "Invalid request format"}), 400

    data = request.json
    student_id = data.get('student_id')
    student_name = data.get('student_name')
    ip = get_real_ip()

    if not student_id or not student_name:
        return jsonify({"status": "error", "message": "Missing student_id or student_name"}), 400

    current_app.data_access.refresh_exam_status()
    try:
        # 通过SQL查询获取学生参加的正在进行的考试
        exam = current_app.data_access.get_student_active_exams(student_id)

        if not exam:
            return jsonify({
                "status": "error",
                "message": "当前没有进行中的考试，请联系管理员"
            }), 400

        exam_id = exam['id']

        # 处理学生登录
        result = current_app.data_access.handle_student_login(student_name, exam_id, student_id, ip)

        if result.get('status') == 'success':
            # 为学生创建专用的截图目录
            student_screenshot_dir = os.path.join(DATA_DIR, str(exam_id), "screenshots", str(student_id))
            if not os.path.exists(student_screenshot_dir):
                os.makedirs(student_screenshot_dir)

            # 为学生创建专用的录屏目录
            student_recording_dir = os.path.join(DATA_DIR, str(exam_id), "recordings", str(student_id))
            if not os.path.exists(student_recording_dir):
                os.makedirs(student_recording_dir)

            # 记录 Redis 实时状态（向上层屏蔽 Redis 细节）
            try:
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                current_app.data_access.set_student_realtime_status(
                    exam_id, student_id, username=student_name, status='online', ip=ip, last_seen=now
                )
            except Exception as e:
                print(f"登录实时状态更新失败: {e}")

            # 登录历史记录已在 handle_student_login 方法中处理，无需重复记录

            # 返回完整的考试和学生信息
            return jsonify({
                "status": "success",
                "message": "登录成功",
                "exam_id": exam_id,
                "student_id": student_id,
                "exam_name": exam.get('name'),
                "start_time": exam.get('start_time'),
                "end_time": exam.get('end_time'),
                "default_url": exam.get('default_url'),
                "delay_min": exam.get('delay_min', 0),
                "disable_new_tabs": exam.get('disable_new_tabs', False)
            })
        else:
            return jsonify(result), 400
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"登录处理失败: {str(e)}"
        }), 500

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

    # 检查学生是否存在
    student_key = f'exam:{exam_id}:student:{student_id}'
    if not current_app.data_access.exists(student_key):
        return jsonify({"status": "error", "message": "Unknown student or exam"}), 404

    # 更新活跃（封装：DB + Redis + 上线历史）
    current_app.data_access.mark_online_activity(student_id, exam_id, ip=get_real_ip())

    # 构建响应,检查是否有考试配置变更需要通知客户端
    response = {"status": "success"}

    # 检查Redis中是否有考试配置变更标记
    r = current_app.data_access._get_redis()

    # 检查结束时间是否变更
    end_time_changed_key = f'exam:{exam_id}:end_time_changed'
    new_end_time = r.get(end_time_changed_key)
    if new_end_time:
        # 解码并返回新的结束时间(已经是ISO格式)
        if isinstance(new_end_time, bytes):
            new_end_time = new_end_time.decode('utf-8')
        response['end_time'] = new_end_time

    # 未来可以扩展其他配置变更,例如:
    # disable_new_tabs_key = f'exam:{exam_id}:disable_new_tabs_changed'
    # new_disable_new_tabs = r.get(disable_new_tabs_key)
    # if new_disable_new_tabs:
    #     response['disable_new_tabs'] = new_disable_new_tabs.decode('utf-8')

    return jsonify(response)

@app.route('/api/logout', methods=['POST'])
def student_logout():
    """学生登出"""
    if not request.is_json:
        return jsonify({"status": "error", "message": "Invalid request format"}), 400

    data = request.json
    student_id = data.get('student_id')
    exam_id = data.get('exam_id')
    ip = get_real_ip()

    if not student_id or not exam_id:
        return jsonify({"status": "error", "message": "Missing student_id or exam_id"}), 400

    try:
        # 获取学生考试记录
        student_exam = current_app.data_access.get_student_exam(student_id, exam_id)
        if student_exam:
            # 更新学生状态为离线
            current_app.data_access.update_student_status(student_id, exam_id, 'logout')

            # 添加登出历史记录
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            current_app.data_access.add_login_history(student_exam['id'], 'logout', timestamp, ip)

            print(f"学生登出: ID={student_id}, 考试={exam_id}, 时间={timestamp}")

            # 更新 Redis 实时状态（通过 DataAccess 封装）
            current_app.data_access.set_student_realtime_status(exam_id, student_id, status='logout')

        # 检查本地是否有该学生的视频片段
        student_recordings_dir = os.path.join(DATA_DIR, str(exam_id), "recordings", str(student_id))
        has_local_videos = False

        if os.path.exists(student_recordings_dir):
            files = [f for f in os.listdir(student_recordings_dir)
                     if f.lower().endswith(('.mp4', '.webm', '.avi', '.mov', '.mkv'))]
            has_local_videos = len(files) > 0

        if has_local_videos:
            # 本地有视频片段，提交到 Celery 任务队列进行合并
            student_name = data.get('username', f"student_{student_id}")
            merge_videos_task.delay(
                exam_id=exam_id,
                student_id=student_id,
                student_name=student_name,
                data_dir=DATA_DIR
            )
            print(f"本地有 {len(files)} 个视频片段，已提交 Celery 合并任务: exam_id={exam_id}, student_id={student_id}")
        else:
            # 本地无视频片段，转发退出请求到远程服务器
            print(f"本地无视频片段，转发退出请求到远程服务器: student_id={student_id}")
            try:
                import requests
                REMOTE_SERVER = 'http://10.188.2.252:5000'
                response = requests.post(
                    f'{REMOTE_SERVER}/api/logout',
                    json=data,  # 转发完整的退出请求
                    timeout=3
                )
                if response.status_code == 200:
                    print(f"退出请求已成功转发到远程服务器: {student_id}")
                else:
                    print(f"转发退出请求失败: HTTP {response.status_code}")
            except Exception as e:
                print(f"转发退出请求异常: {e}")

    except Exception as e:
        print(f"学生登出处理异常: {e}")

    return jsonify({
        "status": "success",
        "message": "成功退出考试"
    })

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

    # 保存截图
    filename = f"{student_id}-{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"

    # 创建违规截图目录
    violations_dir = os.path.join(DATA_DIR, str(exam_id), "violations")
    if not os.path.exists(violations_dir):
        os.makedirs(violations_dir)
    screenshot_path = os.path.join(violations_dir, filename)
    screenshot.save(screenshot_path)

    # 记录异常
    violation_id = current_app.data_access.add_violation({
        'student_id': student_id,
        'exam_id': exam_id,
        'username': username,
        'reason': reason,
        'timestamp': timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'screenshot_path': os.path.join(str(exam_id), "violations", filename),
        'ip': get_real_ip()
    })

    print(f"异常记录: 学生 {username} (ID: {student_id}) 考试: {exam_id} - {reason}")
    return jsonify({
        "status": "success",
        "message": "违规记录已提交",
        "violation_id": violation_id
    })

@app.route('/<int:exam_id>/screenshots/<filename>')
def serve_screenshot(exam_id, filename):
    """提供截图文件（兼容旧格式）"""
    try:
        # 验证考试是否存在
        exam = current_app.data_access.get_exam(exam_id)
        if not exam:
            return jsonify({"status": "error", "message": "考试不存在"}), 404

        # 构建截图文件目录路径
        screenshots_path = os.path.join(DATA_DIR, str(exam_id), "screenshots")

        # 检查目录是否存在
        if not os.path.exists(screenshots_path):
            return jsonify({"status": "error", "message": "截图目录不存在"}), 404

        # 检查文件是否存在
        file_path = os.path.join(screenshots_path, filename)
        if not os.path.exists(file_path):
            return jsonify({"status": "error", "message": "截图文件不存在"}), 404

        return send_from_directory(screenshots_path, filename)

    except Exception as e:
        return jsonify({"status": "error", "message": f"获取截图文件失败: {str(e)}"}), 500

@app.route('/<int:exam_id>/screenshots/<student_id>/<filename>')
def serve_student_screenshot(exam_id, student_id, filename):
    """提供学生专用目录的截图文件"""
    try:
        # 验证考试是否存在
        exam = current_app.data_access.get_exam(exam_id)
        if not exam:
            return jsonify({"status": "error", "message": "考试不存在"}), 404

        # 构建学生截图文件目录路径
        student_screenshots_path = os.path.join(DATA_DIR, str(exam_id), "screenshots", str(student_id))

        # 检查目录是否存在
        if not os.path.exists(student_screenshots_path):
            return jsonify({"status": "error", "message": "学生截图目录不存在"}), 404

        # 检查文件是否存在
        file_path = os.path.join(student_screenshots_path, filename)
        if not os.path.exists(file_path):
            return jsonify({"status": "error", "message": "截图文件不存在"}), 404

        return send_from_directory(student_screenshots_path, filename)

    except Exception as e:
        return jsonify({"status": "error", "message": f"获取学生截图文件失败: {str(e)}"}), 500


@app.route('/<int:exam_id>/violations/<filename>')
def serve_violation_screenshot(exam_id, filename):
    """提供违规截图文件"""
    try:
        # 验证考试是否存在
        exam = current_app.data_access.get_exam(exam_id)
        if not exam:
            return jsonify({"status": "error", "message": "考试不存在"}), 404

        # 构建违规截图文件目录路径
        violations_path = os.path.join(DATA_DIR, str(exam_id), "violations")

        # 检查目录是否存在
        if not os.path.exists(violations_path):
            return jsonify({"status": "error", "message": "违规截图目录不存在"}), 404

        # 检查文件是否存在
        file_path = os.path.join(violations_path, filename)
        if not os.path.exists(file_path):
            return jsonify({"status": "error", "message": "违规截图文件不存在"}), 404

        return send_from_directory(violations_path, filename)

    except Exception as e:
        return jsonify({"status": "error", "message": f"获取违规截图文件失败: {str(e)}"}), 500

@app.route('/api/config')
def get_config():
    """获取服务器配置信息"""
    try:
        # 从文件读取配置（暂时移除 Redis 缓存，统一通过 DataAccess 处理）
        if not os.path.exists(CONFIG_FILE):
            return jsonify({"status": "error", "message": "Configuration file not found"}), 404

        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)

        return jsonify({"status": "success", "config": config})
    except Exception as e:
        print(f"获取配置信息时出错: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

# 新增考试管理API
@app.route('/api/exams', methods=['GET', 'POST'])
def manage_exams():
    """考试管理"""
    if request.method == 'GET':
        return jsonify(current_app.data_access.get_all_exams())

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
            delay_min = request.form.get('delay_min', '0')

            print(f"获取到的参数: name={name}, start_time={start_time}, end_time={end_time}, default_url={default_url}, delay_min={delay_min}")

            if not all([name, start_time, end_time]):
                missing = []
                if not name: missing.append('name')
                if not start_time: missing.append('start_time')
                if not end_time: missing.append('end_time')
                error_msg = f"参数不完整，缺少: {', '.join(missing)}"
                print(error_msg)
                return jsonify({"status": "error", "message": error_msg}), 400

            # 创建考试记录
            exam_config = {
                'name': name,
                'start_time': start_time,
                'end_time': end_time,
                'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'status': 'pending'  # pending, active, completed
            }
            if default_url:
                exam_config['default_url'] = default_url
            exam_config['delay_min'] = int(delay_min)
            disable_new_tabs = request.form.get('disable_new_tabs')
            if disable_new_tabs and disable_new_tabs.lower() in ('true', 'on', '1'):
                exam_config['disable_new_tabs'] = 1
            monitor_password = request.form.get('monitor_password')
            if monitor_password:
                # 检查监控密码是否与时间重叠的其他考试冲突
                # 时间重叠判断：start_time < other_end_time AND end_time > other_start_time
                conn = current_app.data_access.get_connection()
                try:
                    with conn.cursor(dictionary=True) as cursor:
                        cursor.execute("""
                            SELECT id, name, start_time, end_time FROM exams
                            WHERE monitor_password = %s
                            AND %s < end_time
                            AND %s > start_time
                            LIMIT 1
                        """, (monitor_password, start_time, end_time))
                        conflict_exam = cursor.fetchone()

                        if conflict_exam:
                            return jsonify({
                                "status": "error",
                                "message": f"监控密码冲突：考试'{conflict_exam['name']}'（{conflict_exam['start_time']} - {conflict_exam['end_time']}）与本场考试时间重叠，不能使用相同密码。"
                            }), 400
                finally:
                    conn.close()

                exam_config['monitor_password'] = monitor_password

            student_list_text = request.form.get('student_list_text', '').strip()
            students = []
            if student_list_text:
                for line in student_list_text.splitlines():
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        student_id, student_name = parts[0], ' '.join(parts[1:])
                        students.append({'student_id': student_id, 'student_name': student_name})
            # 创建考试记录
            exam_id = current_app.data_access.add_exam(exam_config)
            imported_count = 0
            if students:
                imported_count = import_students_to_exam(exam_id, students)

            exam_dir = os.path.join(DATA_DIR, str(exam_id))
            if not os.path.exists(exam_dir):
                os.makedirs(exam_dir)
            screenshots_dir = os.path.join(exam_dir, "screenshots")
            recordings_dir = os.path.join(exam_dir, "recordings")
            violations_dir = os.path.join(exam_dir, "violations")
            if not os.path.exists(violations_dir):
                os.makedirs(violations_dir)
            if not os.path.exists(screenshots_dir):
                os.makedirs(screenshots_dir)
            if not os.path.exists(recordings_dir):
                os.makedirs(recordings_dir)

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
    """获取指定考试的学生信息，附带login_count、screenshot_count、recording_count字段"""
    students = current_app.data_access.get_exam_students(exam_id)

    # 批量获取所有学生的登录次数，避免N+1查询问题
    login_counts = current_app.data_access.get_all_students_login_count(exam_id)
    login_history_counts = current_app.data_access.get_all_students_login_history_count(exam_id)

    result = []
    for student in students:
        student_id = student['student_id']

        # 从批量查询结果中获取登录次数
        student['login_count'] = login_counts.get(student_id, 0)
        student['login_history_count'] = login_history_counts.get(student_id, 0)

        # 覆盖实时状态：Redis 优先
        try:
            rt = current_app.data_access.get_student_realtime_status(exam_id, student_id)
            if rt and rt.get('status'):
                student['status'] = rt['status']
            if rt and rt.get('last_seen'):
                student['last_active'] = rt['last_seen']
            if rt and rt.get('ip'):
                student['ip'] = rt['ip']
        except Exception as e:
            print(f"读取实时状态失败: {e}")

        # 只有已登录过的学生才查询文件数量，避免不必要的远程请求
        if student['status'] not in ['pending', '未登陆']:
            # 获取截图和录屏数量
            screenshot_count = get_student_screenshot_count(exam_id, student_id)
            recording_count = get_student_recording_count(exam_id, student_id)

            student['screenshot_count'] = screenshot_count
            student['recording_count'] = recording_count
            student['media_count'] = screenshot_count + recording_count
        else:
            # 未登录的学生，文件数量都是0
            student['screenshot_count'] = 0
            student['recording_count'] = 0
            student['media_count'] = 0

        if student['status'] == "pending":
            student['status'] = "未登陆"

        # 格式化last_active时间
        if student.get('last_active'):
            if hasattr(student['last_active'], 'strftime'):
                student['last_active'] = student['last_active'].strftime("%Y-%m-%d %H:%M:%S")
            else:
                student['last_active'] = str(student['last_active'])

        result.append(student)

    return jsonify(result)

@app.route('/api/exams/<int:exam_id>/students/<student_id>', methods=['DELETE'])
def delete_student_from_exam(exam_id, student_id):
    """删除指定考试的单个学生及其相关数据"""
    try:
        import shutil

        # 检查学生是否存在
        students = current_app.data_access.get_exam_students(exam_id)
        student_exists = any(s['student_id'] == student_id for s in students)

        if not student_exists:
            return jsonify({
                "status": "error",
                "message": f"学生 {student_id} 不存在于考试 {exam_id} 中"
            }), 404

        # 删除数据库和Redis中的学生数据
        affected = current_app.data_access.delete_student(exam_id, student_id)

        # 删除学生的录屏文件
        recording_dir = os.path.join(DATA_DIR, str(exam_id), "recordings", str(student_id))
        if os.path.exists(recording_dir):
            shutil.rmtree(recording_dir)
            print(f"已删除录屏目录: {recording_dir}")

        # 删除学生的截图文件
        screenshot_dir = os.path.join(DATA_DIR, str(exam_id), "screenshots", str(student_id))
        if os.path.exists(screenshot_dir):
            shutil.rmtree(screenshot_dir)
            print(f"已删除截图目录: {screenshot_dir}")

        print(f"学生已删除: exam_id={exam_id}, student_id={student_id}, 数据库记录数={affected}")

        return jsonify({
            "status": "success",
            "message": f"学生 {student_id} 已成功删除",
            "deleted_records": affected
        })

    except Exception as e:
        print(f"删除学生失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": f"删除学生失败: {str(e)}"
        }), 500

@app.route('/api/exams/<int:exam_id>/violations')
def get_exam_violations_api(exam_id):
    """获取指定考试的违规记录，支持分页"""
    # 获取分页参数
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 12, type=int)

    # 获取分页的违规记录和总数
    result = current_app.data_access.get_exam_violations(exam_id, page, per_page)
    return jsonify(result)



@app.route('/api/exams/<int:exam_id>', methods=['GET', 'PUT', 'DELETE'])
def manage_exam(exam_id):
    """管理单个考试：获取、更新、删除"""
    try:
        # 检查考试是否存在
        exam = current_app.data_access.get_exam(exam_id)
        if not exam:
            return jsonify({"status": "error", "message": "考试不存在"}), 404

        if request.method == 'GET':
            # 获取考试详情
            return jsonify({
                "status": "success",
                "exam": exam
            })

        elif request.method == 'PUT':
            # 更新考试信息
            try:
                # 获取表单数据
                name = request.form.get('name')
                start_time = request.form.get('start_time')
                end_time = request.form.get('end_time')
                default_url = request.form.get('default_url')
                delay_min = request.form.get('delay_min', '0')
                disable_new_tabs = request.form.get('disable_new_tabs')

                print(f"更新考试参数: name={name}, start_time={start_time}, end_time={end_time}")

                if not all([name, start_time, end_time]):
                    missing = []
                    if not name: missing.append('name')
                    if not start_time: missing.append('start_time')
                    if not end_time: missing.append('end_time')
                    error_msg = f"参数不完整，缺少: {', '.join(missing)}"
                    print(error_msg)
                    return jsonify({"status": "error", "message": error_msg}), 400

                # 构建更新数据
                update_data = {
                    'name': name,
                    'start_time': start_time,
                    'end_time': end_time,
                    'delay_min': int(delay_min) if delay_min else 0
                }

                if default_url:
                    update_data['default_url'] = default_url
                else:
                    update_data['default_url'] = None

                if disable_new_tabs and disable_new_tabs.lower() in ('true', 'on', '1'):
                    update_data['disable_new_tabs'] = 1
                else:
                    update_data['disable_new_tabs'] = 0

                monitor_password = request.form.get('monitor_password')
                if monitor_password:
                    # 检查监控密码是否与时间重叠的其他考试冲突（排除当前考试）
                    # 时间重叠判断：start_time < other_end_time AND end_time > other_start_time
                    conn = current_app.data_access.get_connection()
                    try:
                        with conn.cursor(dictionary=True) as cursor:
                            cursor.execute("""
                                SELECT id, name, start_time, end_time FROM exams
                                WHERE monitor_password = %s
                                AND %s < end_time
                                AND %s > start_time
                                AND id != %s
                                LIMIT 1
                            """, (monitor_password, start_time, end_time, exam_id))
                            conflict_exam = cursor.fetchone()

                            if conflict_exam:
                                return jsonify({
                                    "status": "error",
                                    "message": f"监控密码冲突：考试'{conflict_exam['name']}'（{conflict_exam['start_time']} - {conflict_exam['end_time']}）与本场考试时间重叠，不能使用相同密码。"
                                }), 400
                    finally:
                        conn.close()

                    update_data['monitor_password'] = monitor_password
                else:
                    update_data['monitor_password'] = None

                # 更新考试信息
                success = current_app.data_access.update_exam(exam_id, update_data)

                if success:
                    # 检查end_time是否变更(考试正在进行中时)
                    if exam['status'] == 'active' and str(exam['end_time']) != str(end_time):
                        # 设置Redis标记,通知所有在线学生
                        # 标记值直接存储ISO格式的新end_time,30分钟后自动过期
                        end_time_changed_key = f'exam:{exam_id}:end_time_changed'
                        r = current_app.data_access._get_redis()

                        # 将end_time转换为ISO格式
                        try:
                            from datetime import datetime
                            if isinstance(end_time, str):
                                dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
                            else:
                                dt = end_time
                            iso_time = dt.isoformat()
                        except:
                            iso_time = str(end_time)

                        r.setex(end_time_changed_key, 1800, iso_time)
                        print(f"[考试更新] 考试 {exam_id} 结束时间变更: {exam['end_time']} -> {end_time}, 已设置Redis标记(30分钟过期)")

                    return jsonify({
                        "status": "success",
                        "message": "考试信息更新成功"
                    })
                else:
                    return jsonify({
                        "status": "error",
                        "message": "更新考试信息失败"
                    }), 500

            except Exception as e:
                print(f"更新考试失败: {str(e)}")
                return jsonify({
                    "status": "error",
                    "message": f"更新失败：{str(e)}"
                }), 500

        elif request.method == 'DELETE':
            # 删除考试
            # 如果考试正在进行中，不允许删除
            if exam and exam['status'] == 'active':
                return jsonify({"status": "error", "message": "无法删除正在进行中的考试"}), 400

            # 删除考试配置
            current_app.data_access.delete_exam(exam_id)

            # 删除考试相关的学生数据
            current_app.data_access.delete_students_by_exam(exam_id)

            # 删除考试相关的违规记录
            current_app.data_access.delete_violations_by_exam(exam_id)

            print(f"考试已删除: ID={exam_id}, 名称={exam['name'] if exam else '未知'}")
            return jsonify({"status": "success", "message": "考试已成功删除"})

    except Exception as e:
        print(f"管理考试失败: {str(e)}")
        return jsonify({"status": "error", "message": f"操作失败：{str(e)}"}), 500


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

    # 保存截图文件到学生专用目录
    filename = f"screenshot_{timestamp.replace(' ', '_').replace(':', '-')}.png"

    # 创建学生专用的截图目录
    student_screenshot_dir = os.path.join(DATA_DIR, str(exam_id), "screenshots", str(student_id))
    if not os.path.exists(student_screenshot_dir):
        os.makedirs(student_screenshot_dir)

    screenshot_path = os.path.join(student_screenshot_dir, filename)
    screenshot.save(screenshot_path)

    # 记录活跃（封装：DB + Redis + 上线历史）
    current_app.data_access.mark_online_activity(student_id, exam_id, ip=get_real_ip())

    return jsonify({"status": "success", "message": "截图已上传", "filename": filename})

@app.route('/api/exams/<int:exam_id>/students/<student_id>/screenshots')
def get_student_screenshots(exam_id, student_id):
    """获取指定考生的截图文件URL，支持分页（直接从文件系统读取）"""
    # 获取分页参数
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    # 直接从文件系统获取截图列表
    student_screenshot_dir = os.path.join(DATA_DIR, str(exam_id), "screenshots", str(student_id))
    
    if not os.path.exists(student_screenshot_dir):
        return jsonify({"screenshots": []})
    
    try:
        # 获取所有PNG文件
        files = [f for f in os.listdir(student_screenshot_dir) 
                if f.lower().endswith('.png') and f.startswith('screenshot_')]
        # 按时间戳倒序排序
        files.sort(reverse=True)
        
        # 计算分页范围
        start = (page - 1) * per_page
        end = start + per_page
        
        # 获取指定范围的截图
        files = files[start:end]
        # 生成正确的URL格式: /{exam_id}/screenshots/{student_id}/{filename}
        urls = [f"/{exam_id}/screenshots/{student_id}/{fname}" for fname in files]

        return jsonify({"screenshots": urls})
    except Exception as e:
        print(f"获取学生截图文件失败: {e}")
        return jsonify({"screenshots": []})

@app.route('/api/exams/<int:exam_id>/students/<student_id>/logins')
def get_student_logins(exam_id, student_id):
    """获取学生登录历史记录"""
    records = current_app.data_access.get_student_logins(exam_id, student_id)
    return jsonify(records)

# 统一录屏文件API
@app.route('/api/exams/<int:exam_id>/students/<student_id>/recordings')
def get_student_recordings(exam_id, student_id):
    """获取指定考生的所有录屏文件（片段和合并后的）"""
    # 创建考试专用的录屏目录路径
    exam_recordings_dir = os.path.join(DATA_DIR, str(exam_id), "recordings")

    if not os.path.exists(exam_recordings_dir):
        return jsonify({"recordings": []})

    recordings = []


    # 获取学生姓名
    student_name = current_app.data_access.get_student_username(exam_id, student_id) # Changed to current_app.data_access
    if not student_name:
        student_name = str(student_id)

    # 1. 检查学生专用目录中的录屏片段（如果学生还在线）
    student_recordings_dir = os.path.join(exam_recordings_dir, str(student_id))
    if os.path.exists(student_recordings_dir):
        for filename in os.listdir(student_recordings_dir):
            file_path = os.path.join(student_recordings_dir, filename)

            # 检查是否是录屏片段: {student_id}_*.mp4
            if filename.startswith(f"{student_id}_") and filename.endswith(('.mp4', '.webm', '.avi')):
                file_size = os.path.getsize(file_path)
                file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                recordings.append({
                    'filename': filename,
                    'type': 'segment',  # 录屏片段
                    'file_size': file_size,
                    'created_time': file_time.isoformat(),
                    'download_url': f"/recordings/{exam_id}/{student_id}/{filename}"
                })

    # 2. 检查主目录中的合并后录屏文件
    for filename in os.listdir(exam_recordings_dir):
        file_path = os.path.join(exam_recordings_dir, filename)

        # 跳过子目录
        if os.path.isdir(file_path):
            continue

        # 检查是否是合并后的录屏: {student_name}_{exam_id}_*.mp4
        if filename.startswith(f"{student_id}_") and filename.endswith(('.mp4', '.webm', '.avi')):
            file_size = os.path.getsize(file_path)
            file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
            recordings.append({
                'filename': filename,
                'type': 'merged',  # 合并后的录屏
                'file_size': file_size,
                'created_time': file_time.isoformat(),
                'download_url': f"/recordings/{exam_id}/{filename}"
            })
    
    # 按创建时间倒序排序
    recordings.sort(key=lambda x: x['created_time'], reverse=True)
    return jsonify({"recordings": recordings})

# ChromeDriver下载API
@app.route('/driver/<path:filename>')
def download_chromedriver(filename):
    """下载chromedriver可执行文件"""
    # 假设所有chromedriver文件都放在 DATA_DIR/chromedrivers 目录下
    chromedriver_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'chromedrivers')
    #chromedriver_dir = os.path.join('/var/ftp/pub/upload','chromedrivers')
    file_path = os.path.join(chromedriver_dir, filename)
    print(file_path)
    if not os.path.exists(file_path):
        return jsonify({"status": "error", "message": f"未找到{filename}"}), 404
    # 设置Content-Disposition，建议保存为chromedriver.exe
    print("send")
    return send_file(file_path, as_attachment=True, download_name='chromedriver.exe')

@app.route('/api/server_time')
def get_server_time():
    """返回当前服务器时间"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return jsonify({"server_time": now})

# 修改上传录屏API - 支持流式上传
@app.route('/api/screen_recording', methods=['POST'])
def upload_screen_recording():
    """接收客户端上传的屏幕录制视频 - 流式处理"""
    try:
        # 检查文件大小 - 使用更保守的限制
        content_length = request.content_length
        if content_length and content_length > 200 * 1024 * 1024:  # 200MB
            return jsonify({"status": "error", "message": "文件大小超过限制(200MB)"}), 413
        
        # 获取表单数据
        student_id = request.form.get('student_id')
        exam_id = request.form.get('exam_id')
        timestamp = request.form.get('timestamp')
        sequence = request.form.get('sequence')  # 获取序号
        fps = request.form.get('fps', 10)
        quality = request.form.get('quality', 80)
        
        if not student_id or not exam_id:
            return jsonify({"status": "error", "message": "Missing student information"}), 400
        
        # 检查是否有文件上传
        if 'video' not in request.files:
            return jsonify({"status": "error", "message": "No video file provided"}), 400
        
        video_file = request.files['video']
        if not video_file or video_file.filename == '':
            return jsonify({"status": "error", "message": "No video file selected"}), 400
        
        # 检查文件名安全性
        if video_file.filename:
            # 只允许安全的文件扩展名
            allowed_extensions = {'.mp4', '.webm', '.avi', '.mov', '.mkv'}
            file_ext = os.path.splitext(video_file.filename)[1].lower()
            if file_ext not in allowed_extensions:
                return jsonify({"status": "error", "message": "不支持的文件格式"}), 400
        
        # 生成文件名
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                timestamp_str = dt.strftime("%Y%m%d_%H%M%S")
            except:
                timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        else:
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 支持多种视频格式
        original_filename = video_file.filename
        if original_filename and '.' in original_filename:
            ext = os.path.splitext(original_filename)[1]
        else:
            ext = '.mp4'  # 默认扩展名

        # 文件名格式: {student_id}_{timestamp}_seq_{序号}.mp4
        if sequence:
            filename = f"{student_id}_{timestamp_str}_seq_{int(sequence):04d}{ext}"
        else:
            # 向后兼容：如果没有序号，使用原格式
            filename = f"{student_id}_{timestamp_str}{ext}"

        # 创建学生专用的录屏目录
        student_recording_dir = os.path.join(DATA_DIR, str(exam_id), "recordings", str(student_id))
        if not os.path.exists(student_recording_dir):
            os.makedirs(student_recording_dir)

        video_path = os.path.join(student_recording_dir, filename)

        # 流式保存文件 - 避免内存问题
        try:
            # 使用流式写入，避免一次性加载到内存
            with open(video_path, 'wb') as f:
                chunk_size = 8192  # 8KB chunks
                while True:
                    chunk = video_file.stream.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    
        except Exception as save_error:
            print(f"保存视频文件失败: {save_error}")
            # 清理可能部分写入的文件
            if os.path.exists(video_path):
                try:
                    os.remove(video_path)
                except:
                    pass
            return jsonify({"status": "error", "message": "保存文件失败"}), 500
        
        # 验证文件是否保存成功
        if not os.path.exists(video_path) or os.path.getsize(video_path) == 0:
            return jsonify({"status": "error", "message": "文件保存失败"}), 500
        
        file_size = os.path.getsize(video_path)
        print(f"录屏上传成功: {filename} ({file_size} bytes)")
        
        # 录屏上传也视为活跃
        current_app.data_access.mark_online_activity(student_id, exam_id, ip=get_real_ip())

        return jsonify({
            "status": "success", 
            "message": "录屏已上传", 
            "filename": filename,
            "file_size": file_size
        })
        
    except Exception as e:
        print(f"上传录屏时发生错误: {e}")
        return jsonify({"status": "error", "message": f"服务器内部错误: {str(e)}"}), 500

@app.route('/recordings/<int:exam_id>/<filename>')
def serve_recording(exam_id, filename):
    """提供录屏文件下载 - 支持多种视频格式"""
    try:
        # 验证考试是否存在
        exam = current_app.data_access.get_exam(exam_id)
        if not exam:
            return jsonify({"status": "error", "message": "考试不存在"}), 404

        # 根据文件扩展名设置正确的MIME类型
        if filename.lower().endswith('.webm'):
            mimetype = 'video/webm'
        elif filename.lower().endswith('.mp4'):
            mimetype = 'video/mp4'
        elif filename.lower().endswith('.avi'):
            mimetype = 'video/x-msvideo'
        elif filename.lower().endswith('.mov'):
            mimetype = 'video/quicktime'
        elif filename.lower().endswith('.mkv'):
            mimetype = 'video/x-matroska'
        else:
            mimetype = 'video/mp4'  # 默认

        # 构建录屏文件目录路径
        recording_dir = os.path.join(DATA_DIR, str(exam_id), "recordings")

        # 检查目录是否存在
        if not os.path.exists(recording_dir):
            return jsonify({"status": "error", "message": "录屏目录不存在"}), 404

        # 检查文件是否存在
        file_path = os.path.join(recording_dir, filename)
        if not os.path.exists(file_path):
            return jsonify({"status": "error", "message": "录屏文件不存在"}), 404

        # 返回文件
        return send_from_directory(recording_dir, filename, mimetype=mimetype)

    except Exception as e:
        return jsonify({"status": "error", "message": f"获取录屏文件失败: {str(e)}"}), 500

@app.route('/recordings/<int:exam_id>/<student_id>/<filename>')
def serve_student_recording(exam_id, student_id, filename):
    """提供学生专用目录中的录屏文件"""
    try:
        # 验证考试是否存在
        exam = current_app.data_access.get_exam(exam_id)
        if not exam:
            return jsonify({"status": "error", "message": "考试不存在"}), 404

        # 根据文件扩展名设置正确的MIME类型
        if filename.lower().endswith('.webm'):
            mimetype = 'video/webm'
        elif filename.lower().endswith('.mp4'):
            mimetype = 'video/mp4'
        elif filename.lower().endswith('.avi'):
            mimetype = 'video/x-msvideo'
        elif filename.lower().endswith('.mov'):
            mimetype = 'video/quicktime'
        elif filename.lower().endswith('.mkv'):
            mimetype = 'video/x-matroska'
        else:
            mimetype = 'video/mp4'  # 默认

        # 构建学生录屏文件目录路径
        student_recording_dir = os.path.join(DATA_DIR, str(exam_id), "recordings", str(student_id))

        # 检查目录是否存在
        if not os.path.exists(student_recording_dir):
            return jsonify({"status": "error", "message": "学生录屏目录不存在"}), 404

        # 检查文件是否存在
        file_path = os.path.join(student_recording_dir, filename)
        if not os.path.exists(file_path):
            return jsonify({"status": "error", "message": "录屏文件不存在"}), 404

        # 返回文件
        return send_from_directory(student_recording_dir, filename, mimetype=mimetype)

    except Exception as e:
        return jsonify({"status": "error", "message": f"获取学生录屏文件失败: {str(e)}"}), 500


def import_students_to_exam(exam_id, students):
    """将学生列表导入到指定考试，返回导入人数。students为json列表，每个元素包含student_id和student_name"""
    imported_count = 0
    for stu in students:
        student_id = stu.get('student_id')
        student_name = stu.get('student_name')

        # 如果没有提供学号，自动生成
        if not student_id:
            # 生成格式：exam_id + 序号，例如：4001, 4002, 4003...
            existing_students = current_app.data_access.get_exam_students(exam_id)
            next_number = len(existing_students) + 1
            student_id = f"{exam_id}{next_number:03d}"  # 例如：4001, 4002

            # 确保生成的学号不重复
            while current_app.data_access.get_student_exam(student_id, exam_id):
                next_number += 1
                student_id = f"{exam_id}{next_number:03d}"

        # 检查是否已存在
        exists = current_app.data_access.get_student_exam(student_id, exam_id)
        if exists:
            print(f"学生 {student_id} 已存在于考试 {exam_id} 中，跳过")
            continue

        student_data = {
            'student_id': student_id,
            'student_name': student_name,
            'exam_id': exam_id,
            'status': 'pending'
        }
        current_app.data_access.add_student(student_data)
        imported_count += 1
        print(f"成功导入学生: {student_name} (ID: {student_id})")

    return imported_count

def get_student_screenshot_count(exam_id, student_id):
    """获取学生的截图文件数量（仅本地）"""
    try:
        # 检查学生专用截图目录
        student_screenshot_dir = os.path.join(DATA_DIR, str(exam_id), "screenshots", str(student_id))
        count = 0

        if os.path.exists(student_screenshot_dir):
            files = os.listdir(student_screenshot_dir)
            # 只计算图片文件
            count = len([f for f in files if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp'))])

        return count
    except Exception as e:
        print(f"获取截图数量失败: {e}")
        return 0

def get_student_recording_count(exam_id, student_id):
    """获取学生的录屏文件数量（仅本地，临时禁用远程查询以排查性能问题）"""
    try:
        count = 0

        # 1. 检查学生专用录屏目录中的片段
        student_recordings_dir = os.path.join(DATA_DIR, str(exam_id), "recordings", str(student_id))
        if os.path.exists(student_recordings_dir):
            files = os.listdir(student_recordings_dir)
            # 计算视频文件
            count += len([f for f in files if f.lower().endswith(('.mp4', '.webm', '.avi', '.mov', '.mkv'))])

        # 2. 检查主录屏目录中的合并文件
        main_recordings_dir = os.path.join(DATA_DIR, str(exam_id), "recordings")
        if os.path.exists(main_recordings_dir):
            files = os.listdir(main_recordings_dir)
            # 查找以该学生ID开头的合并文件
            merged_files = [f for f in files if f.startswith(f"{student_id}_") and f.lower().endswith(('.mp4', '.webm', '.avi', '.mov', '.mkv'))]
            count += len(merged_files)

        # 3. 如果本地没有录屏文件，尝试从远程服务器查询
        if count == 0:
            return 0  # 临时禁用远程查询以排查性能问题
            try:
                import requests
                REMOTE_SERVER = 'http://10.188.2.252:5000'
                response = requests.get(
                    f'{REMOTE_SERVER}/api/exams/{exam_id}/students/{student_id}/recordings',
                    timeout=2
                )
                if response.status_code == 200:
                    data = response.json()
                    recordings = data.get('recordings', [])
                    count = len(recordings)
            except Exception as e:
                pass  # 远程查询失败，保持count为0

        return count
    except Exception as e:
        print(f"获取录屏数量失败: {e}")
        return 0

if __name__ == '__main__':
    import sys
    try:
        # 从命令行参数获取端口，默认5000
        port = 5000
        if '--port' in sys.argv:
            port_index = sys.argv.index('--port')
            if port_index + 1 < len(sys.argv):
                port = int(sys.argv[port_index + 1])

        # MergeManager 已迁移到 Celery，不再需要启动
        # 如需启动后台任务，请使用: celery -A celery_tasks worker -Q video_merge
        # 如需启动定时任务，请使用: celery -A celery_tasks beat

        # 启动服务器
        print(f"进程 {os.getpid()}: 考试监控服务器启动在 http://0.0.0.0:{port}/")
        print(f"已注册的路由数量: {len(app.url_map._rules)}")
        app.run(host='0.0.0.0', port=port, debug=True)
    except Exception as e:
        print(f"进程 {os.getpid()}: 服务器启动失败: {str(e)}")
