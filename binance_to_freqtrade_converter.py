#!/usr/bin/env python3
"""
币安数据转换为Freqtrade格式的脚本
支持批量处理zip文件和CSV文件
"""

import os
import zipfile
import pandas as pd
import argparse
from pathlib import Path
from typing import List, Optional
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BinanceToFreqtradeConverter:
    def __init__(self, input_dir: str, output_dir: str):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def convert_csv_file(self, csv_path: Path, pair: str, timeframe: str) -> bool:
        """
        转换单个CSV文件为Freqtrade格式
        """
        try:
            # 读取币安格式的CSV文件
            # 币安格式: timestamp, open, high, low, close, volume, close_time, quote_volume, count, taker_buy_volume, taker_buy_quote_volume, ignore
            df = pd.read_csv(csv_path, header=None, names=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume', 
                'close_time', 'quote_volume', 'count', 'taker_buy_volume', 
                'taker_buy_quote_volume', 'ignore'
            ])
            
            # 转换为Freqtrade格式: timestamp, open, high, low, close, volume
            freqtrade_df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].copy()
            
            # 转换时间戳为秒（Freqtrade使用秒级时间戳）
            freqtrade_df['timestamp'] = freqtrade_df['timestamp'] // 1000
            
            # 创建输出目录
            pair_output_dir = self.output_dir / pair
            pair_output_dir.mkdir(exist_ok=True)
            
            # 生成输出文件名
            output_filename = f"{pair}-{timeframe}.csv"
            output_path = pair_output_dir / output_filename
            
            # 如果文件已存在，追加数据
            if output_path.exists():
                existing_df = pd.read_csv(output_path)
                # 合并数据并去重
                combined_df = pd.concat([existing_df, freqtrade_df], ignore_index=True)
                combined_df = combined_df.drop_duplicates(subset=['timestamp']).sort_values('timestamp')
                combined_df.to_csv(output_path, index=False, header=False)
                logger.info(f"追加数据到 {output_path}")
            else:
                # 保存新文件
                freqtrade_df.to_csv(output_path, index=False, header=False)
                logger.info(f"创建新文件 {output_path}")
            
            return True
            
        except Exception as e:
            logger.error(f"转换文件 {csv_path} 时出错: {e}")
            return False
    
    def convert_zip_file(self, zip_path: Path, pair: str, timeframe: str) -> bool:
        """
        转换zip文件中的CSV数据
        """
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # 获取zip文件中的CSV文件
                csv_files = [f for f in zip_ref.namelist() if f.endswith('.csv')]
                
                if not csv_files:
                    logger.warning(f"ZIP文件 {zip_path} 中没有找到CSV文件")
                    return False
                
                # 处理每个CSV文件
                for csv_file in csv_files:
                    # 从zip中读取CSV内容
                    with zip_ref.open(csv_file) as csv_content:
                        # 创建临时文件路径用于处理
                        temp_csv_path = Path(f"temp_{csv_file}")
                        
                        # 将内容写入临时文件
                        with open(temp_csv_path, 'wb') as temp_file:
                            temp_file.write(csv_content.read())
                        
                        # 转换CSV文件
                        success = self.convert_csv_file(temp_csv_path, pair, timeframe)
                        
                        # 删除临时文件
                        temp_csv_path.unlink()
                        
                        if not success:
                            return False
                
                return True
                
        except Exception as e:
            logger.error(f"处理ZIP文件 {zip_path} 时出错: {e}")
            return False
    
    def convert_directory(self, pair: str, timeframe: str) -> int:
        """
        转换指定交易对和时间框架的所有数据
        """
        pair_timeframe_dir = self.input_dir / pair / timeframe
        
        if not pair_timeframe_dir.exists():
            logger.error(f"目录不存在: {pair_timeframe_dir}")
            return 0
        
        converted_count = 0
        
        # 处理所有zip文件
        zip_files = list(pair_timeframe_dir.glob("*.zip"))
        logger.info(f"找到 {len(zip_files)} 个ZIP文件需要处理")
        
        for zip_file in zip_files:
            if self.convert_zip_file(zip_file, pair, timeframe):
                converted_count += 1
                logger.info(f"成功转换: {zip_file.name}")
            else:
                logger.error(f"转换失败: {zip_file.name}")
        
        return converted_count
    
    def convert_all_pairs(self) -> dict:
        """
        转换所有交易对的数据
        """
        results = {}
        
        # 遍历所有交易对目录
        for pair_dir in self.input_dir.iterdir():
            if not pair_dir.is_dir():
                continue
                
            pair = pair_dir.name
            logger.info(f"开始处理交易对: {pair}")
            
            # 遍历所有时间框架
            for timeframe_dir in pair_dir.iterdir():
                if not timeframe_dir.is_dir():
                    continue
                    
                timeframe = timeframe_dir.name
                logger.info(f"处理时间框架: {timeframe}")
                
                converted_count = self.convert_directory(pair, timeframe)
                results[f"{pair}_{timeframe}"] = converted_count
                
                logger.info(f"完成 {pair}-{timeframe}: 转换了 {converted_count} 个文件")
        
        return results

def main():
    parser = argparse.ArgumentParser(description='将币安数据转换为Freqtrade格式')
    parser.add_argument('--input', '-i', required=True, help='输入目录路径（包含币安数据）')
    parser.add_argument('--output', '-o', required=True, help='输出目录路径（Freqtrade数据目录）')
    parser.add_argument('--pair', '-p', help='指定交易对（如BTCUSDT），不指定则处理所有')
    parser.add_argument('--timeframe', '-t', help='指定时间框架（如1m），不指定则处理所有')
    parser.add_argument('--dry-run', action='store_true', help='预览模式，不实际转换')
    
    args = parser.parse_args()
    
    if args.dry_run:
        logger.info("预览模式 - 不会实际转换文件")
        # 这里可以添加预览逻辑
        return
    
    # 创建转换器
    converter = BinanceToFreqtradeConverter(args.input, args.output)
    
    if args.pair and args.timeframe:
        # 转换指定交易对和时间框架
        converted_count = converter.convert_directory(args.pair, args.timeframe)
        logger.info(f"转换完成，共处理 {converted_count} 个文件")
    elif args.pair:
        # 转换指定交易对的所有时间框架
        pair_dir = Path(args.input) / args.pair
        if pair_dir.exists():
            for timeframe_dir in pair_dir.iterdir():
                if timeframe_dir.is_dir():
                    timeframe = timeframe_dir.name
                    converted_count = converter.convert_directory(args.pair, timeframe)
                    logger.info(f"{args.pair}-{timeframe}: 转换了 {converted_count} 个文件")
    else:
        # 转换所有数据
        results = converter.convert_all_pairs()
        total_files = sum(results.values())
        logger.info(f"全部转换完成，共处理 {total_files} 个文件")
        logger.info("详细结果:")
        for key, count in results.items():
            logger.info(f"  {key}: {count} 个文件")

if __name__ == "__main__":
    main()
