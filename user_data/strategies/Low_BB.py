# --- Do not remove these libs ---
from freqtrade.strategy import IStrategy, IntParameter, RealParameter
from typing import Dict, List
from functools import reduce
from pandas import DataFrame
# --------------------------------

import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib


class Low_BB(IStrategy):
    """
    策略名称: Low_BB (低布林带)
    策略作者: Thorsten
    策略类型: 均值回归 / 抢反弹

    ## 策略核心逻辑

    这是一个极其简单，但包含一个重要高级技巧的"抢反弹"策略。
    它的核心思想是捕捉价格极端超跌的瞬间，并完全依赖于Freqtrade的止盈/止损机制来退出交易。

    ### 盈利逻辑: 捕捉极端超跌

    #### 买入条件:
    - `收盘价 <= 0.98 * 布林带下轨`
    - 这是策略**唯一**的买入条件。它寻找一个非常罕见的、价格严重跌穿布林带下轨的信号。
    - 这种信号通常意味着市场出现了恐慌性抛售，价格过度偏离其价值。策略押注于这种极端情况后，会大概率出现一个快速且强力的"均值回归"式反弹。

    #### 卖出逻辑: (重要技巧)
    - 策略的 `populate_exit_trend` 函数中，使用了 `dataframe.loc[(), 'exit_long'] = 1`。
    - 这是一个 freqtrade 的高级用法：当一个策略在所有K线上都给出卖出信号时，框架会认为该策略**没有自定义的、基于指标的卖出逻辑**。
    - **最终效果**: 完全禁用指标卖出信号，将所有的平仓决策完全交给 `minimal_roi` (止盈), `stoploss` (止损) 和 `trailing_stop` (移动止损) 这三个核心参数来处理。
    - 这完美地实现了作者的意图："...sell if trailing stop loss is hit"。

    ### 优点
    - 逻辑非常简单，只有一个入场条件。
    - 理论上可以捕捉到V型反转的最低点。
    - 将卖出决策与入场逻辑解耦，思路清晰。

    ### 缺点
    - **风险极高**: "接飞刀"的行为非常危险，如果市场继续下跌，会导致巨大亏损。
    - **信号罕见**: 严重跌穿下轨的信号非常少，可能导致长时间没有交易。
    - **高度依赖参数**: 策略的成败完全取决于 `minimal_roi` 和 `stoploss` 等参数的设置。
    - **代码问题**: 策略中重复计算了布林带，并且计算的MACD指标未被使用。
    """

    INTERFACE_VERSION: int = 3
    # ROI table
    @property
    def minimal_roi(self):
        return {
            "0": self.roi_p1.value,
            "1": self.roi_p2.value,
            "10": self.roi_p3.value,
            "15": self.roi_p4.value
        }
    
    roi_p1 = RealParameter(0.5, 1.2, default=0.9, space='roi', optimize=True)
    roi_p2 = RealParameter(0.03, 0.08, default=0.05, space='roi', optimize=True)
    roi_p3 = RealParameter(0.02, 0.06, default=0.04, space='roi', optimize=True)
    roi_p4 = RealParameter(0.3, 0.7, default=0.5, space='roi', optimize=True)


    # Optimal stoploss designed for the strategy
    # This attribute will be overridden if the config file contains "stoploss"
    stoploss = RealParameter(-0.05, -0.01, default=-0.015, space='protection', optimize=True)

    # Optimal timeframe for the strategy
    timeframe = '1m'

    # Indicator parameters
    bb_window = IntParameter(15, 30, default=20, space='buy', optimize=True)
    bb_std = RealParameter(1.5, 3.0, default=2.0, space='buy', optimize=True)
    
    # Buy logic threshold
    buy_bb_factor = RealParameter(0.97, 0.99, default=0.98, space='buy', optimize=True)

    # Unused indicator parameters
    macd_fast = IntParameter(10, 20, default=12, space='buy', optimize=True)
    macd_slow = IntParameter(20, 35, default=26, space='buy', optimize=True)
    macd_signal = IntParameter(7, 15, default=9, space='buy', optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # --- 核心指标: 布林带 ---
        # 注意: 原代码计算了两次布林带，这里保留了实际生效的第二次计算
        bollinger = qtpylib.bollinger_bands(dataframe['close'], window=self.bb_window.value, stds=self.bb_std.value)
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_middleband'] = bollinger['mid']
        dataframe['bb_upperband'] = bollinger['upper']

        # --- 未使用的指标 ---
        # MACD被计算但未在任何买卖逻辑中使用
        macd = ta.MACD(dataframe, fastperiod=self.macd_fast.value, slowperiod=self.macd_slow.value, signalperiod=self.macd_signal.value)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        dataframe['macdhist'] = macd['macdhist']

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义买入信号：寻找价格极端超跌的信号
        """
        dataframe.loc[
            (
                # 条件: 收盘价严重跌穿布林带下轨 (比下轨还低2%)
                (dataframe['close'] <= self.buy_bb_factor.value * dataframe['bb_lowerband'])
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义卖出信号：通过始终返回 "True" 来禁用基于指标的卖出。
        这将让 ROI, Stoploss, Trailing Stoploss 来处理所有卖出决策。
        """
        # loc中的空元组 () 会选中所有行，因此下面这行代码
        # 会在每一根K线上都将 exit_long 设置为 1。
        dataframe.loc[
            (),
            'exit_long'] = 1
        return dataframe
