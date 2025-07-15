# --- 策略总结 ---
# 策略名称: Bandtastic (布林带大师)
#
# 盈利逻辑:
# 该策略是一个高度可配置的"均值回归"策略。其核心思想是，当价格触及布林带的外部通道时，大概率会反转回归至中轨。
#   - 买入(Entry): 主要的买入触发条件是价格跌破某个下轨布林带（标准差可从1到4选择）。这意味着市场可能处于超卖状态，预期价格会反弹。
#   - 卖出(Exit): 主要的卖出触发条件是价格突破某个上轨布林带（标准差可从1到4选择）。这意味着市场可能处于超买状态，预期价格会回调。
# 策略还包含可选的"守护条件"（Guards），如RSI、MFI和EMA交叉，用于进一步确认入场和出场时机，过滤掉一些噪音信号。
# 整个策略通过超参数优化(Hyperopt)来寻找最佳的触发器和守护条件组合。
#
# 优点:
#   - 高度灵活和可定制: 策略的几乎每个部分都可以通过超参数进行开关和调整，适应性强。
#   - 清晰的均值回归逻辑: 基于成熟的布林带指标，逻辑简单直观。
#   - 强大的过滤机制: 可选的RSI/MFI/EMA守护条件可以有效提升信号质量。
#
# 缺点:
#   - 在强趋势市场中表现不佳: 均值回归策略的天然弱点是，在持续的单边上涨或下跌行情中，它会逆势交易，可能导致过早卖出牛市资产或在熊市中"接飞刀"。
#   - 参数极其敏感: 策略的表现高度依赖于超参数的设置，一组好的参数在某个市场周期内可能表现优异，但在另一个周期内可能表现很差。需要频繁优化。
#   - 复杂性: 大量的可调参数使得优化过程非常耗时和复杂。
import talib.abstract as ta
import numpy as np  # noqa
import pandas as pd
from functools import reduce
from pandas import DataFrame
import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.strategy import IStrategy, CategoricalParameter, DecimalParameter, IntParameter, RealParameter, BooleanParameter

__author__ = "Robert Roman"
__copyright__ = "可自由使用"
__license__ = "MIT"
__version__ = "1.0"
__maintainer__ = "Robert Roman"
__email__ = "robertroman7@gmail.com"
__BTC_donation__ = "3FgFaG15yntZYSUzfEpxr5mDt1RArvcQrK"


# 使用夏普比率和1年数据进行优化
# 199/40000: 30918 次交易. 18982/3408/8528 胜/平/负. 平均利润 0.39%. 利润中位数 0.65%. 总利润 119934.26 USDT (119.93%). 平均持仓时间 8:12:00. 目标函数值: -127.60220

