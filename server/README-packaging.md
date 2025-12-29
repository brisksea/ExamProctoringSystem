# 考试监控系统打包指南

本文档详细介绍了如何使用打包工具将考试监控系统的客户端和服务器程序打包为可执行文件，方便分发和部署。

## 打包工具概述

`package_app.py` 是一个专门为考试监控系统设计的打包工具，基于 PyInstaller 实现，具有以下特点：

1. **分离打包**：可以分别打包客户端和服务器程序
2. **自动配置**：自动处理依赖关系和资源文件
3. **跨平台支持**：支持 Windows、macOS 和 Linux 系统
4. **灵活定制**：提供多种打包选项和参数配置

## 准备工作

在使用打包工具之前，请确保您已经：

1. 安装了 Python 3.6 或更高版本
2. 最好使用虚拟环境（参考 `README-venv.md`）
3. 安装了所有依赖 `pip install -r requirements.txt`
4. 对于开发环境，建议安装 `pip install -r requirements-dev.txt`

## 打包命令

### 基本用法

```bash
# 打包客户端（默认）
python package_app.py

# 打包服务器
python package_app.py --type server

# 同时打包客户端和服务器
python package_app.py --type all
```

### 高级选项

```bash
# 指定应用程序名称
python package_app.py --name "我的考试监控系统"

# 使用自定义图标
python package_app.py --icon "path/to/icon.ico"

# 创建多文件应用程序（而非单个可执行文件）
python package_app.py --multi-file

# 使用特定的虚拟环境
python package_app.py --venv "path/to/venv"

# 组合使用多个选项
python package_app.py --type all --name "春季考试系统" --icon "exam_icon.ico"
```

## 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--type` | 打包类型：client(客户端)、server(服务器)或all(全部) | `client` |
| `--name` | 应用程序名称 | 客户端："考试监控客户端"<br>服务器："考试监控服务器" |
| `--icon` | 应用程序图标路径 | 无 |
| `--multi-file` | 创建多文件应用程序（默认为单文件） | 不启用 |
| `--venv` | 虚拟环境路径 | 当前 Python 环境 |

## 打包内容

### 客户端打包

客户端打包会处理以下文件：
- 主程序文件 `main.py`
- 配置文件 `config.json`（如果存在）
- 生成的构建信息 `build_info.py`
- 创建 `logs` 目录

### 服务器打包

服务器打包会处理以下文件：
- 主程序文件 `server.py`
- 配置文件 `server_config.json`（如果存在）
- 模板目录 `templates` 中的所有文件
- 生成的构建信息 `build_info.py`
- 创建 `logs` 目录

## 打包输出

打包成功后，可执行文件将位于 `dist` 目录下：

- Windows：`dist/应用名称.exe`
- macOS/Linux：`dist/应用名称`

## 常见问题解决

### 1. PyInstaller 安装失败

尝试手动安装：
```bash
pip install pyinstaller
```

### 2. 打包过程中缺少依赖

确保您已安装所有依赖：
```bash
pip install -r requirements.txt
```

### 3. 找不到主脚本文件

确保工作目录正确，或提供完整路径：
```bash
cd /path/to/project
python package_app.py
```

### 4. 打包的程序运行时缺少模块

尝试使用 `--multi-file` 选项以便更好地排查问题：
```bash
python package_app.py --multi-file
```

### 5. 打包后程序无法启动

检查是否缺少运行时依赖项，例如：
- Windows 上可能需要 Microsoft Visual C++ Redistributable
- 确保系统有正确的权限设置

## 部署建议

### 客户端部署

1. 将打包好的客户端程序分发给学生
2. 确保学生在考试前测试客户端是否能正常运行
3. 考试期间保持服务器正常运行

### 服务器部署

1. 在教师/监考人员的计算机上运行服务器程序
2. 确保服务器计算机的防火墙设置允许客户端连接
3. 建议使用固定IP地址以避免连接问题 