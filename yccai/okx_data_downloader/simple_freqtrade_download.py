#!/usr/bin/env python3
"""
使用Freqtrade直接下载OKX合约数据
从2025年1月1日到今天的所有分钟级数据
"""

import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime

def run_freqtrade_command(cmd, description):
    """运行freqtrade命令"""
    print(f"\n{'='*20} {description} {'='*20}")
    print(f"执行命令: {' '.join(cmd)}")
    
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

def download_all_contracts():
    """下载所有合约数据"""
    print("🚀 开始下载OKX合约数据 (2025年1月1日后)")
    print("=" * 60)
    
    # 时间框架列表
    timeframes = ['1m']  # 只下载1分钟数据
    
    # 下载每个时间框架
    for timeframe in timeframes:
        cmd = [
            'python', '-m', 'freqtrade', 'download-data',
            '--exchange', 'okx',
            '--pairs', '.*/USDT',  # 所有USDT交易对
            '--timeframes', timeframe,
            '--timerange', '20250101-',  # 从2025年1月1日到现在
            '--config', 'user_data/config.json'
        ]
        
        success = run_freqtrade_command(cmd, f"下载 {timeframe} 数据")
        
        if not success:
            print(f"⚠️ {timeframe} 下载失败，继续下一个...")
        
        # 时间框架间休息
        if timeframe != timeframes[-1]:
            print("休息 5 秒...")
            time.sleep(5)
    
    print("\n" + "="*60)
    print("所有时间框架下载完成！")
    print("="*60)

def download_specific_pairs(pairs):
    """下载指定交易对"""
    print(f"下载指定交易对: {pairs}")
    
    cmd = [
        'python', '-m', 'freqtrade', 'download-data',
        '--exchange', 'okx',
        '--pairs'] + pairs + [
        '--timeframes', '1m',
        '--timerange', '20250101-',  # 从2025年1月1日到现在
        '--config', 'user_data/config.json'
    ]
    
    return run_freqtrade_command(cmd, f"下载 {len(pairs)} 个交易对")

def check_data_status():
    """检查数据状态"""
    print("\n📊 检查数据状态...")
    
    data_dir = Path("../../user_data/data/okx")
    if not data_dir.exists():
        print("❌ 数据目录不存在")
        return
    
    # 统计文件
    feather_files = list(data_dir.glob("*.feather"))
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

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='OKX合约数据下载器 (Freqtrade版)')
    parser.add_argument('--pairs', nargs='+', help='下载指定交易对')
    parser.add_argument('--all', action='store_true', help='下载所有交易对')
    parser.add_argument('--status', action='store_true', help='检查数据状态')
    
    args = parser.parse_args()
    
    print("OKX合约数据下载器 (Freqtrade版)")
    print("="*60)
    print("📅 下载时间范围: 2025年1月1日 到 今天")
    print("⏰ 时间框架: 1分钟")
    print("💱 交易对: 所有USDT现货交易对")
    
    try:
        if args.status:
            check_data_status()
        elif args.pairs:
            download_specific_pairs(args.pairs)
        elif args.all:
            download_all_contracts()
        else:
            print("\n请指定操作:")
            print("  --pairs BTC/USDT ETH/USDT  下载指定交易对")
            print("  --all                      下载所有交易对")
            print("  --status                   检查数据状态")
            print("\n推荐:")
            print("  python simple_freqtrade_download.py --all")
        
        # 检查状态
        if not args.status:
            check_data_status()
        
    except KeyboardInterrupt:
        print("\n⏹️ 用户中断下载")
    except Exception as e:
        print(f"❌ 程序出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
