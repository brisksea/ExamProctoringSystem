#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import platform
import argparse
from datetime import datetime

def print_color(message, color="green"):
    colors = {
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "reset": "\033[0m"
    }
    if platform.system() == "Windows" and not "TERM" in os.environ:
        print(message)
    else:
        print(f"{colors.get(color, colors['green'])}{message}{colors['reset']}")

def run_command(command, error_message="命令执行失败"):
    try:
        command_str = ' '.join(command) if isinstance(command, list) else command
        print_color(f"执行命令: {command_str}", "blue")
        if isinstance(command, str):
            if platform.system() != "Windows":
                import shlex
                command = shlex.split(command)
            # On Windows, we leave command as a string, subprocess.run handles it fine
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print_color(f"{error_message}: {e}", "red")
        if e.stderr:
            print_color(f"错误详情: {e.stderr}", "red")
        if e.stdout:
            print_color(f"输出信息: {e.stdout}", "yellow")
        return None

def check_pyinstaller():
    try:
        import PyInstaller
        return True
    except ImportError:
        return False

def install_pyinstaller():
    command = f'{sys.executable} -m pip install pyinstaller'
    print_color("安装PyInstaller...", "blue")
    result = run_command(command, "安装PyInstaller失败")
    return result is not None

def create_spec_file(app_name, icon_path=None, main_script='main.py', console=False):
    hidden_imports = [
        'requests',
        'selenium',
        'webdriver_manager',
        'numpy', 'numpy._core', 'numpy._core._exceptions',
        'numpy._core.multiarray', 'numpy._core.umath',
        'numpy._core.arrayprint', 'numpy._core.fromnumeric',
        'numpy._core.defchararray', 'numpy._core.records',
        'numpy._core.memmap', 'numpy._core.function_base',
        'cv2', 'mss', 'PIL', 'PIL.Image'
    ]
    hidden_imports_str = ', '.join([f"'{imp}'" for imp in hidden_imports])
    
    # 添加数据文件
    datas = []
    if os.path.exists('openh264-1.8.0-win64.dll'):
        datas.append("('openh264-1.8.0-win64.dll', '.')")
    if os.path.exists('supervise.png'):
        datas.append("('supervise.png', '.')")
        
    datas_str = ', '.join(datas)

    # 确保图标存在
    if icon_path and not os.path.exists(icon_path):
        print_color(f"图标文件不存在: {icon_path}，将使用默认图标", "yellow")
        icon_path = None
    if not icon_path and os.path.exists("exam_monitor.ico"):
        icon_path = "exam_monitor.ico"

    spec_content = f"""# -*- mode: python ; coding: utf-8 -*-
block_cipher = None

a = Analysis([
    '{main_script}'
],
    pathex=[],
    binaries=[],
    datas=[{datas_str}],
    hiddenimports=[{hidden_imports_str}],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=['flask', 'mysql', 'matplotlib', 'pandas', 'scipy', 'mkl', 'tcl', 'tk', 'PIL.ImageQt', 'PIL.ImageTk'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='{app_name}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console={str(console)},
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    {f"icon='{icon_path}'," if icon_path else ''}
)
"""
    spec_path = f"{app_name}.spec"
    with open(spec_path, 'w', encoding='utf-8') as f:
        f.write(spec_content)
    print_color(f"已创建规格文件: {spec_path}")
    return spec_path

def package_application(spec_path, app_name):
    try:
        python_exe = sys.executable
        python_exe = f'"{python_exe}"' if ' ' in python_exe else python_exe
        spec_path = f'"{spec_path}"' if ' ' in spec_path else spec_path
        command = [python_exe, "-m", "PyInstaller", spec_path]
        original_dir = os.getcwd()
        spec_dir = os.path.dirname(os.path.abspath(spec_path.strip('"')))
        os.chdir(spec_dir)
        try:
            print_color(f"开始打包{app_name}...", "blue")
            result = run_command(command, "打包应用程序失败")
            if result is not None:
                print_color(f"应用程序打包成功: dist/{app_name}", "green")
                return True
            return False
        finally:
            os.chdir(original_dir)
    except Exception as e:
        print_color(f"打包过程中出现错误: {str(e)}", "red")
        return False

def main():
    parser = argparse.ArgumentParser(description='考试监控客户端打包工具')
    parser.add_argument('--name', help='应用程序名称（不指定则自动生成）')
    parser.add_argument('--icon', help='应用程序图标路径（可选）')
    parser.add_argument('--console', action='store_true', help='是否显示控制台窗口')
    args = parser.parse_args()

    app_name = args.name if args.name else "考试监控客户端"
    print_color(f"开始打包 {app_name} ...", "blue")

    if not check_pyinstaller():
        print_color("未检测到PyInstaller，正在安装...", "yellow")
        if not install_pyinstaller():
            print_color("无法安装PyInstaller，打包失败", "red")
            return

    spec_path = create_spec_file(app_name, args.icon, 'main.py', args.console)
    if spec_path and package_application(spec_path, app_name):
        print_color(f"{app_name} 打包完成！可执行文件路径: dist/{app_name}.exe", "green")
    else:
        print_color(f"{app_name} 打包失败！", "red")

if __name__ == "__main__":
    main()



