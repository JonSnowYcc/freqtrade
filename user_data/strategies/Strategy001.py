# --- 策略总结 ---
# 策略名称: Strategy001
#
# 盈利逻辑:
# 这是一个趋势跟踪策略，它结合了传统的指数移动平均线 (EMA) 和平均K线 (Heikin-Ashi / HA) 来平滑市场噪音并识别趋势。
#   - 买入(Entry): 当以下三个条件**同时**满足时，产生买入信号：
#       1. 趋势形成: 20周期EMA上穿50周期EMA，形成"黄金交叉"，确认短期上升趋势。
#       2. 趋势维持: 平均K线的收盘价高于20周期EMA，表明平滑后的价格维持在短期趋势线之上。
#       3. 当前动能: 当前的平均K线是一根阳线 (收盘价 > 开盘价)，表明当下的动能是向上的。
#   - 卖出(Exit): 卖出逻辑结合了几个信号，其中一个较为反常：
#       1. 中期趋势加速(?): 50周期EMA上穿100周期EMA。这通常是一个看涨信号，但在此处被用作退出条件，可能意在趋势加速时获利了结，但也可能是逻辑错误。
#       2. 趋势转弱: 平均K线的收盘价跌破20周期EMA。
#       3. 当前动能: 当前的平均K线是一根阴线。
# 总体来看，该策略试图在EMA均线确认的上升趋势中，通过平滑后的Heikin-Ashi K线寻找一个稳固的看涨时点买入。其卖出逻辑较为复杂且存在矛盾之处。
#
# 优点:
#   - 噪音过滤: Heikin-Ashi蜡烛图可以有效过滤掉部分市场噪音，使趋势看起来更平滑，有助于避免在短暂的盘整中被震荡出局。
#   - 多重确认: 结合了EMA交叉和Heikin-Ashi形态，提高了入场信号的可靠性。
#
# 缺点:
#   - 信号滞后: EMA交叉和Heikin-Ashi本身都具有滞后性，两者结合可能会导致入场信号晚于趋势的实际起点。
#   - 退出逻辑可疑: 卖出条件中包含一个看涨的EMA交叉信号，这与另外两个看跌条件相矛盾，使得退出逻辑难以理解，可能导致过早退出或在不合适的时机退出。
#   - 依赖平滑趋势: 在快速反转或无明确趋势的震荡市场中，Heikin-Ashi可能会持续显示同一种颜色，导致信号失效。

# --- 请勿删除这些库 ---
from freqtrade.strategy import IStrategy, IntParameter, RealParameter, BooleanParameter
from typing import Dict, List
from functools import reduce
from pandas import DataFrame
# --------------------------------

import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib


class Strategy001(IStrategy):
    """
    策略 001
    作者@: Gerald Lonlas
    Github@: https://github.com/freqtrade/freqtrade-strategies

    如何使用它?
    > python3 ./freqtrade/main.py -s Strategy001
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
    ema20_period = IntParameter(15, 30, default=20, space='buy', optimize=True)
    ema50_period = IntParameter(40, 60, default=50, space='buy', optimize=True)
    ema100_period = IntParameter(80, 120, default=100, space='sell', optimize=True)

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

        dataframe['ema20'] = ta.EMA(dataframe, timeperiod=self.ema20_period.value)
        dataframe['ema50'] = ta.EMA(dataframe, timeperiod=self.ema50_period.value)
        dataframe['ema100'] = ta.EMA(dataframe, timeperiod=self.ema100_period.value)

        # 计算平均K线 (Heikin-Ashi)
        heikinashi = qtpylib.heikinashi(dataframe)
        dataframe['ha_open'] = heikinashi['open']
        dataframe['ha_close'] = heikinashi['close']

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        基于TA指标，为给定的dataframe填充买入信号
        """
        dataframe.loc[
            (
                # 1. 趋势确认: 20日EMA上穿50日EMA (黄金交叉)
                qtpylib.crossed_above(dataframe['ema20'], dataframe['ema50']) &
                # 2. 价格维持: HA收盘价高于20日EMA
                (dataframe['ha_close'] > dataframe['ema20']) &
                # 3. 动能确认: HA为阳线
                (dataframe['ha_open'] < dataframe['ha_close'])
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        基于TA指标，为给定的dataframe填充卖出信号
        """
        dataframe.loc[
            (
                # 1. 趋势加速(?): 50日EMA上穿100日EMA。此为看涨信号，用作退出条件很反常。
                qtpylib.crossed_above(dataframe['ema50'], dataframe['ema100']) &
                # 2. 趋势转弱: HA收盘价低于20日EMA
                (dataframe['ha_close'] < dataframe['ema20']) &
                # 3. 动能转弱: HA为阴线
                (dataframe['ha_open'] > dataframe['ha_close'])
            ),
            'exit_long'] = 1
        return dataframe
