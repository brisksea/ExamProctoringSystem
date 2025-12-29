from mysql.connector import pooling
from datetime import datetime
import os
import json
import threading

# 统一封装 Redis 访问，向上层屏蔽实现细节
try:
    from redis_helper import get_redis as _get_redis
except Exception:
    _get_redis = None

class DataAccess:
    def __init__(self, config_path=None):
          if config_path is None:
              config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

          with open(config_path, 'r', encoding='utf-8') as f:
              config = json.load(f)
          mysql_conf = config.get('mysql', {})

          # 优化连接池配置（500人并发优化）
          self.pool_config = {
              'pool_name': f'exam_monitor_pool_{os.getpid()}',  # 每个进程独立的池名
              'pool_size': 10,  # 增加到 20 以支持 500 人并发
                                # 总连接数: 8 workers × 20 = 160 MySQL 连接
                                # 需要确保 MySQL max_connections >= 200
              'pool_reset_session': True,
              'host': mysql_conf.get('host', 'localhost'),
              'port': mysql_conf.get('port', 3306),
              'user': mysql_conf.get('user', 'debian-sys-maint'),
              'password': mysql_conf.get('password', 'bGEtT3EfFKGLhYRS'),
              'database': mysql_conf.get('database', 'monitoring'),
              'autocommit': True,
              'charset': 'utf8mb4',
              'use_unicode': True,
              'connection_timeout': 10,  # 连接超时时间
              'sql_mode': 'TRADITIONAL',
          }

          # 创建连接池
          try:
              self.pool = pooling.MySQLConnectionPool(**self.pool_config)
              print(f"进程 {os.getpid()}: 数据库连接池创建成功，池大小: {self.pool_config['pool_size']}")
          except Exception as e:
              print(f"进程 {os.getpid()}: 创建数据库连接池失败: {e}")
              raise

          # 懒加载 Redis 连接（仅在需要时获取）
          self._redis = None

    def _get_redis(self):
        """内部获取 Redis 客户端，不向上层暴露具体实现。"""
        if not _get_redis:
            return None
        if self._redis is None:
            try:
                self._redis = _get_redis()
            except Exception as e:
                print(f"获取 Redis 连接失败: {e}")
                self._redis = None
        return self._redis

    # ------------------- 学生实时状态（Redis + MySQL 协同） -------------------
    def set_student_realtime_status(self, exam_id, student_id, username=None, status=None, ip=None, last_seen=None, ttl_seconds=180):
        """
        写入学生实时状态到 Redis，使用ZSet存储最后活跃时间。

        ZSet结构：exam:{exam_id}:online_students
        - member: student_id
        - score: last_active_timestamp (Unix时间戳)

        Hash结构：exam:{exam_id}:student:{student_id}
        - 存储学生的其他信息（username, status, ip等）
        """
        r = self._get_redis()
        if not r:
            return False
        try:
            import time
            now_timestamp = time.time()

            # 1. 更新学生基本信息（Hash）
            student_key = f"exam:{exam_id}:student:{student_id}"
            mapping = {}
            if username is not None:
                mapping['username'] = username
            if status is not None:
                mapping['status'] = status
            if last_seen is not None:
                mapping['last_seen'] = last_seen
            if ip is not None:
                mapping['ip'] = ip
            if mapping:
                r.hset(student_key, mapping=mapping)
                r.expire(student_key, ttl_seconds)

            # 2. 维护在线学生ZSet（用于掉线检测）
            zset_key = f"exam:{exam_id}:online_students"
            if status == 'online':
                # 添加到ZSet，score为当前时间戳
                r.zadd(zset_key, {student_id: now_timestamp})
            elif status in ('offline', 'logout'):
                # 从ZSet中移除
                r.zrem(zset_key, student_id)

            return True
        except Exception as e:
            print(f"写入 Redis 实时状态失败: {e}")
            return False

    def get_inactive_students(self, exam_id, timeout_seconds=120):
        """
        从Redis ZSet中获取超过指定时间未活跃的学生列表。

        Args:
            exam_id: 考试ID
            timeout_seconds: 超时时间（秒），默认120秒

        Returns:
            list: 超时的学生ID列表
        """
        r = self._get_redis()
        if not r:
            return []

        try:
            import time
            zset_key = f"exam:{exam_id}:online_students"
            current_timestamp = time.time()
            timeout_timestamp = current_timestamp - timeout_seconds

            # 使用ZRANGEBYSCORE获取score小于timeout_timestamp的学生（即超时的学生）
            # 返回的是bytes，需要解码
            inactive_students = r.zrangebyscore(zset_key, '-inf', timeout_timestamp)
            return [s.decode() if isinstance(s, bytes) else s for s in inactive_students]
        except Exception as e:
            print(f"获取超时学生失败: {e}")
            return []

    def get_student_last_active_time(self, exam_id, student_id):
        """
        从Redis ZSet中获取学生的最后活跃时间。

        Returns:
            float: Unix时间戳，如果学生不在ZSet中返回None
        """
        r = self._get_redis()
        if not r:
            return None

        try:
            zset_key = f"exam:{exam_id}:online_students"
            score = r.zscore(zset_key, student_id)
            return score  # 返回Unix时间戳或None
        except Exception as e:
            print(f"获取学生最后活跃时间失败: {e}")
            return None

    def get_student_realtime_status(self, exam_id, student_id):
        """优先从 Redis 读取实时状态，缺失时回退数据库。"""
        # Redis 优先
        r = self._get_redis()
        if r:
            try:
                student_key = f"exam:{exam_id}:student:{student_id}"
                raw = r.hgetall(student_key)
                if raw:
                    def _norm(v):
                        return v.decode() if isinstance(v, (bytes, bytearray)) else v
                    data = { _norm(k): _norm(v) for k, v in raw.items() }
                    return {
                        'status': data.get('status'),
                        'last_seen': data.get('last_seen'),
                        'ip': data.get('ip'),
                        'username': data.get('username')
                    }
            except Exception as e:
                print(f"读取 Redis 实时状态失败: {e}")

        # 回退 MySQL（只可提供 status）
        return {
            'status': self.get_student_status(student_id, exam_id),
            'last_seen': None,
            'ip': None,
            'username': None
        }

    def mark_online_activity(self, student_id, exam_id, ip=None, username=None):
        """
        统一处理"学生有活跃行为"：
        - 若从非 online 变为 online，写入上线历史并更新数据库状态
        - 只更新 Redis 实时状态，不更新数据库 last_active（减少数据库负担）
        - 依赖 Redis 进行掉线检测，Redis 故障时兜底逻辑会标记所有人 offline
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        prev_status = None
        try:
            prev_status = self.get_student_status(student_id, exam_id)
        except Exception:
            prev_status = None

        # 状态变化时更新状态和写入历史
        if prev_status != 'online':
            # 更新 DB 状态（不更新 last_active，避免频繁写库）
            self.update_student_status(student_id, exam_id, 'online')

            # 写历史（从非 online 转为 online）
            try:
                if prev_status:  # 如果之前有状态，写入上线历史
                    student_exam = self.get_student_exam(student_id, exam_id)
                    if student_exam:
                        self.add_login_history(student_exam['id'], 'online', now, ip)
            except Exception as e:
                print(f"写入上线历史失败: {e}")

        # 更新 Redis 实时状态（每次心跳都更新，用于掉线检测）
        self.set_student_realtime_status(exam_id, student_id, username=username, status='online', ip=ip, last_seen=now)
        return True

    def _cleanup_exam_redis_data(self, exam_id):
        """清理考试相关的 Redis 数据"""
        r = self._get_redis()
        if not r:
            return
        
        try:
            # 清理学生实时状态
            pattern = f"exam:{exam_id}:student:*"
            student_keys = r.keys(pattern)
            if student_keys:
                r.delete(*student_keys)
                print(f"清理了 {len(student_keys)} 个学生实时状态键")
            
            # 清理在线学生集合
            online_set_key = f"exam:{exam_id}:online_students"
            if r.exists(online_set_key):
                r.delete(online_set_key)
                print(f"清理了在线学生集合: {online_set_key}")
            
            # 清理考试配置缓存
            exam_config_key = f"exam_config:{exam_id}"
            if r.exists(exam_config_key):
                r.delete(exam_config_key)
                print(f"清理了考试配置缓存: {exam_config_key}")
                
        except Exception as e:
            print(f"清理考试 Redis 数据失败: {e}")

    def _cleanup_student_redis_data(self, exam_id, student_id):
        """清理特定学生的 Redis 数据"""
        r = self._get_redis()
        if not r:
            return
            
        try:
            # 清理学生实时状态
            student_key = f"exam:{exam_id}:student:{student_id}"
            if r.exists(student_key):
                r.delete(student_key)
                print(f"清理了学生实时状态: {student_key}")
            
            # 从在线学生集合中移除
            online_set_key = f"exam:{exam_id}:online_students"
            if r.exists(online_set_key):
                r.srem(online_set_key, student_id)
                print(f"从在线学生集合中移除: {student_id}")
                
        except Exception as e:
            print(f"清理学生 Redis 数据失败: {e}")

    def cleanup_all_redis_data(self):
        """清理所有 Redis 数据（服务器关闭时使用）"""
        r = self._get_redis()
        if not r:
            return
            
        try:
            # 获取所有考试的学生状态并标记为离线
            pattern = "exam:*:student:*"
            student_keys = r.keys(pattern)
            
            for key in student_keys:
                # 检查是否是学生状态键（不是集合键）
                if not key.endswith(":online_students"):
                    # 获取学生信息
                    student_data = r.hgetall(key)
                    if student_data:
                        # 解码字节数据
                        def _norm(v):
                            return v.decode() if isinstance(v, (bytes, bytearray)) else v
                        data = {_norm(k): _norm(v) for k, v in student_data.items()}
                        
                        # 如果学生在线，标记为离线
                        if data.get('status') == 'online':
                            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            r.hset(key, mapping={
                                'status': 'offline',
                                'last_seen': timestamp
                            })
                            
                            # 从在线集合中移除
                            exam_id = key.split(':')[1]
                            student_id = key.split(':')[-1]
                            online_set_key = f"exam:{exam_id}:online_students"
                            r.srem(online_set_key, student_id)
                            
                            print(f"学生 {data.get('username', student_id)} (考试: {exam_id}) 标记为离线")
            
            print(f"Redis 数据清理完成，处理了 {len(student_keys)} 个学生状态")
            
        except Exception as e:
            print(f"清理所有 Redis 数据失败: {e}")

    def _update_exam_cache(self, exam_id):
        """更新考试配置的 Redis 缓存"""
        r = self._get_redis()
        if not r:
            return
            
        try:
            # 从 MySQL 重新读取最新数据
            conn = self.get_connection()
            try:
                with conn.cursor(dictionary=True) as cursor:
                    cursor.execute("SELECT * FROM exams WHERE id=%s", (exam_id,))
                    exam_data = cursor.fetchone()
                    
                    if exam_data:
                        import json
                        exam_key = f"exam_config:{exam_id}"
                        r.setex(exam_key, 3600, json.dumps(exam_data, default=str))
                        print(f"更新考试配置缓存: {exam_id}")
            finally:
                conn.close()
                
        except Exception as e:
            print(f"更新考试配置缓存失败: {e}")

    def get_connection(self):
        """获取数据库连接，带重试机制和超时处理"""
        import time
        max_retries = 3
        retry_delay = 0.5

        # 记录连接获取开始时间
        acquire_start = time.time()

        for attempt in range(max_retries):
            try:
                conn = self.pool.get_connection()
                if conn.is_connected():
                    # 记录连接获取时间
                    acquire_time = time.time() - acquire_start
                    if acquire_time > 0.1:  # 超过100ms就记录
                        print(f"[PERF] 进程 {os.getpid()}: 连接获取耗时 {acquire_time:.3f}s")
                    return conn
                else:
                    conn.close()
                    raise Exception("连接无效")
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"进程 {os.getpid()}: 获取数据库连接失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                    time.sleep(retry_delay * (attempt + 1))  # 指数退避
                    continue
                else:
                    print(f"进程 {os.getpid()}: 获取数据库连接最终失败: {e}")
                    # 记录连接池状态
                    try:
                        pool_status = self.get_pool_status()
                        print(f"连接池状态: {pool_status}")
                    except:
                        pass
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

    def with_connection(self):
        """连接上下文管理器，确保连接总是被正确关闭"""
        import contextlib
        
        @contextlib.contextmanager
        def connection_context():
            conn = None
            try:
                conn = self.get_connection()
                yield conn
            finally:
                if conn:
                    try:
                        conn.close()
                    except Exception as e:
                        print(f"关闭连接时出错: {e}")
        
        return connection_context()

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
        with self.with_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT * FROM exams")
                records =  cursor.fetchall()
                for record in records:
                    record['start_time'] = record['start_time'].strftime("%Y-%m-%d %H:%M:%S")
                    record['end_time'] = record['end_time'].strftime("%Y-%m-%d %H:%M:%S")
                return records

    def get_exam(self, exam_id):
        """获取考试信息，优先从 Redis 缓存读取，回退到 MySQL"""
        # 先尝试从 Redis 缓存读取
        r = self._get_redis()
        if r:
            try:
                exam_key = f"exam_config:{exam_id}"
                cached_data = r.get(exam_key)
                if cached_data:
                    import json
                    return json.loads(cached_data)
            except Exception as e:
                print(f"读取考试配置缓存失败: {e}")
        
        # 从 MySQL 读取
        with self.with_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT * FROM exams WHERE id=%s", (exam_id,))
                exam_data = cursor.fetchone()
                
                # 写入 Redis 缓存（1小时过期）
                if exam_data and r:
                    try:
                        import json
                        exam_key = f"exam_config:{exam_id}"
                        r.setex(exam_key, 3600, json.dumps(exam_data, default=str))
                    except Exception as e:
                        print(f"写入考试配置缓存失败: {e}")
                
                return exam_data

    def add_exam(self, exam_data):
        with self.with_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                sql = """
                INSERT INTO exams (name, start_time, end_time, status, created_at, default_url, delay_min, disable_new_tabs, monitor_password)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(sql, (
                    exam_data['name'],
                    exam_data['start_time'],
                    exam_data['end_time'],
                    exam_data.get('status', 'pending'),
                    exam_data.get('created_at', datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                    exam_data.get('default_url'),
                    exam_data.get('delay_min', 0),
                    exam_data.get('disable_new_tabs', 0),
                    exam_data.get('monitor_password')
                ))
                exam_id = cursor.lastrowid

                # 更新 Redis 缓存
                self._update_exam_cache(exam_id)

                return exam_id

    def get_exam_students(self, exam_id):
        with self.with_connection() as conn:
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

    def add_student_to_exam(self, student_id, student_name, exam_id, status='pending'):
        with self.with_connection() as conn: 
            with conn.cursor(dictionary=True) as cursor:
                sql = "INSERT INTO exam_students (student_id, student_name, exam_id, status) VALUES (%s, %s, %s, %s)"
                cursor.execute(sql, (student_id, student_name, exam_id, status))
                return cursor.lastrowid


    def get_student_exam(self, student_id, exam_id):
        with self.with_connection() as conn: 
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT * FROM exam_students WHERE student_id=%s AND exam_id=%s", (student_id, exam_id))
                return cursor.fetchone()

    def update_student_exam_status(self, exam_student_id, status):
        # exam_student_id为exam_students表的主键id
        with self.with_connection() as conn: 
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("UPDATE exam_students SET status=%s WHERE id=%s", (status, exam_student_id))
                return cursor.rowcount

    def add_login_history(self, exam_student_id, action, timestamp, ip=None):
        with self.with_connection() as conn: 
            with conn.cursor(dictionary=True) as cursor:
                sql = "INSERT INTO student_login_history (student_exam_id, action, timestamp, ip) VALUES (%s, %s, %s, %s)"
                cursor.execute(sql, (exam_student_id, action, timestamp, ip))
                return cursor.lastrowid

    def get_login_history(self, exam_student_id):
        with self.with_connection() as conn: 
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT * FROM student_login_history WHERE student_exam_id=%s ORDER BY timestamp", (exam_student_id,))
                return cursor.fetchall()

    def delete_exam(self, exam_id):
        with self.with_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("DELETE FROM exams WHERE id=%s", (exam_id,))
                result = cursor.rowcount
                
                # 清理相关的 Redis 数据
                self._cleanup_exam_redis_data(exam_id)
                
                return result

    def get_all_students(self):
        with self.with_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT DISTINCT student_id, student_name FROM exam_students")
                return cursor.fetchall()

    def add_student(self, student_data):
        with self.with_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                sql = "INSERT INTO exam_students (student_id, student_name, exam_id, status) VALUES (%s, %s, %s, %s)"
                cursor.execute(sql, (
                    student_data['student_id'],
                    student_data['student_name'],
                    student_data['exam_id'],
                    student_data.get('status', 'pending')
                ))
                return cursor.lastrowid

    def get_exam_violations(self, exam_id, page=1, per_page=12):
        with self.with_connection() as conn:
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
        with self.with_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("DELETE FROM exam_students WHERE exam_id=%s", (exam_id,))
                return cursor.rowcount

    def delete_student(self, exam_id, student_id):
        """删除指定考试的单个学生"""
        with self.with_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                # 删除学生记录
                cursor.execute(
                    "DELETE FROM exam_students WHERE exam_id=%s AND student_id=%s",
                    (exam_id, student_id)
                )
                affected = cursor.rowcount

                # 删除该学生的违规记录
                cursor.execute(
                    "DELETE FROM violations WHERE exam_id=%s AND student_id=%s",
                    (exam_id, student_id)
                )

                # 删除Redis中的学生状态
                try:
                    redis = self.redis
                    if redis:
                        # 删除学生状态
                        student_key = f'exam:{exam_id}:student:{student_id}'
                        redis.delete(student_key)

                        # 删除活跃时间
                        active_key = f'student:{student_id}:exam:{exam_id}:last_active'
                        redis.delete(active_key)
                except Exception as e:
                    print(f"清理Redis学生数据失败: {e}")

                return affected


    def delete_violations_by_exam(self, exam_id):
        """删除考试相关的违规记录"""
        with self.with_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("DELETE FROM violations WHERE exam_id=%s", (exam_id,))
                return cursor.rowcount


    def add_violation(self, violation_data):
        """添加违规记录"""
        with self.with_connection() as conn:
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

            # 注意：最后活跃时间保存在Redis中，不需要更新数据库的last_active字段

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
        with self.with_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(
                    "UPDATE exam_students SET last_active=%s WHERE student_id=%s AND exam_id=%s",
                    (timestamp, student_id, exam_id)
                )
                return cursor.rowcount

    def get_student_status(self, student_id, exam_id):
        """获取学生状态"""
        with self.with_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(
                    "SELECT status FROM exam_students WHERE student_id=%s AND exam_id=%s",
                    (student_id, exam_id)
                )
                result = cursor.fetchone()
                return result['status'] if result else None


    def update_student_status(self, student_id, exam_id, status):
        """更新学生状态"""
        with self.with_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(
                    "UPDATE exam_students SET status=%s WHERE student_id=%s AND exam_id=%s",
                    (status, student_id, exam_id)
                )
                return cursor.rowcount

    def update_student_last_active_and_status(self, student_id, exam_id, timestamp, status):
        """同时更新学生最后活跃时间和状态"""
        with self.with_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(
                    "UPDATE exam_students SET last_active=%s, status=%s WHERE student_id=%s AND exam_id=%s",
                    (timestamp, status, student_id, exam_id)
                )
                return cursor.rowcount

    def get_student_username(self, exam_id, student_id):
        """获取学生用户名"""
        with self.with_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(
                    "SELECT student_name FROM exam_students WHERE exam_id=%s AND student_id=%s",
                    (exam_id, student_id)
                )
                result = cursor.fetchone()
                return result['student_name'] if result else None

    def find_student_id_by_name(self, student_name):
        """根据学生姓名查找学生ID"""
        with self.with_connection() as conn:
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

    def find_student_by_name(self, student_name):
        """在students表中根据姓名查找学生"""
        with self.with_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(
                    "SELECT * FROM students WHERE student_name=%s ORDER BY created_at DESC LIMIT 1",
                    (student_name,)
                )
                return cursor.fetchone()


    def get_all_students_from_table(self):
        """从students表获取所有学生"""
        with self.with_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("SELECT * FROM students ORDER BY created_at DESC")
                return cursor.fetchall()

    def get_student_name_by_id(self, student_id):
        """根据学号获取学生姓名"""
        with self.with_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(
                    "SELECT DISTINCT student_name FROM exam_students WHERE student_id=%s LIMIT 1",
                    (student_id,)
                )
                result = cursor.fetchone()
                if result:
                    return result['student_name']

                return None

    def get_login_count(self, exam_id, student_id):
        """获取学生登录次数"""
        # 首先获取exam_student_id
        student_exam = self.get_student_exam(student_id, exam_id)
        if not student_exam:
            return 0

        with self.with_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(
                    "SELECT COUNT(*) as count FROM student_login_history WHERE student_exam_id=%s AND action='login'",
                    (student_exam['id'],)
                )
                result = cursor.fetchone()
                return result['count'] if result else 0

    def get_login_history_count(self, exam_id, student_id):
        """获取学生所有登录历史记录总数（包括登录、退出、上线、断线等）"""
        # 首先获取exam_student_id
        student_exam = self.get_student_exam(student_id, exam_id)
        if not student_exam:
            return 0

        with self.with_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute(
                    "SELECT COUNT(*) as count FROM student_login_history WHERE student_exam_id=%s",
                    (student_exam['id'],)
                )
                result = cursor.fetchone()
                return result['count'] if result else 0

    def get_all_students_login_count(self, exam_id):
        """批量获取指定考试所有学生的登录次数，返回dict {student_id: count}"""
        with self.with_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("""
                    SELECT es.student_id, COUNT(*) as count
                    FROM exam_students es
                    LEFT JOIN student_login_history slh ON es.id = slh.student_exam_id AND slh.action='login'
                    WHERE es.exam_id = %s
                    GROUP BY es.student_id
                """, (exam_id,))
                results = cursor.fetchall()
                return {row['student_id']: row['count'] for row in results}

    def get_all_students_login_history_count(self, exam_id):
        """批量获取指定考试所有学生的登录历史总数，返回dict {student_id: count}"""
        with self.with_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("""
                    SELECT es.student_id, COUNT(slh.id) as count
                    FROM exam_students es
                    LEFT JOIN student_login_history slh ON es.id = slh.student_exam_id
                    WHERE es.exam_id = %s
                    GROUP BY es.student_id
                """, (exam_id,))
                results = cursor.fetchall()
                return {row['student_id']: row['count'] for row in results}


    def get_student_logins(self, exam_id, student_id):
        """获取学生登录历史"""
        # 首先获取exam_student_id
        student_exam = self.get_student_exam(student_id, exam_id)
        if not student_exam:
            return []

        with self.with_connection() as conn:
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

    def get_student_active_exams(self, student_id):
        """根据学号返回学生可以参加的正在进行的考试"""
        with self.with_connection() as conn:
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


    def refresh_exam_status(self):
        with self.with_connection() as conn:
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

    def update_exam_status(self, exam_id, status):
        """更新考试状态"""
        with self.with_connection() as conn:
            with conn.cursor(dictionary=True) as cursor:
                cursor.execute("UPDATE exams SET status=%s WHERE id=%s", (status, exam_id))
                result = cursor.rowcount
                
                # 更新 Redis 缓存
                if result > 0:
                    self._update_exam_cache(exam_id)
                
                return result

    def update_exam(self, exam_id, update_data):
        """更新考试信息"""
        try:
            with self.with_connection() as conn:
                with conn.cursor() as cursor:
                    # 构建动态更新SQL
                    set_clauses = []
                    values = []
                    
                    for key, value in update_data.items():
                        set_clauses.append(f"{key} = %s")
                        values.append(value)
                    
                    values.append(exam_id)  # WHERE条件的值
                    
                    sql = f"UPDATE exams SET {', '.join(set_clauses)} WHERE id = %s"
                    cursor.execute(sql, values)
                    result = cursor.rowcount
                    
                    # 更新Redis缓存
                    if result > 0:
                        self._update_exam_cache(exam_id)
                    
                    print(f"考试信息已更新: ID={exam_id}, 更新字段={list(update_data.keys())}")
                    return result > 0
        except Exception as e:
            print(f"更新考试信息失败: {e}")
            raise




# 全局清理函数
def cleanup_database_connections():
    """清理数据库连接和 Redis 数据"""
    try:
        # 创建临时的 DataAccess 实例进行清理
        da = DataAccess()
        da.cleanup_all_redis_data()
        da.close_pool()
        print("数据库连接和 Redis 数据已清理")
    except Exception as e:
        print(f"清理数据库连接和 Redis 数据时出错: {e}")

# 注册退出时的清理函数
import atexit
atexit.register(cleanup_database_connections)
