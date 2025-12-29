#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import platform
import shutil
import argparse

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

def run_command(command, error_message="命令执行失败"):
    """运行命令并处理错误"""
    try:
        process = subprocess.run(command, shell=True, check=True, 
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                             universal_newlines=True)
        return process.stdout
    except subprocess.CalledProcessError as e:
        print_color(f"{error_message}: {e}", "red")
        print_color(f"错误详情: {e.stderr}", "red")
        return None

def create_virtual_environment(venv_path, force=False):
    """创建Python虚拟环境"""
    if os.path.exists(venv_path):
        if force:
            print_color(f"删除已存在的虚拟环境: {venv_path}", "yellow")
            shutil.rmtree(venv_path)
        else:
            print_color(f"虚拟环境已存在: {venv_path}", "yellow")
            return False
    
    print_color("正在创建虚拟环境...", "blue")
    result = run_command(f"{sys.executable} -m venv {venv_path}", 
                      "创建虚拟环境失败")
    
    if result is not None:
        print_color(f"成功创建虚拟环境: {venv_path}")
        return True
    return False

def install_requirements(venv_path, requirements_file='requirements.txt'):
    """在虚拟环境中安装依赖"""
    # 检查requirements.txt文件是否存在
    if not os.path.exists(requirements_file):
        print_color(f"依赖文件不存在: {requirements_file}", "red")
        return False
    
    # 根据不同操作系统获取激活命令和pip路径
    if platform.system() == "Windows":
        pip_path = os.path.join(venv_path, "Scripts", "pip")
        activate_path = os.path.join(venv_path, "Scripts", "activate")
        command = f'"{activate_path}" && "{pip_path}" install -r {requirements_file}'
    else:  # macOS或Linux
        pip_path = os.path.join(venv_path, "bin", "pip")
        activate_path = os.path.join(venv_path, "bin", "activate")
        command = f'source "{activate_path}" && "{pip_path}" install -r {requirements_file}'
    
    print_color("正在安装依赖...", "blue")
    result = run_command(command, "安装依赖失败")
    
    if result is not None:
        print_color("依赖安装成功")
        return True
    return False

def create_activation_script(venv_path, output_path='.'):
    """创建激活虚拟环境的脚本"""
    if platform.system() == "Windows":
        script_name = "activate_env.bat"
        script_content = f'@echo off\necho 正在激活考试监控系统环境...\ncall "{os.path.join(venv_path, "Scripts", "activate")}"\necho 环境已激活，可以运行考试监控系统\ncmd /k'
    else:  # macOS或Linux
        script_name = "activate_env.sh"
        script_content = f'#!/bin/bash\necho "正在激活考试监控系统环境..."\nsource "{os.path.join(venv_path, "bin", "activate")}"\necho "环境已激活，可以运行考试监控系统"\nexec $SHELL'
    
    script_path = os.path.join(output_path, script_name)
    
    try:
        with open(script_path, 'w') as f:
            f.write(script_content)
        
        # 为Linux/macOS脚本添加执行权限
        if platform.system() != "Windows":
            os.chmod(script_path, 0o755)
            
        print_color(f"已创建激活脚本: {script_path}")
        return True
    except Exception as e:
        print_color(f"创建激活脚本失败: {e}", "red")
        return False

def create_run_script(venv_path, output_path='.'):
    """创建一键运行脚本"""
    if platform.system() == "Windows":
        script_name = "run_exam_client.bat"
        script_content = f'@echo off\necho 正在启动考试监控系统...\ncall "{os.path.join(venv_path, "Scripts", "activate")}"\npython main.py\npause'
    else:  # macOS或Linux
        script_name = "run_exam_client.sh"
        script_content = f'#!/bin/bash\necho "正在启动考试监控系统..."\nsource "{os.path.join(venv_path, "bin", "activate")}"\npython main.py'
    
    script_path = os.path.join(output_path, script_name)
    
    try:
        with open(script_path, 'w') as f:
            f.write(script_content)
        
        # 为Linux/macOS脚本添加执行权限
        if platform.system() != "Windows":
            os.chmod(script_path, 0o755)
            
        print_color(f"已创建启动脚本: {script_path}")
        return True
    except Exception as e:
        print_color(f"创建启动脚本失败: {e}", "red")
        return False

def check_python_version():
    """检查Python版本是否符合要求"""
    major, minor = sys.version_info.major, sys.version_info.minor
    if major < 3 or (major == 3 and minor < 6):
        print_color(f"当前Python版本 {major}.{minor} 过低，至少需要Python 3.6", "red")
        return False
    return True

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='考试监控系统虚拟环境配置工具')
    parser.add_argument('--path', default='venv', help='虚拟环境路径，默认为venv')
    parser.add_argument('--force', action='store_true', help='强制重新创建虚拟环境')
    parser.add_argument('--requirements', default='requirements.txt', help='依赖文件路径')
    args = parser.parse_args()
    
    print_color("=" * 40, "blue")
    print_color("考试监控系统虚拟环境配置工具", "blue")
    print_color("=" * 40, "blue")
    
    # 检查Python版本
    if not check_python_version():
        return
    
    # 创建虚拟环境
    if create_virtual_environment(args.path, args.force):
        # 安装依赖
        install_requirements(args.path, args.requirements)
        
        # 创建激活脚本
        create_activation_script(args.path)
        
        # 创建运行脚本
        create_run_script(args.path)
        
        print_color("\n虚拟环境配置完成！", "green")
        
        # 输出使用指南
        print_color("\n使用指南:", "yellow")
        if platform.system() == "Windows":
            print_color("  1. 双击 activate_env.bat 激活环境")
            print_color("  2. 双击 run_exam_client.bat 直接运行系统")
        else:
            print_color("  1. 执行 ./activate_env.sh 激活环境")
            print_color("  2. 执行 ./run_exam_client.sh 直接运行系统")
    else:
        print_color("\n虚拟环境配置未完成。", "red")

if __name__ == "__main__":
    main() 