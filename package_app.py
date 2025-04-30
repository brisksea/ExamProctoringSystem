#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import platform
import argparse
import shutil
from datetime import datetime

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
        # 将命令转换为字符串形式显示
        command_str = ' '.join(command) if isinstance(command, list) else command
        print_color(f"执行命令: {command_str}", "blue")

        # 使用subprocess.run时确保使用列表形式的命令
        if isinstance(command, str):
            import shlex
            command = shlex.split(command)

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
    """检查PyInstaller是否已安装"""
    try:
        import PyInstaller
        return True
    except ImportError:
        return False

def install_pyinstaller(venv_path=None):
    """安装PyInstaller"""
    if venv_path:
        # 使用指定的虚拟环境
        if platform.system() == "Windows":
            pip_path = os.path.join(venv_path, "Scripts", "pip")
        else:
            pip_path = os.path.join(venv_path, "bin", "pip")

        command = f'"{pip_path}" install pyinstaller'
    else:
        # 使用当前Python环境
        command = f'{sys.executable} -m pip install pyinstaller'

    print_color("安装PyInstaller...", "blue")
    result = run_command(command, "安装PyInstaller失败")

    return result is not None

def create_spec_file(app_name, icon_path=None, add_data=None, main_script='main.py', one_file=True):
    """创建PyInstaller规格文件"""
    # 确定隐含导入的模块列表
    hidden_imports = []

    # 处理数据文件
    data_files = []
    if add_data:
        data_files.append(add_data)

    # 获取Python版本信息
    python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    is_python_313_plus = (sys.version_info.major == 3 and sys.version_info.minor >= 13)

    # 添加基本必需的模块，解决常见问题
    base_imports = [
        'xml.parsers.expat',
        'xml.etree.ElementTree',
        'plistlib',
        'pkg_resources',
        'importlib.resources',
        'email.mime.text',
        'email.mime.multipart',
        'requests',
    ]

    # Python 3.13+ 需要的额外导入
    if is_python_313_plus:
        base_imports.extend([
            'importlib.metadata',
            'importlib._bootstrap',
            'importlib._bootstrap_external',
            'zoneinfo',
            'typing_extensions'
        ])

    # 如果是客户端，添加Selenium相关依赖
    if 'main.py' in main_script.lower():
        client_imports = [
            'selenium',
            'selenium.webdriver',
            'selenium.webdriver.chrome.service',
            'selenium.webdriver.chrome.webdriver',
            'selenium.webdriver.chrome.options',
            'selenium.webdriver.common.by',
            'selenium.webdriver.common.keys',
            'selenium.webdriver.support.ui',
            'selenium.webdriver.support.expected_conditions',
            'selenium.common.exceptions',
            'requests',
        ]
        hidden_imports = base_imports + client_imports

    # 如果是服务器程序，添加Flask相关的依赖和模板目录
    if 'server' in main_script.lower():
        flask_imports = [
            'flask',
            'flask.json',
            'flask.app',
            'flask.blueprints',
            'flask.config',
            'flask.ctx',
            'flask.globals',
            'flask.helpers',
            'flask.logging',
            'flask.sessions',
            'flask.signals',
            'flask.templating',
            'flask.wrappers',
            'werkzeug',
            'werkzeug.exceptions',
            'werkzeug.routing',
            'werkzeug.urls',
            'werkzeug.datastructures',
            'werkzeug.debug',
            'werkzeug.formparser',
            'werkzeug.http',
            'werkzeug.local',
            'werkzeug.middleware',
            'werkzeug.security',
            'werkzeug.serving',
            'werkzeug.test',
            'werkzeug.utils',
            'werkzeug.wsgi',
            'jinja2',
            'jinja2.ext',
            'jinja2.filters',
            'jinja2.loaders',
            'jinja2.runtime',
            'jinja2.defaults',
            'jinja2.environment',
            'jinja2.nodes',
            'jinja2.optimizer',
            'jinja2.parser',
            'jinja2.sandbox',
            'jinja2.tests',
            'jinja2.visitor',
            'itsdangerous'
        ]

        # 对于Python 3.13+，添加额外的Flask依赖
        if is_python_313_plus:
            flask_imports.extend([
                'flask.sansio',
                'werkzeug.middleware.dispatcher',
                'werkzeug.middleware.shared_data'
            ])

        hidden_imports = base_imports + flask_imports

        # 添加模板目录
        if os.path.exists('templates'):
            data_files.append("('templates', 'templates')")

    # 格式化隐含导入的字符串表示形式
    hidden_imports_str = ', '.join([f"'{imp}'" for imp in hidden_imports]) if hidden_imports else ''

    # 格式化数据文件字符串
    datas_str = ', '.join(data_files) if data_files else ''

    # 添加二进制文件列表
    binaries_str = ""

    # 检测是否在Anaconda环境中
    is_anaconda = False
    python_path = os.path.dirname(sys.executable)
    if "anaconda" in python_path.lower() or "conda" in python_path.lower():
        is_anaconda = True
        print_color("检测到Anaconda环境，建议使用标准Python 3.13环境进行打包", "yellow")

    # 根据one_file参数决定生成单文件还是多文件应用
    if one_file:
        # 单文件应用 (.exe)
        exe_section = f"""exe = EXE(
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
            console=False,
            disable_windowed_traceback=False,
            argv_emulation=False,
            target_arch=None,
            codesign_identity=None,
            entitlements_file=None,
            {f"icon='{icon_path}'," if icon_path else ''}
        )
        """
    else:
        # 多文件应用 (文件夹)
        exe_section = f"""exe = EXE(
            pyz,
            a.scripts,
            [],
            exclude_binaries=True,
            name='{app_name}',
            debug=False,
            bootloader_ignore_signals=False,
            strip=False,
            upx=True,
            console=False,
            disable_windowed_traceback=False,
            argv_emulation=False,
            target_arch=None,
            codesign_identity=None,
            entitlements_file=None,
            {f"icon='{icon_path}'," if icon_path else ''}
        )

        coll = COLLECT(
            exe,
            a.binaries,
            a.zipfiles,
            a.datas,
            strip=False,
            upx=True,
            upx_exclude=[],
            name='{app_name}',
        )
"""

    # 如果是服务器则使用控制台模式
    if 'server' in main_script.lower():
        exe_section = exe_section.replace('console=False', 'console=True')

    # 创建规格文件内容
    spec_content = f"""# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from PyInstaller.utils.hooks import collect_all

block_cipher = None

# 收集所有XML相关模块
xml_datas = []
xml_binaries = []
xml_hiddenimports = []

for pkg in ['xml', 'plistlib', 'pkg_resources']:
    data, binaries, hiddenimports = collect_all(pkg)
    xml_datas.extend(data)
    xml_binaries.extend(binaries)
    xml_hiddenimports.extend(hiddenimports)

# 添加自定义二进制文件
extra_binaries = [{binaries_str}] if '{binaries_str}' else []

a = Analysis(
    ['{main_script}'],
    pathex=[],
    binaries=xml_binaries + extra_binaries,
    datas=[{datas_str}] + xml_datas,
    hiddenimports=[{hidden_imports_str}] + xml_hiddenimports,
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Python 3.13+ 优化选项
if sys.version_info >= (3, 13):
    # 禁用缓冲以提高性能
    a.python_options = ['u']

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

{exe_section}
"""

    spec_path = f"{app_name}.spec"
    try:
        with open(spec_path, 'w', encoding='utf-8') as f:
            f.write(spec_content)

        print_color(f"已创建规格文件: {spec_path}")

        # 为Python 3.13+打印额外信息
        if is_python_313_plus:
            print_color(f"已优化规格文件，适配Python {python_version}", "green")

        return spec_path
    except Exception as e:
        print_color(f"创建规格文件失败: {e}", "red")
        return None

