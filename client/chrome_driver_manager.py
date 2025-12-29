#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Chrome驱动管理模块
集成了Chrome版本检测和ChromeDriver管理功能
"""

import os
import sys
import glob
import platform
import re
import subprocess
from pathlib import Path
import requests
import shutil

# Windows系统需要导入winreg模块
if sys.platform == 'win32':
    import winreg

#------------------------------------------------------------------------------
# Chrome版本检测部分
#------------------------------------------------------------------------------

def get_chrome_version():
    """
    从Windows注册表获取Chrome浏览器版本

    Returns:
        str: Chrome版本号，如果未找到则返回None
    """
    
    # 从注册表获取Chrome版本
    # 下面是一个曾经用于从Windows注册表读取Chrome版本的实现，
    # 被注释掉以避免在部分环境中引起解析器对 \U 转义的错误。
    # 如果需要恢复该功能，请将每一行的注释符号去掉并确保字符串使用原始字符串(r"...")或适当转义。
    try:
         # 尝试从注册表获取Chrome版本
         key_path = r"SOFTWARE\\Google\\Chrome\\BLBeacon"
         key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path)
         version, _ = winreg.QueryValueEx(key, "version")
         winreg.CloseKey(key)
         print("get version from registry:", version)
         return version
    except WindowsError:
         # 如果上面的方法失败，尝试其他注册表位置
         try:
             key_path = r"SOFTWARE\\Wow6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\Google Chrome"
             key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
             version, _ = winreg.QueryValueEx(key, "Version")
             winreg.CloseKey(key)
             return version
         except WindowsError:
             pass
 
    # 如果注册表方法失败，尝试从Chrome可执行文件获取版本
    chrome_paths = [
        os.path.join(os.environ.get('PROGRAMFILES', 'C:\\Program Files'), 'Google\\Chrome\\Application\\chrome.exe'),
        os.path.join(os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)'), 'Google\\Chrome\\Application\\chrome.exe')
    ]

    for chrome_path in chrome_paths:
        if os.path.exists(chrome_path):
            try:
                # 使用wmic获取文件版本信息
                chrome_path = chrome_path.replace("\\", "\\\\")
                output = subprocess.check_output(
                    f'wmic datafile where name="{chrome_path}" get Version /value',
                    shell=True
                ).decode('utf-8', 'ignore')

                # 解析版本信息
                match = re.search(r'Version=(.+)', output)
                if match:
                    print("get version from exe:", chrome_path)
                    return match.group(1).strip()
            except subprocess.SubprocessError:
                pass

    return None

def get_major_version(version):
    """
    从完整版本号中提取主要版本号

    Args:
        version: 完整版本号，如 "96.0.4664.45"

    Returns:
        str: 主要版本号，如 "96"
    """
    if not version:
        return None

    match = re.search(r'^(\d+)', version)
    if match:
        return match.group(1)

    return None

#------------------------------------------------------------------------------
# ChromeDriver管理部分
#------------------------------------------------------------------------------

def find_local_chromedriver():
    """
    查找本地的chromedriver.exe文件

    Returns:
        str: chromedriver.exe的路径，如果未找到则返回None
    """
    # 常见的ChromeDriver位置
    chromedriver_paths = []

    chromedriver_name = "chromedriver.exe"

    # 当前目录及子目录（相对路径）
    chromedriver_paths.append(chromedriver_name)

    # 如果是打包后的 exe，优先在 exe 所在目录查找
    try:
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
            chromedriver_paths.append(os.path.join(exe_dir, chromedriver_name))
    except Exception:
        pass

    # 当前用户的 AppData 下常见位置（LOCALAPPDATA 和 APPDATA）
    local_appdata = os.environ.get('LOCALAPPDATA')
    appdata = os.environ.get('APPDATA')
    if local_appdata:
        # 直接在 Local AppData 根目录搜索
        chromedriver_paths.append(os.path.join(local_appdata, chromedriver_name))
        # 一些工具或环境会把驱动放在 .wdm 或 drivers 子目录下，做一次有限深度搜索
        try:
            # 只匹配常见的 webdriver-manager 路径，避免全盘搜索
            wdm_pattern = os.path.join(local_appdata, '.wdm', 'drivers', 'chromedriver', '**', chromedriver_name)
            for p in glob.glob(wdm_pattern, recursive=True):
                chromedriver_paths.append(p)
        except Exception:
            pass
        # 还有可能在 LocalAppData\Programs 或 LocalAppData\Google 等目录下
        chromedriver_paths.append(os.path.join(local_appdata, 'Programs', chromedriver_name))
        chromedriver_paths.append(os.path.join(local_appdata, 'Google', 'Chrome', 'Application', chromedriver_name))
    if appdata:
        chromedriver_paths.append(os.path.join(appdata, chromedriver_name))

    '''
    # 用户主目录下的.wdm目录
    user_home = os.path.expanduser("~")
    chrome_version = get_chrome_version()
    chrome_major = get_major_version(chrome_version) if chrome_version else None
    
    # 遍历.wdm/drivers/chromedriver/win64目录下的所有版本目录
    wdm_chrome_dir = os.path.join(user_home, ".wdm", "drivers", "chromedriver", "win64")
    if os.path.exists(wdm_chrome_dir):
        for version_dir in os.listdir(wdm_chrome_dir):
            # 如果chrome_major存在且版本目录前三个数字匹配
            if chrome_major and version_dir and '.' in version_dir and version_dir.split('.')[0] == chrome_major:
                driver_path = os.path.join(wdm_chrome_dir, version_dir, chromedriver_name)
                chromedriver_paths.append(driver_path)


    # 检查环境变量PATH中的位置
    if "PATH" in os.environ:
        for path_dir in os.environ["PATH"].split(os.pathsep):
            driver_path = os.path.join(path_dir, chromedriver_name)
            chromedriver_paths.append(driver_path)
    '''
    # 检查每个可能的位置（按顺序优先级查找）
    for path in chromedriver_paths:
        try:
            if os.path.exists(path):
                print(f"找到本地ChromeDriver: {path}")
                return path
        except Exception:
            # 如果某些路径包含非法字符或权限问题，忽略并继续
            continue
    print("未找到本地ChromeDriver")
    return None

def download_chromedriver_from_server(chrome_version, server_url):
    """根据主版本号从服务器下载chromedriver，重命名为chromedriver.exe"""
    if not chrome_version:
        raise ValueError("chrome_version不能为None")
    major_version = chrome_version.split('.')[0]
    download_url = f"{server_url}/chromedriver_{major_version}.exe"
    if getattr(sys, 'frozen', False):
        # 如果是打包后的 exe 运行
        local_path = os.path.join(os.path.dirname(sys.executable), "chromedriver.exe")
    else:
        # 如果是源码运行
        local_path = os.path.join(os.path.dirname(__file__), "chromedriver.exe")
    print(f"尝试从 {download_url} 下载 chromedriver ...")
    r = requests.get(download_url, stream=True)
    if r.status_code == 200:
        with open(local_path, "wb") as f:
            shutil.copyfileobj(r.raw, f)
        print("chromedriver 下载完成")
        return local_path
    else:
        raise RuntimeError(f"下载chromedriver失败，服务器返回: {r.status_code}")

def is_compatible_chromedriver(driver_path, chrome_version):
    """
    检查ChromeDriver是否与当前Chrome版本兼容

    Args:
        driver_path: ChromeDriver路径
        chrome_version: Chrome版本

    Returns:
        bool: 是否兼容
    """
    if not driver_path or not chrome_version:
        return False

    try:
        # 获取ChromeDriver版本
        result = subprocess.run([driver_path, "--version"],
                               capture_output=True,
                               text=True,
                               timeout=5)

        if result.returncode != 0:
            return False

        # 解析版本信息
        output = result.stdout
        match = re.search(r'ChromeDriver (\d+\.\d+\.\d+)', output)
        if not match:
            return False

        driver_version = match.group(1)

        # 提取主要版本号
        driver_major = get_major_version(driver_version)
        chrome_major = get_major_version(chrome_version)

        # 检查主要版本号是否匹配
        if driver_major and chrome_major and driver_major == chrome_major:
            print(f"本地ChromeDriver版本 {driver_version} 与Chrome版本 {chrome_version} 兼容")
            return True

        print(f"本地ChromeDriver版本 {driver_version} 与Chrome版本 {chrome_version} 不兼容")
        # 删除本地不兼容的chromedriver
        return False

    except Exception as e:
        print(f"检查ChromeDriver兼容性时出错: {str(e)}")
        return False

def get_chromedriver_path(chrome_version=None):
    """
    获取适用于当前Chrome版本的ChromeDriver路径
    如果本地有兼容的ChromeDriver，则直接使用
    否则使用webdriver_manager下载

    Args:
        chrome_version: Chrome版本，如果为None则自动检测

    Returns:
        str: ChromeDriver路径
    """
    # 如果未提供Chrome版本，则自动检测
    if not chrome_version:
        chrome_version = get_chrome_version()
        if chrome_version:
            print(f"检测到Chrome版本: {chrome_version}")

    # 查找本地ChromeDriver
    local_driver = find_local_chromedriver()

    # 如果找到本地ChromeDriver并且版本兼容，则直接使用
    if local_driver and chrome_version and is_compatible_chromedriver(local_driver, chrome_version):
        print(f"使用本地兼容的ChromeDriver: {local_driver}")
        return local_driver

    # 否则返回None，表示需要使用webdriver_manager下载
    return None

#------------------------------------------------------------------------------
# 测试代码
#------------------------------------------------------------------------------

if __name__ == "__main__":
    # 测试Chrome版本检测
    chrome_version = get_chrome_version()
    if chrome_version:
        print(f"检测到Chrome版本: {chrome_version}")
        print(f"主要版本号: {get_major_version(chrome_version)}")
    else:
        print("未能检测到Chrome版本")

    # 测试ChromeDriver管理
    if chrome_version:
        driver_path = get_chromedriver_path(chrome_version)
        if driver_path:
            print(f"使用本地ChromeDriver: {driver_path}")
        else:
            print("需要使用webdriver_manager下载ChromeDriver")



