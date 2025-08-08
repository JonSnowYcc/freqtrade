# --- 策略总结 ---
# 策略名称: UniversalMACD (通用MACD)
#
# 盈利逻辑:
# 该策略实现了一种"通用"或"标准化"的MACD指标，并通过这个新指标的值是否落入特定"交易区域"来产生信号。
#   - 通用MACD指标: 传统的MACD是快慢均线的"差值" (`EMA12 - EMA26`)，而此策略中的`umacd`是快慢均线的"比率" (`(EMA12 / EMA26) - 1`)。
#     这样做的好处是，指标的值被"标准化"了，不受币种价格高低的影响，使其在不同交易对之间更具可比性。
#     `umacd > 0` 代表金叉后的多头状态，`< 0` 代表死叉后的空头状态。
#   - 交易逻辑 (区域交易): 策略的核心思想是，当 `umacd` 的值进入一个通过超参数优化找到的特定"最佳交易区域"时，就执行相应的操作。
#       - 买入(Entry): 当`umacd`的值落在一个特定的"买入区域"内时买入。根据优化参数，这个区域通常是`0`下方的一个很窄的负值窗口。
#         这表明，它不是在金叉后追高，而是在即将金叉前的回调末端 (死叉状态的末期) 寻找买点，属于一种"左侧交易"或"均值回归"的思路。
#       - 卖出(Exit): 当`umacd`的值落入另一个独立的"卖出区域"时卖出。这个区域可以被优化为"止盈区"或"止损区"。
#
# 优点:
#   - 指标标准化: "比率"MACD使得在不同价格的币种上进行横向比较和优化成为可能，增强了策略的通用性。
#   - 区域交易思想: 将传统的"交叉"信号转化为"区域"信号，更为灵活，可以通过优化找到更精细的、传统MACD无法表达的交易条件。
#   - 领先信号: 它的买入逻辑旨在比传统金叉信号更早地捕捉到趋势的转折点。
#
# 缺点:
#   - 反转策略风险: 在趋势刚刚转折时入场，如果趋势未能延续而是继续下跌，将面临亏损 (即"抄底抄在半山腰")。
#   - 高度依赖优化: 策略的表现完全取决于能否为"买入区域"和"卖出区域"找到精确、有效的数值范围。
#   - 优化参数可能存在逻辑问题: 默认的卖出参数中，最小值大于最大值，这在代码层面是个逻辑错误，需要修正才能正常工作。

# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# isort: skip_file
# --- 请勿删除这些库 ---
import numpy as np
import pandas as pd
from pandas import DataFrame
from datetime import datetime
from typing import Optional, Union

from freqtrade.strategy import (BooleanParameter, CategoricalParameter, DecimalParameter,
                                IntParameter, IStrategy, merge_informative_pair, RealParameter)

# --------------------------------
# 在此导入您的库
import talib.abstract as ta
import pandas_ta as pta
from technical import qtpylib


class UniversalMACD(IStrategy):
    # 作者: Masoud Azizi (@mablue)
    # Tradingview页面: https://www.tradingview.com/script/xNEWcB8s-Universal-Moving-Average-Convergence-Divergence/

    # 策略接口版本
    INTERFACE_VERSION = 3

    # 策略的最佳时间框架
    timeframe = '5m'

    # 该策略是否可以做空？
    can_short: bool = False

    # --- 优化与配置示例 ---
    # $ freqtrade hyperopt -s UniversalMACD --hyperopt-loss SharpeHyperOptLossDaily
    # "max_open_trades": 1,
    # "stake_currency": "USDT",
    # "stake_amount": 990,

    # 优化结果示例:
    # *16 / 100: 40    trades.
    # 31 / 9 / 0    Wins / Draws / Losses.
    # Avg    profit    2.34 %.
    # Median    profit    3.00 %.
    # Total    profit    928.95036811    USDT(92.90 %).
    # Avg    duration    3: 13:00    min.
    # Objective: -11.63412

    # ROI table
    roi_p1 = RealParameter(0.15, 0.3, default=0.213, space='roi', optimize=True)
    roi_p2 = RealParameter(0.05, 0.15, default=0.099, space='roi', optimize=True)
    roi_p3 = RealParameter(0.01, 0.05, default=0.03, space='roi', optimize=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.minimal_roi = {
            "0": self.roi_p1.value,
            "27": self.roi_p2.value,
            "60": self.roi_p3.value,
            "164": 0
        }

    # 止损:
    stoploss = RealParameter(-0.35, -0.25, default=-0.318, space='protection', optimize=True)

    # 追踪止损:
    trailing_stop = BooleanParameter(default=False, space='protection', optimize=True)
    trailing_stop_positive = RealParameter(0.005, 0.05, default=0.01, space='protection', optimize=True)
    trailing_stop_positive_offset = RealParameter(0.0, 0.05, default=0.0, space='protection', optimize=True)
    trailing_only_offset_is_reached = BooleanParameter(default=False, space='protection', optimize=True)

    # 策略产生有效信号前需要的最少蜡烛图数量
    startup_candle_count: int = 30

    # 策略参数
    buy_umacd_max = DecimalParameter(-0.05, 0.05, decimals=5, default=-0.01176, space="buy", optimize=True)
    buy_umacd_min = DecimalParameter(-0.05, 0.05, decimals=5, default=-0.01416, space="buy", optimize=True)
    # 修正了默认值，确保min <= max
    sell_umacd_max = DecimalParameter(-0.05, 0.05, decimals=5, default=-0.00707, space="sell", optimize=True)
    sell_umacd_min = DecimalParameter(-0.05, 0.05, decimals=5, default=-0.02323, space="sell", optimize=True)

    # Indicator periods
    ma_fast_period = IntParameter(8, 20, default=12, space='buy', optimize=True)
    ma_slow_period = IntParameter(20, 35, default=26, space='buy', optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['ma12'] = ta.EMA(dataframe, timeperiod=self.ma_fast_period.value)
        dataframe['ma26'] = ta.EMA(dataframe, timeperiod=self.ma_slow_period.value)
        # 计算通用MACD指标
        dataframe['umacd'] = (dataframe['ma12'] / dataframe['ma26']) - 1

        # 作者注：以下代码用于显示指标在不同币种上的最大/最小值，以便在超参数优化中设置合理的范围。
        # print(dataframe['umacd'].min(), dataframe['umacd'].max())

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                # 条件: umacd指标值是否落在预设的"买入区域"内
                (dataframe['umacd'].between(self.buy_umacd_min.value, self.buy_umacd_max.value))

            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 注意: 默认的sell_params中min > max，这会导致 `between` 函数永远为False。
        # 在实际使用中需要修正或通过超参数优化找到合理的值。
        dataframe.loc[
            (
                # 条件: umacd指标值是否落在预设的"卖出区域"内
                (dataframe['umacd'].between(self.sell_umacd_min.value, self.sell_umacd_max.value))
            ),
            'exit_long'] = 1

        return dataframe
