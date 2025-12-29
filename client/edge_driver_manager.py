#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Edge驱动管理模块
"""

import os
import sys
import re
import subprocess
import shutil
import platform
import glob
import requests
from pathlib import Path
from webdriver_manager.microsoft import EdgeChromiumDriverManager
if sys.platform == 'win32':
    import winreg

def get_edge_version():
    """
    获取Edge浏览器版本
    """
    # 尝试从注册表获取
    try:
         key_path = r"SOFTWARE\\Microsoft\\Edge\\BLBeacon"
         key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path)
         version, _ = winreg.QueryValueEx(key, "version")
         winreg.CloseKey(key)
         print("Registry (HKCU) Edge version:", version)
         return version
    except WindowsError:
         pass

    try:
         key_path = r"SOFTWARE\\Microsoft\\Edge\\BLBeacon"
         key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
         version, _ = winreg.QueryValueEx(key, "version")
         winreg.CloseKey(key)
         print("Registry (HKLM) Edge version:", version)
         return version
    except WindowsError:
         pass

    # 从文件获取
    edge_paths = [
        os.path.join(os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)'), 'Microsoft\\Edge\\Application\\msedge.exe'),
        os.path.join(os.environ.get('PROGRAMFILES', 'C:\\Program Files'), 'Microsoft\\Edge\\Application\\msedge.exe')
    ]

    for edge_path in edge_paths:
        if os.path.exists(edge_path):
            try:
                edge_path_esc = edge_path.replace("\\", "\\\\")
                output = subprocess.check_output(
                    f'wmic datafile where name="{edge_path_esc}" get Version /value',
                    shell=True
                ).decode('utf-8', 'ignore')
                match = re.search(r'Version=(.+)', output)
                if match:
                    version = match.group(1).strip()
                    print("Exe Edge version:", version)
                    return version
            except Exception:
                pass
    
    return None

def get_major_version(version):
    if not version:
        return None
    match = re.search(r'^(\d+)', version)
    if match:
        return match.group(1)
    return None

def find_local_edgedriver():
    """查找本地 msedgedriver.exe"""
    driver_name = "msedgedriver.exe"
    paths = []
    
    # 1. 当前目录
    paths.append(driver_name)
    
    # 2. 如果是打包后的 exe，优先在 exe 所在目录查找
    try:
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
            paths.append(os.path.join(exe_dir, driver_name))
    except Exception:
        pass
    
    # 3. 当前目录下的子目录 (例如开发者环境下可能在当前文件夹)
    paths.append(os.path.join(os.path.dirname(__file__), driver_name))
    
    # 4. 常见系统/用户目录
    local_appdata = os.environ.get('LOCALAPPDATA')
    if local_appdata:
        paths.append(os.path.join(local_appdata, driver_name))
        # 搜索 webdriver-manager 可能存放的位置
        try:
            wdm_pattern = os.path.join(local_appdata, '.wdm', 'drivers', 'edgedriver', '**', driver_name)
            for p in glob.glob(wdm_pattern, recursive=True):
                paths.append(p)
        except Exception:
            pass
            
    # 5. 用户主目录下的 .wdm
    user_home = os.path.expanduser("~")
    wdm_edge_dir = os.path.join(user_home, ".wdm", "drivers", "edgedriver")
    if os.path.exists(wdm_edge_dir):
        try:
             # 这里可以递归找一下
             for p in glob.glob(os.path.join(wdm_edge_dir, "**", driver_name), recursive=True):
                 paths.append(p)
        except Exception:
            pass
    
    # 检查每个可能的位置
    for path in paths:
        try:
            if os.path.exists(path):
                print(f"找到本地EdgeDriver: {path}")
                return path
        except Exception:
            continue
            
    print("未找到本地EdgeDriver")
    return None

def download_edgedriver_from_server(edge_version, server_url):
    """根据主版本号从服务器下载edgedriver，重命名为msedgedriver.exe"""
    if not edge_version:
        raise ValueError("edge_version不能为None")
    major_version = edge_version.split('.')[0]
    # 注意：服务器上的文件名约定为 msedgedriver_{major}.exe
    download_url = f"{server_url}/msedgedriver_{major_version}.exe"
    
    if getattr(sys, 'frozen', False):
        local_path = os.path.join(os.path.dirname(sys.executable), "msedgedriver.exe")
    else:
        local_path = os.path.join(os.path.dirname(__file__), "msedgedriver.exe")
        
    print(f"尝试从服务器 {download_url} 下载 msedgedriver ...")
    try:
        r = requests.get(download_url, stream=True, timeout=10)
        if r.status_code == 200:
            with open(local_path, "wb") as f:
                shutil.copyfileobj(r.raw, f)
            print("msedgedriver 从服务器下载完成")
            return local_path
        else:
            print(f"服务器未提供该版本的驱动: {r.status_code}")
            return None
    except Exception as e:
        print(f"从服务器下载驱动时出错: {e}")
        return None

def download_edgedriver_from_web(edge_version):
    """从微软官网或通过webdriver_manager下载驱动"""
    print(f"尝试从官网下载 EdgeDriver (版本: {edge_version})...")
    try:
        # 使用 webdriver_manager 下载驱动
        # 它会自动处理版本匹配和解压
        driver_path = EdgeChromiumDriverManager().install()
        print(f"EdgeDriver 从官网下载完成: {driver_path}")
        
        # 拷贝一份到当前目录或 exe 目录，方便下次直接使用
        if getattr(sys, 'frozen', False):
            target_dir = os.path.dirname(sys.executable)
        else:
            target_dir = os.path.dirname(__file__)
            
        target_path = os.path.join(target_dir, "msedgedriver.exe")
        try:
            shutil.copy2(driver_path, target_path)
            print(f"驱动已备份至: {target_path}")
            return target_path
        except Exception:
            # 即使备份失败，也可以直接使用 wdm 下载的路径
            return driver_path
            
    except Exception as e:
        print(f"从官网下载驱动失败: {e}")
        return None

def is_compatible_edgedriver(driver_path, edge_version):
    if not driver_path or not edge_version:
        return False
    try:
        result = subprocess.run([driver_path, "--version"], capture_output=True, text=True, timeout=5)
        if result.returncode != 0:
            return False
        
        output = result.stdout
        # Output example: "Microsoft Edge WebDriver 131.0.2903.112 (9739...)"
        match = re.search(r'WebDriver (\d+\.\d+\.\d+)', output)
        if match:
            driver_ver = match.group(1)
            if get_major_version(driver_ver) == get_major_version(edge_version):
                return True
    except Exception:
        pass
    return False

def get_edgedriver_path(edge_version=None):
    if not edge_version:
        edge_version = get_edge_version()
    
    local_driver = find_local_edgedriver()
    if local_driver and edge_version and is_compatible_edgedriver(local_driver, edge_version):
        print(f"使用本地兼容的EdgeDriver: {local_driver}")
        return local_driver
    
    return None
