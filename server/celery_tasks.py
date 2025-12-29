"""
Celery 任务定义
包含状态检测和视频合并任务
"""
import os
import sys
import time
import logging
import subprocess
import tempfile
from datetime import datetime

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from celery_config import celery_app
from data_access import DataAccess

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/celery_tasks.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ==================== 状态检测任务 ====================

@celery_app.task(name='celery_tasks.status_check_task', bind=True)
def status_check_task(self):
    """
    定时任务：检查考试状态和学生在线状态
    由 Celery Beat 每30秒触发一次
    """
    logger.info(f"[状态检测] 开始执行 (Task ID: {self.request.id})")

    data_access = DataAccess()

    try:
        now = datetime.now()

        # 获取所有考试
        try:
            exams = data_access.get_all_exams()
        except Exception as e:
            logger.error(f"[状态检测] 获取考试列表失败: {e}")
            return {"status": "error", "message": str(e)}

        status_changes = {
            "exam_status_updated": 0,
            "students_offline": 0
        }

        for exam in exams:
            exam_id = exam['id']

            try:
                # 处理 start_time
                start_time = exam['start_time']
                if isinstance(start_time, str):
                    start_time = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
                elif not isinstance(start_time, datetime):
                    raise ValueError(f"Unsupported start_time type: {type(start_time)}")

                # 处理 end_time
                end_time = exam['end_time']
                if isinstance(end_time, str):
                    end_time = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
                elif not isinstance(end_time, datetime):
                    raise ValueError(f"Unsupported end_time type: {type(end_time)}")

                # 更新考试状态
                if now < start_time:
                    new_status = 'pending'
                elif start_time <= now <= end_time:
                    new_status = 'active'
                else:
                    new_status = 'completed'

                # 如果状态发生变化，更新考试状态
                if exam['status'] != new_status:
                    data_access.update_exam_status(exam_id, new_status)
                    logger.info(f"[状态检测] 考试状态更新: {exam['name']} (ID: {exam_id}) {exam['status']} -> {new_status}")
                    status_changes["exam_status_updated"] += 1

                # 处理已结束的考试
                if new_status == 'completed':
                    # 考试刚结束时(状态刚从active变为completed)，自动登出所有online学生
                    if exam['status'] == 'active':
                        students = data_access.get_exam_students(exam_id)
                        for student in students:
                            if student['status'] == 'online':
                                student_id = student['student_id']
                                data_access.update_student_status(student_id, exam_id, 'logout')
                                # 清理Redis中的活跃状态
                                data_access.set_student_realtime_status(exam_id, student_id, status='logout')
                                logger.info(f"[状态检测] 自动登出: 考试={exam_id}, 学生={student_id} ({student.get('student_name', 'Unknown')}), 原因=考试已结束")
                                status_changes["students_auto_logout"] = status_changes.get("students_auto_logout", 0) + 1

                    # 考试结束30分钟后自动合并视频
                    time_since_end = (now - end_time).total_seconds()
                    if time_since_end >= 1800:  # 30分钟 = 1800秒
                        # 获取所有非 logout 状态的学生
                        students = data_access.get_exam_students(exam_id)
                        for student in students:
                            if student['status'] != 'logout':
                                student_id = student['student_id']
                                # 检查学生录屏目录是否存在（存在说明未合并）
                                student_recordings_dir = os.path.join("server_data", str(exam_id), "recordings", str(student_id))
                                if os.path.exists(student_recordings_dir):
                                    # 触发视频合并任务
                                    logger.info(f"[状态检测] 触发视频合并: 考试={exam_id}, 学生={student_id} ({student.get('student_name', 'Unknown')}), 状态={student['status']}")
                                    merge_videos_task.delay(exam_id, student_id, student.get('student_name', 'Unknown'))

                # 只检查正在进行的考试的学生状态
                if new_status == 'active':
                    # 使用Redis ZSet获取超过60秒未活跃的学生（完全依赖Redis）
                    # 客户端心跳间隔30秒，60秒 = 2倍心跳间隔，容忍1次心跳丢失
                    inactive_student_ids = data_access.get_inactive_students(exam_id, timeout_seconds=60)

                    if inactive_student_ids:
                        # 批量获取学生信息
                        students_dict = {}
                        students = data_access.get_exam_students(exam_id)
                        for student in students:
                            students_dict[student['student_id']] = student

                        # 处理每个超时的学生
                        for student_id in inactive_student_ids:
                            student = students_dict.get(student_id)
                            if not student:
                                continue

                            # 跳过已结束考试的学生
                            if student['status'] in ['logout']:
                                continue

                            # 获取当前状态
                            rt_status = data_access.get_student_realtime_status(exam_id, student_id)
                            current_status = rt_status.get('status') or student['status']

                            # 只标记状态为online的学生
                            if current_status == 'online':
                                # 更新 DB 状态
                                data_access.update_student_status(student_id, exam_id, 'offline')

                                # 写入掉线历史
                                try:
                                    student_exam = data_access.get_student_exam(student_id, exam_id)
                                    if student_exam:
                                        data_access.add_login_history(student_exam['id'], 'offline', now.strftime("%Y-%m-%d %H:%M:%S"), 'system')
                                except Exception as e:
                                    logger.warning(f"[状态检测] 写入掉线历史失败: {e}")

                                # 更新 Redis 实时状态（从ZSet中移除）
                                data_access.set_student_realtime_status(exam_id, student_id, status='offline', last_seen=now.strftime("%Y-%m-%d %H:%M:%S"))

                                logger.info(f"[状态检测] 学生掉线: {student['student_name']} (ID: {student_id}, 考试: {exam_id})")
                                status_changes["students_offline"] += 1

            except Exception as e:
                logger.error(f"[状态检测] 处理考试 {exam_id} 时出错: {str(e)}")
                continue

        logger.info(f"[状态检测] 执行完成: {status_changes}")
        return {"status": "success", "changes": status_changes}

    except Exception as e:
        logger.error(f"[状态检测] 执行失败: {str(e)}")
        return {"status": "error", "message": str(e)}


