from mysql.connector import pooling
from datetime import datetime
import os
import json
import threading

class DataAccess:
    def __init__(self, config_path=None):
          if config_path is None:
              config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

          with open(config_path, 'r', encoding='utf-8') as f:
              config = json.load(f)
          mysql_conf = config.get('mysql', {})

          # 简化连接池配置
          self.pool_config = {
              'pool_name': f'exam_monitor_pool_{os.getpid()}',  # 每个进程独立的池名
              'pool_size': 3,  # 减少到3个连接
              'pool_reset_session': True,
              'host': mysql_conf.get('host', 'localhost'),
              'port': mysql_conf.get('port', 3306),
              'user': mysql_conf.get('user', 'debian-sys-maint'),
              'password': mysql_conf.get('password', 'bGEtT3EfFKGLhYRS'),
              'database': mysql_conf.get('database', 'monitoring'),
              'autocommit': True,
              'charset': 'utf8mb4',
              'use_unicode': True,
          }

          # 创建连接池
          try:
              self.pool = pooling.MySQLConnectionPool(**self.pool_config)
              print(f"进程 {os.getpid()}: 数据库连接池创建成功，池大小: {self.pool_config['pool_size']}")
          except Exception as e:
              print(f"进程 {os.getpid()}: 创建数据库连接池失败: {e}")
              raise

    def get_connection(self):
        """简化的连接获取，不重试，不重建连接池"""
        try:
            conn = self.pool.get_connection()
            if conn.is_connected():
                return conn
            else:
                conn.close()
                raise Exception("连接无效")
        except Exception as e:
            print(f"进程 {os.getpid()}: 获取数据库连接失败: {e}")
            raise

    def get_pool_status(self):
        """获取连接池状态"""
        try:
            return {
                'pool_size': self.pool_config['pool_size'],
                'pool_name': self.pool_config['pool_name'],
                'active_connections': len(self.pool._cnx_queue._queue) if hasattr(self.pool, '_cnx_queue') else 'unknown'
            }
        except Exception as e:
            return {'error': str(e)}

    def close_pool(self):
        """关闭连接池"""
        try:
            if hasattr(self, 'pool'):
                # 关闭连接池中的所有连接
                while True:
                    try:
                        conn = self.pool.get_connection()
                        conn.close()
                    except:
                        break
                print("数据库连接池已关闭")
        except Exception as e:
            print(f"关闭连接池时出错: {e}")

    def get_all_exams(self):
        conn = self.get_connection()
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT * FROM exams")
                records =  cursor.fetchall()
                for record in records:
                    record['start_time'] = record['start_time'].strftime("%Y-%m-%d %H:%M:%S")
                    record['end_time'] = record['end_time'].strftime("%Y-%m-%d %H:%M:%S")
                return records
        finally:
            conn.close()

    def get_exam(self, exam_id):
        conn = self.get_connection()
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT * FROM exams WHERE id=%s", (exam_id,))
                return cursor.fetchone()
        finally:
            conn.close()

    def add_exam(self, exam_data):
        conn = self.get_connection()
        try:
            with conn.cursor(dictionary=True) as cursor:
                sql = """
                INSERT INTO exams (name, start_time, end_time, status, created_at, default_url, delay_min, disable_new_tabs)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(sql, (
                    exam_data['name'],
                    exam_data['start_time'],
                    exam_data['end_time'],
                    exam_data.get('status', 'pending'),
                    exam_data.get('created_at', datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                    exam_data.get('default_url'),
                    exam_data.get('delay_min', 0),
                    exam_data.get('disable_new_tabs', 0)
                ))
                return cursor.lastrowid
        finally:
            conn.close()

    def get_exam_students(self, exam_id):
        conn = self.get_connection()
        try:
            with conn.cursor(dictionary=True) as cursor:
                # 获取学生基本信息，并关联最新的IP地址
                sql = """
                SELECT es.*,
                       (SELECT slh.ip
                        FROM student_login_history slh
                        WHERE slh.student_exam_id = es.id
                          AND slh.ip IS NOT NULL
                        ORDER BY slh.timestamp DESC
                        LIMIT 1) as ip
                FROM exam_students es
                WHERE es.exam_id = %s
                """
                cursor.execute(sql, (exam_id,))
                return cursor.fetchall()
        finally:
            conn.close()

    def add_student_to_exam(self, student_id, student_name, exam_id, status='pending'):
        conn = self.get_connection()
        try:
            with conn.cursor(dictionary=True) as cursor:
                sql = "INSERT INTO exam_students (student_id, student_name, exam_id, status) VALUES (%s, %s, %s, %s)"
                cursor.execute(sql, (student_id, student_name, exam_id, status))
                return cursor.lastrowid
        finally:
            conn.close()

    def get_student_exam(self, student_id, exam_id):
        conn = self.get_connection()
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT * FROM exam_students WHERE student_id=%s AND exam_id=%s", (student_id, exam_id))
                return cursor.fetchone()
        finally:
            conn.close()

    def update_student_exam_status(self, exam_student_id, status):
        # exam_student_id为exam_students表的主键id
        conn = self.get_connection()
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("UPDATE exam_students SET status=%s WHERE id=%s", (status, exam_student_id))
                return cursor.rowcount
        finally:
            conn.close()

    def add_login_history(self, exam_student_id, action, timestamp, ip=None):
        conn = self.get_connection()
        try:
            with conn.cursor(dictionary=True) as cursor:
                sql = "INSERT INTO student_login_history (student_exam_id, action, timestamp, ip) VALUES (%s, %s, %s, %s)"
                cursor.execute(sql, (exam_student_id, action, timestamp, ip))
                return cursor.lastrowid
        finally:
            conn.close()

    def get_login_history(self, exam_student_id):
        conn = self.get_connection()
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT * FROM student_login_history WHERE student_exam_id=%s ORDER BY timestamp", (exam_student_id,))
                return cursor.fetchall()
        finally:
            conn.close()

    def delete_exam(self, exam_id):
        conn = self.get_connection()
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("DELETE FROM exams WHERE id=%s", (exam_id,))
                return cursor.rowcount
        finally:
            conn.close()

    def get_all_students(self):
        conn = self.get_connection()
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT DISTINCT student_id, student_name FROM exam_students")
                return cursor.fetchall()
        finally:
            conn.close()

    def add_student(self, student_data):
        conn = self.get_connection()
        try:
            with conn.cursor(dictionary=True) as cursor:
                sql = "INSERT INTO exam_students (student_id, student_name, exam_id, status) VALUES (%s, %s, %s, %s)"
                cursor.execute(sql, (
                    student_data['student_id'],
                    student_data['student_name'],
                    student_data['exam_id'],
                    student_data.get('status', 'pending')
                ))
                return cursor.lastrowid
        finally:
            conn.close()

    def get_exam_violations(self, exam_id, page=1, per_page=12):
        conn = self.get_connection()
        try:
            with conn.cursor(dictionary=True) as cursor:
                # 首先获取总数
                count_sql = "SELECT COUNT(*) as total FROM violations WHERE exam_id=%s"
                cursor.execute(count_sql, (exam_id,))
                total_count = cursor.fetchone()['total']

                # 然后获取分页数据
                offset = (page - 1) * per_page
                sql = "SELECT * FROM violations WHERE exam_id=%s ORDER BY timestamp DESC LIMIT %s OFFSET %s"
                cursor.execute(sql, (exam_id, per_page, offset))
                violations = cursor.fetchall()

                # 为每个违规记录生成正确的截图URL
                for violation in violations:
                    if violation.get('screenshot_path'):
                        # 从完整路径中提取文件名
                        import os
                        filename = os.path.basename(violation['screenshot_path'])
                        # 生成正确的URL格式: /{exam_id}/violations/{filename}
                        violation['screenshot_url'] = f"/{exam_id}/violations/{filename}"
                    else:
                        violation['screenshot_url'] = None

                    # 格式化时间戳
                    if violation.get('timestamp'):
                        if hasattr(violation['timestamp'], 'strftime'):
                            violation['timestamp'] = violation['timestamp'].strftime("%Y-%m-%d %H:%M:%S")
                        else:
                            violation['timestamp'] = str(violation['timestamp'])

                return {
                    'violations': violations,
                    'total': total_count,
                    'page': page,
                    'per_page': per_page
                }
        finally:
            conn.close()

    def exists(self, key):
        # 只支持 exam:{exam_id} 这种格式
        if key.startswith('exam:'):
            try:
                exam_id = int(key.split(':')[1])
            except Exception:
                return False
            conn = self.get_connection()
            try:
                with conn.cursor(dictionary=True) as cursor:
                    cursor.execute("SELECT 1 FROM exams WHERE id=%s", (exam_id,))
                    return cursor.fetchone() is not None
            finally:
                conn.close()
        return False

    def delete_students_by_exam(self, exam_id):
        """删除考试相关的学生数据"""
        conn = self.get_connection()
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("DELETE FROM exam_students WHERE exam_id=%s", (exam_id,))
                return cursor.rowcount
        finally:
            conn.close()

    def delete_violations_by_exam(self, exam_id):
        """删除考试相关的违规记录"""
        conn = self.get_connection()
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("DELETE FROM violations WHERE exam_id=%s", (exam_id,))
                return cursor.rowcount
        finally:
            conn.close()

    def add_violation(self, violation_data):
        """添加违规记录"""
        conn = self.get_connection()
        try:
            with conn.cursor(dictionary=True) as cursor:
                sql = """
                INSERT INTO violations (student_id, exam_id, username, reason, timestamp, screenshot_path, ip)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(sql, (
                    violation_data['student_id'],
                    violation_data['exam_id'],
                    violation_data['username'],
                    violation_data['reason'],
                    violation_data['timestamp'],
                    violation_data['screenshot_path'],
                    violation_data.get('ip')
                ))
                return cursor.lastrowid
        finally:
            conn.close()

    def handle_student_login(self, username, exam_id, student_id, ip):
        """处理学生登录逻辑"""
        try:
            # 验证必要参数
            if not username or not exam_id:
                return {
                    "status": "error",
                    "message": "缺少必要的登录参数"
                }

            # 如果没有提供student_id，使用username作为student_id
            if not student_id:
                student_id = username

            # 查找或创建学生考试记录
            student_exam = self.get_student_exam(student_id, exam_id)
            if not student_exam:
                # 创建新的学生考试记录
                exam_student_id = self.add_student_to_exam(student_id, username, exam_id, 'online')
            else:
                # 更新现有记录状态
                exam_student_id = student_exam['id']
                self.update_student_exam_status(exam_student_id, 'online')

            # 添加登录历史记录
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.add_login_history(exam_student_id, 'login', timestamp, ip)

            # 更新最后活跃时间
            conn = self.get_connection()
            try:
                with conn.cursor(dictionary=True) as cursor:
                    cursor.execute(
                        "UPDATE exam_students SET last_active=%s WHERE id=%s",
                        (timestamp, exam_student_id)
                    )
            finally:
                conn.close()

            return {
                "status": "success",
                "message": "登录成功",
                "exam_student_id": exam_student_id,
                "student_id": student_id,
                "exam_id": exam_id
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"登录失败: {str(e)}"
            }

    def update_last_active(self, student_id, exam_id, timestamp):
        """更新学生最后活跃时间"""
        conn = self.get_connection()
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(
                    "UPDATE exam_students SET last_active=%s WHERE student_id=%s AND exam_id=%s",
                    (timestamp, student_id, exam_id)
                )
                return cursor.rowcount
        finally:
            conn.close()

    def get_student_status(self, student_id, exam_id):
        """获取学生状态"""
        conn = self.get_connection()
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(
                    "SELECT status FROM exam_students WHERE student_id=%s AND exam_id=%s",
                    (student_id, exam_id)
                )
                result = cursor.fetchone()
                return result['status'] if result else None
        finally:
            conn.close()

    def update_student_status(self, student_id, exam_id, status):
        """更新学生状态"""
        conn = self.get_connection()
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(
                    "UPDATE exam_students SET status=%s WHERE student_id=%s AND exam_id=%s",
                    (status, student_id, exam_id)
                )
                return cursor.rowcount
        finally:
            conn.close()

    def update_student_last_active_and_status(self, student_id, exam_id, timestamp, status):
        """同时更新学生最后活跃时间和状态"""
        conn = self.get_connection()
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(
                    "UPDATE exam_students SET last_active=%s, status=%s WHERE student_id=%s AND exam_id=%s",
                    (timestamp, status, student_id, exam_id)
                )
                return cursor.rowcount
        finally:
            conn.close()

    def get_student_username(self, exam_id, student_id):
        """获取学生用户名"""
        conn = self.get_connection()
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(
                    "SELECT student_name FROM exam_students WHERE exam_id=%s AND student_id=%s",
                    (exam_id, student_id)
                )
                result = cursor.fetchone()
                return result['student_name'] if result else None
        finally:
            conn.close()

    def find_student_id_by_name(self, student_name):
        """根据学生姓名查找学生ID"""
        conn = self.get_connection()
        try:
            with conn.cursor(dictionary=True) as cursor:
                # 首先在exam_students表中查找
                cursor.execute(
                    "SELECT DISTINCT student_id FROM exam_students WHERE student_name=%s ORDER BY id DESC LIMIT 1",
                    (student_name,)
                )
                result = cursor.fetchone()
                if result:
                    return result['student_id']

                # 如果没找到，返回None（后续可以创建新的学生ID）
                return None
        finally:
            conn.close()

    def find_student_by_name(self, student_name):
        """在students表中根据姓名查找学生"""
        conn = self.get_connection()
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(
                    "SELECT * FROM students WHERE student_name=%s ORDER BY created_at DESC LIMIT 1",
                    (student_name,)
                )
                return cursor.fetchone()
        finally:
            conn.close()

    def get_all_students_from_table(self):
        """从students表获取所有学生"""
        conn = self.get_connection()
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT * FROM students ORDER BY created_at DESC")
                return cursor.fetchall()
        finally:
            conn.close()

    def get_student_name_by_id(self, student_id):
        """根据学号获取学生姓名"""
        conn = self.get_connection()
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(
                    "SELECT DISTINCT student_name FROM exam_students WHERE student_id=%s LIMIT 1",
                    (student_id,)
                )
                result = cursor.fetchone()
                if result:
                    return result['student_name']

                return None
        finally:
            conn.close()

    def get_login_count(self, exam_id, student_id):
        """获取学生登录次数"""
        # 首先获取exam_student_id
        student_exam = self.get_student_exam(student_id, exam_id)
        if not student_exam:
            return 0

        conn = self.get_connection()
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(
                    "SELECT COUNT(*) as count FROM student_login_history WHERE student_exam_id=%s AND action='login'",
                    (student_exam['id'],)
                )
                result = cursor.fetchone()
                return result['count'] if result else 0
        finally:
            conn.close()

    def get_login_history_count(self, exam_id, student_id):
        """获取学生所有登录历史记录总数（包括登录、退出、上线、断线等）"""
        # 首先获取exam_student_id
        student_exam = self.get_student_exam(student_id, exam_id)
        if not student_exam:
            return 0

        conn = self.get_connection()
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(
                    "SELECT COUNT(*) as count FROM student_login_history WHERE student_exam_id=%s",
                    (student_exam['id'],)
                )
                result = cursor.fetchone()
                return result['count'] if result else 0
        finally:
            conn.close()

    def get_student_logins(self, exam_id, student_id):
        """获取学生登录历史"""
        # 首先获取exam_student_id
        student_exam = self.get_student_exam(student_id, exam_id)
        if not student_exam:
            return []

        conn = self.get_connection()
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(
                    "SELECT * FROM student_login_history WHERE student_exam_id=%s ORDER BY timestamp DESC",
                    (student_exam['id'],)
                )
                results = cursor.fetchall()
                # 直接返回对象数组
                return [{
                    'type': result['action'],
                    'timestamp': result['timestamp'].strftime("%Y-%m-%d %H:%M:%S") if hasattr(result['timestamp'], 'strftime') else str(result['timestamp']),
                    'ip': result['ip'] or 'unknown'
                } for result in results]
        finally:
            conn.close()

    def get_student_active_exams(self, student_id):
        """根据学号返回学生可以参加的正在进行的考试"""
        conn = self.get_connection()
        try:
            with conn.cursor(dictionary=True) as cursor:
                # 查询学生参与的所有活跃考试
                sql = """
                SELECT DISTINCT e.*, es.status as student_status, es.last_active
                FROM exams e
                INNER JOIN exam_students es ON e.id = es.exam_id
                WHERE es.student_id = %s
                AND e.status = 'active'
                ORDER BY e.start_time DESC
                """
                cursor.execute(sql, (student_id,))
                exam = cursor.fetchone()
                # 格式化时间字段
                if exam:
                    if exam.get('start_time'):
                        if hasattr(exam['start_time'], 'strftime'):
                            exam['start_time'] = exam['start_time'].strftime("%Y-%m-%d %H:%M:%S")
                        else:
                            exam['start_time'] = str(exam['start_time'])
                    if exam.get('end_time'):
                        if hasattr(exam['end_time'], 'strftime'):
                            exam['end_time'] = exam['end_time'].strftime("%Y-%m-%d %H:%M:%S")
                        else:
                            exam['end_time'] = str(exam['end_time'])
                    if exam.get('created_at'):
                        if hasattr(exam['created_at'], 'strftime'):
                            exam['created_at'] = exam['created_at'].strftime("%Y-%m-%d %H:%M:%S")
                        else:
                            exam['created_at'] = str(exam['created_at'])
                    if exam.get('last_active'):
                        if hasattr(exam['last_active'], 'strftime'):
                            exam['last_active'] = exam['last_active'].strftime("%Y-%m-%d %H:%M:%S")
                        else:
                            exam['last_active'] = str(exam['last_active'])

                return exam
        finally:
            conn.close()

    def refresh_exam_status(self):
        conn = self.get_connection()
        try:
            with conn.cursor(dictionary=True) as cursor:
                # 更新考试状态为active（当前时间在考试时间范围内）
                cursor.execute("""
                    UPDATE exams 
                    SET status = 'active' 
                    WHERE NOW() BETWEEN start_time AND end_time 
                    AND status != 'active'
                """)
                
                # 更新考试状态为completed（当前时间在考试结束时间之后）
                cursor.execute("""
                    UPDATE exams 
                    SET status = 'completed' 
                    WHERE NOW() > end_time 
                    AND status != 'completed'
                """)
                
                return cursor.rowcount
        finally:
            conn.close()

    def update_exam_status(self, exam_id, status):
        """更新考试状态"""
        conn = self.get_connection()
        try:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("UPDATE exams SET status=%s WHERE id=%s", (status, exam_id))
                return cursor.rowcount
        finally:
            conn.close()

    def get_student_screenshots(self, exam_id, student_id, page=1, per_page=20):
        """从文件系统获取指定学生的截图文件列表，支持分页"""
        import os

        # 计算 DATA_DIR 路径
        DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server_data")

        # 构建学生截图目录路径
        student_screenshot_dir = os.path.join(DATA_DIR, str(exam_id), "screenshots", str(student_id))

        # 检查目录是否存在
        if not os.path.exists(student_screenshot_dir):
            return []

        try:
            # 获取目录中的所有PNG文件
            files = []
            for filename in os.listdir(student_screenshot_dir):
                if filename.lower().endswith('.png') and filename.startswith('screenshot_'):
                    files.append(filename)

            # 按文件名排序（包含时间戳，所以可以按时间排序）
            files.sort(reverse=True)

            # 计算分页
            start = (page - 1) * per_page
            end = start + per_page

            return files[start:end]

        except Exception as e:
            print(f"获取学生截图文件失败: {str(e)}")
            return []

# 全局清理函数
def cleanup_database_connections():
    """清理数据库连接"""
    try:
        if DataAccess._instance:
            DataAccess._instance.close_pool()
            DataAccess._instance = None
            print("数据库连接已清理")
    except Exception as e:
        print(f"清理数据库连接时出错: {e}")

# 注册退出时的清理函数
import atexit
atexit.register(cleanup_database_connections)
