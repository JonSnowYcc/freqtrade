# --- 策略总结 ---
# 策略名称: SwingHighToSky (冲向天际)
# 策略类型: 均值回归 / 超卖反转策略
#
# 盈利逻辑:
# 尽管策略名称听起来像是一个追高或突破策略，但其实际逻辑是一个纯粹的"均值回归"或"超卖反转"策略。
# 它通过寻找CCI和RSI两个指标同时进入超卖状态的时机来买入，并在一有反弹迹象时就快速退出。
#   - 买入(Entry): 策略的买入逻辑由两个条件**同时**满足构成：
#       1. CCI深度超卖: 商品通道指标 (CCI) 的值必须低于一个极低的阈值 (例如-175)，表明价格已严重偏离其统计均值，处于深度超卖状态。
#       2. RSI确认: 相对强弱指数 (RSI) 的值低于一个阈值。根据优化结果，这个RSI条件通常非常宽松 (例如RSI < 90)，这意味着CCI是主要的入场触发器。
#   - 卖出(Exit): 卖出逻辑旨在捕捉反弹的最初阶段，非常灵敏：
#       1. CCI反弹: CCI指标的值从深度超卖区刚刚回升到一个仍然为负但相对较高的水平时 (例如 > -106)，就立即卖出。
#       2. RSI确认: RSI指标也需要高于某个阈值。
#
# 简单来说，策略在市场极度超卖时 (主要看CCI) 入场，然后在市场情绪刚刚从极度悲观中恢复一点点时就获利了结。
#
# 优点:
#   - 逻辑清晰: 策略逻辑简单，即"CCI超卖买入，CCI反弹卖出"。
#   - 参数化: 策略的所有核心参数 (CCI和RSI的周期和水平) 都可以进行超参数优化，适应性较强。
#
# 缺点:
#   - 名称误导: 策略名称与其实际行为完全不符，容易引起误解。
#   - 指标计算效率极低: 与`Supertrend`策略类似，它的`populate_indicators`方法会预计算所有可能的参数组合，非常消耗资源和时间。
#   - 过早退出: 退出条件非常灵敏，可能会导致在强劲的V型反转中只吃到一小段利润就离场，错失更大的机会。
#   - 典型的反转策略风险: 在持续的下跌趋势中，CCI可能会持续保持在低位，导致策略过早抄底并产生亏损。

"""
作者      = "Kevin Ossenbrück"
版权      = "可自由使用"
鸣谢      = ["Bloom Trading, Mohsen Hassan"]
许可协议  = "MIT"
版本      = "1.0"
维护者    = "Kevin Ossenbrück"
邮箱      = "kevin.ossenbrueck@pm.de"
状态      = "线上"
"""

from freqtrade.strategy import IStrategy
from freqtrade.strategy import IntParameter, RealParameter
from functools import reduce
from pandas import DataFrame

import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy



# CCI timerperiods and values
# cciBuyTP = 72
# cciBuyVal = -175
# cciSellTP = 66
# cciSellVal = -106

# RSI timeperiods and values
# rsiBuyTP = 36
# rsiBuyVal = 90
# rsiSellTP = 45
# rsiSellVal = 88


class SwingHighToSky(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = '15m'

    # 止损
    stoploss = RealParameter(-0.4, -0.3, default=-0.34338, space='protection', optimize=True)

    # 最小投资回报率
    @property
    def minimal_roi(self):
        return {
            "0": self.roi_p1.value,
            "33": self.roi_p2.value,
            "64": self.roi_p3.value,
            "244": 0
        }
    
    roi_p1 = RealParameter(0.2, 0.4, default=0.27058, space='roi', optimize=True)
    roi_p2 = RealParameter(0.05, 0.15, default=0.0853, space='roi', optimize=True)
    roi_p3 = RealParameter(0.02, 0.08, default=0.04093, space='roi', optimize=True)

    # 可优化的买入参数
    buy_cci = IntParameter(low=-200, high=200, default=100, space='buy', optimize=True)
    buy_cciTime = IntParameter(low=10, high=80, default=20, space='buy', optimize=True)
    buy_rsi = IntParameter(low=10, high=90, default=30, space='buy', optimize=True)
    buy_rsiTime = IntParameter(low=10, high=80, default=26, space='buy', optimize=True)

    # 可优化的卖出参数
    sell_cci = IntParameter(low=-200, high=200, default=100, space='sell', optimize=True)
    sell_cciTime = IntParameter(low=10, high=80, default=20, space='sell', optimize=True)
    sell_rsi = IntParameter(low=10, high=90, default=30, space='sell', optimize=True)
    sell_rsiTime = IntParameter(low=10, high=80, default=26, space='sell', optimize=True)

    # 买入超参数空间 (优化结果示例):
    buy_params = {
        "buy_cci": -175,
        "buy_cciTime": 72,
        "buy_rsi": 90,
        "buy_rsiTime": 36,
    }

    # 卖出超参数空间 (优化结果示例):
    sell_params = {
        "sell_cci": -106,
        "sell_cciTime": 66,
        "sell_rsi": 88,
        "sell_rsiTime": 45,
    }

    def informative_pairs(self):
        return []

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 只计算当前优化步骤所需的指标
        dataframe[f'cci-buy'] = ta.CCI(dataframe, timeperiod=self.buy_cciTime.value)
        dataframe[f'cci-sell'] = ta.CCI(dataframe, timeperiod=self.sell_cciTime.value)
        dataframe[f'rsi-buy'] = ta.RSI(dataframe, timeperiod=self.buy_rsiTime.value)
        dataframe[f'rsi-sell'] = ta.RSI(dataframe, timeperiod=self.sell_rsiTime.value)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                # 条件1: CCI 进入深度超卖区
                (dataframe[f'cci-buy'] < self.buy_cci.value) &
                # 条件2: RSI 确认超卖 (通常此条件较宽松)
                (dataframe[f'rsi-buy'] < self.buy_rsi.value)
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                # 条件1: CCI 从深度超卖区反弹
                (dataframe[f'cci-sell'] > self.sell_cci.value) &
                # 条件2: RSI 确认反弹
                (dataframe[f'rsi-sell'] > self.sell_rsi.value)
            ),
            'exit_long'] = 1

        return dataframe
