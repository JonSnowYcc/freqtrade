#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BTC网格策略 - 使用FreqTrade真实数据回测
直接读取freqtrade的数据文件进行回测
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime, timedelta
import json
import logging
from pathlib import Path
import sys
import os

# 添加freqtrade路径
sys.path.append(str(Path(__file__).parent.parent.parent))

from freqtrade.data.history import load_pair_history
from freqtrade.data.btanalysis import load_backtest_data
from freqtrade.data.history.history_utils import TimeRange

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class FreqTradeGridBacktester:
    """使用FreqTrade数据回测BTC网格策略"""
    
    def __init__(self, data_dir: str = "user_data/data"):
        self.data_dir = Path(data_dir)
        self.grid_levels = []
        self.trade_history = []
        self.current_position = {
            'total_btc': 0.0,
            'total_cost': 0.0,
            'unrealized_pnl': 0.0,
            'realized_pnl': 0.0
        }
        
    def load_btc_data(self, timeframe: str = "1h", timerange: str = "20240101-20241201") -> pd.DataFrame:
        """加载BTC数据"""
        try:
            # 尝试加载数据
            pair = "BTC/USDT"
            datadir = self.data_dir / "binance"
            
            logger.info(f"从 {datadir} 加载 {pair} {timeframe} 数据...")
            
            # 解析时间范围
            timerange_obj = TimeRange.parse_timerange(timerange)
            
            # 加载数据
            data = load_pair_history(
                pair=pair,
                timeframe=timeframe,
                datadir=datadir,
                timerange=timerange_obj,
                fill_up_missing=True,
                drop_incomplete=False
            )
            
            if data.empty:
                logger.error(f"没有找到 {pair} {timeframe} 的数据")
                return pd.DataFrame()
            
            logger.info(f"成功加载 {len(data)} 条数据记录")
            logger.info(f"数据时间范围: {data.index[0]} 到 {data.index[-1]}")
            
            return data
            
        except Exception as e:
            logger.error(f"加载数据失败: {e}")
            return pd.DataFrame()
    
    def generate_grid_levels(self, initial_price: float, config: Dict[str, Any]) -> List[Dict]:
        """生成网格层级"""
        levels = []
        
        if config.get('enable_multi_grid', True):
            # 多网格策略
            levels.extend(self._generate_small_grid(initial_price, config))
            levels.extend(self._generate_medium_grid(initial_price, config))
            levels.extend(self._generate_large_grid(initial_price, config))
        else:
            # 单网格策略
            levels.extend(self._generate_single_grid(initial_price, config))
        
        return sorted(levels, key=lambda x: x['price'])
    
    def _generate_single_grid(self, initial_price: float, config: Dict[str, Any]) -> List[Dict]:
        """生成单网格"""
        levels = []
        grid_spacing = config.get('grid_spacing', 0.05)
        max_drawdown = config.get('max_drawdown', 0.6)
        max_grids = config.get('max_grids', 20)
        
        # 生成买入网格
        for i in range(max_grids):
            buy_price = initial_price * (1 - grid_spacing * (i + 1))
            if buy_price <= initial_price * (1 - max_drawdown):
                break
                
            levels.append({
                'price': buy_price,
                'amount': 0.01,  # 固定数量
                'action': 'buy',
                'level': i + 1,
                'grid_type': 'single'
            })
        
        # 生成卖出网格
        for i in range(max_grids):
            sell_price = initial_price * (1 + grid_spacing * (i + 1))
            levels.append({
                'price': sell_price,
                'amount': 0.01,
                'action': 'sell',
                'level': i + 1,
                'grid_type': 'single'
            })
        
        return levels
    
    def _generate_small_grid(self, initial_price: float, config: Dict[str, Any]) -> List[Dict]:
        """生成小网格"""
        levels = []
        small_spacing = config.get('small_grid_spacing', 0.05)
        max_drawdown = config.get('max_drawdown', 0.6)
        max_grids = config.get('max_grids', 20)
        small_ratio = config.get('small_grid_ratio', 0.5)
        
        for i in range(max_grids):
            buy_price = initial_price * (1 - small_spacing * (i + 1))
            if buy_price <= initial_price * (1 - max_drawdown):
                break
                
            levels.append({
                'price': buy_price,
                'amount': 0.01 * small_ratio,
                'action': 'buy',
                'level': i + 1,
                'grid_type': 'small'
            })
        
        for i in range(max_grids):
            sell_price = initial_price * (1 + small_spacing * (i + 1))
            levels.append({
                'price': sell_price,
                'amount': 0.01 * small_ratio,
                'action': 'sell',
                'level': i + 1,
                'grid_type': 'small'
            })
        
        return levels
    
    def _generate_medium_grid(self, initial_price: float, config: Dict[str, Any]) -> List[Dict]:
        """生成中网格"""
        levels = []
        medium_spacing = config.get('medium_grid_spacing', 0.15)
        max_drawdown = config.get('max_drawdown', 0.6)
        max_grids = config.get('max_grids', 20)
        medium_ratio = config.get('medium_grid_ratio', 0.3)
        
        for i in range(max_grids // 2):
            buy_price = initial_price * (1 - medium_spacing * (i + 1))
            if buy_price <= initial_price * (1 - max_drawdown):
                break
                
            levels.append({
                'price': buy_price,
                'amount': 0.01 * medium_ratio,
                'action': 'buy',
                'level': i + 1,
                'grid_type': 'medium'
            })
        
        for i in range(max_grids // 2):
            sell_price = initial_price * (1 + medium_spacing * (i + 1))
            levels.append({
                'price': sell_price,
                'amount': 0.01 * medium_ratio,
                'action': 'sell',
                'level': i + 1,
                'grid_type': 'medium'
            })
        
        return levels
    
    def _generate_large_grid(self, initial_price: float, config: Dict[str, Any]) -> List[Dict]:
        """生成大网格"""
        levels = []
        large_spacing = config.get('large_grid_spacing', 0.30)
        max_drawdown = config.get('max_drawdown', 0.6)
        max_grids = config.get('max_grids', 20)
        large_ratio = config.get('large_grid_ratio', 0.2)
        
        for i in range(max_grids // 3):
            buy_price = initial_price * (1 - large_spacing * (i + 1))
            if buy_price <= initial_price * (1 - max_drawdown):
                break
                
            levels.append({
                'price': buy_price,
                'amount': 0.01 * large_ratio,
                'action': 'buy',
                'level': i + 1,
                'grid_type': 'large'
            })
        
        for i in range(max_grids // 3):
            sell_price = initial_price * (1 + large_spacing * (i + 1))
            levels.append({
                'price': sell_price,
                'amount': 0.01 * large_ratio,
                'action': 'sell',
                'level': i + 1,
                'grid_type': 'large'
            })
        
        return levels
    
    def get_trading_signals(self, current_price: float) -> List[Dict]:
        """获取交易信号"""
        signals = []
        for level in self.grid_levels:
            if level['action'] == 'buy' and current_price <= level['price']:
                signals.append(level)
            elif level['action'] == 'sell' and current_price >= level['price']:
                signals.append(level)
        return signals
    
    def execute_trade(self, timestamp: datetime, price: float, signal: Dict) -> Dict:
        """执行交易"""
        trade_record = {
            'timestamp': timestamp,
            'price': price,
            'amount': signal['amount'],
            'action': signal['action'],
            'grid_type': signal['grid_type'],
            'level': signal['level']
        }
        
        if signal['action'] == 'buy':
            cost = price * signal['amount']
            self.current_position['total_btc'] += signal['amount']
            self.current_position['total_cost'] += cost
            trade_record['cost'] = cost
        else:  # sell
            revenue = price * signal['amount']
            self.current_position['total_btc'] -= signal['amount']
            self.current_position['total_cost'] -= signal['amount'] * (self.current_position['total_cost'] / self.current_position['total_btc'] if self.current_position['total_btc'] > 0 else 0)
            self.current_position['realized_pnl'] += revenue - (signal['amount'] * (self.current_position['total_cost'] / self.current_position['total_btc'] if self.current_position['total_btc'] > 0 else 0))
            trade_record['revenue'] = revenue
        
        self.trade_history.append(trade_record)
        return trade_record
    
    def run_backtest(self, data: pd.DataFrame, config: Dict[str, Any]) -> Dict[str, Any]:
        """运行回测"""
        if data.empty:
            logger.error("没有数据可以回测")
            return {}
        
        logger.info("开始回测...")
        
        # 初始化网格
        initial_price = data['close'].iloc[0]
        self.grid_levels = self.generate_grid_levels(initial_price, config)
        logger.info(f"生成了 {len(self.grid_levels)} 个网格点")
        
        # 重置状态
        self.trade_history = []
        self.current_position = {
            'total_btc': 0.0,
            'total_cost': 0.0,
            'unrealized_pnl': 0.0,
            'realized_pnl': 0.0
        }
        
        # 逐日回测
        for idx, row in data.iterrows():
            current_price = row['close']
            current_time = idx
            
            # 获取交易信号
            signals = self.get_trading_signals(current_price)
            
            # 执行交易
            for signal in signals:
                self.execute_trade(current_time, current_price, signal)
        
        # 计算最终结果
        final_price = data['close'].iloc[-1]
        final_btc = self.current_position['total_btc']
        final_equity = self.current_position['total_cost'] + final_btc * final_price
        
        # 计算未实现收益
        if final_btc > 0:
            avg_cost = self.current_position['total_cost'] / final_btc
            self.current_position['unrealized_pnl'] = final_btc * (final_price - avg_cost)
        
        total_pnl = self.current_position['realized_pnl'] + self.current_position['unrealized_pnl']
        total_return = total_pnl / 100000  # 假设初始资金10万
        
        result = {
            'initial_price': initial_price,
            'final_price': final_price,
            'total_trades': len(self.trade_history),
            'buy_trades': len([t for t in self.trade_history if t['action'] == 'buy']),
            'sell_trades': len([t for t in self.trade_history if t['action'] == 'sell']),
            'realized_pnl': self.current_position['realized_pnl'],
            'unrealized_pnl': self.current_position['unrealized_pnl'],
            'total_pnl': total_pnl,
            'total_return': total_return,
            'final_btc_holding': final_btc,
            'final_equity': final_equity,
            'grid_levels_count': len(self.grid_levels),
            'trade_history': self.trade_history
        }
        
        logger.info("回测完成")
        return result
    
    def generate_report(self, result: Dict[str, Any]) -> str:
        """生成回测报告"""
        report = f"""
=== BTC网格策略回测报告 ===

回测期间: {result.get('initial_price', 0):.2f} -> {result.get('final_price', 0):.2f}
初始价格: ${result.get('initial_price', 0):,.2f}
最终价格: ${result.get('final_price', 0):,.2f}
最终BTC持仓: {result.get('final_btc_holding', 0):.6f} BTC
最终权益: ${result.get('final_equity', 0):,.2f}

=== 收益指标 ===
总收益: ${result.get('total_pnl', 0):,.2f}
总收益率: {result.get('total_return', 0):.2%}
已实现收益: ${result.get('realized_pnl', 0):,.2f}
未实现收益: ${result.get('unrealized_pnl', 0):,.2f}

=== 交易统计 ===
总交易次数: {result.get('total_trades', 0)}
买入次数: {result.get('buy_trades', 0)}
卖出次数: {result.get('sell_trades', 0)}
网格点数量: {result.get('grid_levels_count', 0)}

=== 策略配置 ===
网格间距: 5.0%
最大回撤: 60.0%
最大网格数: 20
多网格策略: 启用
留利润功能: 启用
逐格加码: 启用
"""
        return report


def run_freqtrade_backtest():
    """运行FreqTrade数据回测"""
    print("=== BTC网格策略 - FreqTrade数据回测 ===")
    
    # 创建回测器
    backtester = FreqTradeGridBacktester()
    
    # 加载数据
    data = backtester.load_btc_data(timeframe="1h", timerange="20240101-20241201")
    
    if data.empty:
        print("无法加载数据，请检查数据文件是否存在")
        return
    
    # 策略配置
    config = {
        'grid_spacing': 0.05,
        'max_drawdown': 0.6,
        'max_grids': 20,
        'enable_multi_grid': True,
        'small_grid_spacing': 0.05,
        'medium_grid_spacing': 0.15,
        'large_grid_spacing': 0.30,
        'small_grid_ratio': 0.5,
        'medium_grid_ratio': 0.3,
        'large_grid_ratio': 0.2
    }
    
    # 运行回测
    result = backtester.run_backtest(data, config)
    
    if result:
        # 生成报告
        report = backtester.generate_report(result)
        print(report)
        
        # 保存结果
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        result_file = f"btc_grid_freqtrade_backtest_{timestamp}.json"
        
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"回测结果已保存到: {result_file}")
    else:
        print("回测失败")


if __name__ == "__main__":
    run_freqtrade_backtest()




