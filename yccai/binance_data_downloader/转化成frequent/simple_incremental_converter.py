#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
简化的增量转换器
基于数据时间比较进行真正的增量转换，不生成任何日志文件
"""

import sys
import zipfile
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone
import logging

# 设置控制台输出编码为UTF-8
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.detach())

logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

class SimpleIncrementalConverter:
    """简化的增量转换器"""
    
    def __init__(self, source_dir: str, output_dir: str):
        """
        初始化转换器
        
        Args:
            source_dir: 币安数据源目录
            output_dir: 输出目录（Freqtrade的user_data/data）
        """
        self.source_dir = Path(source_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 币安数据列名
        self.binance_columns = [
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_asset_volume', 'number_of_trades',
            'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
        ]
        
        # Freqtrade需要的列名
        self.freqtrade_columns = ['date', 'open', 'high', 'low', 'close', 'volume']
    
    def get_latest_data_time(self, pair: str, timeframe: str) -> datetime:
        """
        获取现有数据的最新时间
        
        Args:
            pair: 交易对名称
            timeframe: 时间间隔
            
        Returns:
            最新数据时间，如果没有数据则返回最早时间
        """
        feather_file = self.output_dir / f"{pair.lower()}-{timeframe}.feather"
        
        if not feather_file.exists():
            # 如果没有现有数据，返回很早的时间
            return datetime(2019, 1, 1, tzinfo=timezone.utc)
        
        try:
            df = pd.read_feather(feather_file)
            # 检查date列（可能是索引）
            if 'date' in df.columns:
                latest_time = df['date'].max()
            elif hasattr(df.index, 'name') and df.index.name == 'date':
                latest_time = df.index.max()
            else:
                # 如果找不到date列，返回很早的时间
                return datetime(2019, 1, 1, tzinfo=timezone.utc)
            
            return latest_time
        except Exception as e:
            logger.warning(f"读取现有数据失败: {e}")
            return datetime(2019, 1, 1, tzinfo=timezone.utc)
    
    def parse_binance_csv(self, csv_path: Path) -> pd.DataFrame:
        """
        解析币安CSV数据
        
        Args:
            csv_path: CSV文件路径
            
        Returns:
            解析后的DataFrame
        """
        try:
            # 读取CSV文件，处理标题行
            df = pd.read_csv(csv_path, header=0)
            
            # 检查是否有标题行
            if 'open_time' in df.columns:
                # 有标题行，直接使用
                pass
            else:
                # 没有标题行，手动设置列名
                df = pd.read_csv(csv_path, header=None, names=self.binance_columns)
            
            # 转换时间戳为datetime
            df['date'] = pd.to_datetime(df['open_time'], unit='ms', utc=True)
            
            # 选择需要的列并重命名
            df = df[['date', 'open', 'high', 'low', 'close', 'volume']]
            
            # 确保数据类型正确
            df = df.astype({
                'open': 'float64',
                'high': 'float64', 
                'low': 'float64',
                'close': 'float64',
                'volume': 'float64'
            })
            
            # 按时间排序
            df = df.sort_values('date').reset_index(drop=True)
            
            return df
            
        except Exception as e:
            logger.error(f"解析CSV文件失败 {csv_path}: {e}")
            return pd.DataFrame()
    
    def convert_pair_timeframe(self, pair: str, timeframe: str) -> bool:
        """
        转换单个交易对和时间间隔的数据
        
        Args:
            pair: 交易对名称
            timeframe: 时间间隔
            
        Returns:
            转换是否成功
        """
        try:
            logger.info(f"开始转换 {pair} {timeframe} 数据...")
            
            # 获取现有数据的最新时间
            latest_time = self.get_latest_data_time(pair, timeframe)
            logger.info(f"现有数据最新时间: {latest_time}")
            
            # 查找币安数据目录
            data_dir = self.source_dir / "futures" / "um" / "daily" / "klines" / pair / timeframe
            
            if not data_dir.exists():
                logger.error(f"数据目录不存在: {data_dir}")
                return False
            
            # 获取所有ZIP文件
            zip_files = list(data_dir.glob("*.zip"))
            if not zip_files:
                logger.error(f"未找到ZIP文件: {data_dir}")
                return False
            
            logger.info(f"找到 {len(zip_files)} 个ZIP文件")
            
            # 收集新数据
            new_data_list = []
            new_files_count = 0
            
            for zip_file in sorted(zip_files):
                try:
                    # 解压ZIP文件
                    with zipfile.ZipFile(zip_file, 'r') as zf:
                        csv_files = [f for f in zf.namelist() if f.endswith('.csv')]
                        
                        for csv_file in csv_files:
                            # 读取CSV内容
                            with zf.open(csv_file) as f:
                                # 创建临时文件
                                temp_csv = Path("temp.csv")
                                with open(temp_csv, 'wb') as tf:
                                    tf.write(f.read())
                                
                                # 解析CSV
                                df = self.parse_binance_csv(temp_csv)
                                
                                if not df.empty:
                                    # 过滤出比现有数据更新的数据
                                    new_df = df[df['date'] > latest_time]
                                    
                                    if not new_df.empty:
                                        new_data_list.append(new_df)
                                        new_files_count += 1
                                        logger.info(f"处理新文件: {zip_file.name}, 新增 {len(new_df)} 条数据")
                                
                                # 清理临时文件
                                temp_csv.unlink(missing_ok=True)
                
                except Exception as e:
                    logger.warning(f"处理文件失败 {zip_file.name}: {e}")
                    continue
            
            if not new_data_list:
                logger.info("没有新数据需要处理，数据已是最新")
                return True
            
            # 合并新数据
            new_data = pd.concat(new_data_list, ignore_index=True)
            new_data = new_data.sort_values('date').reset_index(drop=True)
            
            logger.info(f"合并新数据: {len(new_data)} 条记录")
            
            # 读取现有数据
            feather_file = self.output_dir / f"{pair.lower()}-{timeframe}.feather"
            if feather_file.exists():
                try:
                    existing_data = pd.read_feather(feather_file)
                    # 合并数据
                    combined_data = pd.concat([existing_data, new_data], ignore_index=True)
                    combined_data = combined_data.sort_values('date').reset_index(drop=True)
                    # 去重（基于date列）
                    combined_data = combined_data.drop_duplicates(subset=['date'], keep='last')
                    logger.info(f"合并后总数据: {len(combined_data)} 条记录")
                except Exception as e:
                    logger.warning(f"读取现有数据失败，使用新数据: {e}")
                    combined_data = new_data
            else:
                combined_data = new_data
            
            # 保存数据
            combined_data.to_feather(feather_file, compression='lz4')
            logger.info(f"保存数据到: {feather_file}")
            
            return True
            
        except Exception as e:
            logger.error(f"转换失败 {pair} {timeframe}: {e}")
            return False
    
    def convert_all_data(self, pairs: list, timeframes: list) -> dict:
        """
        转换所有数据
        
        Args:
            pairs: 交易对列表
            timeframes: 时间间隔列表
            
        Returns:
            转换结果字典
        """
        results = {}
        
        logger.info("开始增量转换...")
        logger.info(f"交易对: {pairs}")
        logger.info(f"时间间隔: {timeframes}")
        
        for pair in pairs:
            for timeframe in timeframes:
                key = f"{pair}_{timeframe}"
                results[key] = self.convert_pair_timeframe(pair, timeframe)
        
        # 显示结果
        logger.info("\n=== 转换结果 ===")
        success_count = 0
        for key, success in results.items():
            status = "成功" if success else "失败"
            logger.info(f"{key}: {status}")
            if success:
                success_count += 1
        
        logger.info(f"\n总计: {success_count}/{len(results)} 个文件转换成功")
        
        return results

def main():
    """主函数"""
    # 配置路径
    current_dir = Path(__file__).parent
    source_dir = current_dir.parent / "data"  # 币安数据目录
    
    # 直接输出到 Freqtrade 的 user_data/data 目录
    freqtrade_root = current_dir.parent.parent.parent  # 回到 freqtrade 根目录
    output_dir = freqtrade_root / "user_data" / "data"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info("=" * 60)
    logger.info("简化的增量转换器")
    logger.info("=" * 60)
    logger.info(f"转换时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"源数据目录: {source_dir}")
    logger.info(f"输出目录: {output_dir}")
    
    # 检查源目录
    if not source_dir.exists():
        logger.error(f"源数据目录不存在: {source_dir}")
        logger.info("请先运行币安数据下载工具下载数据")
        return
    
    # 创建转换器
    converter = SimpleIncrementalConverter(
        source_dir=str(source_dir), 
        output_dir=str(output_dir)
    )
    
    # 转换BTC和ETH的主要时间间隔数据
    pairs = ["BTCUSDT", "ETHUSDT"]
    timeframes = ["1m", "5m", "15m", "1h", "4h", "1d"]
    
    logger.info(f"开始增量转换 {pairs} 的 {timeframes} 数据...")
    
    # 执行增量转换
    results = converter.convert_all_data(pairs=pairs, timeframes=timeframes)
    
    # 显示结果
    logger.info("\n" + "=" * 60)
    logger.info("增量转换完成！")
    logger.info("=" * 60)
    
    success_count = sum(1 for success in results.values() if success)
    total_count = len(results)
    
    logger.info(f"成功转换: {success_count}/{total_count} 个文件")
    
    if success_count > 0:
        logger.info("\n更新的文件:")
        for key, success in results.items():
            if success:
                pair, timeframe = key.split('_')
                filename = f"{pair.lower()}-{timeframe}.feather"
                logger.info(f"  - {filename}")
        
        logger.info(f"\n文件保存在: {output_dir}")
        logger.info("\n使用说明:")
        logger.info("1. 数据已直接保存到Freqtrade的user_data/data目录")
        logger.info("2. 在Freqtrade配置中设置dataformat_ohlcv为'feather'")
        logger.info("3. 使用freqtrade list-data命令验证数据")
    else:
        logger.info("没有新数据需要转换，所有数据已是最新")

if __name__ == "__main__":
    main()
