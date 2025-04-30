#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
该脚本用于修复打包后的应用程序缺少chromedriver.exe的问题
自动查找当前目录或系统中的chromedriver.exe，并复制到应用程序目录
"""

import os
import sys
import shutil
import glob
import platform
import subprocess
import zipfile
import tempfile
from pathlib import Path
import urllib.request

def print_color(message, color="green"):
    """打印彩色文本"""
    colors = {
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "reset": "\033[0m"
    }
    
    # Windows命令提示符不支持ANSI颜色代码，直接打印
    if platform.system() == "Windows" and not "TERM" in os.environ:
        print(message)
    else:
        print(f"{colors.get(color, colors['green'])}{message}{colors['reset']}")

def find_chrome_version():
    """查找当前系统中安装的Chrome版本"""
    chrome_version = None
    
    if platform.system() == "Windows":
        # 检查常见的Chrome安装路径
        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe")
        ]
        
        for chrome_path in chrome_paths:
            if os.path.exists(chrome_path):
                try:
                    # 使用wmic查询版本信息
                    result = subprocess.run(
                        ['wmic', 'datafile', 'where', f'name="{chrome_path.replace("\\", "\\\\")}"', 'get', 'Version', '/value'],
                        capture_output=True, text=True, shell=True
                    )
                    
                    if result.returncode == 0:
                        version_line = result.stdout.strip()
                        if "Version=" in version_line:
                            chrome_version = version_line.split("=", 1)[1].strip()
                            # 只保留主版本号（前两个数字）
                            chrome_version = ".".join(chrome_version.split(".")[:2])
                            break
                except:
                    pass
    
    if not chrome_version:
        print_color("无法自动检测Chrome版本，将使用最新版ChromeDriver", "yellow")
        chrome_version = "latest"
    else:
        print_color(f"检测到Chrome版本: {chrome_version}", "green")
    
    return chrome_version

def find_local_chromedriver():
    """查找本地的chromedriver.exe文件"""
    # 常见的ChromeDriver位置
    chromedriver_paths = [
        "chromedriver.exe",
        os.path.join("drivers", "chromedriver.exe"),
        os.path.join("driver", "chromedriver.exe"),
        os.path.join("browser", "chromedriver.exe"),
        os.path.join(os.path.dirname(sys.executable), "chromedriver.exe")
    ]
    
    # 检查环境变量PATH中的位置
    if "PATH" in os.environ:
        for path_dir in os.environ["PATH"].split(os.pathsep):
            chromedriver_paths.append(os.path.join(path_dir, "chromedriver.exe"))
    
    # 检查每个可能的位置
    for path in chromedriver_paths:
        if os.path.exists(path):
            print_color(f"找到本地ChromeDriver: {path}", "green")
            return path
    
    print_color("未找到本地ChromeDriver", "yellow")
    return None

def download_chromedriver(chrome_version):
    """下载与当前Chrome版本匹配的ChromeDriver"""
    base_url = "https://chromedriver.storage.googleapis.com"
    
    if chrome_version == "latest":
        # 获取最新版本
        try:
            with urllib.request.urlopen("https://chromedriver.storage.googleapis.com/LATEST_RELEASE") as response:
                version = response.read().decode("utf-8").strip()
        except:
            print_color("无法获取最新的ChromeDriver版本，使用默认版本", "yellow")
            version = "89.0.4389.23"  # 使用一个相对较新的版本作为默认值
    else:
        # 获取与Chrome主版本匹配的ChromeDriver版本
        try:
            with urllib.request.urlopen(f"https://chromedriver.storage.googleapis.com/LATEST_RELEASE_{chrome_version}") as response:
                version = response.read().decode("utf-8").strip()
        except:
            print_color(f"无法获取Chrome {chrome_version}对应的ChromeDriver版本，使用最新版本", "yellow")
            # 尝试获取最新版本
            try:
                with urllib.request.urlopen("https://chromedriver.storage.googleapis.com/LATEST_RELEASE") as response:
                    version = response.read().decode("utf-8").strip()
            except:
                print_color("无法获取最新的ChromeDriver版本，使用默认版本", "yellow")
                version = "89.0.4389.23"  # 使用一个相对较新的版本作为默认值
    
    # 构建下载URL
    download_url = f"{base_url}/{version}/chromedriver_win32.zip"
    
    # 创建临时目录
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, "chromedriver.zip")
    
    print_color(f"正在下载ChromeDriver版本 {version}...", "blue")
    try:
        # 下载ChromeDriver
        urllib.request.urlretrieve(download_url, zip_path)
        
        # 解压缩
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # 查找chromedriver.exe
        chromedriver_path = os.path.join(temp_dir, "chromedriver.exe")
        if os.path.exists(chromedriver_path):
            print_color(f"ChromeDriver {version} 下载成功", "green")
            return chromedriver_path
        else:
            print_color("下载的压缩包中未找到chromedriver.exe", "red")
            return None
    except Exception as e:
        print_color(f"下载ChromeDriver失败: {e}", "red")
        return None

def find_dist_dirs():
    """查找dist目录下的所有输出目录或可执行文件"""
    targets = []
    
    # 检查dist目录是否存在
    if not os.path.exists("dist"):
        print_color("找不到dist目录。请先运行打包程序创建可执行文件。", "red")
        return targets
    
    # 查找所有可执行文件
    if platform.system() == "Windows":
        for exe_file in glob.glob("dist/*.exe"):
            targets.append(exe_file)
    else:
        # 在Linux/macOS下，可执行文件通常没有扩展名
        for item in os.listdir("dist"):
            full_path = os.path.join("dist", item)
            if os.path.isfile(full_path) and os.access(full_path, os.X_OK):
                targets.append(full_path)
    
    # 查找多文件模式输出的目录
    for item in os.listdir("dist"):
        full_path = os.path.join("dist", item)
        if os.path.isdir(full_path):
            targets.append(full_path)
    
    return targets

def fix_chromedriver(chromedriver_path, target):
    """将chromedriver.exe复制到目标位置"""
    try:
        if os.path.isdir(target):
            # 对于多文件模式，复制到目录中
            dest_path = os.path.join(target, "chromedriver.exe")
            shutil.copy2(chromedriver_path, dest_path)
            print_color(f"已复制 chromedriver.exe 到 {dest_path}", "green")
        else:
            # 对于单文件模式，复制到可执行文件同级目录
            dest_path = os.path.join(os.path.dirname(target), "chromedriver.exe")
            shutil.copy2(chromedriver_path, dest_path)
            print_color(f"已复制 chromedriver.exe 到 {dest_path}", "green")
        return True
    except Exception as e:
        print_color(f"复制 chromedriver.exe 失败: {e}", "red")
        return False

def main():
    print_color("=" * 50, "blue")
    print_color("ChromeDriver 修复工具", "blue")
    print_color("=" * 50, "blue")
    
    # 首先查找本地的chromedriver.exe
    chromedriver_path = find_local_chromedriver()
    
    # 如果本地没有找到，则下载匹配的版本
    if not chromedriver_path:
        print_color("尝试下载匹配的ChromeDriver...", "blue")
        
        # 检测Chrome版本
        chrome_version = find_chrome_version()
        
        # 下载匹配的ChromeDriver
        chromedriver_path = download_chromedriver(chrome_version)
        
        if not chromedriver_path:
            print_color("无法获取ChromeDriver，修复失败", "red")
            return False
    
    # 查找打包输出目录
    print_color("正在查找打包输出目录...", "blue")
    targets = find_dist_dirs()
    
    if not targets:
        print_color("没有找到打包输出目录或可执行文件。", "red")
        return False
    
    # 修复每个输出目标
    success_count = 0
    for target in targets:
        print_color(f"正在修复: {target}", "blue")
        if fix_chromedriver(chromedriver_path, target):
            success_count += 1
    
    if success_count == len(targets):
        print_color(f"\n成功修复所有 {success_count} 个目标!", "green")
    else:
        print_color(f"\n部分修复成功: {success_count}/{len(targets)}", "yellow")
    
    print_color("\n请尝试运行修复后的程序。如果仍有问题，请确保您的Chrome版本与ChromeDriver版本兼容。", "blue")
    
    return success_count > 0

if __name__ == "__main__":
    main() 