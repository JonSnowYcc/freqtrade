# --- Do not remove these libs ---
from freqtrade.strategy import IStrategy, IntParameter, RealParameter
from typing import Dict, List
from functools import reduce
from pandas import DataFrame
# --------------------------------

import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib


class ASDTSRockwellTrading(IStrategy):
    """
    策略名称: ASDTSRockwellTrading (Rockwell交易MACD策略)
    策略作者: Gert Wohlgemuth
    策略来源: https://www.youtube.com/watch?v=mmAWVmKN4J0

    ## 策略核心逻辑

    这是一个极其简单、纯粹，完全基于MACD指标的趋势跟踪策略。
    它使用MACD与零轴的关系来判断长期趋势，然后使用MACD快线与信号线的关系来决定具体的买入和卖出。

    ### 盈利逻辑: "顺大势，逆小势" 的MACD应用

    #### 买入条件: (双重看涨确认)
    1.  **长期趋势看涨**: `MACD > 0`。MACD指标线必须在零轴之上，确认市场整体处于牛市背景。
    2.  **短期动能看涨**: `MACD快线 > MACD信号线`。这表明短期动能也是向上的，与长期趋势一致。

    - **组合解读**: 只有当长、短期动能都同向看涨时，策略才认为是一个有效的入场时机。这是一个基于"状态"的信号，只要该状态持续，信号就有效。

    #### 卖出条件: (短期动能衰竭)
    - `MACD快线 < MACD信号线`。
    - 卖出条件非常简单、灵敏。它不要求MACD跌破零轴，只要短期动能由多转空（即MACD快线跌破信号线），策略就立即退出。
    - 这种设计的目的是为了及时锁定利润，避免在趋势反转时遭受较大回撤。

    ### 优点
    - **逻辑非常简单**: 完全基于MACD，易于理解和实现。
    - **顺势而为**: MACD零轴过滤器有助于避免主要的逆势交易。
    - **退出灵敏**: 能较快地响应短期动能的变化，有助于保护利润。

    ### 缺点
    - **过于简单**: 在复杂的市场中，仅靠MACD可能不足以做出稳健的决策。
    - **盘整行情表现差**: 在横盘震荡市中，MACD会频繁地在信号线和零轴附近交叉，可能导致大量无效交易和亏损。
    """

    INTERFACE_VERSION: int = 3
    # ROI table
    roi_p1 = RealParameter(0.02, 0.06, default=0.05, space='roi', optimize=True)
    roi_p2 = RealParameter(0.02, 0.05, default=0.04, space='roi', optimize=True)
    roi_p3 = RealParameter(0.01, 0.04, default=0.03, space='roi', optimize=True)
    roi_p4 = RealParameter(0.005, 0.02, default=0.01, space='roi', optimize=True)

    minimal_roi = {
        "60": 0.01,
        "30": 0.03,
        "20": 0.04,
        "0": 0.05
    }

    # Optimal stoploss designed for the strategy
    # This attribute will be overridden if the config file contains "stoploss"
    stoploss = RealParameter(-0.35, -0.15, default=-0.3, space='protection', optimize=True)

    # Optimal timeframe for the strategy
    timeframe = '5m'

    # MACD parameters
    macd_fast_period = IntParameter(10, 25, default=12, space='buy', optimize=True)
    macd_slow_period = IntParameter(20, 40, default=26, space='buy', optimize=True)
    macd_signal_period = IntParameter(7, 15, default=9, space='buy', optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # MACD - 异同移动平均线
        macd = ta.MACD(
            dataframe,
            fastperiod=self.macd_fast_period.value,
            slowperiod=self.macd_slow_period.value,
            signalperiod=self.macd_signal_period.value
        )
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        dataframe['macdhist'] = macd['macdhist']

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义买入信号
        """
        dataframe.loc[
            (
                # 条件1: 长期趋势看涨
                (dataframe['macd'] > 0) &
                # 条件2: 短期动能看涨
                (dataframe['macd'] > dataframe['macdsignal'])
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义卖出信号
        """
        dataframe.loc[
            (
                # 条件: 短期动能转为看跌
                (dataframe['macd'] < dataframe['macdsignal'])
            ),
            'exit_long'] = 1
        return dataframe
