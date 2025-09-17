#!/usr/bin/env python3
"""
OKX数据下载器测试脚本
用于测试下载器的基本功能
"""

import sys
import os
from pathlib import Path

# 添加freqtrade路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

def test_imports():
    """测试导入"""
    try:
        import pandas as pd
        import ccxt
        from freqtrade.exchange import Exchange
        from freqtrade.configuration.configuration import Configuration
        print("✅ 所有依赖导入成功")
        return True
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        return False

def test_config_file():
    """测试配置文件"""
    # 从当前目录向上查找配置文件
    current_dir = Path(__file__).parent
    config_path = current_dir.parent.parent / "user_data" / "config.json"
    
    if config_path.exists():
        print("✅ 配置文件存在")
        return True
    else:
        print("❌ 配置文件不存在，请先配置API密钥")
        return False

def test_data_directory():
    """测试数据目录"""
    current_dir = Path(__file__).parent
    data_dir = current_dir.parent.parent / "user_data" / "data"
    if data_dir.exists():
        print("✅ 数据目录存在")
        return True
    else:
        print("⚠️ 数据目录不存在，将在首次运行时创建")
        return True

def test_okx_connection():
    """测试OKX连接"""
    try:
        import ccxt
        import json
        
        # 读取配置文件获取代理设置
        current_dir = Path(__file__).parent
        config_path = current_dir.parent.parent / "user_data" / "config.json"
        
        proxy_config = {}
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                exchange_config = config.get('exchange', {}).get('ccxt_config', {})
                if 'proxies' in exchange_config:
                    proxy_config = exchange_config['proxies']
                    print(f"使用代理设置: {proxy_config}")
        
        # 创建OKX交易所实例（不需要API密钥进行基本连接测试）
        exchange_config = {
            'sandbox': False,
            'enableRateLimit': True,
        }
        
        # 添加代理配置
        if proxy_config:
            exchange_config['proxies'] = proxy_config
        
        exchange = ccxt.okx(exchange_config)
        
        # 测试获取市场信息
        markets = exchange.load_markets()
        print(f"✅ OKX连接成功，获取到 {len(markets)} 个市场")
        return True
        
    except Exception as e:
        print(f"❌ OKX连接失败: {e}")
        print("💡 提示: 可能需要检查代理设置或网络连接")
        return False

def main():
    """主测试函数"""
    print("=" * 50)
    print("OKX数据下载器测试")
    print("=" * 50)
    
    tests = [
        ("依赖导入", test_imports),
        ("配置文件", test_config_file),
        ("数据目录", test_data_directory),
        ("OKX连接", test_okx_connection),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n测试: {test_name}")
        print("-" * 20)
        if test_func():
            passed += 1
    
    print("\n" + "=" * 50)
    print(f"测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！可以开始使用下载器")
    else:
        print("⚠️ 部分测试失败，请检查配置")
    
    print("=" * 50)

if __name__ == "__main__":
    main()
