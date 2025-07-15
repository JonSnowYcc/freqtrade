# --- 策略总结 ---
# 策略名称: Strategy003
#
# 盈利逻辑:
# 该策略是 `Strategy002` 的一个更复杂、更精细的版本，同样属于"共振抄底"或"深度超卖反转"类型。
# 它通过一套极其复杂和严格的条件组合来寻找它认为的"绝对底部"，以捕捉价格反弹。其卖出逻辑与 `Strategy002` 完全相同。
#   - 买入(Entry): 策略的入场条件是一个包含多个子条件的多层逻辑，可以概括为以下几个方面必须**同时**满足：
#       1. 极端动量超卖: RSI、MFI (资金流量指标)、Fisher RSI 这三个动量指标必须全部处于极度超卖的水平。
#       2. 价格处于下跌趋势中: 当前价格必须低于40周期的SMA均线，确认是在一个下跌的波段中寻找买点。
#       3. 长期趋势并非灾难性下跌: 通过一个`或`条件，要求`要么`长期趋势 (EMA50>EMA100) 依然看涨，`要么`超短期趋势 (EMA5>EMA10) 刚刚发生黄金交叉。这个条件旨在避免在"无底深渊"式的熊市中抄底。
#       4. 随机指标的特定形态: 要求`fastd > fastk`，这通常是一个看跌信号，可能意在捕捉下跌动能耗尽前的"最后一跌"。
#   - 卖出(Exit): 逻辑与`Strategy002`一致，当抛物线SAR指标给出卖出信号并且Fisher RSI显示反弹动能已达到一定水平时退出。
#
# 优点:
#   - 极度严格的过滤: 拥有比`Strategy002`更复杂的过滤条件，理论上可以进一步提高信号的准确率，避免进入一些虚假的反弹。
#   - 结合宏观与微观趋势: 通过EMA的`或`条件，巧妙地结合了对长期大趋势和短期微观趋势的判断。
#
# 缺点:
#   - 信号极其稀少: 条件如此复杂和严格，很可能导致策略在绝大多数时间里都处于空仓观望状态。
#   - 逻辑复杂难懂: 部分条件组合 (特别是Stochastic的用法) 非常规，难以直观理解其背后的原理，策略的"黑箱"程度较高。
#   - 典型的反转策略风险: 依然无法从根本上避免在单边熊市中"接飞刀"的风险。

# --- 请勿删除这些库 ---
from freqtrade.strategy import IStrategy, IntParameter, RealParameter, BooleanParameter
from typing import Dict, List
from functools import reduce
from pandas import DataFrame
# --------------------------------

import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy # noqa


