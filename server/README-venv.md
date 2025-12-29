# 考试监控系统虚拟环境设置指南

本文档详细介绍了如何为考试监控系统设置和使用Python虚拟环境，确保系统能够在各种环境中正确运行。

## 为什么使用虚拟环境

虚拟环境可以为我们的考试监控系统提供以下好处：

1. **隔离依赖**：避免与系统Python或其他项目的依赖产生冲突
2. **版本一致性**：确保所有用户使用相同版本的依赖库
3. **简化部署**：易于在新环境中快速重建一致的运行环境
4. **更好的安全性**：限制应用程序的权限范围

## 虚拟环境设置方法

### 方法一：使用自动化脚本（推荐）

我们提供了`create_venv.py`脚本来自动设置虚拟环境：

1. 确保已安装Python 3.6或更高版本
2. 运行以下命令：

```bash
# 基本用法
python create_venv.py

# 高级用法
python create_venv.py --path custom_env_path --force
```

参数说明：
- `--path`：指定虚拟环境的路径（默认为`venv`）
- `--force`：强制重新创建虚拟环境（如果已存在）
- `--requirements`：指定依赖文件的路径（默认为`requirements.txt`）

运行后，脚本将：
- 创建虚拟环境
- 安装所需依赖
- 生成便捷的激活脚本和运行脚本

### 方法二：手动设置

如果您希望手动设置虚拟环境，请按照以下步骤操作：

#### Windows系统

```cmd
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

#### Linux/macOS系统

```bash
# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

## 使用虚拟环境

### 使用自动创建的脚本

自动化脚本会创建便捷的使用脚本：

#### Windows系统

- 双击`activate_env.bat`激活环境
- 双击`run_exam_client.bat`直接运行系统

#### Linux/macOS系统

```bash
# 激活环境
./activate_env.sh

# 直接运行系统
./run_exam_client.sh
```

### 手动使用

激活环境后，您可以直接运行Python脚本：

```bash
# 激活后
python main.py
```

## 开发环境设置

对于开发者，我们提供了更全面的依赖配置：

```bash
# 安装开发依赖
pip install -r requirements-dev.txt
```

这将安装额外的工具，如：
- 测试工具（pytest）
- 代码格式化工具（black）
- 静态类型检查（mypy）
- 打包工具（pyinstaller）

## 打包应用程序

如需将应用程序打包为可执行文件，请使用`package_app.py`脚本：

```bash
# 基本用法
python package_app.py

# 高级用法
python package_app.py --name "考试监控系统" --icon "path/to/icon.ico"
```

参数说明：
- `--name`：指定输出的应用程序名称
- `--venv`：指定虚拟环境路径（可选）
- `--icon`：指定应用程序图标路径（可选）
- `--multi-file`：创建多文件应用程序（默认为单文件）

## 故障排除

如果您在设置虚拟环境时遇到问题，请尝试以下解决方案：

1. **Python版本问题**：确保使用Python 3.6或更高版本
2. **依赖冲突**：尝试使用`--force`选项重新创建环境
3. **权限问题**：在Linux/macOS上可能需要使用`sudo`
4. **路径问题**：避免路径中包含空格或特殊字符 