#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BTC网格策略 - 改进版本回测
解决单边上涨市场中表现差的问题
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime, timedelta
import json
import logging
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ImprovedGridBacktester:
    """改进的BTC网格策略回测器"""
    
    def __init__(self, data_dir: str = "E:/othercode/freqtrade/user_data/data"):
        self.data_dir = Path(data_dir)
        self.grid_levels = []
        self.trade_history = []
        self.current_position = {
            'total_btc': 0.0,
            'total_cost': 0.0,
            'unrealized_pnl': 0.0,
            'realized_pnl': 0.0
        }
        self.trend_direction = "neutral"  # neutral, bullish, bearish
        self.last_trend_check = None
        
    def load_btc_data(self, timeframe: str = "1h") -> pd.DataFrame:
        """直接加载BTC数据文件"""
        try:
            # 构建文件路径
            if timeframe == "1h":
                file_path = self.data_dir / "btcusdt-1h.feather"
            elif timeframe == "1d":
                file_path = self.data_dir / "btcusdt-1d.feather"
            elif timeframe == "4h":
                file_path = self.data_dir / "btcusdt-4h.feather"
            else:
                logger.error(f"不支持的时间框架: {timeframe}")
                return pd.DataFrame()
            
            if not file_path.exists():
                logger.error(f"数据文件不存在: {file_path}")
                return pd.DataFrame()
            
            logger.info(f"从 {file_path} 加载数据...")
            
            # 读取feather文件
            data = pd.read_feather(file_path)
            
            # 确保有正确的列名
            if 'date' in data.columns:
                data = data.set_index('date')
            elif 'timestamp' in data.columns:
                data = data.set_index('timestamp')
            
            # 确保有OHLCV列
            required_columns = ['open', 'high', 'low', 'close', 'volume']
            if not all(col in data.columns for col in required_columns):
                logger.error(f"数据文件缺少必要的列: {required_columns}")
                return pd.DataFrame()
            
            # 过滤2024年的数据
            data = data[data.index >= '2024-01-01']
            data = data[data.index < '2025-01-01']
            
            # 添加技术指标
            data = self._add_technical_indicators(data)
            
            logger.info(f"成功加载 {len(data)} 条数据记录")
            logger.info(f"数据时间范围: {data.index[0]} 到 {data.index[-1]}")
            logger.info(f"价格范围: ${data['close'].min():,.2f} - ${data['close'].max():,.2f}")
            
            return data
            
        except Exception as e:
            logger.error(f"加载数据失败: {e}")
            return pd.DataFrame()
    
    def _add_technical_indicators(self, data: pd.DataFrame) -> pd.DataFrame:
        """添加技术指标"""
        # 移动平均线
        data['sma_20'] = data['close'].rolling(window=20).mean()
        data['sma_50'] = data['close'].rolling(window=50).mean()
        data['sma_200'] = data['close'].rolling(window=200).mean()
        
        # RSI
        delta = data['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        data['rsi'] = 100 - (100 / (1 + rs))
        
        # 布林带
        data['bb_middle'] = data['close'].rolling(window=20).mean()
        bb_std = data['close'].rolling(window=20).std()
        data['bb_upper'] = data['bb_middle'] + (bb_std * 2)
        data['bb_lower'] = data['bb_middle'] - (bb_std * 2)
        
        # 趋势判断
        data['trend'] = 'neutral'
        data.loc[data['close'] > data['sma_20'], 'trend'] = 'bullish'
        data.loc[data['close'] < data['sma_20'], 'trend'] = 'bearish'
        
        return data
    
    def detect_trend(self, data: pd.DataFrame, current_idx: int) -> str:
        """检测当前趋势"""
        if current_idx < 50:  # 需要足够的数据
            return "neutral"
        
        # 获取最近的数据
        recent_data = data.iloc[max(0, current_idx-50):current_idx+1]
        
        # 多重趋势判断
        bullish_signals = 0
        bearish_signals = 0
        
        # 1. 价格与移动平均线的关系
        current_price = recent_data['close'].iloc[-1]
        sma_20 = recent_data['sma_20'].iloc[-1]
        sma_50 = recent_data['sma_50'].iloc[-1]
        
        if current_price > sma_20 > sma_50:
            bullish_signals += 2
        elif current_price < sma_20 < sma_50:
            bearish_signals += 2
        
        # 2. RSI判断
        rsi = recent_data['rsi'].iloc[-1]
        if rsi > 70:
            bearish_signals += 1  # 超买
        elif rsi < 30:
            bullish_signals += 1  # 超卖
        
        # 3. 价格动量
        price_change_20 = (current_price - recent_data['close'].iloc[-20]) / recent_data['close'].iloc[-20]
        if price_change_20 > 0.05:  # 20期涨幅超过5%
            bullish_signals += 1
        elif price_change_20 < -0.05:  # 20期跌幅超过5%
            bearish_signals += 1
        
        # 4. 布林带位置
        bb_upper = recent_data['bb_upper'].iloc[-1]
        bb_lower = recent_data['bb_lower'].iloc[-1]
        if current_price > bb_upper:
            bearish_signals += 1
        elif current_price < bb_lower:
            bullish_signals += 1
        
        # 综合判断
        if bullish_signals >= 3:
            return "bullish"
        elif bearish_signals >= 3:
            return "bearish"
        else:
            return "neutral"
    
    def generate_adaptive_grid_levels(self, initial_price: float, config: Dict[str, Any], trend: str) -> List[Dict]:
        """根据趋势生成自适应网格"""
        levels = []
        
        if trend == "bullish":
            # 牛市：减少卖出网格，增加买入网格
            levels.extend(self._generate_bullish_grid(initial_price, config))
        elif trend == "bearish":
            # 熊市：减少买入网格，增加卖出网格
            levels.extend(self._generate_bearish_grid(initial_price, config))
        else:
            # 震荡市：使用标准网格
            levels.extend(self._generate_neutral_grid(initial_price, config))
        
        return sorted(levels, key=lambda x: x['price'])
    
    def _generate_bullish_grid(self, initial_price: float, config: Dict[str, Any]) -> List[Dict]:
        """牛市网格：更多买入，更少卖出"""
        levels = []
        grid_spacing = config.get('grid_spacing', 0.05)
        max_drawdown = config.get('max_drawdown', 0.6)
        max_grids = config.get('max_grids', 20)
        
        # 生成更多买入网格
        for i in range(max_grids * 2):
            buy_price = initial_price * (1 - grid_spacing * (i + 1))
            if buy_price <= initial_price * (1 - max_drawdown):
                break
                
            levels.append({
                'price': buy_price,
                'amount': 0.01,
                'action': 'buy',
                'level': i + 1,
                'grid_type': 'bullish_buy'
            })
        
        # 生成较少卖出网格，且价格更高
        for i in range(max_grids // 2):
            sell_price = initial_price * (1 + grid_spacing * 2 * (i + 1))  # 更大的间距
            levels.append({
                'price': sell_price,
                'amount': 0.01,
                'action': 'sell',
                'level': i + 1,
                'grid_type': 'bullish_sell'
            })
        
        return levels
    
    def _generate_bearish_grid(self, initial_price: float, config: Dict[str, Any]) -> List[Dict]:
        """熊市网格：更少买入，更多卖出"""
        levels = []
        grid_spacing = config.get('grid_spacing', 0.05)
        max_drawdown = config.get('max_drawdown', 0.6)
        max_grids = config.get('max_grids', 20)
        
        # 生成较少买入网格
        for i in range(max_grids // 2):
            buy_price = initial_price * (1 - grid_spacing * (i + 1))
            if buy_price <= initial_price * (1 - max_drawdown):
                break
                
            levels.append({
                'price': buy_price,
                'amount': 0.01,
                'action': 'buy',
                'level': i + 1,
                'grid_type': 'bearish_buy'
            })
        
        # 生成更多卖出网格
        for i in range(max_grids * 2):
            sell_price = initial_price * (1 + grid_spacing * (i + 1))
            levels.append({
                'price': sell_price,
                'amount': 0.01,
                'action': 'sell',
                'level': i + 1,
                'grid_type': 'bearish_sell'
            })
        
        return levels
    
    def _generate_neutral_grid(self, initial_price: float, config: Dict[str, Any]) -> List[Dict]:
        """震荡市网格：标准网格"""
        levels = []
        grid_spacing = config.get('grid_spacing', 0.05)
        max_drawdown = config.get('max_drawdown', 0.6)
        max_grids = config.get('max_grids', 20)
        
        # 标准买入网格
        for i in range(max_grids):
            buy_price = initial_price * (1 - grid_spacing * (i + 1))
            if buy_price <= initial_price * (1 - max_drawdown):
                break
                
            levels.append({
                'price': buy_price,
                'amount': 0.01,
                'action': 'buy',
                'level': i + 1,
                'grid_type': 'neutral'
            })
        
        # 标准卖出网格
        for i in range(max_grids):
            sell_price = initial_price * (1 + grid_spacing * (i + 1))
            levels.append({
                'price': sell_price,
                'amount': 0.01,
                'action': 'sell',
                'level': i + 1,
                'grid_type': 'neutral'
            })
        
        return levels
    
    def get_trading_signals(self, current_price: float, trend: str) -> List[Dict]:
        """获取交易信号，考虑趋势"""
        signals = []
        
        for level in self.grid_levels:
            should_trade = False
            
            if level['action'] == 'buy' and current_price <= level['price']:
                # 买入信号：在牛市中更积极，在熊市中更保守
                if trend == "bullish":
                    should_trade = True
                elif trend == "bearish":
                    # 熊市中只在价格大幅下跌时买入
                    if current_price <= level['price'] * 0.95:  # 额外5%的折扣
                        should_trade = True
                else:  # neutral
                    should_trade = True
                    
            elif level['action'] == 'sell' and current_price >= level['price']:
                # 卖出信号：在牛市中更保守，在熊市中更积极
                if trend == "bullish":
                    # 牛市中只在价格大幅上涨时卖出
                    if current_price >= level['price'] * 1.05:  # 额外5%的溢价
                        should_trade = True
                elif trend == "bearish":
                    should_trade = True
                else:  # neutral
                    should_trade = True
            
            if should_trade:
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
            if self.current_position['total_btc'] > 0:
                avg_cost = self.current_position['total_cost'] / self.current_position['total_btc']
                profit = revenue - (signal['amount'] * avg_cost)
                self.current_position['realized_pnl'] += profit
                self.current_position['total_btc'] -= signal['amount']
                self.current_position['total_cost'] -= signal['amount'] * avg_cost
            trade_record['revenue'] = revenue
        
        self.trade_history.append(trade_record)
        return trade_record
    
    def run_backtest(self, data: pd.DataFrame, config: Dict[str, Any]) -> Dict[str, Any]:
        """运行改进的回测"""
        if data.empty:
            logger.error("没有数据可以回测")
            return {}
        
        logger.info("开始改进的回测...")
        
        # 初始化
        initial_price = data['close'].iloc[0]
        self.trade_history = []
        self.current_position = {
            'total_btc': 0.0,
            'total_cost': 0.0,
            'unrealized_pnl': 0.0,
            'realized_pnl': 0.0
        }
        
        # 动态调整网格
        grid_update_frequency = 24  # 每24小时更新一次网格
        
        for i, (idx, row) in enumerate(data.iterrows()):
            current_price = row['close']
            current_time = idx
            
            # 定期更新网格
            if i % grid_update_frequency == 0 or self.grid_levels == []:
                trend = self.detect_trend(data, i)
                self.grid_levels = self.generate_adaptive_grid_levels(current_price, config, trend)
                logger.info(f"更新网格: 趋势={trend}, 网格数={len(self.grid_levels)}")
            
            # 获取交易信号
            trend = self.detect_trend(data, i)
            signals = self.get_trading_signals(current_price, trend)
            
            # 执行交易
            for signal in signals:
                self.execute_trade(current_time, current_price, signal)
        
        # 计算最终结果
        final_price = data['close'].iloc[-1]
        final_btc = self.current_position['total_btc']
        
        # 计算未实现收益
        if final_btc > 0 and self.current_position['total_cost'] > 0:
            avg_cost = self.current_position['total_cost'] / final_btc
            self.current_position['unrealized_pnl'] = final_btc * (final_price - avg_cost)
        
        total_pnl = self.current_position['realized_pnl'] + self.current_position['unrealized_pnl']
        total_return = total_pnl / 100000  # 假设初始资金10万
        
        # 计算最大回撤
        equity_curve = []
        current_equity = 100000  # 初始资金
        max_equity = current_equity
        max_drawdown = 0
        
        for trade in self.trade_history:
            if trade['action'] == 'buy':
                current_equity -= trade.get('cost', 0)
            else:
                current_equity += trade.get('revenue', 0)
            
            if current_equity > max_equity:
                max_equity = current_equity
            
            drawdown = (max_equity - current_equity) / max_equity
            if drawdown > max_drawdown:
                max_drawdown = drawdown
            
            equity_curve.append(current_equity)
        
        result = {
            'initial_price': initial_price,
            'final_price': final_price,
            'price_change': (final_price - initial_price) / initial_price,
            'total_trades': len(self.trade_history),
            'buy_trades': len([t for t in self.trade_history if t['action'] == 'buy']),
            'sell_trades': len([t for t in self.trade_history if t['action'] == 'sell']),
            'realized_pnl': self.current_position['realized_pnl'],
            'unrealized_pnl': self.current_position['unrealized_pnl'],
            'total_pnl': total_pnl,
            'total_return': total_return,
            'max_drawdown': max_drawdown,
            'final_btc_holding': final_btc,
            'grid_levels_count': len(self.grid_levels),
            'equity_curve': equity_curve,
            'trade_history': self.trade_history
        }
        
        logger.info("改进的回测完成")
        return result
    
    def generate_report(self, result: Dict[str, Any]) -> str:
        """生成回测报告"""
        report = f"""
=== BTC改进网格策略回测报告 ===

回测期间: 2024年全年
初始价格: ${result.get('initial_price', 0):,.2f}
最终价格: ${result.get('final_price', 0):,.2f}
价格变化: {result.get('price_change', 0):.2%}
最终BTC持仓: {result.get('final_btc_holding', 0):.6f} BTC

=== 收益指标 ===
总收益: ${result.get('total_pnl', 0):,.2f}
总收益率: {result.get('total_return', 0):.2%}
已实现收益: ${result.get('realized_pnl', 0):,.2f}
未实现收益: ${result.get('unrealized_pnl', 0):,.2f}
最大回撤: {result.get('max_drawdown', 0):.2%}

=== 交易统计 ===
总交易次数: {result.get('total_trades', 0)}
买入次数: {result.get('buy_trades', 0)}
卖出次数: {result.get('sell_trades', 0)}
买卖比例: {result.get('buy_trades', 0)}:{result.get('sell_trades', 0)}

=== 策略改进 ===
✓ 动态趋势检测
✓ 自适应网格调整
✓ 牛市减少卖出，增加买入
✓ 熊市减少买入，增加卖出
✓ 震荡市使用标准网格
"""
        return report


def run_improved_backtest():
    """运行改进的回测"""
    print("=== BTC改进网格策略回测 ===")
    
    # 创建回测器
    backtester = ImprovedGridBacktester()
    
    # 加载数据
    data = backtester.load_btc_data(timeframe="1h")
    
    if data.empty:
        print("无法加载数据，请检查数据文件是否存在")
        return
    
    # 策略配置
    config = {
        'grid_spacing': 0.05,
        'max_drawdown': 0.6,
        'max_grids': 20,
    }
    
    # 运行回测
    result = backtester.run_backtest(data, config)
    
    if result:
        # 生成报告
        report = backtester.generate_report(result)
        print(report)
        
        # 保存结果
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        result_file = f"btc_grid_improved_backtest_{timestamp}.json"
        
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"回测结果已保存到: {result_file}")
        
        # 显示一些交易记录
        if result['trade_history']:
            print("\n=== 前10笔交易记录 ===")
            for i, trade in enumerate(result['trade_history'][:10]):
                print(f"{i+1}. {trade['timestamp']} {trade['action']} {trade['amount']:.4f} BTC @ ${trade['price']:,.2f} ({trade['grid_type']})")
    else:
        print("回测失败")


if __name__ == "__main__":
    run_improved_backtest()
