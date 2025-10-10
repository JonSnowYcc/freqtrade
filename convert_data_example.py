#!/usr/bin/env python3
"""
数据转换使用示例
"""

import os
import sys
from pathlib import Path

# 添加当前目录到Python路径
sys.path.append(str(Path(__file__).parent))

from binance_to_freqtrade_converter import BinanceToFreqtradeConverter

def main():
    # 设置路径
    input_dir = "yccai/binance_data_downloader/data/futures/um/daily/klines"
    output_dir = "user_data/data/futures"
    
    print("=" * 60)
    print("币安数据转换为Freqtrade格式")
    print("=" * 60)
    print(f"输入目录: {input_dir}")
    print(f"输出目录: {output_dir}")
    print()
    
    # 检查输入目录是否存在
    if not Path(input_dir).exists():
        print(f"错误: 输入目录不存在: {input_dir}")
        return
    
    # 创建输出目录
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # 创建转换器
    converter = BinanceToFreqtradeConverter(input_dir, output_dir)
    
    print("开始转换数据...")
    print()
    
    # 转换所有数据
    results = converter.convert_all_pairs()
    
    print()
    print("=" * 60)
    print("转换完成!")
    print("=" * 60)
    
    total_files = sum(results.values())
    print(f"总共处理了 {total_files} 个文件")
    print()
    print("详细结果:")
    for key, count in results.items():
        if count > 0:
            print(f"  {key}: {count} 个文件")
    
    print()
    print("转换后的数据已保存到:", output_dir)
    print("您现在可以在Freqtrade中使用这些数据了!")

if __name__ == "__main__":
    main()
