#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
配置文件 - 包含下载设置、代理配置、并发参数等
"""

import os
from typing import Dict

# 代理配置
PROXY_CONFIG = {
    'enabled': True,  # 是否启用代理
    'http': 'http://127.0.0.1:7897',
    'https': 'http://127.0.0.1:7897'
}

# 下载配置
DOWNLOAD_CONFIG = {
    'max_workers': 16,  # 最大并发线程数
    'max_retries': 3,   # 最大重试次数
    'retry_delay': 1,   # 重试延迟（秒）
    'timeout': 30,      # 请求超时时间（秒）
    'chunk_size': 8192, # 下载块大小
}

# 数据存储配置
STORAGE_CONFIG = {
    'base_dir': 'data',  # 数据存储基础目录
}

# USD-M Futures 数据类型
UM_FUTURES_DATA_TYPES = [
    # 'aggTrades',
    # 'bookTicker',
    # 'trades',
    'bookDepth',
    'indexPriceKlines',
    'klines',
    'markPriceKlines',
    'premiumIndexKlines',
    'metrics'
]

# 主流币对列表 - 仅包含BTC和ETH
MAJOR_SYMBOLS = [
    'BTCUSDT', 'ETHUSDT'
]

# 支持的时间间隔
INTERVALS = ["1s", "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w"]



# 基础URL
BASE_URL = 'https://data.binance.vision/data/'

# 支持的年份 - 从2020年开始（U本位合约开始时间）
YEARS = [ '2020', '2021', '2022', '2023', '2024', '2025']

# 月份
MONTHS = list(range(1, 13))

# 开始日期 - U本位合约从2020年1月开始
PERIOD_START_DATE = '2020-01-01'

# 获取代理配置
def get_proxies() -> Dict[str, str]:
    """获取代理配置"""
    if PROXY_CONFIG['enabled']:
        return {
            'http': PROXY_CONFIG['http'],
            'https': PROXY_CONFIG['https']
        }
    return None

# 获取存储目录
def get_storage_dir() -> str:
    """获取数据存储目录"""
    base_dir = STORAGE_CONFIG['base_dir']
    if not os.path.exists(base_dir):
        os.makedirs(base_dir, exist_ok=True)
    return base_dir

# 打印配置信息
def print_config():
    """打印当前配置"""
    # 导入safe_print函数
    try:
        from enhanced_utility import safe_print
        safe_print("=== 下载配置 ===")
        safe_print(f"代理状态: {'启用' if PROXY_CONFIG['enabled'] else '禁用'}")
        if PROXY_CONFIG['enabled']:
            safe_print(f"代理地址: {PROXY_CONFIG['http']}")
        safe_print(f"最大并发数: {DOWNLOAD_CONFIG['max_workers']}")
        safe_print(f"最大重试次数: {DOWNLOAD_CONFIG['max_retries']}")
        safe_print(f"存储目录: {get_storage_dir()}")
        safe_print(f"数据类型: {', '.join(UM_FUTURES_DATA_TYPES)}")
        safe_print("================")
    except ImportError:
        # 如果无法导入safe_print，使用普通print但设置编码
        import sys
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        print("=== 下载配置 ===")
        print(f"代理状态: {'启用' if PROXY_CONFIG['enabled'] else '禁用'}")
        if PROXY_CONFIG['enabled']:
            print(f"代理地址: {PROXY_CONFIG['http']}")
        print(f"最大并发数: {DOWNLOAD_CONFIG['max_workers']}")
        print(f"最大重试次数: {DOWNLOAD_CONFIG['max_retries']}")
        print(f"存储目录: {get_storage_dir()}")
        print(f"数据类型: {', '.join(UM_FUTURES_DATA_TYPES)}")
        print("================")
