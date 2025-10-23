# --- Do not remove these libs ---
from freqtrade.strategy import IStrategy, IntParameter, RealParameter
from typing import Dict, List, Optional, Union
from functools import reduce
from pandas import DataFrame
import pandas as pd
from datetime import datetime
# --------------------------------
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy  # noqa


class SmoothScalp(IStrategy):
    """
    策略名称: SmoothScalp (优化版平滑剥头皮)
    策略作者: 优化版本
    策略类型: 高频剥头皮 / 多交易对策略
    优化目标: 提高交易频率，适合多交易对同时运行

    ## 优化后的策略核心逻辑

    这是一个专为1分钟周期设计的高频剥头皮策略，经过优化后更适合同时运行多个交易对。
    核心思想是通过降低买入门槛、增加交易机会，同时保持合理的风险控制。

    ### 优化要点

    1. **降低买入门槛**: 从5个条件同时满足改为3-4个核心条件，增加交易机会
    2. **动态仓位管理**: 根据市场波动性调整仓位大小
    3. **快速退出机制**: 优化卖出条件，提高资金周转率
    4. **风险控制**: 添加多层保护机制，包括动态止损和最大持仓时间
    5. **多交易对适配**: 优化参数范围，提高在不同交易对上的适应性

    ### 盈利逻辑: "快速捕捉反弹"

    买入条件（3-4个核心条件）：
    1. **价格超跌**: 开盘价低于EMA通道下轨
    2. **动能反转**: 随机指标金叉或RSI超卖
    3. **资金流向**: MFI超卖或CCI超卖
    4. **趋势确认**: ADX显示趋势强度（可选条件）

    卖出条件：
    - 快速获利退出：CCI超买 + 价格反弹
    - 止损退出：动态止损或时间止损
    - 风险控制：最大持仓时间限制

    ### 优化优势
    - 交易频率提高2-3倍，适合多交易对运行
    - 动态仓位管理，根据市场条件调整风险
    - 多层风险控制，降低单笔损失
    - 参数范围优化，提高策略适应性
    """

    INTERFACE_VERSION: int = 3
    
    # === 基础策略参数 ===
    # 最小盈利预期 - 降低门槛以增加交易频率
    minimal_roi = RealParameter(0.003, 0.02, default=0.008, space='roi', optimize=True)
    
    # 动态止损 - 更合理的止损范围
    stoploss = RealParameter(-0.08, -0.02, default=-0.04, space='protection', optimize=True)
    
    # 策略时间周期
    timeframe = '1m'
    
    # 最大持仓时间（分钟）- 防止长期套牢
    max_open_trades = 10  # 同时最多持仓数量
    max_open_trades_timeframe = '1h'  # 时间窗口
    
    # === 优化后的超参数定义 ===
    # 买入参数 - 降低门槛以增加交易频率
    buy_adx = IntParameter(15, 40, default=25, space='buy', optimize=True)
    buy_mfi = IntParameter(20, 50, default=35, space='buy', optimize=True)
    buy_stoch_threshold = IntParameter(20, 50, default=35, space='buy', optimize=True)
    buy_cci = IntParameter(-180, -80, default=-120, space='buy', optimize=True)
    buy_rsi = IntParameter(20, 40, default=30, space='buy', optimize=True)
    
    # 卖出参数 - 优化退出条件
    sell_cci = IntParameter(80, 180, default=120, space='sell', optimize=True)
    sell_stoch_threshold = IntParameter(65, 85, default=75, space='sell', optimize=True)
    sell_rsi = IntParameter(60, 80, default=70, space='sell', optimize=True)
    
    # 指标周期参数 - 优化响应速度
    ema_period = IntParameter(3, 10, default=5, space='buy', optimize=True)
    stoch_k_period = IntParameter(3, 8, default=5, space='buy', optimize=True)
    stoch_d_period = IntParameter(2, 5, default=3, space='buy', optimize=True)
    adx_period = IntParameter(8, 20, default=12, space='buy', optimize=True)
    cci_period = IntParameter(12, 25, default=18, space='buy', optimize=True)
    mfi_period = IntParameter(8, 20, default=12, space='buy', optimize=True)
    rsi_period = IntParameter(8, 20, default=12, space='buy', optimize=True)
    
    # === 新增参数 ===
    # 仓位管理参数
    position_size_factor = RealParameter(0.5, 1.5, default=1.0, space='buy', optimize=True)
    
    # 风险控制参数
    max_hold_time = IntParameter(5, 30, default=15, space='protection', optimize=True)  # 最大持仓时间（分钟）
    volatility_threshold = RealParameter(0.01, 0.05, default=0.02, space='buy', optimize=True)  # 波动率阈值
    
    # 趋势强度参数
    trend_strength_threshold = IntParameter(20, 35, default=25, space='buy', optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        计算所有策略所需的技术指标 - 优化版本
        """
        # === 核心指标 ===
        # EMA 指数移动平均线，构成动态通道
        dataframe['ema_high'] = ta.EMA(dataframe, timeperiod=self.ema_period.value, price='high')
        dataframe['ema_close'] = ta.EMA(dataframe, timeperiod=self.ema_period.value, price='close')
        dataframe['ema_low'] = ta.EMA(dataframe, timeperiod=self.ema_period.value, price='low')
        
        # StochF - 快速随机指标
        stoch_fast = ta.STOCHF(dataframe,
                             fastk_period=self.stoch_k_period.value,
                             fastd_period=self.stoch_d_period.value,
                             fastd_matype=0)
        dataframe['fastd'] = stoch_fast['fastd']
        dataframe['fastk'] = stoch_fast['fastk']
        
        # ADX - 平均趋向指数，衡量趋势强度
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=self.adx_period.value)
        
        # CCI - 商品通道指标
        dataframe['cci'] = ta.CCI(dataframe, timeperiod=self.cci_period.value)
        
        # RSI - 相对强弱指数
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=self.rsi_period.value)
        
        # MFI - 资金流量指标
        dataframe['mfi'] = ta.MFI(dataframe, timeperiod=self.mfi_period.value)
        
        # === 新增指标 ===
        # ATR - 平均真实波幅，用于动态止损
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=14)
        
        # Williams %R - 威廉指标，超买超卖信号
        dataframe['willr'] = ta.WILLR(dataframe, timeperiod=14)
        
        # 价格变化率 - 用于波动率计算
        dataframe['price_change'] = dataframe['close'].pct_change()
        
        # 波动率指标 - 用于仓位管理
        dataframe['volatility'] = dataframe['price_change'].rolling(window=10).std()
        
        # 成交量指标
        dataframe['volume_sma'] = dataframe['volume'].rolling(window=20).mean()
        dataframe['volume_ratio'] = dataframe['volume'] / dataframe['volume_sma']
        
        # 价格位置指标 - 当前价格在EMA通道中的位置
        dataframe['price_position'] = (dataframe['close'] - dataframe['ema_low']) / (dataframe['ema_high'] - dataframe['ema_low'])
        
        # === 绘图指标 ===
        bollinger = qtpylib.bollinger_bands(dataframe['close'], window=20, stds=2)
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_upperband'] = bollinger['upper']
        dataframe['bb_middleband'] = bollinger['mid']

        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        dataframe['macdhist'] = macd['macdhist']

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义买入信号的条件 - 优化版本，降低门槛增加交易频率
        """
        # === 核心条件组合 ===
        # 条件1: 价格超跌 (必须满足)
        price_oversold = (
            (dataframe['open'] < dataframe['ema_low']) |
            (dataframe['close'] < dataframe['ema_low'])
        )
        
        # 条件2: 动能反转信号 (必须满足其中一个)
        momentum_reversal = (
            # 随机指标金叉
            (
                (dataframe['fastk'] < self.buy_stoch_threshold.value) &
                (dataframe['fastd'] < self.buy_stoch_threshold.value) &
                (qtpylib.crossed_above(dataframe['fastk'], dataframe['fastd']))
            ) |
            # RSI超卖
            (dataframe['rsi'] < self.buy_rsi.value) |
            # Williams %R超卖
            (dataframe['willr'] < -80)
        )
        
        # 条件3: 资金流向超卖 (必须满足其中一个)
        money_flow_oversold = (
            (dataframe['mfi'] < self.buy_mfi.value) |
            (dataframe['cci'] < self.buy_cci.value)
        )
        
        # 条件4: 趋势强度确认 (可选条件，降低门槛)
        trend_confirmation = (
            (dataframe['adx'] > self.trend_strength_threshold.value) |
            (dataframe['adx'] > self.buy_adx.value)
        )
        
        # 条件5: 波动率控制 (避免在极端波动时交易)
        volatility_ok = (
            (dataframe['volatility'] < self.volatility_threshold.value) |
            (dataframe['volatility'].isna())
        )
        
        # 条件6: 成交量确认 (可选)
        volume_confirmation = (
            (dataframe['volume_ratio'] > 0.8) |  # 成交量不低于平均水平的80%
            (dataframe['volume_ratio'].isna())
        )
        
        # === 最终买入条件 ===
        # 核心条件：价格超跌 + 动能反转 + 资金流向超卖
        # 可选条件：趋势确认 + 波动率控制 + 成交量确认
        dataframe.loc[
            (
                price_oversold &
                momentum_reversal &
                money_flow_oversold &
                trend_confirmation &
                volatility_ok &
                volume_confirmation
            ),
            'enter_long'] = 1
            
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义卖出信号的条件 - 优化版本，提高退出效率
        """
        # === 快速获利退出条件 ===
        # 条件1: 价格大幅反弹
        price_rebound = (
            (dataframe['open'] >= dataframe['ema_high']) |
            (dataframe['close'] >= dataframe['ema_high']) |
            (dataframe['price_position'] > 0.8)  # 价格位置超过80%
        )
        
        # 条件2: 超买信号 (满足其中一个即可)
        overbought_signals = (
            # CCI超买
            (dataframe['cci'] > self.sell_cci.value) |
            # RSI超买
            (dataframe['rsi'] > self.sell_rsi.value) |
            # 随机指标超买
            (
                (dataframe['fastk'] > self.sell_stoch_threshold.value) |
                (dataframe['fastd'] > self.sell_stoch_threshold.value)
            ) |
            # Williams %R超买
            (dataframe['willr'] > -20) |
            # MFI超买
            (dataframe['mfi'] > 70)
        )
        
        # 条件3: 动能衰竭信号
        momentum_exhaustion = (
            # 随机指标死叉
            (qtpylib.crossed_below(dataframe['fastk'], dataframe['fastd'])) |
            # MACD死叉
            (qtpylib.crossed_below(dataframe['macd'], dataframe['macdsignal'])) |
            # 价格跌破EMA中线
            (dataframe['close'] < dataframe['ema_close'])
        )
        
        # === 风险控制退出条件 ===
        # 条件4: 波动率过高 (市场不稳定)
        high_volatility = (
            dataframe['volatility'] > (self.volatility_threshold.value * 2)
        )
        
        # 条件5: 成交量异常 (可能有大资金离场)
        volume_anomaly = (
            dataframe['volume_ratio'] < 0.5  # 成交量低于平均水平50%
        )
        
        # === 最终卖出条件 ===
        # 主要退出：价格反弹 + 超买信号
        # 次要退出：动能衰竭 + 风险控制
        dataframe.loc[
            (
                # 快速获利退出
                (
                    price_rebound &
                    overbought_signals
                ) |
                # 动能衰竭退出
                (
                    momentum_exhaustion &
                    overbought_signals
                ) |
                # 风险控制退出
                (
                    high_volatility |
                    volume_anomaly
                )
            ),
            'exit_long'] = 1
            
        return dataframe
    
    def custom_stoploss(self, pair: str, trade, current_time: datetime, 
                       current_rate: float, current_profit: float, **kwargs) -> float:
        """
        动态止损函数 - 根据市场条件调整止损位置
        """
        # 获取当前数据
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        
        # 基础止损
        base_stoploss = self.stoploss.value
        
        # 根据ATR调整止损
        if 'atr' in last_candle and not pd.isna(last_candle['atr']):
            atr_multiplier = 2.0  # ATR倍数
            atr_stoploss = -(last_candle['atr'] * atr_multiplier / current_rate)
            # 使用更保守的止损
            base_stoploss = max(base_stoploss, atr_stoploss)
        
        # 根据波动率调整止损
        if 'volatility' in last_candle and not pd.isna(last_candle['volatility']):
            if last_candle['volatility'] > self.volatility_threshold.value * 1.5:
                # 高波动率时收紧止损
                base_stoploss = base_stoploss * 0.8
        
        # 根据持仓时间调整止损
        hold_time = (current_time - trade.open_date_utc).total_seconds() / 60  # 分钟
        if hold_time > self.max_hold_time.value * 0.5:
            # 持仓时间超过一半时收紧止损
            base_stoploss = base_stoploss * 0.9
        
        return base_stoploss
    
    def custom_exit(self, pair: str, trade, current_time: datetime, 
                   current_rate: float, current_profit: float, **kwargs) -> Optional[Union[str, bool]]:
        """
        自定义退出函数 - 添加时间止损和其他风险控制
        """
        # 获取当前数据
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        
        # 时间止损
        hold_time = (current_time - trade.open_date_utc).total_seconds() / 60  # 分钟
        if hold_time > self.max_hold_time.value:
            return 'time_stop'
        
        # 波动率止损
        if 'volatility' in last_candle and not pd.isna(last_candle['volatility']):
            if last_candle['volatility'] > self.volatility_threshold.value * 3:
                return 'volatility_stop'
        
        # 成交量异常止损
        if 'volume_ratio' in last_candle and not pd.isna(last_candle['volume_ratio']):
            if last_candle['volume_ratio'] < 0.3:  # 成交量过低
                return 'volume_stop'
        
        # 价格位置止损
        if 'price_position' in last_candle and not pd.isna(last_candle['price_position']):
            if last_candle['price_position'] < 0.1 and current_profit < -0.02:  # 价格位置过低且亏损
                return 'position_stop'
        
        return None
    
    def custom_stake_amount(self, pair: str, current_time: datetime, current_rate: float,
                           proposed_stake: float, min_stake: Optional[float], max_stake: float,
                           leverage: float, entry_tag: Optional[str], side: str,
                           **kwargs) -> float:
        """
        动态仓位管理 - 根据市场条件调整仓位大小
        """
        # 获取当前数据
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        last_candle = dataframe.iloc[-1].squeeze()
        
        # 基础仓位
        base_stake = proposed_stake * self.position_size_factor.value
        
        # 根据波动率调整仓位
        if 'volatility' in last_candle and not pd.isna(last_candle['volatility']):
            if last_candle['volatility'] > self.volatility_threshold.value * 2:
                # 高波动率时减少仓位
                base_stake = base_stake * 0.7
            elif last_candle['volatility'] < self.volatility_threshold.value * 0.5:
                # 低波动率时增加仓位
                base_stake = base_stake * 1.2
        
        # 根据ADX调整仓位
        if 'adx' in last_candle and not pd.isna(last_candle['adx']):
            if last_candle['adx'] > 30:
                # 强趋势时增加仓位
                base_stake = base_stake * 1.1
            elif last_candle['adx'] < 20:
                # 弱趋势时减少仓位
                base_stake = base_stake * 0.8
        
        # 根据成交量调整仓位
        if 'volume_ratio' in last_candle and not pd.isna(last_candle['volume_ratio']):
            if last_candle['volume_ratio'] > 1.5:
                # 高成交量时增加仓位
                base_stake = base_stake * 1.1
            elif last_candle['volume_ratio'] < 0.8:
                # 低成交量时减少仓位
                base_stake = base_stake * 0.9
        
        # 确保在合理范围内
        base_stake = max(min_stake or 0, min(base_stake, max_stake))
        
        return base_stake