class Bandtastic(IStrategy):
    INTERFACE_VERSION = 3

    timeframe = '15m'

    # 投资回报率 (ROI) 表:
    @property
    def minimal_roi(self):
        return {
            "0": self.roi_p1.value,
            "69": self.roi_p2.value,
            "229": self.roi_p3.value,
            "566": 0
        }
    roi_p1 = RealParameter(0.1, 0.2, default=0.162, space='roi', optimize=True)
    roi_p2 = RealParameter(0.05, 0.12, default=0.097, space='roi', optimize=True)
    roi_p3 = RealParameter(0.03, 0.08, default=0.061, space='roi', optimize=True)


    # 止损:
    stoploss = RealParameter(-0.4, -0.3, default=-0.345, space='protection', optimize=True)

    startup_candle_count = 999

    # 追踪止损 (Trailing stop):
    trailing_stop = BooleanParameter(default=True, space='protection', optimize=True)
    trailing_stop_positive = RealParameter(0.005, 0.02, default=0.01, space='protection', optimize=True)
    trailing_stop_positive_offset = RealParameter(0.03, 0.08, default=0.058, space='protection', optimize=True)
    trailing_only_offset_is_reached = BooleanParameter(default=False, space='protection', optimize=True)

    # Hyperopt 买入参数
    buy_fastema = IntParameter(low=1, high=236, default=211, space='buy', optimize=True, load=True)
    buy_slowema = IntParameter(low=1, high=250, default=250, space='buy', optimize=True, load=True)
    buy_rsi = IntParameter(low=15, high=70, default=52, space='buy', optimize=True, load=True)
    buy_mfi = IntParameter(low=15, high=70, default=30, space='buy', optimize=True, load=True)

    buy_rsi_enabled = CategoricalParameter([True, False], space='buy', optimize=True, default=False)
    buy_mfi_enabled = CategoricalParameter([True, False], space='buy', optimize=True, default=False)
    buy_ema_enabled = CategoricalParameter([True, False], space='buy', optimize=True, default=False)
    buy_trigger = CategoricalParameter(["bb_lower1", "bb_lower2", "bb_lower3", "bb_lower4"], default="bb_lower1", space="buy", optimize=True)

    # Hyperopt 卖出参数
    sell_fastema = IntParameter(low=1, high=365, default=7, space='sell', optimize=True, load=True)
    sell_slowema = IntParameter(low=1, high=365, default=6, space='sell', optimize=True, load=True)
    sell_rsi = IntParameter(low=30, high=100, default=57, space='sell', optimize=True, load=True)
    sell_mfi = IntParameter(low=30, high=100, default=46, space='sell', optimize=True, load=True)

    sell_rsi_enabled = CategoricalParameter([True, False], space='sell', optimize=True, default=False)
    sell_mfi_enabled = CategoricalParameter([True, False], space='sell', optimize=True, default=True)
    sell_ema_enabled = CategoricalParameter([True, False], space='sell', optimize=True, default=False)
    sell_trigger = CategoricalParameter(["sell-bb_upper1", "sell-bb_upper2", "sell-bb_upper3", "sell-bb_upper4"], default="sell-bb_upper2", space="sell", optimize=True)

    # Indicator parameters
    rsi_period = IntParameter(10, 20, default=14, space='buy', optimize=True)
    mfi_period = IntParameter(10, 20, default=14, space='buy', optimize=True)
    bb_window = IntParameter(15, 30, default=20, space='buy', optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=self.rsi_period.value)
        # MFI
        dataframe['mfi'] = ta.MFI(dataframe, timeperiod=self.mfi_period.value)

        # 计算标准差为1, 2, 3, 4的布林带
        bollinger1 = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=self.bb_window.value, stds=1)
        dataframe['bb_lowerband1'] = bollinger1['lower']
        dataframe['bb_middleband1'] = bollinger1['mid']
        dataframe['bb_upperband1'] = bollinger1['upper']

        bollinger2 = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=self.bb_window.value, stds=2)
        dataframe['bb_lowerband2'] = bollinger2['lower']
        dataframe['bb_middleband2'] = bollinger2['mid']
        dataframe['bb_upperband2'] = bollinger2['upper']

        bollinger3 = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=self.bb_window.value, stds=3)
        dataframe['bb_lowerband3'] = bollinger3['lower']
        dataframe['bb_middleband3'] = bollinger3['mid']
        dataframe['bb_upperband3'] = bollinger3['upper']

        bollinger4 = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=self.bb_window.value, stds=4)
        dataframe['bb_lowerband4'] = bollinger4['lower']
        dataframe['bb_middleband4'] = bollinger4['mid']
        dataframe['bb_upperband4'] = bollinger4['upper']
        
        # 构建EMA指标 - 只计算当前需要的周期
        dataframe[f'buy_fast_ema'] = ta.EMA(dataframe, timeperiod=self.buy_fastema.value)
        dataframe[f'buy_slow_ema'] = ta.EMA(dataframe, timeperiod=self.buy_slowema.value)
        dataframe[f'sell_fast_ema'] = ta.EMA(dataframe, timeperiod=self.sell_fastema.value)
        dataframe[f'sell_slow_ema'] = ta.EMA(dataframe, timeperiod=self.sell_slowema.value)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []

        # -- 守护条件 -- (可选的额外验证)
        if self.buy_rsi_enabled.value:
            conditions.append(dataframe['rsi'] < self.buy_rsi.value)
        if self.buy_mfi_enabled.value:
            conditions.append(dataframe['mfi'] < self.buy_mfi.value)
        if self.buy_ema_enabled.value:
            conditions.append(dataframe[f'buy_fast_ema'] > dataframe[f'buy_slow_ema'])

        # -- 触发器 -- (核心买入信号)
        if self.buy_trigger.value == 'bb_lower1':
            conditions.append(dataframe["close"] < dataframe['bb_lowerband1'])
        if self.buy_trigger.value == 'bb_lower2':
            conditions.append(dataframe["close"] < dataframe['bb_lowerband2'])
        if self.buy_trigger.value == 'bb_lower3':
            conditions.append(dataframe["close"] < dataframe['bb_lowerband3'])
        if self.buy_trigger.value == 'bb_lower4':
            conditions.append(dataframe["close"] < dataframe['bb_lowerband4'])

        # 确保交易量不为0
        conditions.append(dataframe['volume'] > 0)

        if conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, conditions),
                'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []

        # -- 守护条件 -- (可选的额外验证)
        if self.sell_rsi_enabled.value:
            conditions.append(dataframe['rsi'] > self.sell_rsi.value)
        if self.sell_mfi_enabled.value:
            conditions.append(dataframe['mfi'] > self.sell_mfi.value)
        if self.sell_ema_enabled.value:
            conditions.append(dataframe[f'sell_fast_ema'] < dataframe[f'sell_slow_ema'])

        # -- 触发器 -- (核心卖出信号)
        if self.sell_trigger.value == 'sell-bb_upper1':
            conditions.append(dataframe["close"] > dataframe['bb_upperband1'])
        if self.sell_trigger.value == 'sell-bb_upper2':
            conditions.append(dataframe["close"] > dataframe['bb_upperband2'])
        if self.sell_trigger.value == 'sell-bb_upper3':
            conditions.append(dataframe["close"] > dataframe['bb_upperband3'])
        if self.sell_trigger.value == 'sell-bb_upper4':
            conditions.append(dataframe["close"] > dataframe['bb_upperband4'])

        # 确保交易量不为0
        conditions.append(dataframe['volume'] > 0)

        if conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, conditions),
                'exit_long'] = 1

        return dataframe
