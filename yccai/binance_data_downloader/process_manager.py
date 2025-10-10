#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
进程管理器 - 确保下载程序能够正确响应终止信号
"""

import os
import sys
import time
import signal
import subprocess
import threading
import psutil
from typing import Optional

class ProcessManager:
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.shutdown_event = threading.Event()
        self.monitor_thread: Optional[threading.Thread] = None
        
    def signal_handler(self, signum, frame):
        """信号处理函数"""
        print(f"\n收到信号 {signum}，正在终止子进程...")
        self.shutdown_event.set()
        self.terminate_process()
        sys.exit(0)
    
    def setup_signal_handlers(self):
        """设置信号处理器"""
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        # Windows 特定信号
        if hasattr(signal, 'SIGBREAK'):
            signal.signal(signal.SIGBREAK, self.signal_handler)
    
    def terminate_process(self):
        """终止子进程"""
        if self.process and self.process.poll() is None:
            print("正在终止子进程...")
            try:
                # 尝试优雅终止
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                print("优雅终止超时，强制杀死进程...")
                self.process.kill()
                self.process.wait()
            except Exception as e:
                print(f"终止进程时出错: {e}")
    
    def monitor_process(self):
        """监控子进程状态"""
        while not self.shutdown_event.is_set():
            if self.process and self.process.poll() is not None:
                print(f"子进程已退出，退出代码: {self.process.returncode}")
                break
            time.sleep(0.1)
    
    def run(self, script_path: str, args: list = None):
        """运行脚本"""
        if args is None:
            args = []
        
        # 设置信号处理器
        self.setup_signal_handlers()
        
        try:
            # 启动子进程
            print(f"启动进程: python {script_path} {' '.join(args)}")
            
            # 设置环境变量确保正确的编码
            env = os.environ.copy()
            env['PYTHONIOENCODING'] = 'utf-8'
            env['PYTHONUNBUFFERED'] = '1'
            if sys.platform.startswith('win'):
                env['PYTHONLEGACYWINDOWSSTDIO'] = 'utf-8'
            
            self.process = subprocess.Popen(
                [sys.executable, script_path] + args,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1,
                encoding='utf-8',
                errors='replace',
                env=env
            )
            
            # 启动监控线程
            self.monitor_thread = threading.Thread(target=self.monitor_process, daemon=True)
            self.monitor_thread.start()
            
            # 实时输出子进程的输出
            while self.process.poll() is None and not self.shutdown_event.is_set():
                try:
                    line = self.process.stdout.readline()
                    if line:
                        # 确保输出能正确处理中文字符
                        try:
                            print(line.rstrip())
                        except UnicodeEncodeError:
                            # 如果输出编码失败，使用安全的编码方式
                            safe_line = line.encode('utf-8', errors='replace').decode('utf-8')
                            print(safe_line.rstrip())
                except Exception as e:
                    print(f"读取输出时出错: {e}")
                    break
            
            # 等待进程结束
            if not self.shutdown_event.is_set():
                self.process.wait()
                return self.process.returncode
            else:
                return 1
                
        except Exception as e:
            print(f"运行脚本时出错: {e}")
            return 1
        finally:
            self.terminate_process()

def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python process_manager.py <script_path> [args...]")
        sys.exit(1)
    
    script_path = sys.argv[1]
    args = sys.argv[2:] if len(sys.argv) > 2 else []
    
    if not os.path.exists(script_path):
        print(f"脚本文件不存在: {script_path}")
        sys.exit(1)
    
    manager = ProcessManager()
    exit_code = manager.run(script_path, args)
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
