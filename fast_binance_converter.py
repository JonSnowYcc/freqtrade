#!/usr/bin/env python3
"""
高速币安数据转换脚本
使用多进程和内存优化技术大幅提升转换速度
"""

import os
import zipfile
import pandas as pd
import argparse
from pathlib import Path
from typing import List, Optional
import logging
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import multiprocessing as mp
from functools import partial
import time

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def process_single_zip(zip_path: Path, output_dir: Path, pair: str, timeframe: str) -> bool:
    """
    处理单个ZIP文件 - 优化版本
    """
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            csv_files = [f for f in zip_ref.namelist() if f.endswith('.csv')]
            
            if not csv_files:
                return False
            
            # 一次性读取所有CSV数据
            all_data = []
            for csv_file in csv_files:
                with zip_ref.open(csv_file) as csv_content:
                    # 直接读取为字符串，避免重复解压
                    content = csv_content.read().decode('utf-8')
                    lines = content.strip().split('\n')
                    
                    for line in lines:
                        if line.strip():
                            parts = line.split(',')
                            if len(parts) >= 6:
                                # 跳过标题行
                                if parts[0] == 'open_time' or not parts[0].isdigit():
                                    continue
                                
                                try:
                                    # 只提取需要的字段：timestamp, open, high, low, close, volume
                                    timestamp = int(parts[0]) // 1000  # 转换为秒
                                    all_data.append([
                                        timestamp,
                                        float(parts[1]),  # open
                                        float(parts[2]),  # high
                                        float(parts[3]),  # low
                                        float(parts[4]),  # close
                                        float(parts[5])   # volume
                                    ])
                                except (ValueError, IndexError):
                                    # 跳过无效的数据行
                                    continue
            
            if not all_data:
                return False
            
            # 创建DataFrame并排序
            df = pd.DataFrame(all_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df = df.sort_values('timestamp').drop_duplicates(subset=['timestamp'])
            
            # 创建输出目录
            pair_output_dir = output_dir / pair
            pair_output_dir.mkdir(parents=True, exist_ok=True)
            
            output_filename = f"{pair}-{timeframe}.csv"
            output_path = pair_output_dir / output_filename
            
            # 如果文件已存在，合并数据
            if output_path.exists():
                existing_df = pd.read_csv(output_path, header=None, names=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                combined_df = pd.concat([existing_df, df], ignore_index=True)
                combined_df = combined_df.drop_duplicates(subset=['timestamp']).sort_values('timestamp')
                combined_df.to_csv(output_path, index=False, header=False)
            else:
                df.to_csv(output_path, index=False, header=False)
            
            return True
            
    except Exception as e:
        logger.error(f"处理文件 {zip_path} 时出错: {e}")
        return False

class FastBinanceConverter:
    def __init__(self, input_dir: str, output_dir: str, max_workers: int = None):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 自动检测CPU核心数
        if max_workers is None:
            self.max_workers = min(mp.cpu_count(), 8)  # 最多使用8个进程
        else:
            self.max_workers = max_workers
        
        logger.info(f"使用 {self.max_workers} 个进程进行并行处理")
    
    def get_zip_files(self, pair: str, timeframe: str) -> List[Path]:
        """
        获取指定交易对和时间框架的所有ZIP文件
        """
        pair_timeframe_dir = self.input_dir / pair / timeframe
        
        if not pair_timeframe_dir.exists():
            return []
        
        zip_files = list(pair_timeframe_dir.glob("*.zip"))
        return sorted(zip_files)
    
    def convert_pair_timeframe(self, pair: str, timeframe: str) -> int:
        """
        转换指定交易对和时间框架的数据
        """
        zip_files = self.get_zip_files(pair, timeframe)
        
        if not zip_files:
            logger.warning(f"未找到 {pair}-{timeframe} 的数据文件")
            return 0
        
        logger.info(f"开始处理 {pair}-{timeframe}: {len(zip_files)} 个文件")
        
        # 使用进程池并行处理
        process_func = partial(process_single_zip, 
                             output_dir=self.output_dir, 
                             pair=pair, 
                             timeframe=timeframe)
        
        start_time = time.time()
        successful_count = 0
        
        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            # 分批处理，避免内存占用过高
            batch_size = 50
            for i in range(0, len(zip_files), batch_size):
                batch = zip_files[i:i + batch_size]
                results = list(executor.map(process_func, batch))
                successful_count += sum(results)
                
                # 显示进度
                processed = min(i + batch_size, len(zip_files))
                elapsed = time.time() - start_time
                rate = processed / elapsed if elapsed > 0 else 0
                logger.info(f"进度: {processed}/{len(zip_files)} ({processed/len(zip_files)*100:.1f}%) - "
                          f"速度: {rate:.1f} 文件/秒")
        
        elapsed = time.time() - start_time
        logger.info(f"完成 {pair}-{timeframe}: 成功 {successful_count}/{len(zip_files)} 个文件, "
                   f"耗时 {elapsed:.1f} 秒")
        
        return successful_count
    
    def convert_all_pairs(self) -> dict:
        """
        转换所有交易对的数据
        """
        results = {}
        total_start_time = time.time()
        
        # 获取所有交易对和时间框架
        all_tasks = []
        for pair_dir in self.input_dir.iterdir():
            if not pair_dir.is_dir():
                continue
                
            pair = pair_dir.name
            for timeframe_dir in pair_dir.iterdir():
                if not timeframe_dir.is_dir():
                    continue
                    
                timeframe = timeframe_dir.name
                all_tasks.append((pair, timeframe))
        
        logger.info(f"找到 {len(all_tasks)} 个任务需要处理")
        
        # 并行处理所有任务
        for pair, timeframe in all_tasks:
            converted_count = self.convert_pair_timeframe(pair, timeframe)
            results[f"{pair}_{timeframe}"] = converted_count
        
        total_elapsed = time.time() - total_start_time
        total_files = sum(results.values())
        
        logger.info(f"全部转换完成!")
        logger.info(f"总文件数: {total_files}")
        logger.info(f"总耗时: {total_elapsed:.1f} 秒")
        logger.info(f"平均速度: {total_files/total_elapsed:.1f} 文件/秒")
        
        return results

def main():
    parser = argparse.ArgumentParser(description='高速币安数据转换为Freqtrade格式')
    parser.add_argument('--input', '-i', required=True, help='输入目录路径')
    parser.add_argument('--output', '-o', required=True, help='输出目录路径')
    parser.add_argument('--pair', '-p', help='指定交易对')
    parser.add_argument('--timeframe', '-t', help='指定时间框架')
    parser.add_argument('--workers', '-w', type=int, help='并行进程数')
    parser.add_argument('--dry-run', action='store_true', help='预览模式')
    
    args = parser.parse_args()
    
    if args.dry_run:
        logger.info("预览模式 - 不会实际转换文件")
        return
    
    # 创建高速转换器
    converter = FastBinanceConverter(args.input, args.output, args.workers)
    
    if args.pair and args.timeframe:
        # 转换指定交易对和时间框架
        converted_count = converter.convert_pair_timeframe(args.pair, args.timeframe)
        logger.info(f"转换完成，共处理 {converted_count} 个文件")
    elif args.pair:
        # 转换指定交易对的所有时间框架
        pair_dir = Path(args.input) / args.pair
        if pair_dir.exists():
            for timeframe_dir in pair_dir.iterdir():
                if timeframe_dir.is_dir():
                    timeframe = timeframe_dir.name
                    converted_count = converter.convert_pair_timeframe(args.pair, timeframe)
                    logger.info(f"{args.pair}-{timeframe}: 转换了 {converted_count} 个文件")
    else:
        # 转换所有数据
        results = converter.convert_all_pairs()
        logger.info("详细结果:")
        for key, count in results.items():
            if count > 0:
                logger.info(f"  {key}: {count} 个文件")

if __name__ == "__main__":
    main()