# ==================== 视频合并任务 ====================

@celery_app.task(name='celery_tasks.merge_videos_task', bind=True, max_retries=3)
def merge_videos_task(self, exam_id, student_id, student_name, data_dir="server_data"):
    """
    队列任务：合并学生的录屏视频片段

    Args:
        exam_id: 考试ID
        student_id: 学生ID
        student_name: 学生姓名
        data_dir: 数据目录
    """
    logger.info(f"[视频合并] 开始处理: 考试={exam_id}, 学生={student_id} ({student_name}), Task ID={self.request.id}")

    try:
        # 1. 查找学生专用录屏目录中的所有录屏片段
        student_recordings_dir = os.path.join(data_dir, str(exam_id), "recordings", str(student_id))

        if not os.path.exists(student_recordings_dir):
            logger.warning(f"[视频合并] 学生录屏目录不存在: {student_recordings_dir}")
            return {"status": "error", "message": "学生录屏目录不存在"}

        files = [f for f in os.listdir(student_recordings_dir)
                 if f.startswith(f"{student_id}_") and
                 f.endswith(('.mp4', '.webm', '.avi'))]

        if not files:
            logger.warning(f"[视频合并] 未找到录屏片段: {student_id}, {exam_id}")
            # 即使没有录屏文件，也要删除空目录
            try:
                os.rmdir(student_recordings_dir)
                logger.info(f"[视频合并] 已删除空的学生录屏目录: {student_recordings_dir}")
            except Exception as e:
                logger.warning(f"[视频合并] 删除空目录失败: {e}")
            return {"status": "success", "message": "无录屏文件，已清理空目录"}

        # 2. 按时间戳或序号排序
        def extract_sort_key(filename):
            """提取排序键：优先使用序号，其次使用时间戳"""
            try:
                name_without_ext = os.path.splitext(filename)[0]
                # 格式: student_id_timestamp_seq_0001.mp4
                if '_seq_' in name_without_ext:
                    # 提取序号部分
                    seq_part = name_without_ext.split('_seq_')[-1]
                    return (0, int(seq_part))  # (优先级, 序号)
                else:
                    # 提取时间戳部分
                    timestamp = name_without_ext.rsplit("_", 1)[-1]
                    return (1, timestamp)  # (优先级, 时间戳)
            except:
                return (2, filename)  # 降级为文件名排序

        files.sort(key=extract_sort_key)
        video_paths = [os.path.join(student_recordings_dir, f) for f in files]

        logger.info(f"[视频合并] 找到 {len(files)} 个视频片段: {files}")

        # 检查序号是否连续（只针对带 _seq_ 的文件）
        seq_files = [f for f in files if '_seq_' in f]
        if seq_files:
            try:
                # 提取所有序号
                seq_numbers = []
                for f in seq_files:
                    name_without_ext = os.path.splitext(f)[0]
                    seq_part = name_without_ext.split('_seq_')[-1]
                    seq_numbers.append(int(seq_part))

                seq_numbers.sort()

                # 检查连续性：应该是 1, 2, 3, ..., n
                expected_seqs = list(range(1, len(seq_numbers) + 1))
                missing_seqs = []

                if seq_numbers != expected_seqs:
                    # 找出缺失的序号
                    all_seqs_set = set(range(1, max(seq_numbers) + 1))
                    actual_seqs_set = set(seq_numbers)
                    missing_seqs = sorted(all_seqs_set - actual_seqs_set)

                    logger.warning(f"[视频合并] 检测到序号缺失: 考试={exam_id}, 学生={student_id}, 缺失序号={missing_seqs}, 实际序号={seq_numbers}")
                else:
                    logger.info(f"[视频合并] 序号连续性检查通过: 序号范围 1-{len(seq_numbers)}")
            except Exception as e:
                logger.error(f"[视频合并] 序号连续性检查失败: {e}")


        # 3. 合并为一个视频文件，保存到主recordings目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # 根据片段的扩展名生成合并后的文件扩展名
        first_ext = os.path.splitext(files[0])[1] if files else '.mp4'
        output_filename = f"{student_id}_{student_name}_{timestamp}{first_ext}"
        main_recordings_dir = os.path.join(data_dir, str(exam_id), "recordings")
        output_path = os.path.join(main_recordings_dir, output_filename)

        # 4. 执行 FFmpeg 合并
        success = _merge_videos_with_ffmpeg(video_paths, output_path)

        if success:
            logger.info(f"[视频合并] 合并成功: {output_path}")
            # 5. 合并成功后删除学生专用目录及其所有内容
            try:
                import shutil
                shutil.rmtree(student_recordings_dir)
                logger.info(f"[视频合并] 已删除学生录屏目录: {student_recordings_dir}")
            except Exception as e:
                logger.warning(f"[视频合并] 删除学生录屏目录失败: {e}")

            return {
                "status": "success",
                "output_file": output_path,
                "segments_count": len(files),
                "student_id": student_id,
                "exam_id": exam_id
            }
        else:
            logger.error(f"[视频合并] 合并失败: {student_id}, {exam_id}")
            # 重试机制
            raise self.retry(countdown=60, max_retries=3)

    except Exception as e:
        logger.error(f"[视频合并] 处理任务出错: {str(e)}")
        raise


