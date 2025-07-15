# --- Do not remove these libs ---
from freqtrade.strategy import IStrategy, IntParameter, RealParameter
from typing import Dict, List
from functools import reduce
from pandas import DataFrame
# --------------------------------

import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy  # noqa


class ClucMay72018(IStrategy):
    """
    策略名称: ClucMay72018
    策略作者: Gert Wohlgemuth
    策略类型: 均值回归 / 抢反弹

    ## 策略核心逻辑

    这是一个定义清晰的均值回归（抢反弹）策略。它在短期下跌趋势中，通过一个成交量过滤器来识别"安全"的、
    由指标确认的极端超卖信号作为买入点，然后以价格回归到布林带中轨作为卖出点。

    该策略也是 `CombinedBinHAndCluc.py` 组合策略的子策略之一。

    ### 盈利逻辑: "安全地抢反弹"

    #### 买入条件:
    1.  **确认短期下跌趋势**: `收盘价 < 50周期EMA` - 要求价格必须处于中期均线下方。
    2.  **寻找极端超卖信号**: `收盘价 < 0.985 * 布林带下轨` - 要求价格严重跌穿布林带下轨（比下轨还低1.5%），这是一个强烈的超卖信号。
    3.  **【核心】成交量风控**: `当前成交量 < 历史平均成交量的20倍` - 这是策略的关键风控。它旨在过滤掉因"拉高出货"（Pump & Dump）等市场操纵行为导致的剧烈波动，只在成交量"正常"的下跌中寻找机会。

    #### 卖出逻辑:
    - `收盘价 > 布林带中轨`。
    - 卖出逻辑非常简单。抢反弹的目标就是价格能"回归均值"，一旦价格成功反弹回20周期的均线（布林带中轨），策略就止盈离场。

    ### 优点
    - 逻辑清晰，买入和卖出条件相辅相成。
    - 成交量过滤器是亮点，能有效规避部分市场风险。

    ### 缺点
    - 逆势交易，风险天然较高。
    - 存在一些计算了但未使用的指标（RSI, MACD, ADX），以及命名不规范的问题（`ema100`实际是50周期）。
    - 依赖"魔法数字"（如0.985, 20倍成交量），在不同市场下可能需要调整。
    """

    INTERFACE_VERSION: int = 3
    # Minimal ROI designed for the strategy.
    # This attribute will be overridden if the config file contains "minimal_roi"
    minimal_roi = RealParameter(0.005, 0.03, default=0.01, space='roi', optimize=True)

    # Optimal stoploss designed for the strategy
    # This attribute will be overridden if the config file contains "stoploss"
    stoploss = RealParameter(-0.10, -0.03, default=-0.05, space='protection', optimize=True)

    # Optimal timeframe for the strategy
    timeframe = '5m'

    # Indicator periods
    bb_window = IntParameter(15, 30, default=20, space='buy', optimize=True)
    bb_std = RealParameter(1.5, 3.0, default=2.0, space='buy', optimize=True)
    ema_period = IntParameter(40, 60, default=50, space='buy', optimize=True)
    volume_rolling_window = IntParameter(20, 40, default=30, space='buy', optimize=True)

    # Buy logic thresholds
    buy_bb_factor = RealParameter(0.97, 0.995, default=0.985, space='buy', optimize=True)
    buy_volume_multiplier = IntParameter(10, 30, default=20, space='buy', optimize=True)

    # --- Unused indicator parameters ---
    rsi_period = IntParameter(3, 15, default=5, space='buy', optimize=True)
    emarsi_period = IntParameter(3, 15, default=5, space='buy', optimize=True)
    macd_fast = IntParameter(10, 20, default=12, space='buy', optimize=True)
    macd_slow = IntParameter(20, 35, default=26, space='buy', optimize=True)
    macd_signal = IntParameter(7, 15, default=9, space='buy', optimize=True)
    adx_period = IntParameter(10, 20, default=14, space='buy', optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # --- 核心指标 ---
        # 布林带
        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=self.bb_window.value, stds=self.bb_std.value)
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_middleband'] = bollinger['mid']
        dataframe['bb_upperband'] = bollinger['upper']
        
        # EMA均线, 用于判断短期趋势
        # 注意: 列名是ema100，但实际计算的是50周期EMA
        dataframe['ema100'] = ta.EMA(dataframe, timeperiod=self.ema_period.value)

        # --- 计算了但未在策略逻辑中使用的指标 ---
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=self.rsi_period.value)
        rsiframe = DataFrame(dataframe['rsi']).rename(columns={'rsi': 'close'})
        dataframe['emarsi'] = ta.EMA(rsiframe, timeperiod=self.emarsi_period.value)
        macd = ta.MACD(dataframe, fastperiod=self.macd_fast.value, slowperiod=self.macd_slow.value, signalperiod=self.macd_signal.value)
        dataframe['macd'] = macd['macd']
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=self.adx_period.value)
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义买入信号
        """
        dataframe.loc[
            (
                # 1. 处于短期下跌趋势
                (dataframe['close'] < dataframe['ema100']) &
                # 2. 价格极端超卖
                (dataframe['close'] < self.buy_bb_factor.value * dataframe['bb_lowerband']) &
                # 3. 成交量正常，非PUMP行情
                (dataframe['volume'] < (dataframe['volume'].rolling(window=self.volume_rolling_window.value).mean().shift(1) * self.buy_volume_multiplier.value))
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义卖出信号：当价格回归均值时卖出
        """
        dataframe.loc[
            (
                (dataframe['close'] > dataframe['bb_middleband'])
            ),
            'exit_long'] = 1
        return dataframe
