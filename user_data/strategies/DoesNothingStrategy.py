# --- Do not remove these libs ---
from freqtrade.strategy import IStrategy, RealParameter
from pandas import DataFrame
# --------------------------------


class DoesNothingStrategy(IStrategy):
    """
    策略名称: DoesNothingStrategy (啥也不干策略)
    策略作者: Gert Wohlgemuth
    策略类型: 模板 / 骨架 / 示例

    ## 策略核心目的

    **警告：这是一个模板文件，它不包含任何有效的交易逻辑，不能用于实盘交易。**

    正如其名，这个策略本身"啥也不干"。它的主要目的是作为：

    1.  **一个最简结构范例**: 展示一个有效的 Freqtrade 策略文件所需要的最基本组成部分（类、必需的函数等）。
    2.  **一个空白的开发骨架**: 开发者可以复制这个文件，然后在此基础上填充自己的指标和交易逻辑，而无需从零开始。
    3.  **一个用于核心功能测试的案例**: 可以用来验证机器人是否能正确加载和运行一个最简单的策略。

    ### 策略行为解读

    - `populate_indicators()`: 此函数为空，不计算任何指标。
    - `populate_entry_trend()`: 此函数的买入条件为空 `()`，这会导致在**每一根K线**上都生成买入信号。
    - `populate_exit_trend()`: 此函数的卖出条件也为空 `()`，这会导致在**每一根K线**上都生成卖出信号。

    在 Freqtrade 中，当一个策略在所有K线上都同时发出买入和卖出信号时，框架会认为这是一个无效信号，
    **因此不会执行任何基于该策略的自动交易**。所有的平仓将完全由 `minimal_roi`, `stoploss` 等核心机制管理。
    """

    INTERFACE_VERSION: int = 3
    # 最小ROI。我们会建议根据市场情况进行调整，保持较低的值以便快速周转
    minimal_roi = RealParameter(0.005, 0.05, default=0.01, space='roi', optimize=True)

    # 优化的止损位
    stoploss = RealParameter(-0.30, -0.15, default=-0.25, space='protection', optimize=True)

    # 最佳时间框架
    timeframe = '5m'

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 这是一个空的指标函数，因为本策略不使用任何指标。
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # loc中的空元组 () 会选中所有行, 从而在每根K线上都设置 enter_long = 1。
        # 这会告诉框架，本策略没有基于指标的买入信号。
        dataframe.loc[
            (
            ),
            'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 同样，这会告诉框架，本策略没有基于指标的卖出信号。
        # 所有的卖出将由 ROI, stoploss, trailing stoploss 控制。
        dataframe.loc[
            (
            ),
            'exit_long'] = 1
        return dataframe