def _merge_videos_with_ffmpeg(video_paths, output_path):
    """
    使用 FFmpeg 合并视频

    Args:
        video_paths: 视频文件路径列表
        output_path: 输出文件路径

    Returns:
        bool: 是否合并成功
    """
    if not video_paths:
        logger.warning("[FFmpeg] 没有视频文件需要合并")
        return False

    try:
        # 1. 生成 ffmpeg concat 列表文件
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as f:
            for path in video_paths:
                abs_path = os.path.abspath(path).replace("\\", "/").replace("'", "'\\''")
                f.write(f"file '{abs_path}'\n")
            filelist_path = f.name

        # 2. 构造 ffmpeg 命令
        cmd = [
            'ffmpeg',
            '-y',  # 覆盖输出
            '-f', 'concat',
            '-safe', '0',
            '-i', filelist_path,
            '-c', 'copy',
            output_path
        ]

        logger.info(f"[FFmpeg] 执行命令: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)

        if result.returncode != 0:
            logger.error(f"[FFmpeg] 合并失败: {result.stderr}")
            return False

        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info(f"[FFmpeg] 合并成功: {output_path}")
            return True
        else:
            logger.error("[FFmpeg] 合并失败，输出文件无效")
            return False

    except subprocess.TimeoutExpired:
        logger.error("[FFmpeg] 合并超时（30分钟）")
        return False
    except Exception as e:
        logger.error(f"[FFmpeg] 合并出错: {e}")
        return False
    finally:
        try:
            if 'filelist_path' in locals() and os.path.exists(filelist_path):
                os.remove(filelist_path)
        except Exception as e:
            logger.warning(f"[FFmpeg] 删除临时文件失败: {e}")
