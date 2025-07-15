# --- 策略总结 ---
# 策略名称: PowerTower (能量塔)
#
# 盈利逻辑:
# 作者将其描述为一个全新的、用于寻找强劲拉升币种的策略或K线形态。其灵感来源于"三只乌鸦"，但规则完全不同，
# 旨在识别爆发性的、加速的上涨动能。这是一个纯粹的价格行为策略，不使用任何传统技术指标。
#   - 买入(Entry): 策略会寻找一个连续的、爆炸性的增长模式。只有当以下三个条件**同时 (`&`)** 满足时，才会买入：
#       1. `当前收盘价 > (2根K线前的收盘价) ^ N`
#       2. `1根K线前的收盘价 > (3根K线前的收盘价) ^ N`
#       3. `2根K线前的收盘价 > (4根K线前的收盘价) ^ N`
#     这里的 `N` 是一个可优化的参数 (默认为3.849)。这个数学关系要求价格在短期内呈现出指数级的、极其迅猛的增长，形态上类似一个"能量塔"。
#   - 卖出(Exit): 卖出逻辑是，只要上述三个指数级增长的条件中，有**任何一个 (`|`)** 被破坏 (即价格增长未能跟上指数曲线)，策略就会立即退出。
#     这是一个非常灵敏的离场信号，旨在动能衰竭的最初迹象出现时就锁定利润。
#
# 优点:
#   - 捕捉强动能: 专门设计用于识别和交易市场中最强劲的突破行情，如果成功，短期回报可能非常高。
#   - 逻辑新颖: 提供了一种量化"爆发性动能"的全新数学方法。
#   - 快速离场: 灵敏的退出机制有助于在动能反转时迅速离场。
#
# 缺点:
#   - 高风险: 追逐顶部的"动能耗尽"风险很高。买入时价格已经非常高，很容易买在短期顶部。
#   - 信号稀少: 如此极端的增长条件在市场中非常罕见。
#   - 参数敏感: 策略表现对 `buy_pow` 和 `sell_pow` 这两个参数的设置极其敏感。
#   - 容易受单个异常K线影响: 一根突然的、巨大的K线可能会错误地触发信号。

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


class PowerTower(IStrategy):
    # 作者: Masoud Azizi (@mablue)
    # Power Tower 是一个全新的策略(或K线形态、或指标)，用于寻找强劲上涨的币种。
    # 它比"三只乌Crows"有效得多，但基于该K线形态的思想，规则却不同！

    # 策略接口版本 - 允许策略接口的新迭代。
    # 查看文档或示例策略以获取最新版本。
    INTERFACE_VERSION = 3

    # 策略的最佳时间框架
    timeframe = '5m'

    # 该策略是否可以做空？
    can_short: bool = False

    # --- 超参数优化与配置示例 ---
    # $ freqtrade hyperopt -s PowerTower --hyperopt-loss SharpeHyperOptLossDaily
    # "max_open_trades": 1,
    # "stake_currency": "USDT",
    # "stake_amount": 990,
    # "dry_run_wallet": 1000,
    
    # 优化结果示例:
    # 38/100:     67 trades. 32/34/1 Wins/Draws/Losses.
    # Avg profit   1.23%. Median profit   0.00%.
    # Total profit 815.05358020 USDT (  81.51%).
    # Avg duration 10:58:00 min. Objective: -9.86920
    
    # ROI table
    @property
    def minimal_roi(self):
        return {
            "0": self.roi_p1.value,
            "39": self.roi_p2.value,
            "56": self.roi_p3.value,
            "159": 0
        }
    roi_p1 = RealParameter(0.15, 0.3, default=0.213, space='roi', optimize=True)
    roi_p2 = RealParameter(0.03, 0.08, default=0.048, space='roi', optimize=True)
    roi_p3 = RealParameter(0.01, 0.05, default=0.029, space='roi', optimize=True)

    # 止损:
    stoploss = RealParameter(-0.3, -0.2, default=-0.288, space='protection', optimize=True)

    # 追踪止损:
    trailing_stop = BooleanParameter(default=False, space='protection', optimize=True)
    trailing_stop_positive = RealParameter(0.005, 0.05, default=0.01, space='protection', optimize=True)
    trailing_stop_positive_offset = RealParameter(0.0, 0.05, default=0.0, space='protection', optimize=True)
    trailing_only_offset_is_reached = BooleanParameter(default=False, space='protection', optimize=True)

    # 策略产生有效信号前需要的最少蜡烛图数量
    startup_candle_count: int = 30

    # 策略参数
    buy_pow = DecimalParameter(0, 4, decimals=3, default=3.849, space="buy", optimize=True)
    sell_pow = DecimalParameter(0, 4, decimals=3, default=3.798, space="sell", optimize=True)

    # Shift periods
    buy_shift_1_1 = IntParameter(0, 2, default=0, space='buy', optimize=True)
    buy_shift_1_2 = IntParameter(1, 4, default=2, space='buy', optimize=True)
    buy_shift_2_1 = IntParameter(0, 2, default=1, space='buy', optimize=True)
    buy_shift_2_2 = IntParameter(2, 5, default=3, space='buy', optimize=True)
    buy_shift_3_1 = IntParameter(1, 4, default=2, space='buy', optimize=True)
    buy_shift_3_2 = IntParameter(3, 6, default=4, space='buy', optimize=True)
    
    sell_shift_1_1 = IntParameter(0, 2, default=0, space='sell', optimize=True)
    sell_shift_1_2 = IntParameter(1, 4, default=2, space='sell', optimize=True)
    sell_shift_2_1 = IntParameter(0, 2, default=1, space='sell', optimize=True)
    sell_shift_2_2 = IntParameter(2, 5, default=3, space='sell', optimize=True)
    sell_shift_3_1 = IntParameter(1, 4, default=2, space='sell', optimize=True)
    sell_shift_3_2 = IntParameter(3, 6, default=4, space='sell', optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 这是一个纯粹的价格行为策略，不需要计算任何技术指标
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                    # 条件1: 当前收盘价 > (N期前收盘价) ^ pow
                    (dataframe['close'].shift(self.buy_shift_1_1.value) > dataframe['close'].shift(self.buy_shift_1_2.value) ** self.buy_pow.value) &
                    # 条件2: M期前收盘价 > (P期前收盘价) ^ pow
                    (dataframe['close'].shift(self.buy_shift_2_1.value) > dataframe['close'].shift(self.buy_shift_2_2.value) ** self.buy_pow.value) &
                    # 条件3: Q期前收盘价 > (R期前收盘价) ^ pow
                    (dataframe['close'].shift(self.buy_shift_3_1.value) > dataframe['close'].shift(self.buy_shift_3_2.value) ** self.buy_pow.value)

            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[(
                # 退出条件: 只要以下任何一个指数增长模式被破坏，就退出
                # 条件1被破坏
                (dataframe['close'].shift(self.sell_shift_1_1.value) < dataframe['close'].shift(self.sell_shift_1_2.value) ** self.sell_pow.value) |
                # 条件2被破坏
                (dataframe['close'].shift(self.sell_shift_2_1.value) < dataframe['close'].shift(self.sell_shift_2_2.value) ** self.sell_pow.value) |
                # 条件3被破坏
                (dataframe['close'].shift(self.sell_shift_3_1.value) < dataframe['close'].shift(self.sell_shift_3_2.value) ** self.sell_pow.value)
        ),
        'exit_long'] = 1

        return dataframe
