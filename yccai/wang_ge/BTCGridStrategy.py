#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BTC网格策略 - FreqTrade版本
基于ETF拯救世界的网格策略思路，适用于比特币的网格交易策略
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass
from freqtrade.strategy import IStrategy, DecimalParameter, IntParameter, BooleanParameter
from freqtrade.strategy.parameters import CategoricalParameter
import talib.abstract as ta
from pandas import DataFrame

logger = logging.getLogger(__name__)


@dataclass
class GridLevel:
    """网格层级配置"""
    price: float
    amount: float
    action: str  # 'buy' or 'sell'
    level: int
    grid_type: str  # 'small', 'medium', 'large'


class BTCGridStrategy(IStrategy):
    """
    BTC网格策略 - FreqTrade版本
    
    核心原则：
    1. 只做不会死的品种（BTC作为数字黄金，符合条件）
    2. 压力测试是最重要的
    3. 低买高卖，吃波动利润
    4. 长短策略结合
    """
    
    # 策略接口版本
    INTERFACE_VERSION = 3
    
    # 策略参数
    timeframe = '1h'  # 使用1小时时间框架
    
    # 可优化的超参数
    grid_spacing = DecimalParameter(0.03, 0.12, default=0.05, space="buy", optimize=True)
    max_drawdown = DecimalParameter(0.3, 0.8, default=0.6, space="buy", optimize=True)
    max_grids = IntParameter(10, 30, default=20, space="buy", optimize=True)
    
    # 2.0版本参数
    enable_profit_retention = BooleanParameter(default=True, space="buy", optimize=True)
    enable_progressive_betting = BooleanParameter(default=True, space="buy", optimize=True)
    enable_multi_grid = BooleanParameter(default=True, space="buy", optimize=True)
    
    # 多网格参数
    small_grid_spacing = DecimalParameter(0.03, 0.08, default=0.05, space="buy", optimize=True)
    medium_grid_spacing = DecimalParameter(0.10, 0.25, default=0.15, space="buy", optimize=True)
    large_grid_spacing = DecimalParameter(0.20, 0.50, default=0.30, space="buy", optimize=True)
    
    # 资金分配参数
    small_grid_ratio = DecimalParameter(0.3, 0.7, default=0.5, space="buy", optimize=True)
    medium_grid_ratio = DecimalParameter(0.1, 0.4, default=0.3, space="buy", optimize=True)
    large_grid_ratio = DecimalParameter(0.1, 0.3, default=0.2, space="buy", optimize=True)
    
    # 高级参数
    profit_retention_ratio = DecimalParameter(0.2, 0.8, default=0.5, space="buy", optimize=True)
    progressive_betting_ratio = DecimalParameter(0.02, 0.10, default=0.05, space="buy", optimize=True)
    min_profit_threshold = DecimalParameter(0.03, 0.08, default=0.05, space="buy", optimize=True)
    max_position_ratio = DecimalParameter(0.6, 0.9, default=0.8, space="buy", optimize=True)
    
    # 策略配置
    can_short = False  # 不做空
    startup_candle_count = 30  # 启动蜡烛数量
    
    # 风险控制
    stoploss = -0.8  # 最大止损80%
    trailing_stop = False
    
    # 仓位管理
    position_adjustment_enable = True
    max_entry_position_adjustment = 10
    
    def __init__(self, config: dict) -> None:
        super().__init__(config)
        self.grid_levels: List[GridLevel] = []
        self.initial_price = None
        self.current_position = {
            'total_btc': 0.0,
            'total_cost': 0.0,
            'unrealized_pnl': 0.0,
            'realized_pnl': 0.0
        }
        
    def informative_pairs(self):
        """
        定义需要的数据对
        """
        pairs = self.dp.current_whitelist()
        informative_pairs = []
        for pair in pairs:
            informative_pairs.append((pair, self.timeframe))
        return informative_pairs
    
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        填充指标
        """
        # 基础价格指标
        dataframe['sma_20'] = ta.SMA(dataframe, timeperiod=20)
        dataframe['sma_50'] = ta.SMA(dataframe, timeperiod=50)
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=14)
        
        # 波动率指标
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        dataframe['volatility'] = dataframe['atr'] / dataframe['close']
        
        # 网格相关指标
        dataframe['price_change'] = dataframe['close'].pct_change()
        dataframe['price_volatility'] = dataframe['price_change'].rolling(window=20).std()
        
        return dataframe
    
    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        填充买入信号
        """
        # 初始化网格
        if self.initial_price is None:
            self.initial_price = dataframe['close'].iloc[0]
            self.generate_grid_levels()
        
        # 生成买入信号
        dataframe.loc[:, 'enter_long'] = 0
        
        for idx, row in dataframe.iterrows():
            current_price = row['close']
            signals = self.get_buy_signals(current_price)
            
            if signals:
                dataframe.loc[idx, 'enter_long'] = 1
        
        return dataframe
    
    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        填充卖出信号
        """
        dataframe.loc[:, 'exit_long'] = 0
        
        for idx, row in dataframe.iterrows():
            current_price = row['close']
            signals = self.get_sell_signals(current_price)
            
            if signals:
                dataframe.loc[idx, 'exit_long'] = 1
        
        return dataframe
    
    def generate_grid_levels(self):
        """生成网格层级"""
        self.grid_levels = []
        
        if self.enable_multi_grid.value:
            # 多网格策略
            self.grid_levels.extend(self._generate_small_grid())
            self.grid_levels.extend(self._generate_medium_grid())
            self.grid_levels.extend(self._generate_large_grid())
        else:
            # 单网格策略
            self.grid_levels.extend(self._generate_single_grid())
            
        self.grid_levels = sorted(self.grid_levels, key=lambda x: x.price)
        logger.info(f"生成了{len(self.grid_levels)}个网格点")
    
    def _generate_single_grid(self) -> List[GridLevel]:
        """生成单网格"""
        levels = []
        current_price = self.initial_price
        
        # 生成买入网格
        for i in range(self.max_grids.value):
            buy_price = current_price * (1 - self.grid_spacing.value * (i + 1))
            if buy_price <= current_price * (1 - self.max_drawdown.value):
                break
                
            amount = 0.01  # 固定数量，实际应该根据资金计算
            levels.append(GridLevel(
                price=buy_price,
                amount=amount,
                action='buy',
                level=i + 1,
                grid_type='single'
            ))
        
        # 生成卖出网格
        for i in range(self.max_grids.value):
            sell_price = current_price * (1 + self.grid_spacing.value * (i + 1))
            amount = 0.01
            levels.append(GridLevel(
                price=sell_price,
                amount=amount,
                action='sell',
                level=i + 1,
                grid_type='single'
            ))
            
        return levels
    
    def _generate_small_grid(self) -> List[GridLevel]:
        """生成小网格"""
        levels = []
        current_price = self.initial_price
        
        # 生成买入网格
        for i in range(self.max_grids.value):
            buy_price = current_price * (1 - self.small_grid_spacing.value * (i + 1))
            if buy_price <= current_price * (1 - self.max_drawdown.value):
                break
                
            amount = 0.01 * self.small_grid_ratio.value
            levels.append(GridLevel(
                price=buy_price,
                amount=amount,
                action='buy',
                level=i + 1,
                grid_type='small'
            ))
        
        # 生成卖出网格
        for i in range(self.max_grids.value):
            sell_price = current_price * (1 + self.small_grid_spacing.value * (i + 1))
            amount = 0.01 * self.small_grid_ratio.value
            levels.append(GridLevel(
                price=sell_price,
                amount=amount,
                action='sell',
                level=i + 1,
                grid_type='small'
            ))
            
        return levels
    
    def _generate_medium_grid(self) -> List[GridLevel]:
        """生成中网格"""
        levels = []
        current_price = self.initial_price
        
        # 生成买入网格
        for i in range(self.max_grids.value // 2):
            buy_price = current_price * (1 - self.medium_grid_spacing.value * (i + 1))
            if buy_price <= current_price * (1 - self.max_drawdown.value):
                break
                
            amount = 0.01 * self.medium_grid_ratio.value
            levels.append(GridLevel(
                price=buy_price,
                amount=amount,
                action='buy',
                level=i + 1,
                grid_type='medium'
            ))
        
        # 生成卖出网格
        for i in range(self.max_grids.value // 2):
            sell_price = current_price * (1 + self.medium_grid_spacing.value * (i + 1))
            amount = 0.01 * self.medium_grid_ratio.value
            levels.append(GridLevel(
                price=sell_price,
                amount=amount,
                action='sell',
                level=i + 1,
                grid_type='medium'
            ))
            
        return levels
    
    def _generate_large_grid(self) -> List[GridLevel]:
        """生成大网格"""
        levels = []
        current_price = self.initial_price
        
        # 生成买入网格
        for i in range(self.max_grids.value // 3):
            buy_price = current_price * (1 - self.large_grid_spacing.value * (i + 1))
            if buy_price <= current_price * (1 - self.max_drawdown.value):
                break
                
            amount = 0.01 * self.large_grid_ratio.value
            levels.append(GridLevel(
                price=buy_price,
                amount=amount,
                action='buy',
                level=i + 1,
                grid_type='large'
            ))
        
        # 生成卖出网格
        for i in range(self.max_grids.value // 3):
            sell_price = current_price * (1 + self.large_grid_spacing.value * (i + 1))
            amount = 0.01 * self.large_grid_ratio.value
            levels.append(GridLevel(
                price=sell_price,
                amount=amount,
                action='sell',
                level=i + 1,
                grid_type='large'
            ))
            
        return levels
    
    def get_buy_signals(self, current_price: float) -> List[GridLevel]:
        """获取买入信号"""
        signals = []
        for level in self.grid_levels:
            if level.action == 'buy' and current_price <= level.price:
                signals.append(level)
        return signals
    
    def get_sell_signals(self, current_price: float) -> List[GridLevel]:
        """获取卖出信号"""
        signals = []
        for level in self.grid_levels:
            if level.action == 'sell' and current_price >= level.price:
                signals.append(level)
        return signals
    
    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                          proposed_stake: float, min_stake: float, max_stake: float,
                          leverage: float, entry_tag: str, side: str, **kwargs) -> float:
        """
        自定义仓位大小
        """
        # 根据网格层级调整仓位大小
        if entry_tag and 'grid' in entry_tag:
            # 从entry_tag中提取网格信息
            try:
                grid_info = entry_tag.split('_')
                if len(grid_info) >= 3:
                    grid_type = grid_info[1]
                    level = int(grid_info[2])
                    
                    # 根据网格类型和层级调整仓位
                    if grid_type == 'small':
                        return proposed_stake * 0.5
                    elif grid_type == 'medium':
                        return proposed_stake * 0.3
                    elif grid_type == 'large':
                        return proposed_stake * 0.2
            except:
                pass
        
        return proposed_stake
    
    def custom_exit(self, pair: str, trade, current_time: datetime, current_rate: float,
                   current_profit: float, **kwargs) -> Optional[Union[str, bool]]:
        """
        自定义退出逻辑
        """
        # 2.0版本：留利润功能
        if self.enable_profit_retention.value and current_profit > self.min_profit_threshold.value:
            # 保留部分利润
            if current_profit > self.profit_retention_ratio.value:
                return 'profit_retention'
        
        return None
    
    def confirm_trade_entry(self, pair: str, order_type: str, amount: float, rate: float,
                          time_in_force: str, current_time: datetime, entry_tag: str,
                          side: str, **kwargs) -> bool:
        """
        确认交易入场
        """
        # 压力测试检查
        if self.initial_price:
            current_drawdown = (self.initial_price - rate) / self.initial_price
            if current_drawdown > self.max_drawdown.value:
                logger.warning(f"价格回撤{current_drawdown:.2%}超过最大回撤限制{self.max_drawdown.value:.2%}")
                return False
        
        return True
    
    def confirm_trade_exit(self, pair: str, trade, order_type: str, amount: float,
                         rate: float, time_in_force: str, exit_reason: str,
                         current_time: datetime, **kwargs) -> bool:
        """
        确认交易出场
        """
        return True
    
    def leverage(self, pair: str, current_time: datetime, current_rate: float,
                proposed_leverage: float, max_leverage: float, entry_tag: str,
                side: str, **kwargs) -> float:
        """
        杠杆设置
        """
        # 网格策略通常不使用杠杆
        return 1.0

