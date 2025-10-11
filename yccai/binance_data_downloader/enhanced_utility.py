#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
增强的工具函数 - 支持代理、并发下载、重试机制
"""

import os
import json
import time
# import ssl  # 暂时未使用
from datetime import date
from typing import List, Dict, Optional, Tuple
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from config import (
    get_proxies, get_storage_dir, DOWNLOAD_CONFIG,
    BASE_URL, PERIOD_START_DATE
)

# 线程锁用于打印和进度保存
print_lock = threading.Lock()
progress_lock = threading.Lock()

def safe_print(*args, **kwargs):
    """线程安全的打印函数"""
    with print_lock:
        # 确保输出使用UTF-8编码
        import sys
        try:
            # 尝试设置UTF-8编码
            if hasattr(sys.stdout, 'reconfigure'):
                sys.stdout.reconfigure(encoding='utf-8')
            
            # 处理中文字符
            if args:
                # 确保所有参数都是字符串且使用UTF-8编码
                processed_args = []
                for arg in args:
                    if isinstance(arg, str):
                        # 确保字符串是UTF-8编码
                        try:
                            arg.encode('utf-8')
                            processed_args.append(arg)
                        except UnicodeEncodeError:
                            # 如果编码失败，使用错误处理
                            processed_args.append(arg.encode('utf-8', errors='replace').decode('utf-8'))
                    else:
                        processed_args.append(str(arg))
                print(*processed_args, **kwargs)
            else:
                print(*args, **kwargs)
                
        except Exception:
            # 如果打印失败，尝试使用最基本的打印方式
            try:
                print(*args, **kwargs)
            except Exception:
                # 最后的备用方案
                print("打印输出时发生编码错误")

# 移除了进度保存相关函数，改为基于文件存在性检查

def get_all_symbols(trading_type: str = 'um') -> List[str]:
    """获取所有交易对符号"""
    # 尝试多个API端点
    urls = []
    if trading_type == 'um':
        urls = [
            "https://fapi.binance.com/fapi/v1/exchangeInfo",
            "https://fapi.binance.com/fapi/v1/ticker/24hr",
            "https://fapi.binance.com/fapi/v1/ticker/price"
        ]
    elif trading_type == 'cm':
        urls = [
            "https://dapi.binance.com/dapi/v1/exchangeInfo",
            "https://dapi.binance.com/dapi/v1/ticker/24hr"
        ]
    else:
        urls = [
            "https://api.binance.com/api/v3/exchangeInfo",
            "https://api.binance.com/api/v3/ticker/24hr"
        ]
    
    proxies = get_proxies()
    
    for url in urls:
        try:
            safe_print(f"尝试从 {url} 获取交易对...")
            req = urllib.request.Request(url)
            req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
            req.add_header('Accept', 'application/json')
            
            if proxies:
                proxy_handler = urllib.request.ProxyHandler(proxies)
                opener = urllib.request.build_opener(proxy_handler)
                response = opener.open(req, timeout=DOWNLOAD_CONFIG['timeout'])
            else:
                response = urllib.request.urlopen(req, timeout=DOWNLOAD_CONFIG['timeout'])
            
            data = json.loads(response.read().decode('utf-8'))
            
            if 'symbols' in data:
                # exchangeInfo 格式
                symbols = [symbol['symbol'] for symbol in data['symbols']]
            elif isinstance(data, list):
                # ticker 格式
                symbols = [item['symbol'] for item in data]
            else:
                continue
                
            safe_print(f"成功获取 {len(symbols)} 个交易对")
            return symbols
            
        except Exception as e:
            safe_print(f"从 {url} 获取交易对失败: {e}")
            continue
    
    # 如果所有API都失败，使用预定义列表
    safe_print("所有API端点都失败，使用预定义交易对列表...")
    return get_symbols_from_data()

def get_symbols_from_data() -> List[str]:
    """从数据源推断交易对列表"""
    try:
        # 尝试从Binance数据源获取可用的交易对列表
        # 这里使用一个已知的交易对列表作为备选
        common_symbols = [
            'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'ADAUSDT', 'XRPUSDT', 'SOLUSDT', 
            'DOTUSDT', 'DOGEUSDT', 'AVAXUSDT', 'SHIBUSDT', 'MATICUSDT', 'LTCUSDT',
            'LINKUSDT', 'UNIUSDT', 'ATOMUSDT', 'FILUSDT', 'TRXUSDT', 'ETCUSDT',
            'XLMUSDT', 'BCHUSDT', 'NEARUSDT', 'ALGOUSDT', 'VETUSDT', 'ICPUSDT',
            'THETAUSDT', 'FTMUSDT', 'HBARUSDT', 'MANAUSDT', 'SANDUSDT', 'AXSUSDT',
            'FLOWUSDT', 'EGLDUSDT', 'XTZUSDT', 'KSMUSDT', 'DASHUSDT', 'ZECUSDT',
            'COMPUSDT', 'MKRUSDT', 'SNXUSDT', 'YFIUSDT', 'SUSHIUSDT', 'AAVEUSDT',
            'CRVUSDT', '1INCHUSDT', 'BATUSDT', 'ZRXUSDT', 'ENJUSDT', 'CHZUSDT',
            'HOTUSDT', 'WINUSDT', 'BTTUSDT', 'ONTUSDT', 'QTUMUSDT', 'IOTAUSDT',
            'NEOUSDT', 'EOSUSDT', 'XMRUSDT', 'DCRUSDT', 'ZILUSDT', 'RVNUSDT',
            'SCUSDT', 'STORJUSDT', 'KNCUSDT', 'REPUSDT', 'LRCUSDT', 'OMGUSDT',
            'BANDUSDT', 'RENUSDT', 'KAVAUSDT', 'BALUSDT', 'UMAUSDT', 'SRMUSDT',
            'YFIIUSDT', 'SUNUSDT', 'CREAMUSDT', 'ALPHAUSDT', 'ZENUSDT', 'SKLUSDT',
            'GRTUSDT', 'JSTUSDT', 'SFPUSDT', 'DODOUSDT', 'BCHAUSDT', 'LINAUSDT',
            'PERPUSDT', 'RAMPUSDT', 'SUPERUSDT', 'CFXUSDT', 'EPSUSDT', 'AUTOUSDT',
            'TKOUSDT', 'PONDUSDT', 'DEGOUSDT', 'ALICEUSDT', 'LITUSDT', 'SFPUSDT',
            'DYDXUSDT', 'GALAUSDT', 'CELRUSDT', 'KLAYUSDT', 'ARUSDT', 'CTSIUSDT',
            'LPTUSDT', 'ENSUSDT', 'PEOPLEUSDT', 'ANTUSDT', 'ROSEUSDT', 'DUSKUSDT',
            'FLOWUSDT', 'IMXUSDT', 'API3USDT', 'GMTUSDT', 'APEUSDT', 'BNXUSDT',
            'WAXPUSDT', 'FTMUSDT', 'OPUSDT', 'INJUSDT', 'STGUSDT', 'FOOTBALLUSDT',
            'SPELLUSDT', '1000SATSUSDT', '1000PEPEUSDT', '1000FLOKIUSDT', '1000LUNCUSDT',
            '1000BONKUSDT', '1000SHIBUSDT', '1000BABYDOGEUSDT', '1000DOGEUSDT'
        ]
        
        safe_print(f"使用预定义交易对列表，共 {len(common_symbols)} 个交易对")
        return common_symbols
        
    except Exception as e:
        safe_print(f"获取交易对失败: {e}")
        return []

def get_download_url(file_path: str) -> str:
    """构建下载URL"""
    return f"{BASE_URL}{file_path}"

def get_destination_path(base_path: str, file_name: str, date_range: Optional[str] = None) -> str:
    """获取文件保存路径"""
    storage_dir = get_storage_dir()
    
    # 不再创建日期范围子目录，直接保存到基础路径
    full_path = os.path.join(storage_dir, base_path)
    return os.path.join(full_path, file_name)

def download_file_with_retry(file_path: str, file_name: str, date_range: Optional[str] = None, shutdown_event=None) -> bool:
    """带重试机制的文件下载，支持断电续传和增量下载"""
    save_path = get_destination_path(file_path, file_name, date_range)
    
    # 检查文件是否已存在且完整
    if os.path.exists(save_path):
        file_size = os.path.getsize(save_path)
        if file_size > 0:  # 文件存在且不为空
            # 静默跳过已存在的文件，不输出日志
            return True
        else:
            # 只在发现损坏文件时输出警告
            safe_print(f"{file_name} [警告] 发现损坏的空文件，重新下载")
            os.remove(save_path)  # 删除损坏的文件
    
    # 创建目录
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    
    download_url = get_download_url(f"{file_path}{file_name}")
    proxies = get_proxies()
    
    for attempt in range(DOWNLOAD_CONFIG['max_retries']):
        # 检查退出信号 - 更频繁的检查
        if shutdown_event and shutdown_event.is_set():
            safe_print(f"{file_name} [取消] 下载被取消")
            return False
            
        try:
            req = urllib.request.Request(download_url)
            
            if proxies:
                proxy_handler = urllib.request.ProxyHandler(proxies)
                opener = urllib.request.build_opener(proxy_handler)
                response = opener.open(req, timeout=DOWNLOAD_CONFIG['timeout'])
            else:
                response = urllib.request.urlopen(req, timeout=DOWNLOAD_CONFIG['timeout'])
            
            # 获取文件大小
            length = response.getheader('content-length')
            if length:
                length = int(length)
                blocksize = max(DOWNLOAD_CONFIG['chunk_size'], length // 100)
            else:
                blocksize = DOWNLOAD_CONFIG['chunk_size']
            
            # 下载文件
            with open(save_path, 'wb') as out_file:
                dl_progress = 0
                while True:
                    # 检查退出信号
                    if shutdown_event and shutdown_event.is_set():
                        safe_print(f"\n{file_name} [取消] 下载被取消")
                        return False
                        
                    buf = response.read(blocksize)
                    if not buf:
                        break
                    dl_progress += len(buf)
                    out_file.write(buf)
                    
                    # 移除进度显示，减少日志输出
                    # 只在下载大文件时偶尔显示进度
                    if length and length > 1024*1024 and dl_progress % (blocksize * 50) == 0:  # 只对大文件显示进度
                        done = int(50 * dl_progress / length)
                        progress_bar = f"[{'#' * done}{'.' * (50-done)}]"
                        safe_print(f"\r下载 {file_name}: {progress_bar} {dl_progress}/{length} bytes", end='')
            
            # 移除单个文件完成的日志输出，改为在文件夹级别输出
            return True
            
        except urllib.error.HTTPError as e:
            if e.code == 404:
                safe_print(f"{file_name} [错误] 文件不存在")
                return False
            else:
                safe_print(f"{file_name} [错误] HTTP错误 {e.code} (尝试 {attempt + 1}/{DOWNLOAD_CONFIG['max_retries']})")
        except Exception as e:
            safe_print(f"{file_name} [错误] 下载失败: {e} (尝试 {attempt + 1}/{DOWNLOAD_CONFIG['max_retries']})")
        
        if attempt < DOWNLOAD_CONFIG['max_retries'] - 1:
            delay = DOWNLOAD_CONFIG['retry_delay'] * (2 ** attempt)  # 指数退避
            safe_print(f"等待 {delay} 秒后重试...")
            time.sleep(delay)
    
    safe_print(f"{file_name} [失败] 下载失败，已达到最大重试次数")
    return False

def extract_folder_key(file_path: str, file_name: str) -> str:
    """从文件路径和文件名中提取文件夹标识"""
    # 从文件名中提取关键信息，如 BTCUSDT-1m-2021-10.zip -> BTCUSDT-1m-2021-10
    if file_name.endswith('.zip'):
        return file_name[:-4]  # 去掉 .zip 后缀
    elif file_name.endswith('.CHECKSUM'):
        # 对于 CHECKSUM 文件，去掉 .CHECKSUM 后缀，然后去掉 .zip 后缀
        base_name = file_name[:-9]  # 去掉 .CHECKSUM 后缀
        if base_name.endswith('.zip'):
            return base_name[:-4]  # 再去掉 .zip 后缀
        return base_name
    else:
        # 如果无法从文件名提取，使用路径的最后一部分
        return file_path.split('/')[-2] if '/' in file_path else file_name

def download_files_by_folder(folder_tasks: Dict[str, List[Tuple[str, str, Optional[str]]]], shutdown_event=None) -> Dict[str, int]:
    """按文件夹顺序下载文件，确保按逻辑顺序处理"""
    results = {'success': 0, 'failed': 0, 'skipped': 0}
    
    # 按文件夹键排序，确保按逻辑顺序处理
    sorted_folders = sorted(folder_tasks.keys())
    
    for folder_key in sorted_folders:
        if shutdown_event and shutdown_event.is_set():
            safe_print(f"\n检测到退出信号，停止处理文件夹: {folder_key}")
            break
            
        folder_file_tasks = folder_tasks[folder_key]
        
        # 下载当前文件夹的所有文件
        folder_results = download_files_concurrent(folder_file_tasks, shutdown_event)
        
        # 累加结果
        for key in results:
            results[key] += folder_results[key]
        
        # 输出文件夹完成信息
        total_files = len(folder_file_tasks)
        safe_print(f"{folder_key} [完成] 文件夹处理完成: 成功 {folder_results['success']}/{total_files}, 失败 {folder_results['failed']}, 跳过 {folder_results['skipped']}")
    
    return results

def download_files_concurrent(file_tasks: List[Tuple[str, str, Optional[str]]], shutdown_event=None) -> Dict[str, int]:
    """并发下载多个文件，支持优雅退出，日志按顺序输出"""
    results = {'success': 0, 'failed': 0, 'skipped': 0}
    
    # 按文件夹组织任务，用于统计
    folder_stats = {}
    download_results = []  # 存储下载结果，用于后续按顺序输出日志
    total_tasks = len(file_tasks)
    completed_tasks = 0
    
    # 简化开始信息
    safe_print(f"开始下载 {total_tasks} 个文件...")
    
    for file_path, file_name, date_range in file_tasks:
        # 从文件路径中提取文件夹信息
        folder_key = extract_folder_key(file_path, file_name)
        if folder_key not in folder_stats:
            folder_stats[folder_key] = {'total': 0, 'success': 0, 'failed': 0, 'skipped': 0}
        folder_stats[folder_key]['total'] += 1
    
    with ThreadPoolExecutor(max_workers=DOWNLOAD_CONFIG['max_workers']) as executor:
        # 提交所有下载任务
        future_to_task = {
            executor.submit(download_file_with_retry, file_path, file_name, date_range, shutdown_event): (file_path, file_name, date_range)
            for file_path, file_name, date_range in file_tasks
        }
        
        try:
            # 处理完成的任务 - 收集结果但不立即输出日志
            while future_to_task:
                # 检查是否需要退出 - 更频繁的检查
                if shutdown_event and shutdown_event.is_set():
                    safe_print("\n检测到退出信号，取消剩余下载任务...")
                    # 取消所有未完成的任务
                    for f in future_to_task:
                        if not f.done():
                            f.cancel()
                    break
                
                # 使用更短的超时时间，让信号处理更及时
                try:
                    future = next(as_completed(future_to_task, timeout=0.05))  # 更短的超时时间
                except TimeoutError:
                    # 没有任务完成，继续检查退出信号
                    continue
                
                file_path, file_name, date_range = future_to_task[future]
                
                try:
                    success = future.result()
                    folder_key = extract_folder_key(file_path, file_name)
                    
                    # 记录下载结果，稍后按顺序输出
                    result_type = 'unknown'
                    if success:
                        # 下载成功，直接标记为成功（不再检查文件是否存在，因为刚下载完）
                        result_type = 'success'
                        results['success'] += 1
                        folder_stats[folder_key]['success'] += 1
                    else:
                        result_type = 'failed'
                        results['failed'] += 1
                        folder_stats[folder_key]['failed'] += 1
                    
                    # 存储结果用于后续按顺序输出
                    download_results.append({
                        'file_name': file_name,
                        'folder_key': folder_key,
                        'result_type': result_type,
                        'timestamp': time.time()
                    })
                    
                except Exception as e:
                    result_type = 'exception'
                    results['failed'] += 1
                    folder_key = extract_folder_key(file_path, file_name)
                    folder_stats[folder_key]['failed'] += 1
                    
                    # 存储异常结果
                    download_results.append({
                        'file_name': file_name,
                        'folder_key': folder_key,
                        'result_type': result_type,
                        'error': str(e),
                        'timestamp': time.time()
                    })
                
                # 从待处理任务中移除已完成的任务
                del future_to_task[future]
                
                # 更新进度显示
                completed_tasks += 1
                progress_percent = (completed_tasks / total_tasks) * 100
                remaining_tasks = total_tasks - completed_tasks
                
                # 每完成10个任务或完成所有任务时显示进度
                if completed_tasks % 10 == 0 or completed_tasks == total_tasks:
                    safe_print(f"进度: {completed_tasks}/{total_tasks} ({progress_percent:.1f}%) - 剩余: {remaining_tasks} 个任务")
                    
        except KeyboardInterrupt:
            safe_print("\n收到键盘中断信号，正在取消所有任务...")
            if shutdown_event:
                shutdown_event.set()
            # 取消所有未完成的任务
            for f in future_to_task:
                if not f.done():
                    f.cancel()
    
    # 只输出失败的下载结果
    failed_results = [r for r in download_results if r['result_type'] in ['failed', 'exception']]
    
    if failed_results:
        safe_print(f"\n=== 下载失败的文件 ({len(failed_results)} 个) ===")
        for i, result in enumerate(failed_results, 1):
            file_name = result['file_name']
            result_type = result['result_type']
            
            if result_type == 'failed':
                safe_print(f"[{i:3d}] {file_name} [失败] 下载失败")
            elif result_type == 'exception':
                error_msg = result.get('error', '未知错误')
                safe_print(f"[{i:3d}] {file_name} [异常] 任务执行异常: {error_msg}")
        safe_print("=== 失败文件列表结束 ===")
    
    # 输出简要统计
    if results['failed'] > 0:
        safe_print(f"警告: 有 {results['failed']} 个文件下载失败!")
    else:
        safe_print("所有文件处理完成!")
    
    return results

def convert_to_date_object(date_str: str) -> date:
    """将日期字符串转换为日期对象"""
    year, month, day = [int(x) for x in date_str.split('-')]
    return date(year, month, day)

def get_path(trading_type: str, market_data_type: str, time_period: str, symbol: str, interval: Optional[str] = None) -> str:
    """构建文件路径"""
    if trading_type == 'spot':
        trading_type_path = 'spot'
    else:
        trading_type_path = f'futures/{trading_type}'
    
    if interval is not None:
        path = f'{trading_type_path}/{time_period}/{market_data_type}/{symbol.upper()}/{interval}/'
    else:
        path = f'{trading_type_path}/{time_period}/{market_data_type}/{symbol.upper()}/'
    
    return path

def generate_date_range(start_date: str, end_date: str) -> List[str]:
    """生成日期范围列表"""
    from datetime import timedelta
    
    start = convert_to_date_object(start_date)
    end = convert_to_date_object(end_date)
    
    dates = []
    current = start
    while current <= end:
        dates.append(current.strftime('%Y-%m-%d'))
        current = current + timedelta(days=1)
    
    return dates

def get_file_tasks_by_folder(
    data_type: str, 
    symbols: List[str], 
    intervals: List[str], 
    years: List[str], 
    months: List[int],
    dates: List[str],
    start_date: str,
    end_date: str,
    include_checksum: bool = False
) -> Dict[str, List[Tuple[str, str, Optional[str]]]]:
    """按文件夹组织下载任务"""
    folder_tasks = {}
    
    for symbol in symbols:
        # 月度数据
        for year in years:
            for month in months:
                current_date = convert_to_date_object(f'{year}-{month:02d}-01')
                start_obj = convert_to_date_object(start_date) if start_date else convert_to_date_object(PERIOD_START_DATE)
                end_obj = convert_to_date_object(end_date) if end_date else date.today()
                
                if start_obj <= current_date <= end_obj:
                    if data_type in ['klines', 'indexPriceKlines', 'markPriceKlines', 'premiumIndexKlines']:
                        # 需要间隔的数据类型
                        for interval in intervals:
                            path = get_path('um', data_type, 'monthly', symbol, interval)
                            file_name = f"{symbol.upper()}-{interval}-{year}-{month:02d}.zip"
                            # 使用物理文件夹路径作为folder_key，这样同一文件夹内的文件会被分组
                            folder_key = path
                            
                            if folder_key not in folder_tasks:
                                folder_tasks[folder_key] = []
                            folder_tasks[folder_key].append((path, file_name, None))
                            
                            if include_checksum:
                                checksum_name = f"{symbol.upper()}-{interval}-{year}-{month:02d}.zip.CHECKSUM"
                                folder_tasks[folder_key].append((path, checksum_name, None))
                    elif data_type in ['bookTicker']:
                        # bookTicker 数据不需要间隔，但需要特殊处理
                        path = get_path('um', data_type, 'monthly', symbol)
                        file_name = f"{symbol.upper()}-{data_type}-{year}-{month:02d}.zip"
                        # 使用物理文件夹路径作为folder_key，这样同一文件夹内的文件会被分组
                        folder_key = path
                        
                        if folder_key not in folder_tasks:
                            folder_tasks[folder_key] = []
                        folder_tasks[folder_key].append((path, file_name, None))
                        
                        if include_checksum:
                            checksum_name = f"{symbol.upper()}-{data_type}-{year}-{month:02d}.zip.CHECKSUM"
                            folder_tasks[folder_key].append((path, checksum_name, None))
                    elif data_type in ['depth']:
                        # 深度数据需要特殊处理
                        for interval in ['5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d']:
                            path = get_path('um', data_type, 'monthly', symbol, interval)
                            file_name = f"{symbol.upper()}-{interval}-{year}-{month:02d}.zip"
                            # 使用物理文件夹路径作为folder_key，这样同一文件夹内的文件会被分组
                            folder_key = path
                            
                            if folder_key not in folder_tasks:
                                folder_tasks[folder_key] = []
                            folder_tasks[folder_key].append((path, file_name, None))
                            
                            if include_checksum:
                                checksum_name = f"{symbol.upper()}-{interval}-{year}-{month:02d}.zip.CHECKSUM"
                                folder_tasks[folder_key].append((path, checksum_name, None))
                    else:
                        # trades 和 aggTrades 数据
                        path = get_path('um', data_type, 'monthly', symbol)
                        file_name = f"{symbol.upper()}-{data_type}-{year}-{month:02d}.zip"
                        # 使用物理文件夹路径作为folder_key，这样同一文件夹内的文件会被分组
                        folder_key = path
                        
                        if folder_key not in folder_tasks:
                            folder_tasks[folder_key] = []
                        folder_tasks[folder_key].append((path, file_name, None))
                        
                        if include_checksum:
                            checksum_name = f"{symbol.upper()}-{data_type}-{year}-{month:02d}.zip.CHECKSUM"
                            folder_tasks[folder_key].append((path, checksum_name, None))
        
        # 日度数据
        for date_str in dates:
            if data_type in ['klines', 'indexPriceKlines', 'markPriceKlines', 'premiumIndexKlines']:
                # 需要间隔的数据类型
                for interval in intervals:
                    path = get_path('um', data_type, 'daily', symbol, interval)
                    file_name = f"{symbol.upper()}-{interval}-{date_str}.zip"
                    # 使用物理文件夹路径作为folder_key，这样同一文件夹内的文件会被分组
                    folder_key = path
                    
                    if folder_key not in folder_tasks:
                        folder_tasks[folder_key] = []
                    folder_tasks[folder_key].append((path, file_name, None))
                    
                    if include_checksum:
                        checksum_name = f"{symbol.upper()}-{interval}-{date_str}.zip.CHECKSUM"
                        folder_tasks[folder_key].append((path, checksum_name, None))
            elif data_type in ['bookTicker']:
                # bookTicker 数据不需要间隔
                path = get_path('um', data_type, 'daily', symbol)
                file_name = f"{symbol.upper()}-{data_type}-{date_str}.zip"
                # 使用物理文件夹路径作为folder_key，这样同一文件夹内的文件会被分组
                folder_key = path
                
                if folder_key not in folder_tasks:
                    folder_tasks[folder_key] = []
                folder_tasks[folder_key].append((path, file_name, None))
                
                if include_checksum:
                    checksum_name = f"{symbol.upper()}-{data_type}-{date_str}.zip.CHECKSUM"
                    folder_tasks[folder_key].append((path, checksum_name, None))
            elif data_type in ['depth']:
                # 深度数据需要特殊处理
                for interval in ['5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d']:
                    path = get_path('um', data_type, 'daily', symbol, interval)
                    file_name = f"{symbol.upper()}-{interval}-{date_str}.zip"
                    # 使用物理文件夹路径作为folder_key，这样同一文件夹内的文件会被分组
                    folder_key = path
                    
                    if folder_key not in folder_tasks:
                        folder_tasks[folder_key] = []
                    folder_tasks[folder_key].append((path, file_name, None))
                    
                    if include_checksum:
                        checksum_name = f"{symbol.upper()}-{interval}-{date_str}.zip.CHECKSUM"
                        folder_tasks[folder_key].append((path, checksum_name, None))
            else:
                # trades 和 aggTrades 数据
                path = get_path('um', data_type, 'daily', symbol)
                file_name = f"{symbol.upper()}-{data_type}-{date_str}.zip"
                # 使用物理文件夹路径作为folder_key，这样同一文件夹内的文件会被分组
                folder_key = path
                
                if folder_key not in folder_tasks:
                    folder_tasks[folder_key] = []
                folder_tasks[folder_key].append((path, file_name, None))
                
                if include_checksum:
                    checksum_name = f"{symbol.upper()}-{data_type}-{date_str}.zip.CHECKSUM"
                    folder_tasks[folder_key].append((path, checksum_name, None))
    
    return folder_tasks

def get_file_tasks_for_data_type(
    data_type: str, 
    symbols: List[str], 
    intervals: List[str], 
    years: List[str], 
    months: List[int],
    dates: List[str],
    start_date: str,
    end_date: str,
    include_checksum: bool = False
) -> List[Tuple[str, str, Optional[str]]]:
    """为特定数据类型生成下载任务列表"""
    tasks = []
    
    for symbol in symbols:
        safe_print(f"准备 {symbol} 的 {data_type} 下载任务...")
        
        # 月度数据
        for year in years:
            for month in months:
                current_date = convert_to_date_object(f'{year}-{month:02d}-01')
                start_obj = convert_to_date_object(start_date) if start_date else convert_to_date_object(PERIOD_START_DATE)
                end_obj = convert_to_date_object(end_date) if end_date else date.today()
                
                if start_obj <= current_date <= end_obj:
                    if data_type in ['klines', 'indexPriceKlines', 'markPriceKlines', 'premiumIndexKlines']:
                        # 需要间隔的数据类型
                        for interval in intervals:
                            path = get_path('um', data_type, 'monthly', symbol, interval)
                            file_name = f"{symbol.upper()}-{interval}-{year}-{month:02d}.zip"
                            tasks.append((path, file_name, None))
                            
                            if include_checksum:
                                checksum_name = f"{symbol.upper()}-{interval}-{year}-{month:02d}.zip.CHECKSUM"
                                tasks.append((path, checksum_name, None))
                    elif data_type in ['bookTicker']:
                        # bookTicker 数据不需要间隔，但需要特殊处理
                        path = get_path('um', data_type, 'monthly', symbol)
                        file_name = f"{symbol.upper()}-{data_type}-{year}-{month:02d}.zip"
                        tasks.append((path, file_name, None))
                        
                        if include_checksum:
                            checksum_name = f"{symbol.upper()}-{data_type}-{year}-{month:02d}.zip.CHECKSUM"
                            tasks.append((path, checksum_name, None))
                    elif data_type in ['depth']:
                        # 深度数据需要特殊处理
                        for interval in ['5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d']:
                            path = get_path('um', data_type, 'monthly', symbol, interval)
                            file_name = f"{symbol.upper()}-{interval}-{year}-{month:02d}.zip"
                            tasks.append((path, file_name, None))
                            
                            if include_checksum:
                                checksum_name = f"{symbol.upper()}-{interval}-{year}-{month:02d}.zip.CHECKSUM"
                                tasks.append((path, checksum_name, None))
                    else:
                        # 不需要间隔的数据类型
                        path = get_path('um', data_type, 'monthly', symbol)
                        file_name = f"{symbol.upper()}-{data_type}-{year}-{month:02d}.zip"
                        tasks.append((path, file_name, None))
                        
                        if include_checksum:
                            checksum_name = f"{symbol.upper()}-{data_type}-{year}-{month:02d}.zip.CHECKSUM"
                            tasks.append((path, checksum_name, None))
        
        # 日度数据
        for date_str in dates:
            current_date = convert_to_date_object(date_str)
            start_obj = convert_to_date_object(start_date) if start_date else convert_to_date_object(PERIOD_START_DATE)
            end_obj = convert_to_date_object(end_date) if end_date else date.today()
            
            if start_obj <= current_date <= end_obj:
                if data_type in ['klines', 'indexPriceKlines', 'markPriceKlines', 'premiumIndexKlines']:
                    # 需要间隔的数据类型 - 使用所有传入的intervals
                    for interval in intervals:
                        path = get_path('um', data_type, 'daily', symbol, interval)
                        file_name = f"{symbol.upper()}-{interval}-{date_str}.zip"
                        tasks.append((path, file_name, None))
                        
                        if include_checksum:
                            checksum_name = f"{symbol.upper()}-{interval}-{date_str}.zip.CHECKSUM"
                            tasks.append((path, checksum_name, None))
                elif data_type in ['depth']:
                    # 深度数据需要特殊处理
                    for interval in ['5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d']:
                        path = get_path('um', data_type, 'daily', symbol, interval)
                        file_name = f"{symbol.upper()}-{interval}-{date_str}.zip"
                        tasks.append((path, file_name, None))
                        
                        if include_checksum:
                            checksum_name = f"{symbol.upper()}-{interval}-{date_str}.zip.CHECKSUM"
                            tasks.append((path, checksum_name, None))
                elif data_type in ['bookTicker']:
                    # bookTicker 数据不需要间隔，但需要特殊处理
                    path = get_path('um', data_type, 'daily', symbol)
                    file_name = f"{symbol.upper()}-{data_type}-{date_str}.zip"
                    tasks.append((path, file_name, None))
                    
                    if include_checksum:
                        checksum_name = f"{symbol.upper()}-{data_type}-{date_str}.zip.CHECKSUM"
                        tasks.append((path, checksum_name, None))
                else:
                    # 不需要间隔的数据类型
                    path = get_path('um', data_type, 'daily', symbol)
                    file_name = f"{symbol.upper()}-{data_type}-{date_str}.zip"
                    tasks.append((path, file_name, None))
                    
                    if include_checksum:
                        checksum_name = f"{symbol.upper()}-{data_type}-{date_str}.zip.CHECKSUM"
                        tasks.append((path, checksum_name, None))
    
    return tasks

def scan_existing_files(data_types: List[str], symbols: List[str], intervals: List[str], years: List[str], months: List[int], dates: List[str], start_date: str, end_date: str) -> Dict[str, Dict[str, int]]:
    """扫描已有文件并按数据类型汇总统计"""
    existing_stats = {}
    
    safe_print("\n=== 扫描已有文件 ===")
    
    for data_type in data_types:
        existing_stats[data_type] = {'total': 0, 'existing': 0, 'missing': 0}
        
        # 生成该数据类型的所有文件任务
        folder_tasks = get_file_tasks_by_folder(
            data_type=data_type,
            symbols=symbols,
            intervals=intervals,
            years=years,
            months=months,
            dates=dates,
            start_date=start_date,
            end_date=end_date,
            include_checksum=False
        )
        
        # 统计文件
        for folder_key, tasks in folder_tasks.items():
            for file_path, file_name, date_range in tasks:
                existing_stats[data_type]['total'] += 1
                save_path = get_destination_path(file_path, file_name, date_range)
                
                if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
                    existing_stats[data_type]['existing'] += 1
                else:
                    existing_stats[data_type]['missing'] += 1
        
        # 输出统计信息
        total = existing_stats[data_type]['total']
        existing = existing_stats[data_type]['existing']
        missing = existing_stats[data_type]['missing']
        safe_print(f"{data_type}: 总计 {total} 个文件, 已有 {existing} 个, 缺失 {missing} 个")
    
    safe_print("=== 扫描完成 ===\n")
    return existing_stats

def get_server_folder_files(folder_path: str) -> List[str]:
    """
    获取服务器上指定文件夹的所有文件列表
    通过访问S3 API获取文件列表，处理分页
    """
    all_files = []
    continuation_token = None
    
    while True:
        # 构建S3 API URL
        s3_url = f"https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?delimiter=/&prefix={folder_path}&max-keys=1000"
        if continuation_token:
            s3_url += f"&marker={continuation_token}"
        
        proxies = get_proxies()
        
        try:
            req = urllib.request.Request(s3_url)
            req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
            
            if proxies:
                proxy_handler = urllib.request.ProxyHandler(proxies)
                opener = urllib.request.build_opener(proxy_handler)
                response = opener.open(req, timeout=DOWNLOAD_CONFIG['timeout'])
            else:
                response = urllib.request.urlopen(req, timeout=DOWNLOAD_CONFIG['timeout'])
            
            xml_content = response.read().decode('utf-8')
            
            # 解析XML内容，提取文件链接
            import re
            # 匹配zip文件的正则表达式
            file_pattern = r'<Key>([^<]+\.zip)</Key>'
            files = re.findall(file_pattern, xml_content)
            
            # 只返回文件名，不包含路径
            for file_path in files:
                if file_path.startswith(folder_path):
                    file_name = file_path[len(folder_path):]
                    if file_name:  # 确保不是空字符串
                        all_files.append(file_name)
            
            # 检查是否有更多页面
            # S3 API使用NextMarker而不是NextContinuationToken
            next_marker_pattern = r'<NextMarker>([^<]+)</NextMarker>'
            next_marker_match = re.search(next_marker_pattern, xml_content)
            
            if next_marker_match:
                continuation_token = next_marker_match.group(1)
            else:
                break  # 没有更多页面了
                
        except Exception as e:
            safe_print(f"    警告: 无法获取文件夹 {folder_path} 的文件列表: {e}")
            break
    
    return all_files

def check_server_file_exists(file_path: str, file_name: str) -> bool:
    """
    检查服务器上文件是否存在
    """
    download_url = get_download_url(f"{file_path}{file_name}")
    proxies = get_proxies()
    
    try:
        req = urllib.request.Request(download_url, method='HEAD')
        req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        if proxies:
            proxy_handler = urllib.request.ProxyHandler(proxies)
            opener = urllib.request.build_opener(proxy_handler)
            response = opener.open(req, timeout=5)  # 减少超时时间
        else:
            response = urllib.request.urlopen(req, timeout=5)
        
        return response.status == 200
        
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        else:
            # 其他HTTP错误，假设文件存在，让下载时处理
            return True
    except Exception:
        # 网络错误等，假设文件存在，让下载时处理
        return True

def check_folder_has_data(folder_path: str) -> bool:
    """
    检查文件夹是否有数据，通过尝试访问一个典型的文件来判断
    """
    # 尝试一些典型的文件名模式
    test_files = [
        f"BTCUSDT-1m-2024-01-01.zip",
        f"BTCUSDT-1h-2024-01-01.zip", 
        f"BTCUSDT-1d-2024-01-01.zip"
    ]
    
    for test_file in test_files:
        if check_server_file_exists(folder_path, test_file):
            return True
    
    return False

def get_server_available_files_fast(symbol: str, data_type: str, intervals: List[str]) -> List[Tuple[str, str]]:
    """
    超快速获取服务器上实际可用的文件列表
    直接通过S3 API获取所有文件列表
    """
    available_files = []
    
    # 判断数据类型是否需要间隔
    needs_interval = data_type in ['klines', 'indexPriceKlines', 'markPriceKlines', 'premiumIndexKlines']
    
    if needs_interval:
        # 需要间隔的数据类型：BTCUSDT/1m/ 结构
        for interval in intervals:
            folder_path = f"data/futures/um/daily/{data_type}/{symbol}/{interval}/"
            safe_print(f"    直接获取文件列表: {folder_path}")
            
            # 直接获取文件夹中的所有文件
            server_files = get_server_folder_files(folder_path)
            
            if not server_files:
                safe_print(f"    无文件，跳过")
                continue
            
            # 将文件名转换为完整的文件路径
            for file_name in server_files:
                available_files.append((f"futures/um/daily/{data_type}/{symbol}/{interval}/", file_name))
            
            safe_print(f"    找到 {len(server_files)} 个文件")
    
    else:
        # 不需要间隔的数据类型：BTCUSDT/ 结构
        folder_path = f"data/futures/um/daily/{data_type}/{symbol}/"
        safe_print(f"    直接获取文件列表: {folder_path}")
        
        # 直接获取文件夹中的所有文件
        server_files = get_server_folder_files(folder_path)
        
        if not server_files:
            safe_print(f"    无文件，跳过")
        else:
            # 将文件名转换为完整的文件路径
            for file_name in server_files:
                available_files.append((f"futures/um/daily/{data_type}/{symbol}/", file_name))
            
            safe_print(f"    找到 {len(server_files)} 个文件")
    
    return available_files

def scan_missing_files_for_symbol(
    symbol: str,
    data_types: List[str],
    intervals: List[str],
    years: List[str],
    months: List[int],
    dates: List[str],
    start_date: str,
    end_date: str
) -> Tuple[Dict[str, List[Tuple[str, str, Optional[str]]]], bool]:
    """
    真正的增量写入：扫描服务器上实际存在的文件，立即检查本地缺失的文件并补齐
    返回: (missing_tasks, has_downloaded)
    """
    missing_tasks = {}
    has_downloaded = False
    
    safe_print(f"\n=== 增量写入扫描 {symbol} ===")
    
    for data_type in data_types:
        safe_print(f"扫描 {symbol} 的 {data_type} 数据...")
        
        # 判断数据类型是否需要间隔
        needs_interval = data_type in ['klines', 'indexPriceKlines', 'markPriceKlines', 'premiumIndexKlines']
        
        if needs_interval:
            # 需要间隔的数据类型：BTCUSDT/1m/ 结构
            for interval in intervals:
                folder_path = f"data/futures/um/daily/{data_type}/{symbol}/{interval}/"
                safe_print(f"    直接获取文件列表: {folder_path}")
                
                # 直接获取文件夹中的所有文件
                server_files = get_server_folder_files(folder_path)
                
                if not server_files:
                    safe_print(f"    无文件，跳过")
                    continue
                
                safe_print(f"    找到 {len(server_files)} 个文件")
                
                # 立即检查本地缺失的文件
                missing_files = []
                local_existing = 0
                
                for file_name in server_files:
                    full_file_path = f"futures/um/daily/{data_type}/{symbol}/{interval}/"
                    save_path = get_destination_path(full_file_path, file_name, None)
                    
                    # 检查本地文件是否存在且不为空
                    if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
                        local_existing += 1
                    else:
                        # 本地文件缺失，添加到下载列表
                        folder_key = full_file_path
                        if folder_key not in missing_tasks:
                            missing_tasks[folder_key] = []
                        missing_tasks[folder_key].append((full_file_path, file_name, None))
                        missing_files.append((full_file_path, file_name))
                
                safe_print(f"    本地已有 {local_existing} 个, 缺失 {len(missing_files)} 个")
                
                # 如果有缺失文件，立即下载
                if missing_files:
                    safe_print(f"    立即下载 {len(missing_files)} 个缺失文件...")
                    download_tasks = {full_file_path: missing_tasks[full_file_path]}
                    download_files_by_folder(download_tasks)
                    has_downloaded = True
        
        else:
            # 不需要间隔的数据类型：BTCUSDT/ 结构
            folder_path = f"data/futures/um/daily/{data_type}/{symbol}/"
            safe_print(f"    直接获取文件列表: {folder_path}")
            
            # 直接获取文件夹中的所有文件
            server_files = get_server_folder_files(folder_path)
            
            if not server_files:
                safe_print(f"    无文件，跳过")
            else:
                safe_print(f"    找到 {len(server_files)} 个文件")
                
                # 立即检查本地缺失的文件
                missing_files = []
                local_existing = 0
                
                for file_name in server_files:
                    full_file_path = f"futures/um/daily/{data_type}/{symbol}/"
                    save_path = get_destination_path(full_file_path, file_name, None)
                    
                    # 检查本地文件是否存在且不为空
                    if os.path.exists(save_path) and os.path.getsize(save_path) > 0:
                        local_existing += 1
                    else:
                        # 本地文件缺失，添加到下载列表
                        folder_key = full_file_path
                        if folder_key not in missing_tasks:
                            missing_tasks[folder_key] = []
                        missing_tasks[folder_key].append((full_file_path, file_name, None))
                        missing_files.append((full_file_path, file_name))
                
                safe_print(f"    本地已有 {local_existing} 个, 缺失 {len(missing_files)} 个")
                
                # 如果有缺失文件，立即下载
                if missing_files:
                    safe_print(f"    立即下载 {len(missing_files)} 个缺失文件...")
                    download_tasks = {full_file_path: missing_tasks[full_file_path]}
                    download_files_by_folder(download_tasks)
                    has_downloaded = True
    
    safe_print(f"=== {symbol} 增量扫描完成，共发现 {sum(len(tasks) for tasks in missing_tasks.values())} 个缺失文件 ===\n")
    
    return missing_tasks, has_downloaded

def scan_missing_files_for_all_symbols(
    symbols: List[str],
    data_types: List[str],
    intervals: List[str],
    years: List[str],
    months: List[int],
    dates: List[str],
    start_date: str,
    end_date: str
) -> Dict[str, Dict[str, List[Tuple[str, str, Optional[str]]]]]:
    """
    扫描所有币种的缺失文件
    返回格式: {symbol: {folder_key: [(file_path, file_name, date_range), ...]}}
    """
    all_missing_tasks = {}
    
    safe_print(f"\n{'='*60}")
    safe_print("开始扫描所有币种的缺失文件")
    safe_print(f"{'='*60}")
    
    for symbol in symbols:
        if symbol not in all_missing_tasks:
            all_missing_tasks[symbol] = {}
        
        # 扫描当前币种的缺失文件
        symbol_missing_tasks, has_downloaded = scan_missing_files_for_symbol(
            symbol=symbol,
            data_types=data_types,
            intervals=intervals,
            years=years,
            months=months,
            dates=dates,
            start_date=start_date,
            end_date=end_date
        )
        
        all_missing_tasks[symbol] = symbol_missing_tasks
    
    # 输出总体统计
    total_missing = sum(
        sum(len(tasks) for tasks in symbol_tasks.values())
        for symbol_tasks in all_missing_tasks.values()
    )
    
    safe_print("\n=== 扫描完成 - 总体统计 ===")
    safe_print(f"扫描币种数量: {len(symbols)}")
    safe_print(f"总缺失文件数: {total_missing}")
    
    for symbol in symbols:
        symbol_missing = sum(len(tasks) for tasks in all_missing_tasks[symbol].values())
        safe_print(f"  {symbol}: 缺失 {symbol_missing} 个文件")
    
    safe_print("=" * 40)
    
    return all_missing_tasks

def download_missing_files_only(
    all_missing_tasks: Dict[str, Dict[str, List[Tuple[str, str, Optional[str]]]]],
    shutdown_event=None
) -> Dict[str, int]:
    """
    只下载缺失的文件
    输入格式: {symbol: {folder_key: [(file_path, file_name, date_range), ...]}}
    """
    results = {'success': 0, 'failed': 0, 'skipped': 0}
    
    safe_print(f"\n{'='*60}")
    safe_print("开始下载缺失文件")
    safe_print(f"{'='*60}")
    
    # 按币种处理
    for symbol, symbol_tasks in all_missing_tasks.items():
        if shutdown_event and shutdown_event.is_set():
            safe_print(f"\n检测到退出信号，停止处理币种: {symbol}")
            break
        
        if not symbol_tasks:
            safe_print(f"{symbol}: 没有缺失文件，跳过")
            continue
        
        safe_print(f"\n--- 处理币种: {symbol} ---")
        
        # 计算该币种的总缺失文件数
        total_missing = sum(len(tasks) for tasks in symbol_tasks.values())
        safe_print(f"{symbol}: 需要下载 {total_missing} 个缺失文件")
        
        # 下载该币种的所有缺失文件
        symbol_results = download_files_by_folder(symbol_tasks, shutdown_event)
        
        # 累加结果
        for key in results:
            results[key] += symbol_results[key]
        
        # 输出该币种的完成信息
        safe_print(f"{symbol} [完成] 成功: {symbol_results['success']}, 失败: {symbol_results['failed']}, 跳过: {symbol_results['skipped']}")
    
    # 输出最终统计
    safe_print("\n=== 缺失文件下载完成 ===")
    safe_print(f"成功下载: {results['success']} 个文件")
    safe_print(f"下载失败: {results['failed']} 个文件")
    safe_print(f"跳过文件: {results['skipped']} 个文件")
    safe_print("=" * 40)
    
    return results

def print_download_summary(results: Dict[str, int], data_type: str):
    """打印下载摘要"""
    total = results['success'] + results['failed'] + results['skipped']
    safe_print(f"\n=== {data_type} 下载摘要 ===")
    safe_print(f"总计: {total}")
    safe_print(f"成功: {results['success']}")
    safe_print(f"失败: {results['failed']}")
    safe_print(f"跳过: {results['skipped']}")
    safe_print("=" * 30)
