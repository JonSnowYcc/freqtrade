# --- Do not remove these libs ---
from freqtrade.strategy import IStrategy, IntParameter, RealParameter
from typing import Dict, List
from functools import reduce
from pandas import DataFrame
# --------------------------------

import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib


class MACDStrategy_crossed(IStrategy):
    """
    策略名称: MACDStrategy_crossed (带过滤的MACD交叉策略)
    策略作者: 未知
    策略类型: 动量 / 均值回归

    ## 策略核心逻辑

    这是一个非常经典和稳健的交易系统。它将MACD的动量信号和CCI的超买超卖信号相结合，
    旨在过滤掉盘整行情中的无效信号，专注于捕捉从一个极端摆动到另一个极端的波段行情。

    ### 盈利逻辑: "在超卖区金叉买入，在超买区死叉卖出"

    #### 买入条件:
    1.  **MACD金叉**: MACD的快线（`macd`）向上穿越其慢线（`macdsignal`）。这是一个经典的看涨动量信号，表明趋势可能从下跌或盘整转为上涨。
    2.  **CCI超卖过滤**: 与此同时，CCI指标必须小于或等于-50。这表明价格正处于相对的低位或"超卖"区域。
    - **组合解读**: 策略只在"价格处于相对低位时发生的金叉"才买入。CCI过滤器有效地避免了在价格已经很高时追高，从而提高了信号的可靠性。

    #### 卖出条件:
    1.  **MACD死叉**: MACD的快线向下穿越其慢线。这是一个经典的看跌动量信号。
    2.  **CCI超买过滤**: 与此同时，CCI指标必须大于或等于100，表明价格处于相对高位或"超买"区域。
    - **组合解读**: 策略在"价格已经上涨到相对高位，并且动量开始衰竭"时卖出。

    ### 优点
    - 逻辑清晰，易于理解，是组合策略的入门典范。
    - CCI过滤器可以有效提高MACD交叉信号的胜率。
    - 在有明显波段的震荡行情中表现较好。

    ### 缺点
    - 在强烈的单边趋势行情中，CCI可能长时间不进入超买/超卖区，导致错过整个趋势。
    - 依赖参数优化，不同的市场可能需要不同的CCI阈值。
    """

    INTERFACE_VERSION: int = 3
    # ROI table
    roi_p1 = RealParameter(0.02, 0.06, default=0.05, space='roi', optimize=True)
    roi_p2 = RealParameter(0.02, 0.05, default=0.04, space='roi', optimize=True)
    roi_p3 = RealParameter(0.01, 0.04, default=0.03, space='roi', optimize=True)
    roi_p4 = RealParameter(0.005, 0.02, default=0.01, space='roi', optimize=True)

    @property
    def minimal_roi(self):
        return {
            "60": self.roi_p4.value,
            "30": self.roi_p3.value,
            "20": self.roi_p2.value,
            "0": self.roi_p1.value
        }

    # Optimal stoploss
    stoploss = RealParameter(-0.35, -0.15, default=-0.3, space='protection', optimize=True)

    # Optimal timeframe
    timeframe = '5m'

    # --- 超参数定义 ---
    # CCI 阈值
    buy_cci_threshold = IntParameter(-150, 0, default=-50, space='buy', optimize=True)
    sell_cci_threshold = IntParameter(0, 200, default=100, space='sell', optimize=True)

    # 指标周期
    macd_fast_period = IntParameter(10, 25, default=12, space='buy', optimize=True)
    macd_slow_period = IntParameter(20, 40, default=26, space='buy', optimize=True)
    macd_signal_period = IntParameter(7, 15, default=9, space='buy', optimize=True)
    cci_period = IntParameter(15, 30, default=20, space='buy', optimize=True)

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
        
        # CCI - 商品通道指标
        dataframe['cci'] = ta.CCI(dataframe, timeperiod=self.cci_period.value)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义买入信号
        """
        dataframe.loc[
            (
                # 条件1: MACD金叉
                qtpylib.crossed_above(dataframe['macd'], dataframe['macdsignal']) &
                # 条件2: CCI处于超卖区
                (dataframe['cci'] <= self.buy_cci_threshold.value)
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义卖出信号
        """
        dataframe.loc[
            (
                # 条件1: MACD死叉
                qtpylib.crossed_below(dataframe['macd'], dataframe['macdsignal']) &
                # 条件2: CCI处于超买区
                (dataframe['cci'] >= self.sell_cci_threshold.value)
            ),
            'exit_long'] = 1

        return dataframe
