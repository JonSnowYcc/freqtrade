# --- Do not remove these libs ---
from functools import reduce
from freqtrade.strategy import IStrategy
from freqtrade.strategy import CategoricalParameter, DecimalParameter, IntParameter, RealParameter
from pandas import DataFrame
# --------------------------------

import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib


class AverageStrategy(IStrategy):
    """
    策略名称: AverageStrategy (均线策略优化框架)
    策略作者: Gert Wohlgemuth
    策略类型: 均线交叉 / 超参数优化框架

    ## 策略核心逻辑

    **重要警告**: 作者在代码中明确指出："本策略基于均线交叉买卖 - 表现并不好，只是一个概念验证"。

    这是一个为**超参数优化（Hyperopt）**而设计的、用于寻找最佳均线交叉参数的**策略框架**。
    它本身不是一个固定的策略，而是一个用来**发现最佳均线交叉策略**的工具。

    ### 关键特征: 完全可优化的均线周期

    策略的核心是将快、慢均线的周期定义为两个可优化的 `IntParameter`（整数参数）：
    - `buy_range_short`: 快线周期，可在5到20之间选择。
    - `buy_range_long`: 慢线周期，可在20到120之间选择。

    通过超参数优化功能，可以在大量的均线组合中（如8/21, 10/50, 20/100等），自动寻找出在特定市场上最有利可图的那一对均线参数。

    ### 盈利逻辑: "寻找最优的金叉和死叉"

    - **买入条件**: 当由`hyperopt`选出的"最优快线"向上穿越"最优慢线"时（金叉），买入。
    - **卖出条件**: 当"最优快线"向下穿越"最优慢线"时（死叉），卖出。

    ### 优点
    - **高度灵活**: 能够通过优化来发现适用于不同市场的最佳均线参数。
    - **高效计算**: `populate_indicators` 中对指标的预处理方法非常高效，是为超参数优化量身定做的典范，大大提升了优化速度。

    ### 缺点
    - **性能依赖优化**: 未经优化的默认参数可能表现平平，策略的有效性完全取决于优化结果。
    - **作者负面评价**: 作者本人已"劝退"，表明其作为概念验证的意义大于实战价值。
    - 均线交叉策略普遍存在滞后性。
    """

    INTERFACE_VERSION: int = 3
    # Minimal ROI designed for the strategy.
    # This attribute will be overridden if the config file contains "minimal_roi"
    minimal_roi = RealParameter(0.1, 0.6, default=0.5, space='roi', optimize=True)

    # Optimal stoploss designed for the strategy
    # This attribute will be overridden if the config file contains "stoploss"
    stoploss = RealParameter(-0.25, -0.15, default=-0.2, space='protection', optimize=True)

    # Optimal timeframe for the strategy
    timeframe = '4h'

    # 定义可优化的快、慢均线周期范围
    buy_range_short = IntParameter(5, 20, default=8)
    buy_range_long = IntParameter(20, 120, default=21)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        高效的指标计算方法：
        一次性计算出超参数优化过程中所有可能会用到的EMA值，以提高优化效率。
        """
        # 将快慢均线的所有可能周期值合并，并去重
        all_periods = set(list(self.buy_range_short.range) + list(self.buy_range_long.range))
        
        # 循环一次性计算所有EMA
        for val in all_periods:
            dataframe[f'ema{val}'] = ta.EMA(dataframe, timeperiod=val)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义买入信号：使用由hyperopt选择的快慢均线进行金叉判断
        """
        dataframe.loc[
            (
                qtpylib.crossed_above(
                    dataframe[f'ema{self.buy_range_short.value}'],
                    dataframe[f'ema{self.buy_range_long.value}']
                ) &
                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义卖出信号：使用由hyperopt选择的快慢均线进行死叉判断
        """
        dataframe.loc[
            (
                qtpylib.crossed_above(
                    dataframe[f'ema{self.buy_range_long.value}'],
                    dataframe[f'ema{self.buy_range_short.value}']
                    ) &
                (dataframe['volume'] > 0)
            ),
            'exit_long'] = 1
        return dataframe
