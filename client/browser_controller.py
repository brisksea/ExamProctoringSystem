#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import time
import psutil
from selenium import webdriver

class BaseBrowserController:
    def __init__(self, config_manager=None, default_url=None, disable_new_tabs=False):
        """
        初始化浏览器控制器基类

        Args:
            config_manager: 配置管理器实例
            default_url: 默认URL
            disable_new_tabs: 是否禁用新标签页
        """
        self.config_manager = config_manager
        self.disable_new_tabs = disable_new_tabs
        self.driver = None
        self.default_url = default_url
        self.window_title = None
        self.chrome_pid = None  # 在Edge中也可以叫这个，或者改名为 browser_pid
        
        # 编译URL匹配模式
        self.url_restriction_enabled = True
        self.compiled_patterns = []
        self.allowed_urls = []
        if config_manager:
            patterns = config_manager.get_url_patterns()
            self.compiled_patterns = [re.compile(pattern) for pattern in patterns]
            self.allowed_urls = config_manager.get_allowed_urls() or []
            if self.default_url and self.default_url not in self.allowed_urls:
                self.allowed_urls.append(self.default_url)

    def start(self, url=None):
        """启动浏览器，子类必须实现此方法"""
        raise NotImplementedError("Subclasses must implement start method")

    def stop(self):
        """停止浏览器"""
        try:
            if self.driver:
                self.driver.quit()
                self.driver = None
                print("浏览器已关闭")
                self.chrome_pid = None
        except Exception as e:
            print(f"关闭浏览器时出错: {str(e)}")

    def is_running(self):
        """检查浏览器是否正在运行"""
        return self.chrome_pid is not None and psutil.pid_exists(self.chrome_pid)

    def is_controlled(self, pid):
        """检查当前浏览器实例是否是受控的"""
        if self.chrome_pid is None:
            return False
        return self.chrome_pid == pid

    def _strip_protocol(self, url):
        if url.startswith('http://'):
            return url[len('http://'):]
        elif url.startswith('https://'):
            return url[len('https://'):]
        return url

    def _is_url_allowed(self, url):
        """
        检查URL是否允许访问
        """
        if not self.url_restriction_enabled:
            return True

        # 处理 None 或空URL
        if not url:
            return True

        # 特殊页面总是允许 (Edge也有类似的schema)
        if (url.startswith("about:") or
            url.startswith("chrome://") or
            url.startswith("edge://") or
            url.startswith("chrome-error://") or
            url.startswith("edge-error://") or
            url.startswith("data:text/html") or
            url.startswith("chrome-extension://") or
            url.startswith("extension://") or
            url == "about:blank" or
            "chrome-search://" in url or 
            "edge-search://" in url):
            return True

        # 检查是否匹配任何允许的URL模式
        try:
            for pattern in self.compiled_patterns:
                if pattern.match(url):
                    return True
        except Exception as e:
            print(f"正则表达式匹配错误: {str(e)}")
            return True
        
        try:
            url_no_proto = self._strip_protocol(url)
            for allowed_url in self.allowed_urls:
                allowed_url_no_proto = self._strip_protocol(allowed_url)
                if url_no_proto.startswith(allowed_url_no_proto):
                    return True
        except Exception as e:
            print(f"URL前缀匹配错误: {str(e)}")
            return True

        return False

    def to_default_url(self):
        if self.default_url:
            self.driver.execute_script(f"window.location.href = '{self.default_url}';")
        else:
            self.driver.execute_script("window.location.href = 'about:blank';")

    def check(self, pid, window_title):
        if not self.is_controlled(pid):
            return "未受控的浏览器，请切换到允许的浏览器进行考试"
        
        try:
            # 尝试使用CDP Check，适用于Chrome和Edge (Chromium based)
            result = self.driver.execute_cdp_cmd('Target.getTargets', {})
            
            # CDP 返回的是字典，包含 targetInfos 键
            # 处理不同的返回格式：可能是字典或直接是列表
            if isinstance(result, dict):
                targets = result.get('targetInfos', [])
            elif isinstance(result, list):
                targets = result
            else:
                # 如果返回格式不符合预期，回退到旧方法
                raise ValueError(f"Unexpected CDP response format: {type(result)}")
            
            # 检查标签页数量
            page_targets = [t for t in targets if isinstance(t, dict) and t.get('type') == 'page']
            if self.disable_new_tabs and len(page_targets) > 1:
                return f"检测到多个标签页，请关闭多余标签页"

            # 检查每个标签页的URL
            for target in page_targets:
                url = target.get('url', '')
                if not self._is_url_allowed(url):
                    return f"未授权的URL: {url}，切换到允许的URL进行考试"
                    
        except Exception as e:
            # 如果CDP失败，回退到原来的方法
            print(f"CDP检查失败，回退到常规检查: {str(e)}")
            return self._check_legacy(pid, window_title)

        self.window_title = window_title
        return None

    def _check_legacy(self, pid, window_title):
        """旧的检查方法，作为回退"""
        handles = self.driver.window_handles
        if self.disable_new_tabs and len(handles) > 1:
            return f"检测到多个标签页，请关闭多余标签页"
        
        #如果链接没有发生变化不检查
        if self.window_title == window_title:
            return None
        
        if not window_title:
            return None
            
        # 简单处理标题分割，Chrome是 " - Google Chrome", Edge是 " - Microsoft Edge" 等
        # 这里不做严格分割，只用来大致判断
        
        try:
            current_handle = handles[0]
            for handle in handles:
                self.driver.switch_to.window(handle)
                url = self.driver.current_url
                if not self._is_url_allowed(url):
                    return f"未授权的URL: {url}，切换到允许的URL进行考试"
                
                # 尝试匹配当前窗口
                if window_title.startswith(self.driver.title):
                    current_handle = handle
            self.driver.switch_to.window(current_handle)           
        except Exception as e:
            return f"获取标签页句柄时出错: {str(e)}"
        
        self.window_title = window_title
        return None

    def handle_multiple_tabs_when_disabled(self):
        """处理禁用新标签页时的多标签页情况"""
        try:
            handles = self.driver.window_handles
            if len(handles) <= 1:
                return

            first_handle = handles[0]
            for handle in handles[1:]:
                try:
                    self.driver.switch_to.window(handle)
                    self.driver.close()
                except Exception as e:
                    print(f"关闭多余标签页时出错: {str(e)}")

            try:
                self.driver.switch_to.window(first_handle)
            except Exception as e:
                print(f"切换回第一个标签页时出错: {str(e)}")

        except Exception as e:
            print(f"处理多标签页时出错: {str(e)}")

    def check_and_restart_if_needed(self):
        """检查浏览器是否需要重启"""
        try:
            if self.is_running():
                return 'running'

            print("浏览器未运行或未受控，尝试重启...")
            self.stop() # 确保清理清理干净
            self.start()
            return "restart"

        except Exception as e:
            print(f"重启浏览器时出错: {str(e)}")
            return "error"

    def restart(self):
        """重启浏览器"""
        try:
            print("正在重启浏览器...")
            self.stop()
            self.window_title = None
            self.start()
            print("浏览器重启成功")
            return True
        except Exception as e:
            print(f"重启浏览器时出错: {str(e)}")
            return False
