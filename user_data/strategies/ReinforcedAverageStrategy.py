# --- Do not remove these libs ---
from freqtrade.strategy import IStrategy, IntParameter, RealParameter, BooleanParameter
from typing import Dict, List
from functools import reduce
from pandas import DataFrame, merge, DatetimeIndex
# --------------------------------

import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
from technical.util import resample_to_interval, resampled_merge
from freqtrade.exchange import timeframe_to_minutes


class ReinforcedAverageStrategy(IStrategy):
    """
    策略名称: ReinforcedAverageStrategy (加强版均线策略)
    策略作者: Gert Wohlgemuth
    策略类型: 均线交叉 / 多时间周期 (MTF)

    ## 策略核心逻辑

    这是一个教科书级别的"带趋势过滤的均线交叉策略"。它在经典的双EMA均线交叉系统的基础上，
    引入了更高时间周期的趋势判断作为"加强"过滤器，以提高信号的胜率。

    **重要警告**: 作者在代码中明确指出："本策略基于均线交叉买卖 - 表现并不好，只是一个概念验证"。

    ### 盈利逻辑: "顺大势，逆小势" 的均线交叉

    1.  **定义"大势"**: 策略将当前4小时图表数据，重采样为48小时（2天）的宏观周期，并在此之上计算一条50周期的SMA。这条"2日线"被用作判断长期牛熊的基准。
    2.  **定义"小势"**: 在4小时主图表上，使用8周期EMA作为快线，21周期EMA作为慢线。

    #### 买入条件 (金叉 + 顺大势)
    - **金叉信号**: 在4小时图上，8 EMA（快线）向上穿越 21 EMA（慢线）。
    - **趋势过滤**: 发生金叉时，4小时的收盘价必须高于"2日线"。
    - **总结**: 只有当宏观趋势（2日）向上时，微观周期（4小时）出现的金叉信号才被认为是有效的买入机会。

    #### 卖出条件 (死叉)
    - **死叉信号**: 在4小时图上，8 EMA（快线）向下穿越 21 EMA（慢线）。
    - **注意**: 卖出时**没有**趋势过滤。无论宏观趋势如何，只要4小时图出现死叉，就立即平仓。这体现了"入场从严，出场从速"的风控思想。

    ### 优点
    - 逻辑清晰，是均线系统和MTF思想结合的典范。
    - MTF过滤器能有效避免在长期熊市中因短期反弹而被套。
    - 参数较少，易于理解和调整。

    ### 缺点
    - 均线策略普遍存在延迟性，可能错过最佳买卖点。
    - 作者本人已明确表示其表现不佳，可能仅适用于特定行情。
    - 4小时和2天的周期组合非常长线，交易机会很少。
    """

    INTERFACE_VERSION: int = 3
    # Minimal ROI designed for the strategy.
    # This attribute will be overridden if the config file contains "minimal_roi"
    minimal_roi = RealParameter(0.1, 1.0, default=0.5, space='roi', optimize=True)

    # Optimal stoploss designed for the strategy
    # This attribute will be overridden if the config file contains "stoploss"
    stoploss = RealParameter(-0.3, -0.1, default=-0.2, space='protection', optimize=True)

    # Optimal timeframe for the strategy
    timeframe = '4h'

    # trailing stoploss
    trailing_stop = BooleanParameter(default=False, space='protection', optimize=True)
    trailing_stop_positive = RealParameter(0.005, 0.03, default=0.01, space='protection', optimize=True)
    trailing_stop_positive_offset = RealParameter(0.01, 0.05, default=0.02, space='protection', optimize=True)
    trailing_only_offset_is_reached = BooleanParameter(default=False, space='protection', optimize=True)

    # run "populate_indicators" only for new candle
    process_only_new_candles = True

    # Experimental settings (configuration will overide these if set)
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # Indicator parameters
    ma_short_period = IntParameter(5, 15, default=8, space='buy', optimize=True)
    ma_medium_period = IntParameter(15, 30, default=21, space='buy', optimize=True)
    resample_multiplier = IntParameter(8, 20, default=12, space='buy', optimize=True)
    resample_sma_period = IntParameter(40, 60, default=50, space='buy', optimize=True)
    
    # Plotting indicator parameters
    bb_window = IntParameter(15, 30, default=20, space='buy', optimize=True)
    bb_std = RealParameter(1.5, 3.0, default=2.0, space='buy', optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # --- 主图表指标 (4h) ---
        dataframe['maShort'] = ta.EMA(dataframe, timeperiod=self.ma_short_period.value)  # 短期均线/快线
        dataframe['maMedium'] = ta.EMA(dataframe, timeperiod=self.ma_medium_period.value) # 中期均线/慢线
        
        # --- 宏观图表指标 (4h * 12 = 48h = 2d) ---
        # 1. 计算重采样周期
        self.resample_interval = timeframe_to_minutes(self.timeframe) * self.resample_multiplier.value
        # 2. 获取重采样后的dataframe
        dataframe_long = resample_to_interval(dataframe, self.resample_interval)
        # 3. 在大周期上计算SMA
        dataframe_long['sma'] = ta.SMA(dataframe_long, timeperiod=self.resample_sma_period.value, price='close')
        # 4. 将大周期指标合并回主dataframe
        dataframe = resampled_merge(dataframe, dataframe_long, fill_na=True)

        # --- 绘图用指标 ---
        bollinger = qtpylib.bollinger_bands(dataframe['close'], window=self.bb_window.value, stds=self.bb_std.value)
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_upperband'] = bollinger['upper']
        dataframe['bb_middleband'] = bollinger['mid']
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the buy signal for the given dataframe
        :param dataframe: DataFrame
        :return: DataFrame with buy column
        """

        dataframe.loc[
            (
                # 信号1: 短期均线上穿中期均线 (金叉)
                qtpylib.crossed_above(dataframe['maShort'], dataframe['maMedium']) &
                # 信号2: 价格必须高于大周期的SMA (顺大势)
                (dataframe['close'] > dataframe[f'resample_{self.resample_interval}_sma']) &
                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the sell signal for the given dataframe
        :param dataframe: DataFrame
        :return: DataFrame with buy column
        """
        dataframe.loc[
            (
                # 信号: 短期均线下穿中期均线 (死叉)
                qtpylib.crossed_above(dataframe['maMedium'], dataframe['maShort']) &
                (dataframe['volume'] > 0)
            ),
            'exit_long'] = 1
        return dataframe
