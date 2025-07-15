# --- Do not remove these libs ---
from freqtrade.strategy import IStrategy, IntParameter, RealParameter
from typing import Dict, List
from functools import reduce
from pandas import DataFrame
# --------------------------------

import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib


class Simple(IStrategy):
    """
    策略名称: Simple (简单策略)
    策略作者: Gert Wohlgemuth
    策略思想来源: 'The Simple Strategy' - https://www.amazon.com/Simple-Strategy-Powerful-Trading-Futures-ebook/dp/B00E66QPCG/

    ## 策略核心逻辑

    这是一个非常纯粹且激进的**趋势动量策略**。它完全颠覆了"超卖买入，超买卖出"的传统思路，信奉"强者恒强"的交易哲学。
    策略旨在识别出最强劲的上升趋势，并在趋势中途介入，期望趋势能延续，实现"追高卖更高"。

    ### 盈利逻辑: "动量追涨"

    策略的买入条件是寻找多个指标同时确认强劲动能的"共振点"：

    1.  **MACD确认趋势**: `MACD > 0` 并且 `MACD线 > MACD信号线` - 这确保了市场处于一个整体的上升趋势中，并且短期动能也是向上的。
    2.  **布林带确认波动**: `布林带上轨向上倾斜` - 这表明布林带通道正在开口，波动性在增加，上涨趋势正在加速，而不是减弱。
    3.  **RSI确认强势**: `RSI(7) > 70` - 这是策略的精髓。它不在RSI处于低位时买入，而是在RSI已经进入**超买区**时才入场。这是一种典型的动量交易行为，押注于已经很强的市场会变得更强。

    ### 卖出逻辑

    卖出逻辑非常简单：`RSI(7) > 80`。当短期RSI从"超买"区域(>70)进一步飙升至"极度超买"区域(>80)时，策略选择离场。这可以理解为在市场情绪最狂热时获利了结，以防盛极而衰。

    ### 优点
    - 在强劲的单边牛市中，这种策略能够抓住主升浪，带来可观的回报。
    - 逻辑清晰，易于理解，是学习动量交易思想的一个好例子。

    ### 缺点
    - **风险极高**: 在震荡市或趋势反转时，追涨操作很容易买在顶部，导致亏损。
    - 对市场条件的依赖性很强，只在特定的强趋势行情中有效。
    - 使用了7周期的RSI，信号非常灵敏，可能会产生很多假信号。
    """

    INTERFACE_VERSION: int = 3
    # 最小ROI。根据市场情况调整。建议保持较低的值以便快速周转。
    minimal_roi = RealParameter(0.005, 0.05, default=0.01, space='roi', optimize=True)

    # 优化的止损位
    stoploss = RealParameter(-0.30, -0.15, default=-0.25, space='protection', optimize=True)

    # 最佳时间框架
    timeframe = '5m'

    # Indicator periods
    macd_fast = IntParameter(10, 20, default=12, space='buy', optimize=True)
    macd_slow = IntParameter(20, 35, default=26, space='buy', optimize=True)
    macd_signal = IntParameter(7, 15, default=9, space='buy', optimize=True)
    rsi_period = IntParameter(5, 15, default=7, space='buy', optimize=True)
    bb_window = IntParameter(8, 20, default=12, space='buy', optimize=True)
    bb_std = RealParameter(1.5, 3.0, default=2.0, space='buy', optimize=True)

    # Logic thresholds
    buy_rsi_threshold = IntParameter(60, 80, default=70, space='buy', optimize=True)
    sell_rsi_threshold = IntParameter(75, 95, default=80, space='sell', optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # MACD (默认参数: fast 12, slow 26, signal 9)
        macd = ta.MACD(dataframe, fastperiod=self.macd_fast.value, slowperiod=self.macd_slow.value, signalperiod=self.macd_signal.value)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        dataframe['macdhist'] = macd['macdhist']

        # RSI - 相对强弱指数。使用7周期使其更灵敏。
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=self.rsi_period.value)

        # Bollinger Bands - 布林带 (12周期, 2倍标准差)
        # 用于绘图和判断趋势强度
        bollinger = qtpylib.bollinger_bands(dataframe['close'], window=self.bb_window.value, stds=self.bb_std.value)
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_upperband'] = bollinger['upper']
        dataframe['bb_middleband'] = bollinger['mid']

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义买入信号的条件
        """
        dataframe.loc[
            (
                # 1. MACD在零轴之上，并且快线在慢线之上 (确认牛市动能)
                (dataframe['macd'] > 0)
                & (dataframe['macd'] > dataframe['macdsignal'])
                # 2. 布林带上轨向上，表明趋势在加速
                & (dataframe['bb_upperband'] > dataframe['bb_upperband'].shift(1))
                # 3. RSI进入超买区 (确认强势，追涨)
                # 作者注: 这是一个可选的过滤器，需要研究
                & (dataframe['rsi'] > self.buy_rsi_threshold.value)
            ),
            'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义卖出信号的条件
        """
        dataframe.loc[
            (
                # 当RSI进入极度超买区时卖出
                (dataframe['rsi'] > self.sell_rsi_threshold.value)
            ),
            'exit_long'] = 1
        return dataframe
