# --- 策略总结 ---
# 策略名称: multi_tf (多时间周期)
# 策略类型: 教学/示例代码 (切勿用于实盘)
#
# 核心功能:
# 该策略是一个功能强大的教学示例，旨在全面展示 Freqtrade 中 `@informative` 装饰器的各种用法，
# 以实现复杂的多时间周期和多资产分析。其核心目的是展示如何将不同时间周期、不同交易对的指标整合起来，形成一个统一的交易逻辑。
#   - 多种`@informative`用法展示:
#       1. 高周期自身指标: 获取当前交易对在 `30m` 和 `1h` 周期下的RSI。
#       2. 大盘指标: 获取 `BTC/USDT` 在 `1h` 周期下的RSI，作为市场风向标。
#       3. 其他关键对指标: 获取 `ETH/BTC` 的指标，分析主要竞争币种的相对强弱。
#       4. 自定义命名: 展示如何通过格式化字符串，为引入的指标自定义列名，使代码更清晰。
#   - 交易逻辑 (示例):
#       - 买入: 这是一个极致的"共振抄底"逻辑。只有当**所有**层面 (当前币种的5m, 30m, 1h周期、BTC的1h周期、ETH/BTC的1h周期) 的RSI指标**同时**显示"超卖"信号时，才会入场。这是一种等待全市场同步超跌才行动的策略。
#       - 卖出: 当当前币种在 `5m` 周期上显示"超买"时卖出。
#
# 优点:
#   - 绝佳的教学范例: 完美地展示了 `@informative` 装饰器的灵活性和强大功能，是学习多时间周期分析的必看代码。
#   - 强大的共振逻辑: 展示了如何构建一个需要多重信号确认的、非常稳健的 (虽然可能信号稀少) 交易系统。
#
# 缺点:
#   - 仅为教学目的: 作者明确标出切勿用于实盘。其交易逻辑是为了展示功能而设计的，不保证盈利。
#   - 信号可能极其稀少: 要求所有指标同时满足条件，在真实市场中可能很长时间都不会出现一次交易信号。
#   - 数据处理复杂: 管理和合并多个数据源需要非常小心，以防引入bug。

import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy as np
import talib.abstract as ta
from freqtrade.strategy import (IStrategy, informative, IntParameter, RealParameter, BooleanParameter)
from pandas import DataFrame, Series
import math
import pandas_ta as pta
import logging

logger = logging.getLogger(__name__)

# !!!! 切勿用于实盘交易 !!!!

