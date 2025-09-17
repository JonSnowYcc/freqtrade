#!/usr/bin/env python3
"""
代理连接测试工具
用于测试OKX API的网络连接和代理设置
"""

import requests
import json
import time
from pathlib import Path

def test_direct_connection():
    """测试直接连接"""
    print("测试直接连接到OKX API...")
    try:
        url = "https://www.okx.com/api/v5/public/time"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 直接连接成功: {data}")
            return True
        else:
            print(f"❌ 直接连接失败: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ 直接连接失败: {e}")
        return False

def test_proxy_connection():
    """测试代理连接"""
    print("\n测试代理连接到OKX API...")
    
    # 读取配置文件中的代理设置
    current_dir = Path(__file__).parent
    config_path = current_dir.parent.parent / "user_data" / "config.json"
    
    if not config_path.exists():
        print("❌ 配置文件不存在")
        return False
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        exchange_config = config.get('exchange', {}).get('ccxt_config', {})
        proxies = exchange_config.get('proxies', {})
        
        if not proxies:
            print("❌ 配置文件中没有代理设置")
            return False
        
        print(f"使用代理: {proxies}")
        
        # 测试代理连接
        url = "https://www.okx.com/api/v5/public/time"
        response = requests.get(url, proxies=proxies, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 代理连接成功: {data}")
            return True
        else:
            print(f"❌ 代理连接失败: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ 代理连接失败: {e}")
        return False

def test_ccxt_connection():
    """测试CCXT连接"""
    print("\n测试CCXT库连接...")
    try:
        import ccxt
        
        # 读取配置文件
        current_dir = Path(__file__).parent
        config_path = current_dir.parent.parent / "user_data" / "config.json"
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        exchange_config = config.get('exchange', {}).get('ccxt_config', {})
        
        # 创建交易所实例
        okx_config = {
            'sandbox': False,
            'enableRateLimit': True,
        }
        
        if 'proxies' in exchange_config:
            okx_config['proxies'] = exchange_config['proxies']
            print(f"使用代理: {exchange_config['proxies']}")
        
        exchange = ccxt.okx(okx_config)
        
        # 测试获取市场信息
        markets = exchange.load_markets()
        print(f"✅ CCXT连接成功，获取到 {len(markets)} 个市场")
        
        # 测试获取K线数据
        ohlcv = exchange.fetch_ohlcv('BTC/USDT', '1m', limit=1)
        if ohlcv:
            print(f"✅ K线数据获取成功: {len(ohlcv)} 条记录")
            return True
        else:
            print("❌ K线数据获取失败")
            return False
            
    except Exception as e:
        print(f"❌ CCXT连接失败: {e}")
        return False

def test_proxy_server():
    """测试代理服务器是否可用"""
    print("\n测试代理服务器连接...")
    
    current_dir = Path(__file__).parent
    config_path = current_dir.parent.parent / "user_data" / "config.json"
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        exchange_config = config.get('exchange', {}).get('ccxt_config', {})
        proxies = exchange_config.get('proxies', {})
        
        if not proxies:
            print("❌ 没有代理配置")
            return False
        
        # 提取代理地址
        proxy_url = proxies.get('https', proxies.get('http', ''))
        if not proxy_url:
            print("❌ 无法解析代理地址")
            return False
        
        print(f"测试代理服务器: {proxy_url}")
        
        # 测试代理服务器
        test_proxies = {'https': proxy_url, 'http': proxy_url}
        response = requests.get('https://httpbin.org/ip', proxies=test_proxies, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 代理服务器可用，IP: {data.get('origin', 'Unknown')}")
            return True
        else:
            print(f"❌ 代理服务器测试失败: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ 代理服务器测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("=" * 60)
    print("OKX网络连接诊断工具")
    print("=" * 60)
    
    tests = [
        ("直接连接测试", test_direct_connection),
        ("代理服务器测试", test_proxy_server),
        ("代理连接测试", test_proxy_connection),
        ("CCXT连接测试", test_ccxt_connection),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ 测试异常: {e}")
            results.append((test_name, False))
        
        time.sleep(1)  # 避免请求过于频繁
    
    # 总结
    print("\n" + "=" * 60)
    print("测试结果总结")
    print("=" * 60)
    
    passed = 0
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n总体结果: {passed}/{len(results)} 测试通过")
    
    if passed == len(results):
        print("🎉 所有测试通过！网络连接正常")
    elif passed >= 2:
        print("⚠️ 部分测试通过，可以尝试使用代理")
    else:
        print("❌ 大部分测试失败，请检查网络和代理设置")
        print("\n💡 建议:")
        print("1. 检查代理服务器是否运行")
        print("2. 确认代理端口和协议设置正确")
        print("3. 检查防火墙设置")
        print("4. 尝试更换代理服务器")

if __name__ == "__main__":
    main()
