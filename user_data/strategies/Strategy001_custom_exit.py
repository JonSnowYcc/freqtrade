# --- 策略总结 ---
# 策略名称: Strategy001_custom_exit (策略001之自定义退出)
#
# 盈利逻辑:
# 该策略是 `Strategy001` 的一个改进版。它保留了与原版完全相同的、基于EMA交叉和Heikin-Ashi K线的买入逻辑，
# 但通过添加一个 `custom_exit` (自定义退出) 函数，引入了更清晰、更合理的退出机制。
#   - 买入逻辑 (与原版相同):
#       1. 趋势形成: 20周期EMA上穿50周期EMA (黄金交叉)。
#       2. 趋势维持: 平均K线(HA)的收盘价高于20周期EMA。
#       3. 当前动能: 平均K线(HA)为阳线。
#   - 混合退出逻辑: 策略现在有两个独立的退出触发器，满足**任何一个**即可退出：
#       1. 原版退出信号: 保留了原版中那个令人困惑的退出逻辑（EMA50上穿EMA100，同时HA转为阴线）。
#       2. 新增自定义退出信号: 这是关键的改进。它增加了一个新的条件：**如果RSI指标大于70 (进入超买区) 并且当前交易是盈利的，则立即卖出**。
#
# 这个新增的 `custom_exit` 逻辑是一个非常标准的"超买止盈"信号，它为原策略提供了一个更可靠、更容易理解的获利了结方式。
#
# 优点:
#   - 退出机制更合理: 新增的基于RSI的退出条件，符合传统的技术分析逻辑，弥补了原版策略退出逻辑可疑的缺陷。
#   - 保护利润: `custom_exit` 中的 `current_profit > 0` 条件确保了只有在盈利时才会因为超买而退出，避免了在亏损时因为RSI超买而卖出。
#   - 功能演示: 很好地展示了如何使用 `custom_exit` 函数来实现独立于 `populate_exit_trend` 的、更灵活的退出条件。
#
# 缺点:
#   - 保留了可疑逻辑: 原版中那个令人困惑的退出逻辑依然被保留在 `populate_exit_trend` 中，可能会与新的 `custom_exit` 逻辑产生冲突或非预期的行为。
#   - 买入逻辑滞后性: 继承了原版策略买入信号滞后的缺点。

# --- 请勿删除这些库 ---
from freqtrade.strategy import IStrategy, Trade, IntParameter, RealParameter, BooleanParameter
from typing import Dict, List
from functools import reduce
from pandas import DataFrame
from datetime import datetime
# --------------------------------

import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib


class Strategy001_custom_exit(IStrategy):

    """
    策略 001_custom_exit
    作者@: Gerald Lonlas, froggleston
    Github@: https://github.com/freqtrade/freqtrade-strategies

    如何使用它?
    > python3 ./freqtrade/main.py -s Strategy001_custom_exit
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
    ema100_period = IntParameter(80, 120, default=100, space='buy', optimize=True)
    rsi_period = IntParameter(10, 20, default=14, space='sell', optimize=True)

    # Custom exit threshold
    sell_rsi_threshold = IntParameter(65, 85, default=70, space='sell', optimize=True)

    def informative_pairs(self):
        """
        定义需要从交易所缓存的额外、信息性的交易对/时间间隔组合。
        """
        return []

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        向给定的DataFrame中添加几个不同的TA指标。
        """

        dataframe['ema20'] = ta.EMA(dataframe, timeperiod=self.ema20_period.value)
        dataframe['ema50'] = ta.EMA(dataframe, timeperiod=self.ema50_period.value)
        dataframe['ema100'] = ta.EMA(dataframe, timeperiod=self.ema100_period.value)

        heikinashi = qtpylib.heikinashi(dataframe)
        dataframe['ha_open'] = heikinashi['open']
        dataframe['ha_close'] = heikinashi['close']

        # 为自定义退出逻辑新增RSI指标
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=self.rsi_period.value)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        基于TA指标，为给定的dataframe填充买入信号 (逻辑与Strategy001完全相同)
        """
        dataframe.loc[
            (
                qtpylib.crossed_above(dataframe['ema20'], dataframe['ema50']) &
                (dataframe['ha_close'] > dataframe['ema20']) &
                (dataframe['ha_open'] < dataframe['ha_close'])  # HA 绿K线
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        基于TA指标，为给定的dataframe填充卖出信号。
        注意：此为原版中令人困惑的卖出逻辑，但它依然有效。
        """
        dataframe.loc[
            (
                qtpylib.crossed_above(dataframe['ema50'], dataframe['ema100']) &
                (dataframe['ha_close'] < dataframe['ema20']) &
                (dataframe['ha_open'] > dataframe['ha_close'])  # HA 红K线
            ),
            'exit_long'] = 1
        return dataframe

    def custom_exit(self, pair: str, trade: Trade, current_time: datetime, current_rate: float, current_profit: float, **kwargs):
        """
        自定义退出逻辑，提供了一个额外的、更清晰的退出条件。
        :return: 如果满足条件，返回一个说明退出原因的字符串；否则返回None。
        """
        # 获取最新的分析数据帧
        dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
        # 获取最后一根K线
        current_candle = dataframe.iloc[-1].squeeze()

        # 条件：如果RSI大于阈值 (超买) 并且 当前交易盈利
        if (current_candle['rsi'] > self.sell_rsi_threshold.value) and (current_profit > 0):
            # 返回一个字符串来触发卖出，这个字符串会作为退出原因被记录
            return "rsi_profit_sell"

        # 如果不满足条件，返回 None
        return None
