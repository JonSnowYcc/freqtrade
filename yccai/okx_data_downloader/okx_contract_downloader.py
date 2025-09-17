#!/usr/bin/env python3
"""
OKX合约数据下载器
专门下载2025年1月1日后的所有合约币种分钟级数据
支持断点续传和智能频率控制
"""

import ccxt
import pandas as pd
import time
import json
import os
from pathlib import Path
from datetime import datetime, timedelta
import threading
from typing import Dict, List, Optional

class OKXContractDownloader:
    def __init__(self):
        self.exchange = None
        self.data_dir = Path("../../user_data/data/okx")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.progress_file = Path("download_progress.json")
        self.config_file = Path("../../user_data/config.json")
        
        # 频率控制参数（经过测试优化）
        self.min_delay = 0.05  # 最小延迟50ms
        self.max_delay = 1.0   # 最大延迟1秒
        self.current_delay = 0.1  # 当前延迟100ms
        self.rate_limit_window = 60  # 频率限制窗口60秒
        self.max_requests_per_window = 100  # 每窗口最大请求数（提高）
        self.request_times = []  # 请求时间记录
        
        # 断点续传
        self.progress = self.load_progress()
        
        # 初始化交易所
        self.init_exchange()
        
    def init_exchange(self):
        """初始化OKX交易所"""
        try:
            # 读取配置
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            exchange_config = config['exchange']
            
            # 创建OKX配置
            okx_config = {
                'apiKey': exchange_config['key'],
                'secret': exchange_config['secret'],
                'password': exchange_config.get('password', ''),
                'sandbox': False,
                'enableRateLimit': True,
                'rateLimit': 200,  # 200ms基础延迟
                'timeout': 30000,
            }
            
            # 添加代理配置（如果可用）
            if 'ccxt_config' in exchange_config and 'proxies' in exchange_config['ccxt_config']:
                test_proxies = exchange_config['ccxt_config']['proxies']
                print(f"🔧 尝试使用代理: {test_proxies}")
                okx_config['proxies'] = test_proxies
            
            self.exchange = ccxt.okx(okx_config)
            print("✅ OKX交易所初始化成功")
            
        except Exception as e:
            print(f"❌ 交易所初始化失败: {e}")
            raise
    
    def load_progress(self) -> Dict:
        """加载下载进度"""
        if self.progress_file.exists():
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return {
            'completed_pairs': [],
            'failed_pairs': [],
            'last_update': None,
            'total_pairs': 0
        }
    
    def save_progress(self):
        """保存下载进度"""
        self.progress['last_update'] = datetime.now().isoformat()
        with open(self.progress_file, 'w', encoding='utf-8') as f:
            json.dump(self.progress, f, indent=2, ensure_ascii=False)
    
    def rate_limit_control(self):
        """智能频率控制"""
        now = time.time()
        
        # 清理过期的时间记录
        self.request_times = [t for t in self.request_times if now - t < self.rate_limit_window]
        
        # 如果请求过于频繁，增加延迟
        if len(self.request_times) >= self.max_requests_per_window:
            self.current_delay = min(self.current_delay * 1.5, self.max_delay)
            print(f"⚠️ 请求过于频繁，延迟增加到 {self.current_delay:.2f}s")
        else:
            # 逐渐减少延迟
            self.current_delay = max(self.current_delay * 0.95, self.min_delay)
        
        # 记录当前请求时间
        self.request_times.append(now)
        
        # 应用延迟
        time.sleep(self.current_delay)
    
    def get_contract_pairs(self) -> List[str]:
        """获取所有合约交易对"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"🔄 尝试获取交易对列表 (第 {attempt + 1}/{max_retries} 次)...")
                
                # 先测试基本连接
                self.exchange.fetch_time()
                print("✅ 时间API连接成功")
                
                # 获取市场信息
                markets = self.exchange.load_markets()
                contract_pairs = []
                
                for symbol, market in markets.items():
                    # 只获取USDT合约交易对
                    if (market['quote'] == 'USDT' and 
                        market['active'] and 
                        market['type'] == 'spot' and  # OKX的现货交易对
                        not any(x in symbol.upper() for x in ['3L', '3S', '5L', '5S', 'BEAR', 'BULL'])):  # 排除杠杆代币
                        contract_pairs.append(symbol)
                
                print(f"✅ 找到 {len(contract_pairs)} 个合约交易对")
                return sorted(contract_pairs)
                
            except Exception as e:
                print(f"❌ 第 {attempt + 1} 次尝试失败: {e}")
                if attempt < max_retries - 1:
                    print(f"⏳ 等待 5 秒后重试...")
                    time.sleep(5)
                else:
                    print("❌ 所有尝试都失败了")
                    return []
    
    def download_pair_data(self, pair: str, start_date: datetime = None) -> bool:
        """下载单个交易对的数据"""
        if start_date is None:
            start_date = datetime(2025, 1, 1)  # 2025年1月1日
        
        try:
            print(f"📥 下载 {pair} 数据...")
            
            # 检查是否已完成
            if pair in self.progress['completed_pairs']:
                print(f"⏭️ {pair} 已完成，跳过")
                return True
            
            # 检查文件是否存在
            filename = f"{pair.replace('/', '_')}-1m.feather"
            filepath = self.data_dir / filename
            
            # 如果文件存在，检查是否需要更新
            if filepath.exists():
                try:
                    df_existing = pd.read_feather(filepath)
                    if len(df_existing) > 0:
                        first_date = pd.to_datetime(df_existing.index[0])
                        last_date = pd.to_datetime(df_existing.index[-1])
                        
                        # 检查是否从2025年1月1日开始，并且数据量足够
                        expected_days = (datetime.now() - datetime(2025, 1, 1)).days
                        actual_days = (last_date.date() - first_date.date()).days
                        
                        if (first_date.date() <= datetime(2025, 1, 2).date() and 
                            last_date.date() >= datetime.now().date() - timedelta(days=1) and
                            actual_days >= expected_days * 0.8):  # 至少80%的数据
                            print(f"✅ {pair} 数据已是最新 ({len(df_existing)} 条记录)")
                            self.progress['completed_pairs'].append(pair)
                            self.save_progress()
                            return True
                        else:
                            print(f"🔄 {pair} 数据不完整，重新下载")
                except:
                    pass
            
            # 开始下载
            since = int(start_date.timestamp() * 1000)
            all_data = []
            current_since = since
            batch_count = 0
            
            print(f"  📅 下载时间范围: {start_date.strftime('%Y-%m-%d')} 到 {datetime.now().strftime('%Y-%m-%d')}")
            
            while current_since < int(datetime.now().timestamp() * 1000):
                try:
                    # 应用频率控制
                    self.rate_limit_control()
                    
                    # 获取数据（OKX限制每次最多300条）
                    ohlcv = self.exchange.fetch_ohlcv(
                        pair, 
                        '1m', 
                        since=current_since, 
                        limit=300
                    )
                    
                    if not ohlcv:
                        break
                    
                    all_data.extend(ohlcv)
                    batch_count += 1
                    
                    # 更新下次请求的起始时间
                    current_since = ohlcv[-1][0] + 1
                    
                    print(f"  📊 批次 {batch_count}: {len(ohlcv)} 条记录")
                    
                    # 如果返回的数据少于300条，说明已经到最新
                    if len(ohlcv) < 300:
                        break
                        
                except ccxt.RateLimitExceeded:
                    print(f"  ⚠️ API限制，等待5秒...")
                    time.sleep(5)
                    continue
                except Exception as e:
                    print(f"  ❌ 批次 {batch_count + 1} 失败: {e}")
                    time.sleep(2)
                    break
            
            if not all_data:
                print(f"❌ {pair} 没有数据")
                self.progress['failed_pairs'].append(pair)
                self.save_progress()
                return False
            
            # 转换为DataFrame
            df = pd.DataFrame(all_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
            df = df.drop('timestamp', axis=1)
            df = df.set_index('date')
            
            # 去重并排序
            df = df[~df.index.duplicated(keep='first')].sort_index()
            
            # 保存数据
            df.to_feather(filepath)
            
            print(f"✅ {pair} 下载完成: {len(df)} 条记录, {filepath.stat().st_size / 1024:.1f} KB")
            print(f"  📅 时间范围: {df.index.min()} 到 {df.index.max()}")
            
            # 更新进度
            self.progress['completed_pairs'].append(pair)
            self.save_progress()
            
            return True
            
        except Exception as e:
            print(f"❌ {pair} 下载失败: {e}")
            self.progress['failed_pairs'].append(pair)
            self.save_progress()
            return False
    
    def download_all_contracts(self):
        """下载所有合约数据"""
        print("🚀 开始下载OKX合约数据 (2025年1月1日后)")
        print("=" * 60)
        
        # 获取所有合约交易对
        all_pairs = self.get_contract_pairs()
        if not all_pairs:
            print("❌ 没有找到合约交易对")
            return
        
        self.progress['total_pairs'] = len(all_pairs)
        
        # 过滤已完成的交易对
        remaining_pairs = [p for p in all_pairs if p not in self.progress['completed_pairs']]
        
        print(f"📊 总交易对: {len(all_pairs)}")
        print(f"✅ 已完成: {len(self.progress['completed_pairs'])}")
        print(f"📥 待下载: {len(remaining_pairs)}")
        print(f"❌ 失败: {len(self.progress['failed_pairs'])}")
        
        if not remaining_pairs:
            print("🎉 所有数据已下载完成！")
            return
        
        # 开始下载
        success_count = 0
        start_time = time.time()
        
        for i, pair in enumerate(remaining_pairs, 1):
            print(f"\n📈 进度: {i}/{len(remaining_pairs)} ({i/len(remaining_pairs)*100:.1f}%)")
            
            if self.download_pair_data(pair):
                success_count += 1
            
            # 每10个交易对显示一次统计
            if i % 10 == 0:
                elapsed = time.time() - start_time
                avg_time = elapsed / i
                remaining_time = avg_time * (len(remaining_pairs) - i)
                print(f"⏱️ 已用时: {elapsed/60:.1f}分钟, 预计剩余: {remaining_time/60:.1f}分钟")
        
        # 最终统计
        total_time = time.time() - start_time
        print(f"\n🎉 下载完成！")
        print(f"⏱️ 总用时: {total_time/60:.1f}分钟")
        print(f"✅ 成功: {success_count} 个交易对")
        print(f"❌ 失败: {len(remaining_pairs) - success_count} 个交易对")
        
        # 显示失败列表
        failed_this_round = [p for p in remaining_pairs if p in self.progress['failed_pairs']]
        if failed_this_round:
            print(f"\n❌ 本次失败的交易对:")
            for pair in failed_this_round[:10]:  # 只显示前10个
                print(f"  - {pair}")
            if len(failed_this_round) > 10:
                print(f"  ... 还有 {len(failed_this_round) - 10} 个")
    
    def retry_failed_pairs(self):
        """重试失败的交易对"""
        if not self.progress['failed_pairs']:
            print("✅ 没有失败的交易对需要重试")
            return
        
        print(f"🔄 重试 {len(self.progress['failed_pairs'])} 个失败的交易对")
        
        # 清空失败列表，重新尝试
        failed_pairs = self.progress['failed_pairs'].copy()
        self.progress['failed_pairs'] = []
        self.save_progress()
        
        for pair in failed_pairs:
            print(f"\n🔄 重试 {pair}")
            self.download_pair_data(pair)
    
    def check_data_status(self):
        """检查数据状态"""
        print("📊 数据状态检查")
        print("=" * 40)
        
        if not self.data_dir.exists():
            print("❌ 数据目录不存在")
            return
        
        # 统计文件
        feather_files = list(self.data_dir.glob("*-1m.feather"))
        print(f"📁 数据文件: {len(feather_files)} 个")
        
        # 按交易对分组
        pairs = {}
        total_size = 0
        
        for file in feather_files:
            name = file.stem
            if '-1m' in name:
                pair = name.replace('-1m', '').replace('_', '/')
                pairs[pair] = file.stat().st_size
                total_size += file.stat().st_size
        
        print(f"💰 交易对数量: {len(pairs)} 个")
        print(f"💾 总数据大小: {total_size / (1024*1024):.1f} MB")
        
        # 显示前10个交易对
        print(f"\n📈 前10个交易对:")
        for i, (pair, size) in enumerate(sorted(pairs.items())[:10]):
            print(f"  {pair}: {size/1024:.1f} KB")
        
        # 进度统计
        print(f"\n📊 下载进度:")
        print(f"  总交易对: {self.progress.get('total_pairs', 0)}")
        print(f"  已完成: {len(self.progress.get('completed_pairs', []))}")
        print(f"  失败: {len(self.progress.get('failed_pairs', []))}")
        
        if self.progress.get('last_update'):
            print(f"  最后更新: {self.progress['last_update']}")

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='OKX合约数据下载器')
    parser.add_argument('--retry', action='store_true', help='重试失败的交易对')
    parser.add_argument('--status', action='store_true', help='检查数据状态')
    parser.add_argument('--pair', type=str, help='下载指定交易对')
    
    args = parser.parse_args()
    
    try:
        downloader = OKXContractDownloader()
        
        if args.status:
            downloader.check_data_status()
        elif args.retry:
            downloader.retry_failed_pairs()
        elif args.pair:
            downloader.download_pair_data(args.pair)
        else:
            downloader.download_all_contracts()
            
    except KeyboardInterrupt:
        print("\n⏹️ 用户中断下载")
        print("💡 下次运行将自动从断点继续")
    except Exception as e:
        print(f"❌ 程序出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
