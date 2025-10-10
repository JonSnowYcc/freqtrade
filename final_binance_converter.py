#!/usr/bin/env python3
"""
最终版币安数据转换脚本
处理indexPriceKlines数据
"""

import os
import zipfile
import argparse
from pathlib import Path
from typing import List
import logging
from concurrent.futures import ProcessPoolExecutor
import multiprocessing as mp
from functools import partial
import time

# 设置日志
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def process_single_zip(zip_path: Path, output_dir: Path, pair: str, timeframe: str) -> bool:
    """
    处理单个ZIP文件
    """
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            csv_files = [f for f in zip_ref.namelist() if f.endswith('.csv')]
            
            if not csv_files:
                return False
            
            # 收集所有有效数据
            all_data = []
            
            for csv_file in csv_files:
                with zip_ref.open(csv_file) as csv_content:
                    # 尝试不同编码
                    content = None
                    for encoding in ['utf-8', 'gbk', 'gb2312', 'latin-1']:
                        try:
                            content = csv_content.read().decode(encoding)
                            break
                        except UnicodeDecodeError:
                            csv_content.seek(0)
                            continue
                    
                    if content is None:
                        continue
                    
                    # 按行处理
                    lines = content.strip().split('\n')
                    
                    for line_num, line in enumerate(lines):
                        line = line.strip()
                        if not line:
                            continue
                        
                        # 跳过标题行
                        if line.startswith('open_time,open,high,low,close,volume'):
                            continue
                        
                        # 简单分割，只取前6个字段
                        parts = line.split(',')[:6]  # 取前6个字段
                        
                        if len(parts) < 6:
                            continue
                        
                        try:
                            # 验证时间戳
                            timestamp_str = parts[0].strip()
                            if not timestamp_str.replace('.', '').isdigit():
                                continue
                            
                            timestamp = int(float(timestamp_str)) // 1000
                            
                            # 验证价格数据
                            open_price = float(parts[1])
                            high_price = float(parts[2])
                            low_price = float(parts[3])
                            close_price = float(parts[4])
                            volume = float(parts[5])
                            
                            # 基本验证
                            if (open_price <= 0 or high_price <= 0 or 
                                low_price <= 0 or close_price <= 0):
                                continue
                            
                            # 价格逻辑验证
                            if (high_price < max(open_price, close_price) or 
                                low_price > min(open_price, close_price)):
                                continue
                            
                            all_data.append((timestamp, open_price, high_price, low_price, close_price, volume))
                            
                        except (ValueError, IndexError):
                            continue
            
            if not all_data:
                logger.debug(f"文件 {zip_path} 没有有效数据")
                return False
            
            # 去重并排序
            unique_data = {}
            for item in all_data:
                timestamp = item[0]
                if timestamp not in unique_data:
                    unique_data[timestamp] = item
            
            sorted_data = sorted(unique_data.values())
            
            # 创建输出目录
            pair_output_dir = output_dir / pair
            pair_output_dir.mkdir(parents=True, exist_ok=True)
            
            output_filename = f"{pair}-{timeframe}.csv"
            output_path = pair_output_dir / output_filename
            
            # 写入数据
            if output_path.exists():
                # 读取现有数据
                existing_data = {}
                try:
                    with open(output_path, 'r', encoding='utf-8') as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                parts = line.split(',')
                                if len(parts) >= 6:
                                    try:
                                        timestamp = int(parts[0])
                                        existing_data[timestamp] = tuple(map(float, parts))
                                    except ValueError:
                                        continue
                except Exception:
                    pass
                
                # 合并数据
                for item in sorted_data:
                    existing_data[item[0]] = item
                
                # 写入合并后的数据
                sorted_combined = sorted(existing_data.values())
                with open(output_path, 'w', encoding='utf-8') as f:
                    for item in sorted_combined:
                        f.write(f"{int(item[0])},{item[1]},{item[2]},{item[3]},{item[4]},{item[5]}\n")
            else:
                # 写入新数据
                with open(output_path, 'w', encoding='utf-8') as f:
                    for item in sorted_data:
                        f.write(f"{int(item[0])},{item[1]},{item[2]},{item[3]},{item[4]},{item[5]}\n")
            
            return True
            
    except Exception as e:
        logger.error(f"处理文件 {zip_path} 时出错: {e}")
        return False

class FinalBinanceConverter:
    def __init__(self, input_dir: str, output_dir: str, max_workers: int = None):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        if max_workers is None:
            self.max_workers = min(mp.cpu_count(), 4)
        else:
            self.max_workers = max_workers
        
        logger.info(f"使用 {self.max_workers} 个进程进行并行处理")
    
    def get_zip_files(self, pair: str, timeframe: str) -> List[Path]:
        """获取指定交易对和时间框架的所有ZIP文件"""
        pair_timeframe_dir = self.input_dir / pair / timeframe
        
        if not pair_timeframe_dir.exists():
            return []
        
        zip_files = list(pair_timeframe_dir.glob("*.zip"))
        return sorted(zip_files)
    
    def convert_pair_timeframe(self, pair: str, timeframe: str) -> int:
        """转换指定交易对和时间框架的数据"""
        zip_files = self.get_zip_files(pair, timeframe)
        
        if not zip_files:
            logger.warning(f"未找到 {pair}-{timeframe} 的数据文件")
            return 0
        
        logger.info(f"开始处理 {pair}-{timeframe}: {len(zip_files)} 个文件")
        
        process_func = partial(process_single_zip, 
                             output_dir=self.output_dir, 
                             pair=pair, 
                             timeframe=timeframe)
        
        start_time = time.time()
        successful_count = 0
        
        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            # 分批处理
            batch_size = 100
            for i in range(0, len(zip_files), batch_size):
                batch = zip_files[i:i + batch_size]
                results = list(executor.map(process_func, batch))
                successful_count += sum(results)
                
                # 显示进度
                processed = min(i + batch_size, len(zip_files))
                elapsed = time.time() - start_time
                rate = processed / elapsed if elapsed > 0 else 0
                logger.info(f"进度: {processed}/{len(zip_files)} ({processed/len(zip_files)*100:.1f}%) - "
                          f"速度: {rate:.1f} 文件/秒 - 成功: {successful_count}")
        
        elapsed = time.time() - start_time
        logger.info(f"完成 {pair}-{timeframe}: 成功 {successful_count}/{len(zip_files)} 个文件, "
                   f"耗时 {elapsed:.1f} 秒")
        
        return successful_count

def main():
    parser = argparse.ArgumentParser(description='最终版币安数据转换')
    parser.add_argument('--input', '-i', required=True, help='输入目录路径')
    parser.add_argument('--output', '-o', required=True, help='输出目录路径')
    parser.add_argument('--pair', '-p', help='指定交易对')
    parser.add_argument('--timeframe', '-t', help='指定时间框架')
    parser.add_argument('--workers', '-w', type=int, help='并行进程数')
    
    args = parser.parse_args()
    
    # 创建转换器
    converter = FinalBinanceConverter(args.input, args.output, args.workers)
    
    if args.pair and args.timeframe:
        # 转换指定交易对和时间框架
        converted_count = converter.convert_pair_timeframe(args.pair, args.timeframe)
        logger.info(f"转换完成，共处理 {converted_count} 个文件")
    else:
        logger.error("请指定 --pair 和 --timeframe 参数")

if __name__ == "__main__":
    main()
