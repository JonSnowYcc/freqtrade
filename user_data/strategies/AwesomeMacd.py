# --- Do not remove these libs ---
from freqtrade.strategy import IStrategy, IntParameter, RealParameter
from pandas import DataFrame
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib


# --------------------------------


class AwesomeMacd(IStrategy):
    """
    策略名称: AwesomeMacd (AO与MACD组合策略)
    策略作者: Gert Wohlgemuth
    策略来源: https://github.com/sthewissen/Mynt/blob/master/src/Mynt.Core/Strategies/AwesomeMacd.cs

    ## 策略核心逻辑

    这是一个逻辑清晰、非常经典的**趋势跟踪策略**。它使用MACD指标作为判断长期趋势的"宏观过滤器"，
    然后使用AO指标（Awesome Oscillator，动量震荡指标）的零轴穿越作为精确的入场和出场时机。

    其核心思想是：只在宏观趋势的方向上，寻找短期动量与宏观趋势一致的精确时刻进行交易。

    ### 盈利逻辑: "顺大势，抓拐点"

    #### 买入条件:
    1.  **MACD > 0 (定大势)**: MACD指标线必须在零轴之上。这被用作一个"牛市过滤器"，确保只在市场整体看涨的环境下寻找买入机会。
    2.  **AO上穿零轴 (抓拐点)**: AO指标（`ao`）从负值向上穿越零轴。这是一个经典的看涨动量信号，表明短期动能由空转多。

    - **组合解读**: 在由MACD确认的牛市背景下，等待一个短期回调结束、上升动能重启的信号（AO上穿零轴），然后入场。

    #### 卖出条件:
    1.  **MACD < 0 (定大势)**: MACD指标线必须在零轴之下，作为"熊市过滤器"。
    2.  **AO下穿零轴 (抓拐点)**: AO指标从正值向下穿越零轴。这是一个经典的看跌动量信号。

    - **组合解读**: 在由MACD确认的熊市背景下，当短期动量由多转空时，平仓离场。

    ### 优点
    - **逻辑清晰**: 双指标各司其职（一个判断趋势，一个选择时机），易于理解。
    - **趋势过滤**: MACD过滤器能有效避免逆势交易，提高胜率。
    - 是一个非常经典的趋势跟踪系统范例。

    ### 缺点
    - **依赖趋势**: 在长期横盘震荡的市场中，MACD可能在零轴附近反复徘徊，导致策略失效或产生错误信号。
    - **信号延迟**: MACD和AO本身都具有一定的滞后性。
    """

    INTERFACE_VERSION: int = 3
    # Minimal ROI designed for the strategy.
    # adjust based on market conditions. We would recommend to keep it low for quick turn arounds
    # This attribute will be overridden if the config file contains "minimal_roi"
    minimal_roi = RealParameter(0.01, 0.2, default=0.1, space='roi', optimize=True)

    # Optimal stoploss designed for the strategy
    stoploss = RealParameter(-0.30, -0.10, default=-0.25, space='protection', optimize=True)

    # Optimal timeframe for the strategy
    timeframe = '1h'

    # Indicator parameters
    adx_period = IntParameter(10, 25, default=14, space='buy', optimize=True)
    macd_fast_period = IntParameter(10, 25, default=12, space='buy', optimize=True)
    macd_slow_period = IntParameter(20, 40, default=26, space='buy', optimize=True)
    macd_signal_period = IntParameter(7, 15, default=9, space='buy', optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # ADX被计算但未在策略逻辑中使用
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=self.adx_period.value)
        
        # AO - Awesome Oscillator (动量震荡指标)
        dataframe['ao'] = qtpylib.awesome_oscillator(dataframe)

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
                # 条件1: MACD大于0，确认宏观牛市
                (dataframe['macd'] > 0) &
                # 条件2: AO上穿零轴，确认短期动能转为看涨
                (dataframe['ao'] > 0) &
                (dataframe['ao'].shift() < 0)
            ),
            'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义卖出信号
        """
        dataframe.loc[
            (
                # 条件1: MACD小于0，确认宏观熊市
                (dataframe['macd'] < 0) &
                # 条件2: AO下穿零轴，确认短期动能转为看跌
                (dataframe['ao'] < 0) &
                (dataframe['ao'].shift() > 0)
            ),
            'exit_long'] = 1
        return dataframe