def package_application(spec_path, app_name, venv_path=None):
    """打包应用程序"""
    try:
        if venv_path:
            # 使用指定的虚拟环境
            if platform.system() == "Windows":
                python_exe = os.path.join(venv_path, "Scripts", "python.exe")
            else:
                python_exe = os.path.join(venv_path, "bin", "python")
        else:
            # 使用当前Python环境
            python_exe = sys.executable

        # 确保路径使用双引号包裹
        python_exe = f'"{python_exe}"' if ' ' in python_exe else python_exe
        spec_path = f'"{spec_path}"' if ' ' in spec_path else spec_path

        # 构建命令列表
        command = [
            python_exe,
            "-m",
            "PyInstaller",
            spec_path
        ]

        # 切换到正确的工作目录
        original_dir = os.getcwd()
        spec_dir = os.path.dirname(os.path.abspath(spec_path.strip('"')))
        os.chdir(spec_dir)

        try:
            # 执行打包命令
            print_color(f"开始打包{app_name}...", "blue")
            result = run_command(command, "打包应用程序失败")

            if result is not None:
                print_color(f"应用程序打包成功: dist/{app_name}", "green")
                return True

            return False

        finally:
            # 恢复原始工作目录
            os.chdir(original_dir)

    except Exception as e:
        print_color(f"打包过程中出现错误: {str(e)}", "red")
        return False

