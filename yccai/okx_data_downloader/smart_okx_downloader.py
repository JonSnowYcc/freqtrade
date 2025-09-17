#!/usr/bin/env python3
"""
智能OKX数据下载器
专门规避OKX API限制，使用保守的频率控制
"""

import subprocess
import sys
import time
import json
from pathlib import Path
from datetime import datetime, timedelta
import threading

class SmartOKXDownloader:
    def __init__(self):
        self.data_dir = Path("../../user_data/data/okx")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.progress_file = Path("smart_download_progress.json")
        self.config_file = Path("../../user_data/config.json").resolve()
        
        # 保守的频率控制参数
        self.min_delay = 2.0  # 最小延迟2秒
        self.max_delay = 10.0  # 最大延迟10秒
        self.current_delay = 3.0  # 当前延迟3秒
        self.rate_limit_window = 60  # 频率限制窗口60秒
        self.max_requests_per_window = 10  # 每窗口最大请求数（非常保守）
        self.request_times = []  # 请求时间记录
        
        # 断点续传
        self.progress = self.load_progress()
        
    def load_progress(self):
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
    
    def smart_rate_limit(self):
        """智能频率控制"""
        now = time.time()
        
        # 清理过期的时间记录
        self.request_times = [t for t in self.request_times if now - t < self.rate_limit_window]
        
        # 如果请求过于频繁，大幅增加延迟
        if len(self.request_times) >= self.max_requests_per_window:
            self.current_delay = min(self.current_delay * 2, self.max_delay)
            print(f"⚠️ 请求过于频繁，延迟增加到 {self.current_delay:.1f}s")
        else:
            # 逐渐减少延迟
            self.current_delay = max(self.current_delay * 0.9, self.min_delay)
        
        # 记录当前请求时间
        self.request_times.append(now)
        
        # 应用延迟
        print(f"⏳ 等待 {self.current_delay:.1f}s 避免API限制...")
        time.sleep(self.current_delay)
    
    def run_freqtrade_command(self, cmd, description):
        """运行freqtrade命令"""
        print(f"\n{'='*20} {description} {'='*20}")
        print(f"执行命令: {' '.join(cmd)}")
        
        # 应用智能频率控制
        self.smart_rate_limit()
        
        start_time = time.time()
        
        try:
            result = subprocess.run(
                cmd,
                cwd=Path(__file__).parent.parent.parent,
                text=True,
                encoding='utf-8'
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            if result.returncode == 0:
                print(f"✅ {description} 完成 (耗时: {duration:.1f}秒)")
                return True
            else:
                print(f"❌ {description} 失败 (耗时: {duration:.1f}秒)")
                return False
                
        except Exception as e:
            print(f"❌ {description} 异常: {e}")
            return False
    
    def get_all_pairs(self):
        """获取所有USDT交易对"""
        try:
            cmd = [
                'python', '-m', 'freqtrade', 'list-pairs',
                '--exchange', 'okx',
                '--pairs', '.*/USDT',
                '--config', str(self.config_file)
            ]
            
            result = subprocess.run(
                cmd,
                cwd=Path(__file__).parent.parent.parent,
                capture_output=True,
                text=True,
                encoding='utf-8'
            )
            
            if result.returncode == 0:
                pairs = []
                for line in result.stdout.split('\n'):
                    line = line.strip()
                    if line and '/' in line and 'USDT' in line:
                        pairs.append(line)
                
                print(f"✅ 找到 {len(pairs)} 个USDT交易对")
                return pairs
            else:
                print(f"❌ 获取交易对失败: {result.stderr}")
                return []
                
        except Exception as e:
            print(f"❌ 获取交易对时出错: {e}")
            return []
    
    def download_single_pair(self, pair):
        """下载单个交易对"""
        try:
            print(f"\n📥 下载 {pair} 数据...")
            
            # 检查是否已完成
            if pair in self.progress['completed_pairs']:
                print(f"⏭️ {pair} 已完成，跳过")
                return True
            
            cmd = [
                'python', '-m', 'freqtrade', 'download-data',
                '--exchange', 'okx',
                '--pairs', pair,
                '--timeframes', '1m',
                '--timerange', '20250101-',  # 从2025年1月1日到现在
                '--config', str(self.config_file)
            ]
            
            success = self.run_freqtrade_command(cmd, f"下载 {pair}")
            
            if success:
                self.progress['completed_pairs'].append(pair)
                self.save_progress()
                return True
            else:
                self.progress['failed_pairs'].append(pair)
                self.save_progress()
                return False
                
        except Exception as e:
            print(f"❌ {pair} 下载失败: {e}")
            self.progress['failed_pairs'].append(pair)
            self.save_progress()
            return False
    
    def download_batch_pairs(self, pairs, batch_size=1):
        """批量下载交易对（每批1个，避免API限制）"""
        print(f"📦 批量下载 {len(pairs)} 个交易对")
        print(f"🔧 批次大小: {batch_size} (保守设置)")
        
        success_count = 0
        failed_pairs = []
        
        for i in range(0, len(pairs), batch_size):
            batch_pairs = pairs[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(pairs) + batch_size - 1) // batch_size
            
            print(f"\n{'='*10} 第 {batch_num}/{total_batches} 批 {'='*10}")
            
            for pair in batch_pairs:
                if self.download_single_pair(pair):
                    success_count += 1
                else:
                    failed_pairs.append(pair)
            
            # 批次间额外休息
            if batch_num < total_batches:
                print(f"⏳ 批次 {batch_num} 完成，额外休息 30 秒...")
                time.sleep(30)
        
        print(f"\n📊 批量下载完成!")
        print(f"✅ 成功: {success_count} 个交易对")
        print(f"❌ 失败: {len(failed_pairs)} 个交易对")
        
        if failed_pairs:
            print(f"❌ 失败的交易对: {failed_pairs[:10]}...")  # 只显示前10个
        
        return success_count, failed_pairs
    
    def download_all_contracts(self):
        """下载所有合约数据"""
        print("🚀 开始智能下载OKX合约数据 (2025年1月1日后)")
        print("=" * 60)
        print("⚠️ 使用保守的频率控制，避免API限制")
        
        # 获取所有交易对
        all_pairs = self.get_all_pairs()
        if not all_pairs:
            print("❌ 没有找到交易对")
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
        
        # 开始下载（每批1个交易对，最保守）
        start_time = time.time()
        success_count, failed_pairs = self.download_batch_pairs(remaining_pairs, batch_size=1)
        
        # 最终统计
        total_time = time.time() - start_time
        print(f"\n🎉 下载完成！")
        print(f"⏱️ 总用时: {total_time/60:.1f}分钟")
        print(f"✅ 成功: {success_count} 个交易对")
        print(f"❌ 失败: {len(failed_pairs)} 个交易对")
        
        # 显示失败列表
        if failed_pairs:
            print(f"\n❌ 失败的交易对:")
            for pair in failed_pairs[:10]:  # 只显示前10个
                print(f"  - {pair}")
            if len(failed_pairs) > 10:
                print(f"  ... 还有 {len(failed_pairs) - 10} 个")
    
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
            self.download_single_pair(pair)
    
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
    
    parser = argparse.ArgumentParser(description='智能OKX合约数据下载器')
    parser.add_argument('--retry', action='store_true', help='重试失败的交易对')
    parser.add_argument('--status', action='store_true', help='检查数据状态')
    parser.add_argument('--pair', type=str, help='下载指定交易对')
    parser.add_argument('--all', action='store_true', help='下载所有交易对')
    
    args = parser.parse_args()
    
    try:
        downloader = SmartOKXDownloader()
        
        if args.status:
            downloader.check_data_status()
        elif args.retry:
            downloader.retry_failed_pairs()
        elif args.pair:
            downloader.download_single_pair(args.pair)
        elif args.all:
            downloader.download_all_contracts()
        else:
            print("请指定操作:")
            print("  --pair BTC/USDT    下载指定交易对")
            print("  --all              下载所有交易对")
            print("  --retry            重试失败的交易对")
            print("  --status           检查数据状态")
            print("\n推荐:")
            print("  python smart_okx_downloader.py --all")
            
    except KeyboardInterrupt:
        print("\n⏹️ 用户中断下载")
        print("💡 下次运行将自动从断点继续")
    except Exception as e:
        print(f"❌ 程序出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
