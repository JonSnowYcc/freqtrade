from freqtrade.strategy import IStrategy, IntParameter, RealParameter
from typing import Dict, List
from functools import reduce
from pandas import DataFrame
# --------------------------------

import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy  # noqa


class EMASkipPump(IStrategy):
    """
    策略名称: EMASkipPump (EMA并跳过PUMP行情)
    策略作者: 未知 (分享自 tradingview slack)
    策略类型: 均值回归 / 抢反弹

    ## 策略核心逻辑

    这是一个专注于"极端均值回归"的抢反弹策略。它的独到之处在于，它试图通过一个成交量过滤器，
    将"正常的技术性深蹲"与"高风险的拉高出货(Pump and Dump)行情"区分开来。

    ### 盈利逻辑: "接住那把正常的飞刀"

    #### 买入条件:
    策略的买入条件非常苛刻，要求同时满足以下五个条件：

    1.  **【核心】成交量过滤**: `当前成交量 < 过去30根K线平均成交量的20倍`。这是策略的灵魂，它首先排除了成交量异常放大的情况，以试图避免在剧烈的PUMP行情中进行交易。
    2.  **价格低于均线**: `收盘价 < 5周期EMA` 并且 `收盘价 < 12周期EMA`。价格处于短期和中期均线下方，确认了回调趋势。
    3.  **创近期新低**: `收盘价 == 过去12根K线的最低价`。这是一个非常强的信号，表明价格达到了波段的绝对低点。
    4.  **跌破布林下轨**: `收盘价 <= 布林带下轨`。价格已经突破了正常的波动下轨，进入统计上的超卖区。

    **买入逻辑解读**: 这是一个非常激进的"接飞刀"策略。它只想接"正常下跌的飞刀"，而通过成交量过滤，试图避开那些"被PUMP后暴跌的飞刀"。

    #### 卖出逻辑:
    卖出逻辑是买入逻辑的完美镜像，它等待价格反弹至极端强势时才离场：
    - `收盘价 > 5周期EMA` 并且 `收盘价 > 12周期EMA`。
    - `收盘价 == 过去12根K线的最高价`。
    - `收盘价 >= 布林带上轨`。

    **卖出逻辑解读**: 旨在完整地捕捉从波段低点到波段高点的整个反弹过程，在市场情绪最狂热时获利了结。

    ### 优点
    - 目标明确，专注于一种特定的市场失衡形态。
    - 成交量过滤器是一个非常聪明的风险控制手段。

    ### 缺点
    - 均值回归策略，尤其是"接飞刀"式的，本身风险极高。
    - 买入条件非常苛刻，交易信号可能非常稀少。
    - 强依赖于参数，例如成交量放大的倍数、均线周期等都需要仔细测试。
    """
    INTERFACE_VERSION: int = 3
    # EMA 均线周期
    ema_short_term = IntParameter(3, 10, default=5, space='buy', optimize=True)
    ema_medium_term = IntParameter(10, 20, default=12, space='buy', optimize=True)
    ema_long_term = IntParameter(20, 30, default=21, space='buy', optimize=True)

    # Minimal ROI designed for the strategy.
    # we only sell after 100%, unless our sell points are found before
    minimal_roi = RealParameter(0.05, 0.2, default=0.1, space='roi', optimize=True)

    # Optimal stoploss designed for the strategy
    # This attribute will be overridden if the config file contains "stoploss"
    # should be converted to a trailing stop loss
    stoploss = RealParameter(-0.10, -0.03, default=-0.05, space='protection', optimize=True)

    # Optimal timeframe for the strategy
    timeframe = '5m'

    # Indicator parameters
    bb_window = IntParameter(15, 30, default=20, space='buy', optimize=True)
    bb_std = RealParameter(1.5, 3.0, default=2.0, space='buy', optimize=True)

    # Logic parameters
    volume_rolling_window = IntParameter(20, 40, default=30, space='buy', optimize=True)
    volume_multiplier = IntParameter(10, 30, default=20, space='buy', optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        计算所需的技术指标
        """
        # EMA 均线
        dataframe[f'ema_{self.ema_short_term.value}'] = ta.EMA(dataframe, timeperiod=self.ema_short_term.value)
        dataframe[f'ema_{self.ema_medium_term.value}'] = ta.EMA(dataframe, timeperiod=self.ema_medium_term.value)
        dataframe[f'ema_{self.ema_long_term.value}'] = ta.EMA(dataframe, timeperiod=self.ema_long_term.value)

        # 布林带
        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=self.bb_window.value, stds=self.bb_std.value)
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_middleband'] = bollinger['mid']
        dataframe['bb_upperband'] = bollinger['upper']

        # 近期最高/最低价
        dataframe['min'] = ta.MIN(dataframe, timeperiod=self.ema_medium_term.value)
        dataframe['max'] = ta.MAX(dataframe, timeperiod=self.ema_medium_term.value)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义买入信号
        """
        dataframe.loc[
            (
                # 1. 核心: 过滤掉成交量激增的PUMP行情
                (dataframe['volume'] < (dataframe['volume'].rolling(window=self.volume_rolling_window.value).mean().shift(1) * self.volume_multiplier.value)) &
                # 2. 价格处于均线下方
                (dataframe['close'] < dataframe[f'ema_{self.ema_short_term.value}']) &
                (dataframe['close'] < dataframe[f'ema_{self.ema_medium_term.value}']) &
                # 3. 价格创下近期新低
                (dataframe['close'] == dataframe['min']) &
                # 4. 价格跌破布林下轨
                (dataframe['close'] <= dataframe['bb_lowerband'])
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义卖出信号
        """
        dataframe.loc[
            (
                # 1. 价格反弹至均线上方
                (dataframe['close'] > dataframe[f'ema_{self.ema_short_term.value}']) &
                (dataframe['close'] > dataframe[f'ema_{self.ema_medium_term.value}']) &
                # 2. 价格创下近期新高
                (dataframe['close'] >= dataframe['max']) &
                # 3. 价格突破布林上轨
                (dataframe['close'] >= dataframe['bb_upperband'])
            ),
            'exit_long'] = 1

        return dataframe
