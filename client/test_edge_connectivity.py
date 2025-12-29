import requests
import sys
import os
import subprocess
import re

# 导入我们的管理器来获取版本
from edge_driver_manager import get_edge_version

def test_url(url):
    print(f"Checking: {url} ...", end=" ", flush=True)
    try:
        response = requests.get(url, timeout=5)
        print(f"SUCCESS (Status: {response.status_code})")
        return True
    except Exception as e:
        print(f"FAILED ({type(e).__name__})")
        return False

def check_version_source():
    print("=== Version Source Comparison ===")
    v = get_edge_version()
    print(f"Detected via our manager: {v}")
    
    # 尝试直接运行 wmic 再看一遍
    edge_paths = [
        os.path.join(os.environ.get('PROGRAMFILES(X86)', 'C:\\Program Files (x86)'), 'Microsoft\\Edge\\Application\\msedge.exe'),
        os.path.join(os.environ.get('PROGRAMFILES', 'C:\\Program Files'), 'Microsoft\\Edge\\Application\\msedge.exe')
    ]
    for path in edge_paths:
        if os.path.exists(path):
            try:
                path_esc = path.replace("\\", "\\\\")
                output = subprocess.check_output(
                    f'wmic datafile where name="{path_esc}" get Version /value',
                    shell=True
                ).decode('utf-8', 'ignore')
                print(f"WMIC for {path}: {output.strip()}")
            except:
                pass

def main():
    print("=== Edge Driver Connectivity Test ===")
    
    version = get_edge_version()
    check_version_source()
    
    print("\n=== Testing URLs ===")
    # 1. 官网基础路径
    test_url("https://msedgedriver.azureedge.net/")
    
    # 2. 稳定版驱动路径 (示例版本)
    stable_v = "131.0.2903.112"
    test_url(f"https://msedgedriver.azureedge.net/{stable_v}/edgedriver_win64.zip")
    
    # 3. 你的版本驱动路径 (如果 143 是正确的)
    if version:
        test_url(f"https://msedgedriver.azureedge.net/{version}/edgedriver_win64.zip")

    # 4. 考试服务器 API 前缀
    server_ip = '172.16.229.162'
    test_url(f"http://{server_ip}:5000/api/config")

if __name__ == "__main__":
    main()
