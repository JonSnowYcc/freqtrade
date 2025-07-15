# --- Do not remove these libs ---
from freqtrade.strategy import IStrategy, IntParameter, RealParameter
from pandas import DataFrame
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib


# --------------------------------


class AdxSmas(IStrategy):
    """
    策略名称: AdxSmas (ADX与SMA组合策略)
    策略作者: Gert Wohlgemuth
    策略来源: https://github.com/sthewissen/Mynt/blob/master/src/Mynt.Core/Strategies/AdxSmas.cs

    ## 策略核心逻辑

    这是一个经典、简单的趋势跟踪策略。它使用ADX指标作为"趋势过滤器"，以确保只在市场存在明确趋势时进行交易，
    然后利用两条超短周期的简单移动平均线（SMA）的交叉来作为入场和出场的信号。

    ### 盈利逻辑: "趋势确认，交叉入场"

    #### 买入条件:
    1.  **趋势确认**: `ADX > 25`。ADX（平均趋向指数）必须高于25，这表明市场目前处于一个有效的趋势行情中（上涨或下跌），而不是无方向的盘整。
    2.  **金叉入场**: `3周期SMA 向上穿越 6周期SMA`。使用两条反应极快的均线形成的"黄金交叉"作为买入信号，旨在第一时间捕捉到上升趋势的启动。

    - **组合解读**: 只有当市场被确认为"有趋势"时，才去响应那个"看涨"的均线交叉信号。

    #### 卖出逻辑:
    1.  **趋势衰竭**: `ADX < 25`。ADX回落到25以下，表明趋势已经显著减弱或结束。
    2.  **死叉离场**: `3周期SMA 向下穿越 6周期SMA`。均线"死亡交叉"发出看跌信号。

    - **组合解读**: 卖出条件使用了"与"逻辑，即**趋势衰竭和死叉信号必须同时满足**才卖出。这是一个相对"迟钝"的退出机制，旨在尽可能地"让利润奔跑"，直到趋势被明确地确认为已经结束后才离场。

    ### 优点
    - **逻辑清晰**: ADX过滤+均线交叉，是非常经典的趋势策略组合，易于理解。
    - **避免盘整**: ADX过滤器能有效帮助策略规避在横盘市场中的无效交易。

    ### 缺点
    - **均线滞后性**: 所有均线策略都存在一定的滞后性。
    - **退出可能较晚**: "与"逻辑的卖出条件，可能导致在价格快速反转时无法及时离场。
    - **超短周期均线**: 3和6周期的均线非常敏感，可能会产生较多毛刺信号。
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

    # --- 超参数定义 ---
    # 买入参数
    buy_adx_threshold = IntParameter(20, 40, default=25, space='buy', optimize=True)

    # 卖出参数
    sell_adx_threshold = IntParameter(20, 40, default=25, space='sell', optimize=True)

    # 指标周期参数
    adx_period = IntParameter(10, 25, default=14, space='buy', optimize=True)
    short_sma_period = IntParameter(2, 10, default=3, space='buy', optimize=True)
    long_sma_period = IntParameter(5, 20, default=6, space='buy', optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # ADX - 平均趋向指数, 用于衡量趋势强度
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=self.adx_period.value)
        
        # 两条超短周期SMA均线
        dataframe['short'] = ta.SMA(dataframe, timeperiod=self.short_sma_period.value)
        dataframe['long'] = ta.SMA(dataframe, timeperiod=self.long_sma_period.value)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义买入信号：趋势已形成，且出现金叉
        """
        dataframe.loc[
            (
                (dataframe['adx'] > self.buy_adx_threshold.value) &
                (qtpylib.crossed_above(dataframe['short'], dataframe['long']))
            ),
            'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义卖出信号：趋势已衰竭，且出现死叉
        """
        dataframe.loc[
            (
                (dataframe['adx'] < self.sell_adx_threshold.value) &
                (qtpylib.crossed_above(dataframe['long'], dataframe['short']))
            ),
            'exit_long'] = 1
        return dataframe
