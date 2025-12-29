#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
录屏管理工具
用于管理服务器上的录屏文件
"""

import os
import json
import requests
import shutil
from datetime import datetime, timedelta
import argparse

class ScreenRecordingManager:
    """录屏管理器"""
    
    def __init__(self, server_url="http://localhost:5000"):
        self.server_url = server_url
        self.recordings_dir = "server_data/screen_recordings"
        self.screenshots_dir = "server_data/screenshots"
    
    def list_recordings(self, exam_id=None, student_id=None):
        """列出录屏文件"""
        print("=== 录屏文件列表 ===")
        
        if exam_id and student_id:
            # 获取特定学生的录屏
            try:
                response = requests.get(
                    f"{self.server_url}/api/exams/{exam_id}/students/{student_id}/recordings",
                    timeout=10
                )
                if response.status_code == 200:
                    recordings = response.json().get('recordings', [])
                    self._display_recordings(recordings)
                else:
                    print(f"获取录屏列表失败: {response.status_code}")
            except Exception as e:
                print(f"获取录屏列表出错: {e}")
        else:
            # 列出所有录屏文件
            if os.path.exists(self.recordings_dir):
                files = os.listdir(self.recordings_dir)
                mp4_files = [f for f in files if f.endswith('.mp4')]
                mp4_files.sort(reverse=True)
                
                print(f"找到 {len(mp4_files)} 个录屏文件:")
                for i, filename in enumerate(mp4_files[:20], 1):  # 只显示前20个
                    file_path = os.path.join(self.recordings_dir, filename)
                    file_size = os.path.getsize(file_path)
                    file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                    print(f"{i:2d}. {filename}")
                    print(f"    大小: {self._format_size(file_size)}")
                    print(f"    时间: {file_time.strftime('%Y-%m-%d %H:%M:%S')}")
                    print()
            else:
                print("录屏目录不存在")
    
    def list_frames(self, exam_id=None, student_id=None):
        """列出帧文件"""
        print("=== 帧文件列表 ===")
        
        if exam_id and student_id:
            # 获取特定学生的帧
            try:
                response = requests.get(
                    f"{self.server_url}/api/exams/{exam_id}/students/{student_id}/frames",
                    timeout=10
                )
                if response.status_code == 200:
                    frames = response.json().get('frames', [])
                    self._display_frames(frames)
                else:
                    print(f"获取帧列表失败: {response.status_code}")
            except Exception as e:
                print(f"获取帧列表出错: {e}")
        else:
            # 列出所有帧文件
            if os.path.exists(self.screenshots_dir):
                files = os.listdir(self.screenshots_dir)
                frame_files = [f for f in files if f.startswith('frame_') and f.endswith('.jpg')]
                frame_files.sort(reverse=True)
                
                print(f"找到 {len(frame_files)} 个帧文件:")
                for i, filename in enumerate(frame_files[:20], 1):  # 只显示前20个
                    file_path = os.path.join(self.screenshots_dir, filename)
                    file_size = os.path.getsize(file_path)
                    file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                    print(f"{i:2d}. {filename}")
                    print(f"    大小: {self._format_size(file_size)}")
                    print(f"    时间: {file_time.strftime('%Y-%m-%d %H:%M:%S')}")
                    print()
            else:
                print("截图目录不存在")
    
    def download_recording(self, filename, output_dir="downloads"):
        """下载录屏文件"""
        try:
            # 创建下载目录
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            # 下载文件
            url = f"{self.server_url}/screen_recordings/{filename}"
            response = requests.get(url, stream=True, timeout=30)
            
            if response.status_code == 200:
                output_path = os.path.join(output_dir, filename)
                with open(output_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                file_size = os.path.getsize(output_path)
                print(f"下载成功: {filename}")
                print(f"保存位置: {output_path}")
                print(f"文件大小: {self._format_size(file_size)}")
            else:
                print(f"下载失败: {response.status_code}")
                
        except Exception as e:
            print(f"下载出错: {e}")
    
    def cleanup_old_files(self, days=7):
        """清理旧文件"""
        print(f"=== 清理 {days} 天前的文件 ===")
        
        cutoff_date = datetime.now() - timedelta(days=days)
        deleted_count = 0
        
        # 清理录屏文件
        if os.path.exists(self.recordings_dir):
            for filename in os.listdir(self.recordings_dir):
                if filename.endswith('.mp4'):
                    file_path = os.path.join(self.recordings_dir, filename)
                    file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                    
                    if file_time < cutoff_date:
                        try:
                            os.remove(file_path)
                            print(f"删除录屏文件: {filename}")
                            deleted_count += 1
                        except Exception as e:
                            print(f"删除失败 {filename}: {e}")
        
        # 清理帧文件
        if os.path.exists(self.screenshots_dir):
            for filename in os.listdir(self.screenshots_dir):
                if filename.startswith('frame_') and filename.endswith('.jpg'):
                    file_path = os.path.join(self.screenshots_dir, filename)
                    file_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                    
                    if file_time < cutoff_date:
                        try:
                            os.remove(file_path)
                            print(f"删除帧文件: {filename}")
                            deleted_count += 1
                        except Exception as e:
                            print(f"删除失败 {filename}: {e}")
        
        print(f"清理完成，共删除 {deleted_count} 个文件")
    
    def get_storage_info(self):
        """获取存储信息"""
        print("=== 存储信息 ===")
        
        total_size = 0
        file_count = 0
        
        # 统计录屏文件
        if os.path.exists(self.recordings_dir):
            for filename in os.listdir(self.recordings_dir):
                if filename.endswith('.mp4'):
                    file_path = os.path.join(self.recordings_dir, filename)
                    if os.path.isfile(file_path):
                        total_size += os.path.getsize(file_path)
                        file_count += 1
        
        # 统计帧文件
        frame_count = 0
        frame_size = 0
        if os.path.exists(self.screenshots_dir):
            for filename in os.listdir(self.screenshots_dir):
                if filename.startswith('frame_') and filename.endswith('.jpg'):
                    file_path = os.path.join(self.screenshots_dir, filename)
                    if os.path.isfile(file_path):
                        frame_size += os.path.getsize(file_path)
                        frame_count += 1
        
        print(f"录屏文件: {file_count} 个，总大小: {self._format_size(total_size)}")
        print(f"帧文件: {frame_count} 个，总大小: {self._format_size(frame_size)}")
        print(f"总计: {file_count + frame_count} 个文件，{self._format_size(total_size + frame_size)}")
    
    def _display_recordings(self, recordings):
        """显示录屏列表"""
        if not recordings:
            print("没有找到录屏文件")
            return
        
        print(f"找到 {len(recordings)} 个录屏文件:")
        for i, recording in enumerate(recordings[:20], 1):  # 只显示前20个
            print(f"{i:2d}. {recording.get('filename', 'Unknown')}")
            print(f"    时间: {recording.get('timestamp', 'Unknown')}")
            print(f"    大小: {self._format_size(recording.get('file_size', 0))}")
            print(f"    帧率: {recording.get('fps', 'Unknown')} FPS")
            print(f"    质量: {recording.get('quality', 'Unknown')}%")
            print()
    
    def _display_frames(self, frames):
        """显示帧列表"""
        if not frames:
            print("没有找到帧文件")
            return
        
        print(f"找到 {len(frames)} 个帧文件:")
        for i, frame in enumerate(frames[:20], 1):  # 只显示前20个
            print(f"{i:2d}. {frame.get('filename', 'Unknown')}")
            print(f"    时间: {frame.get('timestamp', 'Unknown')}")
            print(f"    类型: {frame.get('type', 'Unknown')}")
            print()
    
    def _format_size(self, size_bytes):
        """格式化文件大小"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.1f} {size_names[i]}"

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="录屏管理工具")
    parser.add_argument("--server", default="http://localhost:5000", help="服务器URL")
    parser.add_argument("--action", choices=["list", "list-frames", "download", "cleanup", "info"], 
                       default="list", help="操作类型")
    parser.add_argument("--exam-id", help="考试ID")
    parser.add_argument("--student-id", help="学生ID")
    parser.add_argument("--filename", help="文件名（用于下载）")
    parser.add_argument("--output-dir", default="downloads", help="下载输出目录")
    parser.add_argument("--days", type=int, default=7, help="清理天数（默认7天）")
    
    args = parser.parse_args()
    
    manager = ScreenRecordingManager(args.server)
    
    if args.action == "list":
        manager.list_recordings(args.exam_id, args.student_id)
    elif args.action == "list-frames":
        manager.list_frames(args.exam_id, args.student_id)
    elif args.action == "download":
        if args.filename:
            manager.download_recording(args.filename, args.output_dir)
        else:
            print("请指定要下载的文件名 (--filename)")
    elif args.action == "cleanup":
        manager.cleanup_old_files(args.days)
    elif args.action == "info":
        manager.get_storage_info()

if __name__ == "__main__":
    main() 