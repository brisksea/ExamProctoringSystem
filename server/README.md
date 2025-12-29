# 考试监控客户端

用于监控考试期间的应用程序和控制Chrome浏览器的客户端。

## 功能

- 用户登录：记录考生姓名，追踪用户活动
- 前台应用监控：只监控用户正在使用的前台应用，忽略后台进程
- 允许使用各种IDE和编辑器：VS Code、Visual Studio、IntelliJ、PyCharm等
- 完全控制Chrome浏览器及禁用插件
- 可配置允许访问的网址列表
- 异常检测延时：检测到未授权应用后等待指定时间再次检测
- 考试服务器：实时显示学生登录状态和异常记录，包含屏幕截图

## 系统要求

- Windows 10或更高版本
- Python 3.8+（安装时必须选中"tcl/tk和IDLE"选项，确保tkinter可用）
- Google Chrome浏览器

## 系统架构

本系统由客户端和服务器两部分组成：

### 客户端
- 监控前台应用程序
- 控制Chrome浏览器
- 捕获屏幕截图
- 向服务器报告异常

### 服务器
- 显示学生登录状态和IP
- 实时显示异常记录和截图
- 提供Web界面供监考人员查看

## 安装

1. 确保已安装Python 3.8+，并且在安装过程中选择了"tcl/tk和IDLE"选项
2. 确保已安装Google Chrome浏览器
3. 克隆或下载本项目
4. 安装依赖：
   ```
   pip install -r requirements.txt
   ```

## 使用方法

### 启动服务器

1. 在一台计算机上启动监控服务器：
   ```
   python server.py
   ```

2. 默认情况下，服务器将在 http://127.0.0.1:5000 上运行，可以通过浏览器访问该地址查看监控界面

### 启动客户端

1. 修改配置文件 `config.json` 中的 `server_url` 为服务器地址
2. 使用启动脚本运行程序：
   ```
   python run_exam_client.py
   ```
   或者直接运行主程序：
   ```
   python main.py
   ```
3. 在登录窗口中输入您的姓名并登录
4. 点击"启动考试模式"按钮进入考试模式
5. 程序将监控前台运行的应用程序并向服务器报告异常

## 用户活动日志

系统会自动记录用户活动，包括：

- 用户登录和退出
- 考试监控启动和停止
- 检测到的未授权应用
- 其他重要事件

日志文件保存在`logs`目录下，文件名格式为`user_姓名_yyyy-mm-dd.log`，方便管理员查看和管理考试记录。

## 前台应用监控

本系统采用前台监控模式，只监控用户当前正在使用的应用程序窗口，不会干扰后台运行的程序。这意味着：

- 只有当未授权的应用位于前台（正在被用户使用）时才会发出警告
- 检测到异常后会进入1分钟的冷却期，给用户足够时间切换应用
- 冷却期间会显示倒计时，等待期结束后再次检测
- 后台运行的程序不会被监控或限制
- 系统会实时显示当前前台应用的名称和授权状态

## 配置说明

配置文件`config.json`包含以下设置：

- `allowed_apps`: 允许运行的应用程序名称列表（如notepad.exe, code.exe等）
- `allowed_executables`: 允许运行的可执行文件路径列表
- `allowed_urls`: 允许访问的URL列表
- `exam_time_limit`: 考试时间限制（分钟）
- `chrome_settings`: Chrome浏览器设置
- `only_monitor_foreground`: 是否只监控前台窗口（默认为true）
- `server_url`: 考试监控服务器URL
- `enable_server_reporting`: 是否启用服务器报告功能
- `screenshot_on_violation`: 是否在违规时截图

系统默认允许使用以下类型的应用程序：
- 各种浏览器：Chrome、Edge、Firefox
- 编辑器和IDE：VS Code、Visual Studio、IntelliJ IDEA、PyCharm、Eclipse等
- 文档工具：Word、Excel、PowerPoint、PDF阅读器
- 系统工具：计算器、文件资源管理器、终端

## 常见问题排除

### ImportError: No module named tkinter

这表示Python安装时未包含tkinter模块。请重新安装Python，并确保在安装时选中"tcl/tk和IDLE"选项。

### Chrome启动失败

确保已正确安装Google Chrome浏览器，并且路径在以下位置之一：
- `C:\Program Files\Google\Chrome\Application\chrome.exe`
- `C:\Program Files (x86)\Google\Chrome\Application\chrome.exe`

### 依赖项安装问题

如果安装依赖时遇到问题，可以尝试以下命令：
```
pip install --upgrade pip
pip install -r requirements.txt
``` 