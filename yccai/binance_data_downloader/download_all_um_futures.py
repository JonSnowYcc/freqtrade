#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
USD-M Futures 数据下载脚本
下载所有 USD-M Futures（U本位合约）的完整历史数据
"""

import sys
import time
import signal
import threading
import os
import atexit
import psutil
from datetime import datetime
import argparse

# 设置控制台编码为UTF-8，解决Windows中文乱码问题
if sys.platform.startswith('win'):
    import codecs
    import locale
    
    # 尝试设置控制台编码
    try:
        # 设置环境变量
        import os
        os.environ['PYTHONIOENCODING'] = 'utf-8'
        
        # 设置标准输出编码
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        else:
            # 对于较老版本的Python
            sys.stdout = codecs.getwriter('utf-8')(sys.stdout.detach())
            sys.stderr = codecs.getwriter('utf-8')(sys.stderr.detach())
            
        # 设置locale
        try:
            locale.setlocale(locale.LC_ALL, 'C.UTF-8')
        except locale.Error:
            try:
                locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
            except locale.Error:
                pass  # 如果都失败，继续执行
                
    except Exception as e:
        # 如果编码设置失败，记录但不中断程序
        print(f"警告: 无法设置UTF-8编码: {e}")

from config import (
    UM_FUTURES_DATA_TYPES, MAJOR_SYMBOLS, INTERVALS, YEARS, MONTHS, 
    PERIOD_START_DATE, print_config
)
from enhanced_utility import (
    generate_date_range, safe_print, scan_missing_files_for_all_symbols,
    download_missing_files_only
)

# 全局变量用于优雅退出
shutdown_event = threading.Event()
current_process = None
child_processes = []

def cleanup_processes():
    """清理所有子进程"""
    global child_processes
    if child_processes:
        safe_print("正在清理子进程...")
        for proc in child_processes:
            try:
                if proc.is_running():
                    proc.terminate()
                    proc.wait(timeout=5)
            except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                try:
                    proc.kill()
                except psutil.NoSuchProcess:
                    pass
        child_processes.clear()

def signal_handler(signum, frame):
    """信号处理函数，用于优雅退出"""
    safe_print(f"\n\n收到信号 {signum}，正在优雅退出...")
    shutdown_event.set()
    safe_print("已设置退出标志，请等待当前任务完成...")
    
    # 立即清理子进程
    cleanup_processes()
    
    # 强制退出，不等待
    safe_print("强制退出程序...")
    os._exit(1)

def setup_signal_handlers():
    """设置信号处理器"""
    global current_process
    
    # 获取当前进程
    current_process = psutil.Process()
    
    # 注册退出清理函数
    atexit.register(cleanup_processes)
    
    # 设置信号处理器
    signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # 终止信号
    
    # Windows 特定信号
    if hasattr(signal, 'SIGBREAK'):  # Windows Ctrl+Break
        signal.signal(signal.SIGBREAK, signal_handler)
    
    # 处理 Windows 控制台关闭事件
    if sys.platform.startswith('win'):
        try:
            import ctypes
            from ctypes import wintypes
            
            # 定义控制台事件处理函数
            def console_handler(ctrl_type):
                if ctrl_type in [0, 1, 2, 5]:  # CTRL_C_EVENT, CTRL_BREAK_EVENT, CTRL_CLOSE_EVENT, CTRL_LOGOFF_EVENT
                    safe_print(f"\n收到控制台事件 {ctrl_type}，正在退出...")
                    signal_handler(ctrl_type, None)
                    return True
                return False
            
            # 注册控制台事件处理器
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleCtrlHandler(
                ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.DWORD)(console_handler),
                True
            )
        except Exception as e:
            safe_print(f"无法设置Windows控制台处理器: {e}")

def monitor_parent_process():
    """监控父进程，如果父进程退出则自动退出"""
    global current_process
    
    if not current_process:
        return
    
    try:
        parent = current_process.parent()
        if parent and parent.pid != 1:  # 有父进程且不是init进程
            while not shutdown_event.is_set():
                try:
                    if not parent.is_running():
                        safe_print("\n检测到父进程已退出，正在自动退出...")
                        shutdown_event.set()
                        cleanup_processes()
                        os._exit(0)
                except psutil.NoSuchProcess:
                    safe_print("\n检测到父进程已退出，正在自动退出...")
                    shutdown_event.set()
                    cleanup_processes()
                    os._exit(0)
                
                time.sleep(1)  # 每秒检查一次
    except Exception as e:
        safe_print(f"监控父进程时出错: {e}")

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='下载 USD-M Futures 数据（默认只下载daily数据）',
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument(
        '-s', '--symbols', nargs='+',
        help='指定交易对符号，不指定则下载所有符号'
    )
    
    parser.add_argument(
        '--major-only', action='store_true',
        help='仅下载主流币对数据（BTC和ETH）'
    )
    
    parser.add_argument(
        '-d', '--data-types', nargs='+', 
        choices=UM_FUTURES_DATA_TYPES,
        default=UM_FUTURES_DATA_TYPES,
        help=f'指定数据类型，可选: {", ".join(UM_FUTURES_DATA_TYPES)}'
    )
    
    parser.add_argument(
        '-i', '--intervals', nargs='+',
        choices=INTERVALS,
        default=INTERVALS,
        help=f'指定时间间隔，可选: {", ".join(INTERVALS)}'
    )
    
    parser.add_argument(
        '-y', '--years', nargs='+',
        choices=YEARS,
        default=YEARS,
        help=f'指定年份，可选: {", ".join(YEARS)}'
    )
    
    parser.add_argument(
        '-m', '--months', nargs='+', type=int,
        choices=MONTHS,
        default=MONTHS,
        help=f'指定月份，可选: {", ".join(map(str, MONTHS))}'
    )
    
    parser.add_argument(
        '--start-date', type=str,
        default=PERIOD_START_DATE,
        help=f'开始日期 (YYYY-MM-DD)，默认: {PERIOD_START_DATE}'
    )
    
    parser.add_argument(
        '--end-date', type=str,
        default=datetime.now().strftime('%Y-%m-%d'),
        help='结束日期 (YYYY-MM-DD)，默认: 今天'
    )
    
    parser.add_argument(
        '--skip-monthly', action='store_true', default=True,
        help='跳过月度数据下载（默认启用，只下载daily数据）'
    )
    
    parser.add_argument(
        '--include-monthly', action='store_true',
        help='包含月度数据下载（覆盖默认的跳过行为）'
    )
    
    parser.add_argument(
        '--skip-daily', action='store_true',
        help='跳过日度数据下载'
    )
    
    parser.add_argument(
        '--include-checksum', action='store_true',
        help='同时下载校验和文件'
    )
    
    parser.add_argument(
        '--dry-run', action='store_true',
        help='仅显示将要下载的文件，不实际下载'
    )
    
    
    return parser.parse_args()

def validate_date(date_str: str) -> bool:
    """验证日期格式"""
    try:
        datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False


def main():
    """主函数"""
    # 设置信号处理器
    setup_signal_handlers()
    
    # 启动父进程监控线程
    monitor_thread = threading.Thread(target=monitor_parent_process, daemon=True)
    monitor_thread.start()
    
    args = parse_arguments()
    
    # 验证日期格式
    if not validate_date(args.start_date):
        safe_print(f"错误: 开始日期格式无效: {args.start_date}")
        sys.exit(1)
    
    if not validate_date(args.end_date):
        safe_print(f"错误: 结束日期格式无效: {args.end_date}")
        sys.exit(1)
    
    # 打印配置信息
    print_config()
    
    # 获取交易对 - 默认只下载BTC和ETH
    if args.symbols:
        symbols = [s.upper() for s in args.symbols]
        safe_print(f"使用指定的 {len(symbols)} 个交易对")
    else:
        # 默认使用主流币对（BTC和ETH）
        symbols = MAJOR_SYMBOLS
        safe_print(f"使用主流币对列表（BTC和ETH），共 {len(symbols)} 个交易对")
    
    # 生成日期列表
    dates = generate_date_range(args.start_date, args.end_date)
    safe_print(f"日期范围: {args.start_date} 到 {args.end_date} ({len(dates)} 天)")
    
    # 统计信息
    total_results = {'success': 0, 'failed': 0, 'skipped': 0}
    
    # 使用扫描模式进行增量写入
    safe_print(f"\n{'='*60}")
    safe_print("增量下载模式：遍历每个币种文件夹，只下载缺失的文件")
    safe_print(f"{'='*60}")
    
    # 扫描所有币种的缺失文件
    # 根据参数决定是否包含monthly数据
    if args.include_monthly:
        # 包含monthly数据
        all_missing_tasks = scan_missing_files_for_all_symbols(
            symbols=symbols,
            data_types=args.data_types,
            intervals=args.intervals,
            years=args.years,
            months=args.months,
            dates=dates,
            start_date=args.start_date,
            end_date=args.end_date
        )
    else:
        # 默认只处理daily数据，跳过monthly数据
        all_missing_tasks = scan_missing_files_for_all_symbols(
            symbols=symbols,
            data_types=args.data_types,
            intervals=args.intervals,
            years=[],  # daily数据不需要年份
            months=[],  # daily数据不需要月份
            dates=dates,
            start_date=args.start_date,
            end_date=args.end_date
        )
    
    if args.dry_run:
        safe_print("\n=== 预览模式 - 将要下载的缺失文件 ===")
        for symbol, symbol_tasks in all_missing_tasks.items():
            if symbol_tasks:
                total_missing = sum(len(tasks) for tasks in symbol_tasks.values())
                safe_print(f"{symbol}: 缺失 {total_missing} 个文件")
                # 显示前几个文件夹的示例
                for i, (folder_key, tasks) in enumerate(list(symbol_tasks.items())[:2]):
                    safe_print(f"  文件夹: {folder_key}")
                    for j, (path, file_name, date_range) in enumerate(tasks[:3]):
                        safe_print(f"    {j+1}. {path}{file_name}")
                    if len(tasks) > 3:
                        safe_print(f"    ... 还有 {len(tasks) - 3} 个文件")
                if len(symbol_tasks) > 2:
                    safe_print(f"  ... 还有 {len(symbol_tasks) - 2} 个文件夹")
            else:
                safe_print(f"{symbol}: 没有缺失文件")
        safe_print("=" * 50)
        return
    
    # 下载所有缺失文件
    total_results = download_missing_files_only(all_missing_tasks, shutdown_event)
    
    # 输出最终摘要
    safe_print(f"\n{'='*60}")
    safe_print("增量下载完成 - 最终摘要")
    safe_print(f"{'='*60}")
    
    safe_print("下载模式: 增量下载模式")
    safe_print(f"交易对数量: {len(symbols)}")
    safe_print(f"数据类型: {', '.join(args.data_types)}")
    safe_print(f"总文件数: {sum(total_results.values())}")
    safe_print(f"成功下载: {total_results['success']}")
    safe_print(f"下载失败: {total_results['failed']}")
    safe_print(f"跳过文件: {total_results['skipped']}")
    
    if total_results['failed'] > 0:
        safe_print(f"\n警告: 有 {total_results['failed']} 个文件下载失败")
        sys.exit(1)
    else:
        safe_print("\n[成功] 所有缺失文件下载成功!")
    
    return

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        safe_print("\n\n用户中断下载")
        shutdown_event.set()
        cleanup_processes()
        # 立即退出，不等待
        os._exit(1)
    except Exception as e:
        safe_print(f"\n错误: {e}")
        import traceback
        safe_print(f"详细错误信息: {traceback.format_exc()}")
        shutdown_event.set()
        cleanup_processes()
        os._exit(1)
    finally:
        if shutdown_event.is_set():
            safe_print("\n程序已安全退出")
            cleanup_processes()