class multi_tf (IStrategy):

    def version(self) -> str:
        """返回策略版本"""
        return "v1"

    INTERFACE_VERSION = 3

    # 投资回报率 (ROI) 表:
    minimal_roi = RealParameter(0.1, 0.5, default=0.2, space='roi', optimize=True)

    # 止损:
    stoploss = RealParameter(-0.15, -0.05, default=-0.1, space='protection', optimize=True)

    # 追踪止损:
    trailing_stop = BooleanParameter(default=False, space='protection', optimize=True)
    trailing_stop_positive = RealParameter(0.001, 0.01, default=0.001, space='protection', optimize=True)
    trailing_stop_positive_offset = RealParameter(0.005, 0.02, default=0.01, space='protection', optimize=True)
    trailing_only_offset_is_reached = BooleanParameter(default=True, space='protection', optimize=True)

    # 卖出信号设置
    use_exit_signal = True
    exit_profit_only = False
    exit_profit_offset = 0.01
    ignore_roi_if_entry_signal = False

    # 基础时间框架
    timeframe = '5m'

    process_only_new_candles = True
    startup_candle_count = 100

    # Indicator periods
    rsi_period_30m_1h = IntParameter(10, 20, default=14, space='buy', optimize=True)
    rsi_period_btc_1h = IntParameter(10, 20, default=14, space='buy', optimize=True)
    rsi_period_eth_btc_1h = IntParameter(10, 20, default=14, space='buy', optimize=True)
    rsi_fast_upper_period = IntParameter(2, 8, default=4, space='buy', optimize=True)
    rsi_super_fast_period = IntParameter(1, 5, default=2, space='buy', optimize=True)
    rsi_main_period = IntParameter(10, 20, default=14, space='buy', optimize=True)

    # Logic thresholds
    buy_btc_1h_rsi = IntParameter(30, 45, default=35, space='buy', optimize=True)
    buy_eth_btc_1h_rsi = IntParameter(40, 60, default=50, space='buy', optimize=True)
    buy_btc_fast_upper_rsi = IntParameter(30, 50, default=40, space='buy', optimize=True)
    buy_btc_super_fast_rsi = IntParameter(20, 40, default=30, space='buy', optimize=True)
    buy_30m_rsi = IntParameter(30, 50, default=40, space='buy', optimize=True)
    buy_1h_rsi = IntParameter(30, 50, default=40, space='buy', optimize=True)
    buy_main_rsi = IntParameter(20, 40, default=30, space='buy', optimize=True)
    
    sell_main_rsi = IntParameter(65, 85, default=70, space='sell', optimize=True)

    # `informative_pairs` 方法不是必须的，因为我们使用了 `@informative` 装饰器。
    # def informative_pairs(self): ...

    # 为每个交易对定义信息性的更高时间周期。装饰器可以堆叠在同一个方法上。
    # 在 populate_indicators 中可用作 'rsi_30m' 和 'rsi_1h'。
    @informative('30m')
    @informative('1h')
    def populate_indicators_1h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """为当前交易对计算30分钟和1小时周期的RSI"""
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=self.rsi_period_30m_1h.value)
        return dataframe

    # 定义 BTC/STAKE (例如 BTC/USDT) 的信息对。
    # 当前的计价货币应作为 {stake} 格式的变量指定，而不是硬编码。
    # 在 populate_indicators 等方法中可用作 'btc_usdt_rsi_1h'。
    @informative('1h', 'BTC/{stake}')
    def populate_indicators_btc_1h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """为 BTC/STAKE 交易对计算1小时周期的RSI"""
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=self.rsi_period_btc_1h.value)
        return dataframe

    # 定义 ETH/BTC 的信息对。如果报价货币与计价货币不同，必须明确指定。
    # 在 populate_indicators 等方法中可用作 'eth_btc_rsi_1h'。
    @informative('1h', 'ETH/BTC')
    def populate_indicators_eth_btc_1h(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """为 ETH/BTC 交易对计算1小时周期的RSI"""
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=self.rsi_period_eth_btc_1h.value)
        return dataframe

    # 定义 BTC/STAKE 信息对，并使用自定义格式化器来命名列。
    # 可用的列名: `BTC_rsi_fast_upper_1h`, `BTC_close_1h` ...
    @informative('1h', 'BTC/{stake}', 'BTC_{column}_{timeframe}')
    def populate_indicators_btc_1h_2(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """为 BTC/STAKE 计算一个快速RSI，并自定义列名"""
        dataframe['rsi_fast_upper'] = ta.RSI(dataframe, timeperiod=self.rsi_fast_upper_period.value)
        return dataframe

    # 定义 BTC/STAKE 信息对，并使用另一个自定义格式化器。
    # 可用的列名: `btc_rsi_super_fast_1h`
    @informative('1h', 'BTC/{stake}', '{base}_{column}_{timeframe}')
    def populate_indicators_btc_1h_3(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """为 BTC/STAKE 计算一个超快速RSI，并自定义列名"""
        dataframe['rsi_super_fast'] = ta.RSI(dataframe, timeperiod=self.rsi_super_fast_period.value)
        return dataframe

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 当前交易对的策略时间框架（5m）指标。
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=self.rsi_main_period.value)
        # 来自装饰器的信息对数据在此方法中已可用。
        dataframe['rsi_less'] = dataframe['rsi'] < dataframe['rsi_1h']
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        stake = self.config['stake_currency'].lower()
        dataframe.loc[
            (
                # --- 共振抄底条件 ---
                (dataframe[f'btc_{stake}_rsi_1h'] < self.buy_btc_1h_rsi.value)       # 1. BTC 1h RSI 超卖
                &
                (dataframe['eth_btc_rsi_1h'] < self.buy_eth_btc_1h_rsi.value)            # 2. ETH/BTC 1h RSI 弱势
                &
                (dataframe['BTC_rsi_fast_upper_1h'] < self.buy_btc_fast_upper_rsi.value)     # 3. BTC 1h 快速 RSI 超卖
                &
                (dataframe['btc_rsi_super_fast_1h'] < self.buy_btc_super_fast_rsi.value)     # 4. BTC 1h 超快速 RSI 极度超卖
                &
                (dataframe['rsi_30m'] < self.buy_30m_rsi.value)                   # 5. 当前币种 30m RSI 超卖
                &
                (dataframe['rsi_1h'] < self.buy_1h_rsi.value)                    # 6. 当前币种 1h RSI 超卖
                &
                (dataframe['rsi'] < self.buy_main_rsi.value)                       # 7. 当前币种 5m RSI 极度超卖
                &
                (dataframe['rsi_less'] == True)               # 8. 5m RSI < 1h RSI (短期动能弱于长期)
                &
                (dataframe['volume'] > 0)
            ),
            ['enter_long', 'enter_tag']] = (1, 'buy_signal_rsi_all_tf_oversold')

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:

        dataframe.loc[
            (
                (dataframe['rsi'] > self.sell_main_rsi.value)                  # 1. 当前币种 5m RSI 超买
                &
                (dataframe['rsi_less'] == False)         # 2. 5m RSI > 1h RSI (短期动能强于长期)
                &
                (dataframe['volume'] > 0)
            ),
            ['exit_long', 'exit_tag']] = (1, 'exit_signal_rsi_overbought')

        return dataframe
