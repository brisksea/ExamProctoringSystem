import os
import threading
import time
import logging
from datetime import datetime
import cv2


class MergeManager:
    def __init__(self, data_dir="server_data"):
        print("init:", os.getpid())
        # 使用同一个目录
        self.data_dir = data_dir

        self.task_queue = []
        self.lock = threading.Lock()
        self.running = False
        self.worker = None
        self.logger = logging.getLogger("MergeManager")
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('merge_manager.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )

    def start(self):
        """启动 MergeManager 工作线程"""
        if self.running:
            self.logger.warning("MergeManager 已经在运行中")
            return

        self.running = True
        self.worker = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker.start()
        self.logger.info(f"MergeManager 已启动 (PID: {os.getpid()})")

    def add_merge_task(self, exam_id, student_id, student_name):
        with self.lock:
            self.task_queue.append((exam_id, student_id, student_name))
            self.logger.info(f"任务已加入队列: {exam_id}, {student_id}, {student_name}")

    def _worker_loop(self):
        while self.running:
            task = None
            with self.lock:
                if self.task_queue:
                    task = self.task_queue.pop(0)
            if task:
                print("process task:", os.getpid())
                self._process_task(*task)
            else:
                #print("no task:", os.getpid())
                time.sleep(2)

    def _process_task(self, exam_id, student_id, student_name):
        try:
            print("student_name", student_name)
            # 1. 查找学生专用录屏目录中的所有录屏片段
            student_recordings_dir = os.path.join(self.data_dir, str(exam_id), "recordings", str(student_id))

            if not os.path.exists(student_recordings_dir):
                self.logger.warning(f"学生录屏目录不存在: {student_recordings_dir}")
                return

            files = [f for f in os.listdir(student_recordings_dir)
                     if f.startswith(f"{student_id}_") and
                     f.endswith(('.mp4', '.webm', '.avi'))]

            if not files:
                self.logger.warning(f"未找到录屏片段: {student_id}, {exam_id}")
                # 即使没有录屏文件，也要删除空目录
                try:
                    os.rmdir(student_recordings_dir)
                    self.logger.info(f"已删除空的学生录屏目录: {student_recordings_dir}")
                except Exception as e:
                    self.logger.warning(f"删除空目录失败: {e}")
                return

            # 2. 按时间戳排序
            def extract_ts(filename):
                try:
                    # 移除扩展名后提取时间戳
                    name_without_ext = os.path.splitext(filename)[0]
                    return name_without_ext.rsplit("_", 1)[-1]
                except:
                    return ""
            files.sort(key=extract_ts)
            video_paths = [os.path.join(student_recordings_dir, f) for f in files]

            # 3. 合并为一个视频文件，保存到主recordings目录
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # 根据片段的扩展名生成合并后的文件扩展名
            first_ext = os.path.splitext(files[0])[1] if files else '.mp4'
            output_filename = f"{student_id}_{timestamp}{first_ext}"
            main_recordings_dir = os.path.join(self.data_dir, str(exam_id), "recordings")
            output_path = os.path.join(main_recordings_dir, output_filename)

            success = self._merge_videos(video_paths, output_path)
            if success:
                self.logger.info(f"合并成功: {output_path}")
                # 4. 合并成功后删除学生专用目录及其所有内容
                try:
                    import shutil
                    shutil.rmtree(student_recordings_dir)
                    self.logger.info(f"已删除学生录屏目录: {student_recordings_dir}")
                except Exception as e:
                    self.logger.warning(f"删除学生录屏目录失败: {e}")
            else:
                self.logger.error(f"合并失败: {student_id}, {exam_id}")
        except Exception as e:
            self.logger.error(f"处理合并任务出错: {e}")

    def _merge_videos(self, video_paths, output_path, fps=10):
        if not video_paths:
            self.logger.warning("没有视频文件需要合并")
            return False
        import subprocess
        import tempfile
        try:
            # 1. 生成ffmpeg concat列表文件
            with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as f:
                for path in video_paths:
                    abs_path = os.path.abspath(path).replace("\\", "/").replace("'", "'\\''")
                    f.write(f"file '{abs_path}'\n")
                filelist_path = f.name

            # 2. 构造ffmpeg命令
            cmd = [
                'ffmpeg',
                '-y',  # 覆盖输出
                '-f', 'concat',
                '-safe', '0',
                '-i', filelist_path,
                '-c', 'copy',
                output_path
            ]
            self.logger.info(f"执行ffmpeg合并命令: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                self.logger.error(f"ffmpeg合并失败: {result.stderr}")
                return False
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                self.logger.info(f"ffmpeg合并成功: {output_path}")
                return True
            else:
                self.logger.error("ffmpeg合并失败，输出文件无效")
                return False
        except Exception as e:
            self.logger.error(f"ffmpeg合并出错: {e}")
            return False
        finally:
            try:
                if 'filelist_path' in locals() and os.path.exists(filelist_path):
                    os.remove(filelist_path)
            except Exception as e:
                self.logger.warning(f"删除临时文件失败: {e}")

    def stop(self):
        """停止 MergeManager 工作线程"""
        if not self.running:
            self.logger.warning("MergeManager 未在运行")
            return

        self.running = False
        if self.worker:
            self.worker.join(timeout=5)
        self.logger.info(f"MergeManager 已停止 (PID: {os.getpid()})") 
