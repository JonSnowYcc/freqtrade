# --- 策略总结 ---
# 策略名称: Strategy002
#
# 盈利逻辑:
# 这是一个典型的"共振抄底"或"深度超卖反转"策略。它的核心思想是，只有当多个来自不同维度 (动量、价格通道、K线形态)
# 的指标**同时**发出强烈的超卖信号时，才认为市场处于一个极端底部，并入场捕捉价格反弹。
#   - 买入(Entry): 策略的入场条件非常苛刻，需要以下四个信号**同时**成立：
#       1. RSI超卖: 相对强弱指数 (RSI) 低于30。
#       2. Stoch超卖: 随机指标 (Stochastic) 的 %K线低于20。
#       3. 价格极端便宜: 收盘价跌破布林带下轨，表明价格已严重偏离均值。
#       4. K线反转形态: 图表上出现了一个看涨的"锤子线" (Hammer)形态。
#   - 卖出(Exit): 卖出逻辑结合了趋势和动量指标：
#       1. 趋势反转: 抛物线转向指标 (Parabolic SAR) 的信号点出现在价格上方，发出卖出信号，起到追踪止损的作用。
#       2. 动能确认: 费雪RSI (Fisher RSI) 指标大于0.3，表明向上的反弹动能已经达到一定强度，可能接近尾声。
#
# 优点:
#   - 高可靠性: 多重、多维度的入场确认，可以过滤掉绝大多数的噪音和假信号，理论上入场胜率较高。
#   - 逻辑清晰: 策略的买卖逻辑都基于经典、成熟的技术指标组合，易于理解。
#   - 风险明确: 在市场极度恐慌时入场，风险回报比可能较好。
#
# 缺点:
#   - 信号稀少: 同时满足四个苛刻的条件非常困难，可能导致策略在很长一段时间内都没有交易信号。
#   - 典型的反转策略风险: 在持续的"下跌不言底"的单边熊市中，任何抄底行为都面临"接飞刀"的巨大风险。
#   - 对参数敏感: 策略中使用的阈值 (如RSI<30, slowk<20) 都是固定值，可能需要针对不同市场进行优化。

# --- 请勿删除这些库 ---
from freqtrade.strategy import IStrategy, IntParameter, RealParameter, BooleanParameter
from typing import Dict, List
from functools import reduce
from pandas import DataFrame
# --------------------------------

import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy # noqa


class Strategy002(IStrategy):
    """
    策略 002
    作者@: Gerald Lonlas
    Github@: https://github.com/freqtrade/freqtrade-strategies

    如何使用它?
    > python3 ./freqtrade/main.py -s Strategy002
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
    stoch_k_period = IntParameter(3, 10, default=5, space='buy', optimize=True)
    stoch_d_period = IntParameter(2, 7, default=3, space='buy', optimize=True)
    stoch_slowing = IntParameter(2, 7, default=3, space='buy', optimize=True)
    rsi_period = IntParameter(10, 20, default=14, space='buy', optimize=True)
    fisher_rsi_multiplier = RealParameter(0.05, 0.2, default=0.1, space='buy', optimize=True)
    bb_window = IntParameter(15, 30, default=20, space='buy', optimize=True)
    bb_std = RealParameter(1.5, 3.0, default=2.0, space='buy', optimize=True)
    sar_acceleration = RealParameter(0.01, 0.05, default=0.02, space='buy', optimize=True)
    sar_maximum = RealParameter(0.1, 0.3, default=0.2, space='buy', optimize=True)

    # Logic thresholds
    buy_rsi_threshold = IntParameter(20, 40, default=30, space='buy', optimize=True)
    buy_slowk_threshold = IntParameter(15, 30, default=20, space='buy', optimize=True)
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

        # Stoch 随机指标
        stoch = ta.STOCH(dataframe,
                       fastk_period=self.stoch_k_period.value,
                       slowk_period=self.stoch_d_period.value,
                       slowd_period=self.stoch_slowing.value)
        dataframe['slowk'] = stoch['slowk']

        # RSI 相对强弱指数
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=self.rsi_period.value)

        # Fisher RSI - 对RSI进行反费雪变换，值域[-1.0, 1.0] (https://goo.gl/2JGGoy)
        rsi = self.fisher_rsi_multiplier.value * (dataframe['rsi'] - 50)
        dataframe['fisher_rsi'] = (numpy.exp(2 * rsi) - 1) / (numpy.exp(2 * rsi) + 1)

        # Bollinger bands 布林带
        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=self.bb_window.value, stds=self.bb_std.value)
        dataframe['bb_lowerband'] = bollinger['lower']

        # SAR Parabol 抛物线转向指标
        dataframe['sar'] = ta.SAR(dataframe, acceleration=self.sar_acceleration.value, maximum=self.sar_maximum.value)

        # Hammer K线形态: 值为 [0, 100]
        dataframe['CDLHAMMER'] = ta.CDLHAMMER(dataframe)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        基于TA指标，为给定的dataframe填充买入信号
        """
        dataframe.loc[
            (
                # 1. RSI 指标超卖
                (dataframe['rsi'] < self.buy_rsi_threshold.value) &
                # 2. 随机指标超卖
                (dataframe['slowk'] < self.buy_slowk_threshold.value) &
                # 3. 价格跌破布林带下轨
                (dataframe['bb_lowerband'] > dataframe['close']) &
                # 4. 出现锤子线反转形态
                (dataframe['CDLHAMMER'] > 0)
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        基于TA指标，为给定的dataframe填充卖出信号
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
