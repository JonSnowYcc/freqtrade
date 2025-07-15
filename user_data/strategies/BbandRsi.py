# --- Do not remove these libs ---
from freqtrade.strategy import IStrategy, IntParameter, RealParameter
from pandas import DataFrame
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib


# --------------------------------


class BbandRsi(IStrategy):
    """
    策略名称: BbandRsi (布林带与RSI组合策略)
    策略作者: Gert Wohlgemuth
    策略来源: https://github.com/sthewissen/Mynt/blob/master/src/Mynt.Core/Strategies/BbandRsi.cs

    ## 策略核心逻辑

    这是一个非常经典、简单且流传广泛的均值回归策略。它组合了两个最常用于此目的的指标——RSI和布林带（Bollinger Bands），
    通过寻找两个指标的"共振"信号来提高交易的成功率。

    ### 盈利逻辑: "共振抄底，超买离场"

    #### 买入条件: (双重超卖确认)
    策略的买入条件要求两种不同类型的"超卖"信号必须**同时发生**：

    1.  **RSI动能超卖**: `RSI < 30`。RSI进入30下方的传统超卖区，表明下跌动能可能耗尽，市场随时可能反弹。
    2.  **布林带价格超卖**: `收盘价 < 布林带下轨`。价格跌破布林带下轨，表明从统计学角度看，价格已过度向下偏离其近期均值。

    - **组合解读**: 通过要求两个指标达成"共识"，策略旨在过滤掉单一指标的假信号，只在"高确定性"的超卖时机入场。

    #### 卖出逻辑: (动能超买确认)
    - `RSI > 70`。
    - 卖出逻辑非常纯粹。它不等待价格回归到布林带中轨或上轨，而是只要RSI指标显示反弹的动能已经进入"超买"状态，就立即平仓以锁定利润。

    ### 优点
    - **逻辑经典**: 结合了两种最受欢迎的振荡器，逻辑清晰，易于理解。
    - **信号可靠**: 双重确认机制可以有效过滤市场噪音。
    - 在震荡行情中表现通常较好。

    ### 缺点
    - **容易钝化**: 在强烈的单边下跌趋势中，RSI和布林带可能长时间处于超卖区，导致过早入场。
    - **可能过早离场**: 在强劲的V型反转中，仅凭RSI超买就退出，可能会错过后半段更大的涨幅。
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
    buy_rsi_threshold = IntParameter(10, 40, default=30, space='buy', optimize=True)

    # 卖出参数
    sell_rsi_threshold = IntParameter(60, 90, default=70, space='sell', optimize=True)

    # 指标参数
    rsi_period = IntParameter(10, 25, default=14, space='buy', optimize=True)
    bb_window = IntParameter(15, 30, default=20, space='buy', optimize=True)
    bb_std = RealParameter(1.5, 2.5, default=2.0, space='buy', optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # RSI - 相对强弱指数
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=self.rsi_period.value)

        # Bollinger Bands - 布林带
        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=self.bb_window.value, stds=self.bb_std.value)
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_middleband'] = bollinger['mid']
        dataframe['bb_upperband'] = bollinger['upper']

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义买入信号：RSI和布林带共振超卖
        """
        dataframe.loc[
            (
                (dataframe['rsi'] < self.buy_rsi_threshold.value) &
                (dataframe['close'] < dataframe['bb_lowerband'])
            ),
            'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义卖出信号：RSI超买
        """
        dataframe.loc[
            (
                (dataframe['rsi'] > self.sell_rsi_threshold.value)
            ),
            'exit_long'] = 1
        return dataframe
