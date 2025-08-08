# --- Do not remove these libs ---
from freqtrade.strategy import IStrategy, IntParameter, RealParameter
from typing import Dict, List
from functools import reduce
from pandas import DataFrame
# --------------------------------

import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib


class Quickie(IStrategy):
    """
    策略名称: Quickie (快枪手)
    策略作者: Gert Wohlgemuth
    策略类型: 动量 / 回调 / **逆势交易 (有风险)**

    ## 策略核心逻辑

    作者声称这是一个旨在"快速了结交易"的动量策略。然而，其买入逻辑包含一个非常关键且有风险的**逆势条件**。

    ### 盈利逻辑: 熊市中的回调买入 (高风险!)

    #### 卖出逻辑的矛盾
    策略的买入条件由四个部分组成，其中第四个条件使其成为一个逆势交易策略：
    1.  **趋势强度**: `ADX > 30` - 要求市场处于一个强劲的趋势中。
    2.  **价格回调**: `TEMA(9) < 布林带中轨` - 要求价格回调至20周期均线下方。
    3.  **动能企稳**: `TEMA(9) 向上` - 要求9周期TEMA（一个更灵敏的均线）刚刚掉头向上，表明回调可能结束。
    4.  **【风险点】长期熊市背景**: `收盘价 < SMA(200)` - 这是技术分析中**长期熊市**的典型定义。

    **逻辑总结**: 该策略的实际行为是：在一个由200日均线确认的**长期下跌趋势**中，去捕捉一个微小的、刚刚企稳的反弹。这是一种**在熊市中逆势抄底**的行为，与作者声称的"动量策略"理念相悖，风险极高。
    **这非常可能是一个笔误**，作者或许想写成 `dataframe['sma_200'] < dataframe['close']` (即在牛市中回调买入)。

    ### 卖出逻辑
    卖出逻辑相对传统：当趋势极度强劲（ADX > 70），且短期动能（TEMA）开始掉头向下时，策略退出。

    ### 优点
    - 卖出逻辑符合"快速退出"的思想。
    - TEMA指标的应用值得学习。

    ### 缺点
    - **核心逻辑风险极高**: 在长期熊市中逆势抄底是非常危险的行为。
    - **代码错误**: 策略计算了`MACD`和`sma_50`指标但并未使用。其中`sma_50`的计算周期错误地设为了200。
    - **理念与实际行为不符**: 名为动量策略，实为逆势策略。
    """

    INTERFACE_VERSION: int = 3
    # ROI table
    minimal_roi = {
        "100": 0.01,
        "30": 0.03,
        "15": 0.06,
        "10": 0.15
    }

    roi_p1 = RealParameter(0.005, 0.02, default=0.01, space='roi', optimize=True)
    roi_p2 = RealParameter(0.01, 0.05, default=0.03, space='roi', optimize=True)
    roi_p3 = RealParameter(0.04, 0.08, default=0.06, space='roi', optimize=True)
    roi_p4 = RealParameter(0.1, 0.2, default=0.15, space='roi', optimize=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.minimal_roi = {
            "100": self.roi_p1.value,
            "30": self.roi_p2.value,
            "15": self.roi_p3.value,
            "10": self.roi_p4.value
        }

    # Optimal stoploss designed for the strategy
    # This attribute will be overridden if the config file contains "stoploss"
    stoploss = RealParameter(-0.30, -0.20, default=-0.25, space='protection', optimize=True)

    # Optimal timeframe for the strategy
    timeframe = '5m'

    # Indicator parameters
    tema_period = IntParameter(5, 15, default=9, space='buy', optimize=True)
    sma_200_period = IntParameter(150, 250, default=200, space='buy', optimize=True)
    sma_50_period = IntParameter(40, 60, default=50, space='buy', optimize=True)
    adx_period = IntParameter(10, 20, default=14, space='buy', optimize=True)
    bb_window = IntParameter(15, 30, default=20, space='buy', optimize=True)
    bb_std = RealParameter(1.5, 3.0, default=2.0, space='buy', optimize=True)

    # Unused indicator parameters
    macd_fast = IntParameter(10, 20, default=12, space='buy', optimize=True)
    macd_slow = IntParameter(20, 35, default=26, space='buy', optimize=True)
    macd_signal = IntParameter(7, 15, default=9, space='buy', optimize=True)

    # Logic thresholds
    buy_adx_threshold = IntParameter(20, 40, default=30, space='buy', optimize=True)
    sell_adx_threshold = IntParameter(60, 80, default=70, space='sell', optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # MACD指标被计算但未在策略逻辑中使用
        macd = ta.MACD(dataframe, fastperiod=self.macd_fast.value, slowperiod=self.macd_slow.value, signalperiod=self.macd_signal.value)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        dataframe['macdhist'] = macd['macdhist']

        # TEMA - 三重指数移动平均线，延迟更低，是策略的核心
        dataframe['tema'] = ta.TEMA(dataframe, timeperiod=self.tema_period.value)
        # 长期趋势均线
        dataframe['sma_200'] = ta.SMA(dataframe, timeperiod=self.sma_200_period.value)
        
        # !! BUG: sma_50的周期被错误地设置成了200，且该指标未被使用
        dataframe['sma_50'] = ta.SMA(dataframe, timeperiod=self.sma_50_period.value)

        dataframe['adx'] = ta.ADX(dataframe, timeperiod=self.adx_period.value)

        # 绘图用指标
        bollinger = qtpylib.bollinger_bands(dataframe['close'], window=self.bb_window.value, stds=self.bb_std.value)
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_middleband'] = bollinger['mid']
        dataframe['bb_upperband'] = bollinger['upper']

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                # 1. 强趋势
                (dataframe['adx'] > self.buy_adx_threshold.value) &
                # 2. 价格回调
                (dataframe['tema'] < dataframe['bb_middleband']) &
                # 3. 短期动能向上
                (dataframe['tema'] > dataframe['tema'].shift(1)) &
                # 4. 【警告】价格处于长期均线下方，这是一个熊市信号！
                # 此条件使策略成为逆势交易，风险很高。
                (dataframe['sma_200'] > dataframe['close'])

            ),
            'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                # 1. 趋势极度强劲 (可能力竭)
                (dataframe['adx'] > self.sell_adx_threshold.value) &
                # 2. 价格已反弹至均线上方
                (dataframe['tema'] > dataframe['bb_middleband']) &
                # 3. 短期动能开始掉头向下
                (dataframe['tema'] < dataframe['tema'].shift(1))
            ),
            'exit_long'] = 1
        return dataframe
