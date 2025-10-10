#!/usr/bin/env python3
"""
调试版转换脚本
"""

import zipfile
from pathlib import Path

def test_single_file():
    zip_path = Path('yccai/binance_data_downloader/data/futures/um/daily/indexPriceKlines/BTCUSDT/1m/BTCUSDT-1m-2019-12-23.zip')
    
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        csv_files = [f for f in zip_ref.namelist() if f.endswith('.csv')]
        print(f'CSV files: {csv_files}')
        
        for csv_file in csv_files:
            with zip_ref.open(csv_file) as csv_content:
                content = csv_content.read().decode('utf-8')
                lines = content.strip().split('\n')
                print(f'Total lines: {len(lines)}')
                
                valid_data = []
                
                for line_num, line in enumerate(lines):
                    line = line.strip()
                    if not line:
                        continue
                    
                    # 跳过标题行
                    if line.startswith('open_time,open,high,low,close,volume'):
                        print(f'跳过标题行: {line}')
                        continue
                    
                    # 简单分割，取前6个字段
                    parts = line.split(',')[:6]
                    
                    if len(parts) < 6:
                        print(f'行 {line_num} 字段不足: {len(parts)}')
                        continue
                    
                    try:
                        # 验证时间戳
                        timestamp_str = parts[0].strip()
                        if not timestamp_str.replace('.', '').isdigit():
                            print(f'行 {line_num} 时间戳无效: {timestamp_str}')
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
                            print(f'行 {line_num} 价格无效: {open_price}, {high_price}, {low_price}, {close_price}')
                            continue
                        
                        # 价格逻辑验证
                        if (high_price < max(open_price, close_price) or 
                            low_price > min(open_price, close_price)):
                            print(f'行 {line_num} 价格逻辑错误: high={high_price}, low={low_price}, open={open_price}, close={close_price}')
                            continue
                        
                        valid_data.append((timestamp, open_price, high_price, low_price, close_price, volume))
                        
                        if len(valid_data) <= 5:
                            print(f'有效数据 {len(valid_data)}: {valid_data[-1]}')
                        
                    except (ValueError, IndexError) as e:
                        print(f'行 {line_num} 解析错误: {e}')
                        continue
                
                print(f'总共有效数据: {len(valid_data)}')
                
                if valid_data:
                    # 写入测试文件
                    output_path = Path('test_output.csv')
                    with open(output_path, 'w', encoding='utf-8') as f:
                        for item in valid_data:
                            f.write(f"{item[0]},{item[1]},{item[2]},{item[3]},{item[4]},{item[5]}\n")
                    print(f'测试文件已写入: {output_path}')
                    return True
                else:
                    print('没有有效数据')
                    return False

if __name__ == "__main__":
    test_single_file()
