"""
视频合并工具模块
提供 FFmpeg 视频合并功能，供 exam_scheduler.py 和 server.py 共同使用
"""

import os
import shutil
import logging
import subprocess
import tempfile
from datetime import datetime

logger = logging.getLogger(__name__)


def merge_videos_with_ffmpeg(video_paths, output_path):
    """使用 FFmpeg 将多个视频片段合并为一个文件"""
    if not video_paths:
        return False

    filelist_path = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as f:
            for path in video_paths:
                abs_path = os.path.abspath(path).replace("\\", "/").replace("'", "\\'")
                f.write(f"file '{abs_path}'\n")
            filelist_path = f.name

        cmd = ['ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', filelist_path, '-c', 'copy', output_path]
        logger.info(f"[FFmpeg] {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)

        if result.returncode != 0:
            logger.error(f"[FFmpeg] 合并失败: {result.stderr[-500:]}")
            return False

        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info(f"[FFmpeg] 合并成功: {output_path}")
            return True

        logger.error("[FFmpeg] 输出文件无效")
        return False

    except subprocess.TimeoutExpired:
        logger.error("[FFmpeg] 超时（30分钟）")
        return False
    except Exception as e:
        logger.error(f"[FFmpeg] 出错: {e}")
        return False
    finally:
        if filelist_path and os.path.exists(filelist_path):
            try:
                os.remove(filelist_path)
            except Exception:
                pass


def merge_student_videos(exam_id, student_id, student_name, data_dir="server_data"):
    """合并指定学生的所有录屏片段，完成后清理片段目录"""
    student_recordings_dir = os.path.join(data_dir, str(exam_id), "recordings", str(student_id))

    if not os.path.exists(student_recordings_dir):
        return

    files = [f for f in os.listdir(student_recordings_dir)
             if f.startswith(f"{student_id}_") and f.endswith(('.mp4', '.webm', '.avi'))]

    if not files:
        try:
            os.rmdir(student_recordings_dir)
        except Exception:
            pass
        return

    def _sort_key(filename):
        try:
            name = os.path.splitext(filename)[0]
            if '_seq_' in name:
                return (0, int(name.split('_seq_')[-1]))
            return (1, name.rsplit('_', 1)[-1])
        except Exception:
            return (2, filename)

    files.sort(key=_sort_key)

    # 检查序列号连续性
    seq_files = [f for f in files if '_seq_' in f]
    if seq_files:
        try:
            seq_numbers = [int(os.path.splitext(f)[0].split('_seq_')[-1]) for f in seq_files]
            missing = sorted(set(range(1, max(seq_numbers) + 1)) - set(seq_numbers))
            if missing:
                logger.warning(f"[视频合并] 序号不连续，跳过: exam={exam_id}, student={student_id}, 缺失={missing}")
                return
        except Exception as e:
            logger.error(f"[视频合并] 序号检查失败: {e}")

    video_paths = [os.path.join(student_recordings_dir, f) for f in files]
    first_ext = os.path.splitext(files[0])[1]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename = f"{student_id}_{student_name}_{timestamp}{first_ext}"
    output_path = os.path.join(data_dir, str(exam_id), "recordings", output_filename)

    logger.info(f"[视频合并] 开始: exam={exam_id}, student={student_id}, 片段数={len(files)}")

    if merge_videos_with_ffmpeg(video_paths, output_path):
        try:
            shutil.rmtree(student_recordings_dir)
        except Exception as e:
            logger.warning(f"[视频合并] 清理目录失败: {e}")
        logger.info(f"[视频合并] 完成: {output_path}")
    else:
        logger.error(f"[视频合并] 失败: exam={exam_id}, student={student_id}")
