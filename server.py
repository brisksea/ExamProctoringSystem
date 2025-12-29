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
from data_access import DataAccess
from merge_manager import MergeManager
from redis_helper import get_redis

# 数据存储目录
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server_data")
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

# 确保目录存在
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)


# 创建Flask应用
def create_app():
    app = Flask(__name__)
    
    # 设置文件上传配置
    app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB 最大文件大小
    app.config['UPLOAD_FOLDER'] = DATA_DIR
    
    app.data_access = DataAccess()
    app.merge_manager = MergeManager()
    return app

app = create_app()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/student_management')
def student_management():
    return render_template('student_management.html')

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
    ip = request.remote_addr

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

            # Redis 标记在线与最近活跃
            try:
                r = get_redis()
                student_key = f"exam:{exam_id}:student:{student_id}"
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                r.hset(student_key, mapping={
                    "username": student_name,
                    "status": "online",
                    "login_time": now,
                    "last_seen": now,
                    "ip": ip,
                })
                r.sadd(f"exam:{exam_id}:online_students", student_id)
                r.expire(student_key, 180)
            except Exception as e:
                print(f"登录写入Redis失败: {e}")

            # 记录登录事件到数据库
            try:
                student_exam = current_app.data_access.get_student_exam(student_id, exam_id)
                if student_exam:
                    current_app.data_access.add_login_history(student_exam['id'], 'login', now, ip)
            except Exception as e:
                print(f"记录登录历史失败: {e}")

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

    # 更新最后活跃时间
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    current_app.data_access.update_last_active(student_id, exam_id, timestamp)

    # 如果学生状态不是online，则更新为online并记录上线历史
    student_status = current_app.data_access.get_student_status(student_id, exam_id)
    if student_status != 'online':
        current_app.data_access.update_student_status(student_id, exam_id, 'online')

        # 如果是从离线状态恢复，记录上线历史
        if student_status == 'offline':
            student_exam = current_app.data_access.get_student_exam(student_id, exam_id)
            if student_exam:
                current_app.data_access.add_login_history(student_exam['id'], 'online', timestamp, request.remote_addr)
                print(f"学生上线: ID={student_id}, 考试={exam_id}, 时间={timestamp}")

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
    ip = request.remote_addr

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

            # Redis 下线标记
            try:
                r = get_redis()
                student_key = f"exam:{exam_id}:student:{student_id}"
                r.hset(student_key, mapping={"status": "logout", "logout_time": timestamp})
                r.srem(f"exam:{exam_id}:online_students", student_id)
            except Exception as e:
                print(f"Redis登出标记失败: {e}")

        # 登出时将合并任务加入队列
        current_app.merge_manager.add_merge_task(
            exam_id,
            student_id,
            data.get('username', f"student_{student_id}")
        )
        print(f"已将合并任务加入队列: exam_id={exam_id}, student_id={student_id}")

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
        'ip': request.remote_addr
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
        # 先尝试 Redis 缓存
        try:
            r = get_redis()
            cache = r.get("server_config")
            if cache:
                return jsonify({"status": "success", "config": json.loads(cache)})
        except Exception as e:
            print(f"读取配置Redis缓存失败: {e}")

        # 文件兜底
        if not os.path.exists(CONFIG_FILE):
            return jsonify({"status": "error", "message": "Configuration file not found"}), 404

        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # 写入 Redis 短缓存
        try:
            r = get_redis()
            r.setex("server_config", 60, json.dumps(config))
        except Exception as e:
            print(f"写入配置Redis缓存失败: {e}")

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
    result = []
    for student in students:  # students is now a list, not a dict
        student_id = student['student_id']

        # 获取登录历史条数（只包含登录）
        login_count = current_app.data_access.get_login_count(exam_id, student_id)
        student['login_count'] = login_count

        # 获取所有历史记录总数（包括登录、退出、上线、断线等）
        login_history_count = current_app.data_access.get_login_history_count(exam_id, student_id)
        student['login_history_count'] = login_history_count

        # 获取截图数量
        screenshot_count = get_student_screenshot_count(exam_id, student_id)
        student['screenshot_count'] = screenshot_count

        # 获取录屏数量
        recording_count = get_student_recording_count(exam_id, student_id)
        student['recording_count'] = recording_count

        # 总文件数量
        student['media_count'] = screenshot_count + recording_count

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