class Strategy003(IStrategy):
    """
    策略 003
    作者@: Gerald Lonlas
    Github@: https://github.com/freqtrade/freqtrade-strategies

    如何使用它?
    > python3 ./freqtrade/main.py -s Strategy003
    """

    INTERFACE_VERSION: int = 3
    # 为该策略设计的最小投资回报率(ROI)。
    # 如果配置文件中包含 "minimal_roi"，此属性将被覆盖。
    @property
    def minimal_roi(self):
        return {
            "60": self.roi_p1.value,
            "30": self.roi_p2.value,
            "20": self.roi_p3.value,
            "0": self.roi_p4.value
        }
    roi_p1 = RealParameter(0.005, 0.02, default=0.01, space='roi', optimize=True)
    roi_p2 = RealParameter(0.01, 0.04, default=0.03, space='roi', optimize=True)
    roi_p3 = RealParameter(0.02, 0.05, default=0.04, space='roi', optimize=True)
    roi_p4 = RealParameter(0.04, 0.08, default=0.05, space='roi', optimize=True)


    # 为该策略设计的优化止损。
    # 如果配置文件中包含 "stoploss"，此属性将被覆盖。
    stoploss = RealParameter(-0.15, -0.05, default=-0.10, space='protection', optimize=True)

    # 策略的最佳时间框架
    timeframe = '5m'

    # 追踪止损
    trailing_stop = BooleanParameter(default=False, space='protection', optimize=True)
    trailing_stop_positive = RealParameter(0.005, 0.02, default=0.01, space='protection', optimize=True)
    trailing_stop_positive_offset = RealParameter(0.01, 0.03, default=0.02, space='protection', optimize=True)
    trailing_only_offset_is_reached = BooleanParameter(default=False, space='protection', optimize=True)


    # 仅在新蜡烛图上运行 "populate_indicators()"
    process_only_new_candles = True

    # 实验性设置 (如果设置，配置将覆盖这些)
    use_exit_signal = True
    exit_profit_only = True
    ignore_roi_if_entry_signal = False

    # 可选的订单类型映射
    order_types = {
        'entry': 'limit',
        'exit': 'limit',
        'stoploss': 'market',
        'stoploss_on_exchange': False
    }

    # Indicator parameters
    mfi_period = IntParameter(10, 20, default=14, space='buy', optimize=True)
    stochf_k_period = IntParameter(3, 10, default=5, space='buy', optimize=True)
    rsi_period = IntParameter(10, 20, default=14, space='buy', optimize=True)
    fisher_rsi_multiplier = RealParameter(0.05, 0.2, default=0.1, space='buy', optimize=True)
    bb_window = IntParameter(15, 30, default=20, space='buy', optimize=True)
    bb_std = RealParameter(1.5, 3.0, default=2.0, space='buy', optimize=True)
    ema5_period = IntParameter(3, 10, default=5, space='buy', optimize=True)
    ema10_period = IntParameter(8, 15, default=10, space='buy', optimize=True)
    ema50_period = IntParameter(40, 60, default=50, space='buy', optimize=True)
    ema100_period = IntParameter(80, 120, default=100, space='buy', optimize=True)
    sar_acceleration = RealParameter(0.01, 0.05, default=0.02, space='buy', optimize=True)
    sar_maximum = RealParameter(0.1, 0.3, default=0.2, space='buy', optimize=True)
    sma_period = IntParameter(30, 50, default=40, space='buy', optimize=True)
    
    # Logic thresholds
    buy_rsi_threshold = IntParameter(20, 40, default=28, space='buy', optimize=True)
    buy_fisher_rsi_threshold = RealParameter(-1.0, -0.8, default=-0.94, space='buy', optimize=True)
    buy_mfi_threshold = IntParameter(10, 25, default=16, space='buy', optimize=True)
    sell_fisher_rsi_threshold = RealParameter(0.1, 0.5, default=0.3, space='sell', optimize=True)

    def informative_pairs(self):
        """
        定义需要从交易所缓存的额外、信息性的交易对/时间间隔组合。
        """
        return []

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        向给定的DataFrame中添加几个不同的TA指标。

        性能提示: 为了获得最佳性能，请节约使用指标的数量。
        """

        # MFI 资金流量指标
        dataframe['mfi'] = ta.MFI(dataframe, timeperiod=self.mfi_period.value)

        # Stoch fast 快速随机指标
        stoch_fast = ta.STOCHF(dataframe, fastk_period=self.stochf_k_period.value)
        dataframe['fastd'] = stoch_fast['fastd']
        dataframe['fastk'] = stoch_fast['fastk']

        # RSI 相对强弱指数
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=self.rsi_period.value)

        # Fisher RSI - 对RSI进行反费雪变换
        rsi = self.fisher_rsi_multiplier.value * (dataframe['rsi'] - 50)
        dataframe['fisher_rsi'] = (numpy.exp(2 * rsi) - 1) / (numpy.exp(2 * rsi) + 1)

        # Bollinger bands 布林带
        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=self.bb_window.value, stds=self.bb_std.value)
        dataframe['bb_lowerband'] = bollinger['lower']

        # EMA - 指数移动平均线
        dataframe['ema5'] = ta.EMA(dataframe, timeperiod=self.ema5_period.value)
        dataframe['ema10'] = ta.EMA(dataframe, timeperiod=self.ema10_period.value)
        dataframe['ema50'] = ta.EMA(dataframe, timeperiod=self.ema50_period.value)
        dataframe['ema100'] = ta.EMA(dataframe, timeperiod=self.ema100_period.value)

        # SAR Parabol 抛物线转向指标
        dataframe['sar'] = ta.SAR(dataframe, acceleration=self.sar_acceleration.value, maximum=self.sar_maximum.value)

        # SMA - 简单移动平均线
        dataframe['sma'] = ta.SMA(dataframe, timeperiod=self.sma_period.value)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        基于TA指标，为给定的dataframe填充买入信号
        """
        dataframe.loc[
            (
                # --- 极端动量超卖条件 ---
                (dataframe['rsi'] < self.buy_rsi_threshold.value) &
                (dataframe['fisher_rsi'] < self.buy_fisher_rsi_threshold.value) &
                (dataframe['mfi'] < self.buy_mfi_threshold.value) &
                
                # --- 价格位置条件 ---
                (dataframe['close'] < dataframe['sma']) &
                
                # --- 长期趋势过滤条件 (OR) ---
                (
                    # 长期趋势看涨
                    (dataframe['ema50'] > dataframe['ema100']) |
                    # 或，超短期趋势刚刚金叉
                    (qtpylib.crossed_above(dataframe['ema5'], dataframe['ema10']))
                ) &

                # --- 随机指标形态条件 (捕捉最后一跌?) ---
                (dataframe['fastd'] > dataframe['fastk']) &
                (dataframe['fastd'] > 0)
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        基于TA指标，为给定的dataframe填充卖出信号 (逻辑与Strategy002相同)
        """
        dataframe.loc[
            (
                # 1. 抛物线SAR指标发出卖出信号 (作为追踪止损)
                (dataframe['sar'] > dataframe['close']) &
                # 2. Fisher RSI 指标显示上涨动能已达一定强度
                (dataframe['fisher_rsi'] > self.sell_fisher_rsi_threshold.value)
            ),
            'exit_long'] = 1
        return dataframe
