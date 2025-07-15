# --- 策略总结 ---
# 策略名称: hlhb (Huck loves her bucks!)
# 策略来源: BabyPips.com 网站上一个公开的外汇交易系统。
#
# 盈利逻辑:
# 这是一个经典教科书式的"三重确认"趋势跟踪策略，旨在捕捉短期趋势。
# 它通过结合三种不同类型的指标来确认入场和出场，以提高信号的可靠性。
#   - 买入(Entry): 只有当以下三个条件**同时**满足时，才会产生买入信号：
#       1. 动量确认 (RSI): RSI指标上穿50，表明市场由空头转为多头动量。
#       2. 趋势确认 (EMA交叉): 5周期EMA线上穿10周期EMA线，发出经典的"黄金交叉"买入信号，确认短期上升趋势。
#       3. 趋势强度确认 (ADX): ADX指标大于25，表明当前趋势足够强劲，值得参与 (过滤掉弱趋势或震荡市)。
#   - 卖出(Exit): 卖出逻辑与买入逻辑完全相反，当RSI下穿50、EMA(5)下穿EMA(10)（死亡交叉）、且ADX依然大于25（确认下跌趋势强度）时，产生卖出信号。
#
# 优点:
#   - 高可靠性: 多重指标共振可以有效过滤掉许多假信号，避免在方向不明的震荡市场中进行交易，提高了胜率。
#   - 逻辑清晰: 策略逻辑基于三种广为人知的经典技术指标，易于理解和实现。
#   - 顺势而为: 严格遵循"趋势是你的朋友"原则，只在趋势确认后才入场。
#
# 缺点:
#   - 信号可能滞后: 由于需要三个指标同时确认，信号的发出可能会晚于趋势的起始点，从而错过一部分早期利润。
#   - 在快速反转行情中表现不佳: 在V型反转等市场中，当信号最终形成时，行情可能已经接近尾声或已经反转。
#   - 参数固定: 策略中的参数（如RSI周期10, EMA周期5/10, ADX阈值25）是固定的，可能无法适应所有市场周期和交易品种，需要调整优化。

# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement

import numpy as np  # noqa
import pandas as pd  # noqa
from pandas import DataFrame
from freqtrade.strategy import IStrategy, IntParameter, RealParameter, BooleanParameter
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib


class hlhb(IStrategy):
    """
    HLHB ("Huck loves her bucks!") 系统旨在捕捉短期的外汇趋势。
    更多信息请访问: https://www.babypips.com/trading/forex-hlhb-system-explained
    """

    INTERFACE_VERSION: int = 3

    position_stacking = "True"

    # 为该策略设计的最小投资回报率(ROI)。
    # 如果配置文件中包含 "minimal_roi"，此属性将被覆盖。
    @property
    def minimal_roi(self):
        return {
            "0": self.roi_p1.value,
            "703": self.roi_p2.value,
            "2849": self.roi_p3.value,
            "5520": 0
        }
    roi_p1 = RealParameter(0.5, 0.8, default=0.6225, space='roi', optimize=True)
    roi_p2 = RealParameter(0.15, 0.3, default=0.2187, space='roi', optimize=True)
    roi_p3 = RealParameter(0.02, 0.05, default=0.0363, space='roi', optimize=True)

    # 为该策略设计的优化止损。
    # 如果配置文件中包含 "stoploss"，此属性将被覆盖。
    stoploss = RealParameter(-0.35, -0.25, default=-0.3211, space='protection', optimize=True)

    # 追踪止损
    trailing_stop = BooleanParameter(default=True, space='protection', optimize=True)
    trailing_stop_positive = RealParameter(0.01, 0.02, default=0.0117, space='protection', optimize=True)
    trailing_stop_positive_offset = RealParameter(0.01, 0.03, default=0.0186, space='protection', optimize=True)
    trailing_only_offset_is_reached = BooleanParameter(default=True, space='protection', optimize=True)

    # 策略的最佳时间框架。
    timeframe = '4h'

    # 仅在新蜡烛图上运行 "populate_indicators()"。
    process_only_new_candles = True

    # 这些值可以在配置文件的 "ask_strategy" 部分被覆盖。
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = True

    # 策略产生有效信号前需要的最少蜡烛图数量
    startup_candle_count: int = 30

    # 可选的订单类型映射。
    order_types = {
        'entry': 'limit',
        'exit': 'limit',
        'stoploss': 'market',
        'stoploss_on_exchange': False
    }

    # 可选的订单有效时间。
    order_time_in_force = {
        'entry': 'gtc',
        'exit': 'gtc'
    }

    # 图表绘制配置
    plot_config = {
        # 主图指标 (移动平均线, ...)
        'main_plot': {
            'ema5': {},
            'ema10': {},
        },
        'subplots': {
            # 子图 - 每个字典定义一个额外的图表
            "RSI": {
                'rsi': {'color': 'red'},
            },
            "ADX": {
                'adx': {},
            }
        }
    }

    # Indicator periods
    rsi_period = IntParameter(5, 15, default=10, space='buy', optimize=True)
    ema5_period = IntParameter(3, 8, default=5, space='buy', optimize=True)
    ema10_period = IntParameter(8, 15, default=10, space='buy', optimize=True)
    adx_period = IntParameter(10, 20, default=14, space='buy', optimize=True)

    # Logic thresholds
    rsi_threshold = IntParameter(40, 60, default=50, space='buy', optimize=True)
    adx_threshold = IntParameter(20, 35, default=25, space='buy', optimize=True)

    def informative_pairs(self):
        return []

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 使用 (开盘价+收盘价)/2 作为RSI的计算源
        dataframe['hl2'] = (dataframe["close"] + dataframe["open"]) / 2

        # 动量指标
        # ------------------------------------

        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=self.rsi_period.value, price='hl2')

        # EMA - 指数移动平均线
        dataframe['ema5'] = ta.EMA(dataframe, timeperiod=self.ema5_period.value)
        dataframe['ema10'] = ta.EMA(dataframe, timeperiod=self.ema10_period.value)

        # ADX - 平均动向指数
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=self.adx_period.value)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                # 1. 动量确认: RSI 上穿 50
                (qtpylib.crossed_above(dataframe['rsi'], self.rsi_threshold.value)) &
                # 2. 趋势确认: 5日EMA 上穿 10日EMA (黄金交叉)
                (qtpylib.crossed_above(dataframe['ema5'], dataframe['ema10'])) &
                # 3. 趋势强度确认: ADX 大于 25
                (dataframe['adx'] > self.adx_threshold.value) &
                (dataframe['volume'] > 0)  # 确保交易量不为0
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                # 1. 动量确认: RSI 下穿 50
                (qtpylib.crossed_below(dataframe['rsi'], self.rsi_threshold.value)) &
                # 2. 趋势确认: 5日EMA 下穿 10日EMA (死亡交叉)
                (qtpylib.crossed_below(dataframe['ema5'], dataframe['ema10'])) &
                # 3. 趋势强度确认: ADX 大于 25
                (dataframe['adx'] > self.adx_threshold.value) &
                (dataframe['volume'] > 0)  # 确保交易量不为0
            ),
            'exit_long'] = 1
        return dataframe