@app.route('/api/exams/<int:exam_id>/violations')
def get_exam_violations_api(exam_id):
    """获取指定考试的违规记录，支持分页"""
    # 获取分页参数
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 12, type=int)

    # 获取分页的违规记录和总数
    result = current_app.data_access.get_exam_violations(exam_id, page, per_page)
    return jsonify(result)

EXAM_CONFIG_KEY = "exam_configs"  # Redis中存储考试配置的key # Removed as per edit hint

@app.route('/api/exams/<int:exam_id>', methods=['DELETE'])
def delete_exam(exam_id):
    """删除考试"""
    try:
        # client = get_redis() # Removed as per edit hint

        # 检查考试是否存在
        if not current_app.data_access.exists(f'exam:{exam_id}'): # Changed to current_app.data_access
            return jsonify({"status": "error", "message": "考试不存在"}), 404

        # 获取考试信息
        exam = current_app.data_access.get_exam(exam_id) # exam已是dict，无需json.loads
        # 如果考试正在进行中，不允许删除
        if exam and exam['status'] == 'active':
            return jsonify({"status": "error", "message": "无法删除正在进行中的考试"}), 400

        # 删除考试配置
        # client.hdel(EXAM_CONFIG_KEY, exam_id) # Removed as per edit hint
        current_app.data_access.delete_exam(exam_id) # Changed to current_app.data_access

        # 删除考试相关的学生数据
        current_app.data_access.delete_students_by_exam(exam_id)

        # 删除考试相关的违规记录
        current_app.data_access.delete_violations_by_exam(exam_id)
        

        print(f"考试已删除: ID={exam_id}, 名称={exam['name'] if exam else '未知'}")
        return jsonify({"status": "success", "message": "考试已成功删除"})

    except Exception as e:
        print(f"删除考试失败: {str(e)}")
        return jsonify({"status": "error", "message": f"删除失败：{str(e)}"}), 500


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

    current_app.data_access.update_student_last_active_and_status(student_id, exam_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), 'online') # Changed to current_app.data_access

    return jsonify({"status": "success", "message": "截图已上传", "filename": filename})

@app.route('/api/exams/<int:exam_id>/students/<student_id>/screenshots')
def get_student_screenshots(exam_id, student_id):
    """获取指定考生的截图文件URL，支持分页"""
    # 获取分页参数
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    
    # client = get_redis() # Removed as per edit hint
    files = current_app.data_access.get_student_screenshots(exam_id, student_id, page, per_page) # Changed to current_app.data_access
    # 解码文件名
    files = [fname.decode() if isinstance(fname, bytes) else fname for fname in files]
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
    # client = get_redis() # Removed as per edit hint

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
@app.route('/chromedriver_<int:major_version>.exe')
def download_chromedriver(major_version):
    """根据主版本号下载对应的chromedriver可执行文件"""
    # 假设所有chromedriver文件都放在 DATA_DIR/chromedrivers 目录下
    chromedriver_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'chromedrivers')
    print(chromedriver_dir)
    filename = f'chromedriver_{major_version}.exe'
    file_path = os.path.join(chromedriver_dir, filename)
    print(file_path)
    if not os.path.exists(file_path):
        return jsonify({"status": "error", "message": f"未找到chromedriver_{major_version}.exe"}), 404
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
    """获取学生的截图文件数量"""
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
    """获取学生的录屏文件数量"""
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

        return count
    except Exception as e:
        print(f"获取录屏数量失败: {e}")
        return 0

if __name__ == '__main__':
    try:
        # 启动服务器
        print(f"进程 {os.getpid()}: 考试监控服务器启动在 http://0.0.0.0:5000/")
        print(f"已注册的路由数量: {len(app.url_map._rules)}")
        app.run(host='0.0.0.0', port=5000, debug=True)
    except Exception as e:
        print(f"进程 {os.getpid()}: 服务器启动失败: {str(e)}")
        # cleanup_redis() # Removed as per edit hint