def copy_config_files(app_name, app_type="client"):
    """复制配置文件到dist目录"""
    dist_dir = os.path.join('dist', app_name)
    if not os.path.exists(dist_dir):
        dist_dir = 'dist'  # fallback to dist directory

    files_to_copy = []

    # 根据应用类型添加相应的配置文件
    if app_type == "client" or app_type == "all":
        if os.path.exists('config.json'):
            files_to_copy.append(('config.json', 'config.json'))

        # 复制Chrome驱动程序 - 修改搜索顺序
        chromedriver_paths = [
            'chromedriver.exe',                       # 当前目录
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'chromedriver.exe'),  # 脚本所在目录
            os.path.join('drivers', 'chromedriver.exe'),
            os.path.join('driver', 'chromedriver.exe'),
            os.path.join('browser', 'chromedriver.exe')
        ]

        for driver_path in chromedriver_paths:
            if os.path.exists(driver_path):
                files_to_copy.append((driver_path, 'chromedriver.exe'))  # 始终复制到根目录
                print_color(f"找到Chrome驱动: {driver_path}", "green")
                break
        else:
            print_color("警告: 未找到Chrome驱动程序(chromedriver.exe)，客户端可能无法正常工作", "yellow")
            print_color("请确保chromedriver.exe位于项目目录中，版本需与客户端Chrome版本匹配", "yellow")

    if app_type == "server" or app_type == "all":
        if os.path.exists('server_config.json'):
            files_to_copy.append(('server_config.json', 'server_config.json'))
        # 服务器模板目录
        if os.path.exists('templates'):
            try:
                templates_dir = os.path.join(dist_dir, 'templates')
                if not os.path.exists(templates_dir):
                    os.makedirs(templates_dir)
                # 复制所有模板文件
                for template_file in os.listdir('templates'):
                    src_path = os.path.join('templates', template_file)
                    if os.path.isfile(src_path):
                        shutil.copy(src_path, templates_dir)
                print_color("已复制模板文件到输出目录")
            except Exception as e:
                print_color(f"复制模板文件失败: {e}", "red")

    # 拷贝README.md（如果存在）
    if os.path.exists('README.md'):
        files_to_copy.append(('README.md', 'README.md'))

    # 复制所有文件
    for src, dst in files_to_copy:
        try:
            dest_path = os.path.join(dist_dir, dst)
            # 确保目标目录存在
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            shutil.copy(src, dest_path)
            print_color(f"已复制{src}到{dest_path}")
        except Exception as e:
            print_color(f"复制{src}失败: {e}", "red")

    # 创建空的logs目录
    logs_dir = os.path.join(dist_dir, 'logs')
    if not os.path.exists(logs_dir):
        try:
            os.makedirs(logs_dir)
            print_color("已创建logs目录")
        except Exception as e:
            print_color(f"创建logs目录失败: {e}", "red")

    return True

def clean_temp_files(app_name):
    """清理临时文件，包括spec文件和build目录"""
    # 清理spec文件
    spec_file = f"{app_name}.spec"
    if os.path.exists(spec_file):
        try:
            os.remove(spec_file)
            print_color(f"已删除临时文件: {spec_file}", "blue")
        except Exception as e:
            print_color(f"无法删除临时文件 {spec_file}: {e}", "yellow")

    # 清理build目录
    if os.path.exists('build') and os.path.isdir('build'):
        try:
            shutil.rmtree('build')
            print_color("已删除临时构建目录", "blue")
        except Exception as e:
            print_color(f"无法删除临时构建目录: {e}", "yellow")

def print_usage_instructions(app_name, app_type, one_file=True):
    """打印应用程序使用说明"""
    print_color("\n================ 使用说明 ================", "blue")

    if one_file:
        executable = f"{app_name}.exe" if platform.system() == "Windows" else app_name
        print_color(f"可执行文件: dist/{executable}", "green")
    else:
        print_color(f"应用程序目录: dist/{app_name}/", "green")
        executable = f"{app_name}.exe" if platform.system() == "Windows" else app_name
        print_color(f"主可执行文件: dist/{app_name}/{executable}", "green")

    if app_type == "client":
        print_color("\n客户端使用说明:", "yellow")
        print_color("1. 双击可执行文件启动客户端", "yellow")
        print_color("2. 输入用户信息并连接到考试服务器", "yellow")
        print_color("3. 确保服务器地址正确配置", "yellow")
    elif app_type == "server":
        print_color("\n服务器使用说明:", "yellow")
        print_color("1. 双击可执行文件启动服务器", "yellow")
        print_color("2. 确保防火墙设置允许客户端连接", "yellow")
        print_color("3. 将服务器IP地址和端口提供给考生", "yellow")
        print_color("4. 服务器默认监听在 http://127.0.0.1:5000", "yellow")

    print_color("\n提示: 首次运行可能被安全软件拦截，请允许运行", "blue")
    print_color("=========================================", "blue")

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='考试监控系统打包工具')
    parser.add_argument('--type', choices=['client', 'server', 'all'], default='client',
                       help='打包类型：client(客户端)、server(服务器)或all(全部)')
    parser.add_argument('--name', help='应用程序名称（不指定则自动生成）')
    parser.add_argument('--venv', help='虚拟环境路径（可选）')
    parser.add_argument('--icon', help='应用程序图标路径（可选）')
    parser.add_argument('--multi-file', action='store_true', help='创建多文件应用程序（默认为单文件）')
    parser.add_argument('--clean', action='store_true', help='打包后清理临时文件')
    parser.add_argument('--no-version-check', action='store_true', help='跳过版本检查')
    args = parser.parse_args()

    print_color("=" * 50, "blue")
    print_color("考试监控系统打包工具 - 支持分别打包客户端和服务器", "blue")
    print_color("=" * 50, "blue")

    # 版本检查
    if not args.no_version_check:
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        if sys.version_info < (3, 7):
            print_color(f"警告：当前Python版本({python_version})可能过低，建议使用Python 3.7+", "red")
            confirm = input("是否继续打包？(y/n): ")
            if confirm.lower() != 'y':
                return
        elif sys.version_info < (3, 13):
            print_color(f"提示：当前Python版本({python_version})可用，但推荐使用Python 3.13+获得更好支持", "yellow")
        else:
            print_color(f"当前Python版本({python_version})适合打包", "green")

        # 检查环境类型
        python_path = os.path.dirname(sys.executable)
        if "anaconda" in python_path.lower() or "conda" in python_path.lower():
            print_color("检测到Anaconda环境，打包可能遇到DLL问题，建议使用标准Python环境", "yellow")
            confirm = input("是否继续使用Anaconda环境打包？(y/n): ")
            if confirm.lower() != 'y':
                return

    # 检查PyInstaller是否已安装
    try:
        import PyInstaller
        print_color(f"PyInstaller已安装: {getattr(PyInstaller, '__version__', 'unknown')}", "green")
    except ImportError:
        print_color("未检测到PyInstaller，正在安装...", "yellow")
        if not install_pyinstaller(args.venv):
            print_color("无法安装PyInstaller，打包失败", "red")
            return

    # 根据类型确定主脚本和应用名称
    to_package = []

    if args.type == 'client' or args.type == 'all':
        client_name = args.name if args.name else "考试监控客户端"
        to_package.append({
            'type': 'client',
            'name': client_name,
            'script': 'main.py'
        })

    if args.type == 'server' or args.type == 'all':
        server_name = args.name if args.name else "考试监控服务器"
        if args.type == 'all' and args.name:
            server_name = f"{args.name}_服务器"
        to_package.append({
            'type': 'server',
            'name': server_name,
            'script': 'server.py'
        })

    # 创建build_info.py记录构建信息
    build_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    build_version = "1.0.0"  # 可以从版本文件或git标签获取

    try:
        with open('build_info.py', 'w', encoding='utf-8') as f:
            f.write(f'BUILD_TIME = "{build_time}"\n')
            f.write(f'BUILD_VERSION = "{build_version}"\n')
            f.write(f'PYTHON_VERSION = "{sys.version.split()[0]}"\n')

        print_color("已创建构建信息文件")

        # 将build_info.py添加到数据文件列表
        add_data = "('build_info.py', '.')"

        # 执行打包
        success_count = 0
        packaged_apps = []

        for package_info in to_package:
            print_color(f"\n开始打包 {package_info['type']} ({package_info['name']})...", "blue")

            # First create the spec file
            spec_path = create_spec_file(
                package_info['name'],
                args.icon,
                add_data,
                package_info['script'],
                not args.multi_file
            )

            # Then package the application using the spec file
            if spec_path and package_application(spec_path, package_info['name'], args.venv):
                # 复制配置文件
                copy_config_files(package_info['name'], package_info['type'])
                success_count += 1
                packaged_apps.append(package_info)

                print_color(f"{package_info['name']}打包完成！", "green")
                print_color(f"可执行文件路径: dist/{package_info['name']}" +
                           (".exe" if platform.system() == "Windows" else ""))

                # 清理临时文件
                if args.clean:
                    clean_temp_files(package_info['name'])

        if success_count == len(to_package):
            print_color("\n全部打包完成！", "green")
        else:
            print_color(f"\n部分打包完成 ({success_count}/{len(to_package)})", "yellow")

        # 打印使用说明
        for app_info in packaged_apps:
            print_usage_instructions(app_info['name'], app_info['type'], not args.multi_file)

    finally:
        # 清理临时生成的build_info.py
        if os.path.exists('build_info.py'):
            os.remove('build_info.py')

if __name__ == "__main__":
    main()



