# --- 策略总结 ---
# 策略名称: InformativeSample (信息对示例)
# 策略类型: 示例/模板代码
#
# 盈利逻辑:
# 该策略是一个示例，旨在演示如何在Freqtrade中使用"信息对"(Informative Pairs)功能。
# 其核心思想是，在对某个交易对（如 `XRP/BTC`）做交易决策时，引入一个更具市场代表性的"信息对"(如 `BTC/USDT`)的数据作为"市场滤镜"，
# 只有在大盘行情向好时，才入场交易个别币种。
#   - 定义信息对: 策略首先在 `informative_pairs` 中定义需要额外获取的"信息对"及其时间周期，例如获取 `BTC/USDT` 的 `15m` K线数据。
#   - 数据合并: 在 `populate_indicators` 中，策略分别计算当前交易对 (`5m` 周期) 的指标和信息对 (`15m` 周期) 的指标，然后使用 `merge_informative_pair` 函数将两者数据合并到一张表中。
#   - 买入(Entry): 只有当两个条件**同时**满足时才买入：
#       1. 自身趋势: 当前交易对 (`XRP/BTC`) 的 `5m` 图上，短期均线 (ema20) 上穿长期均线 (ema50)，表明其自身处于上升趋势。
#       2. 大盘趋势: "信息对" (`BTC/USDT`) 的 `15m` 图上，价格高于其20周期均线，表明整个市场 (以比特币为代表) 也处于上升趋势。
#   - 卖出(Exit): 卖出逻辑相反，当自身趋势和"大盘"趋势同时转为下跌时卖出。
#
# 优点:
#   - 市场环境过滤: 引入大盘指标作为过滤器，可以有效避免在整体市场下跌时逆势买入，提高交易胜率。
#   - 多时间周期分析: 展示了如何结合不同时间周期（如用15分钟线指导5分钟线交易）进行分析，增加了策略的深度。
#   - 代码清晰: 是学习和理解 `informative_pairs` 这一强大功能的绝佳范例。
#
# 缺点:
#   - 不一定是完整策略: 作为一个示例，其本身的交易逻辑 (EMA交叉) 非常基础，可能不具备直接盈利的能力。
#   - 增加了数据复杂性: 管理和合并不同的数据源和时间周期需要小心，避免出现数据错位 (lookahead bias) 等问题。
#   - 强相关性假设: 策略假设所有交易对都与"信息对" (如BTC) 强相关。在某些"山寨币独立行情"中，这种过滤可能会错失机会。

# --- 请勿删除这些库 ---
from freqtrade.strategy import IStrategy, merge_informative_pair, IntParameter, RealParameter, BooleanParameter, CategoricalParameter
from typing import Dict, List
from functools import reduce
from pandas import DataFrame
# --------------------------------

import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib


class InformativeSample(IStrategy):
    """
    一个实现了"信息对"的示例策略 - 将计价货币与USDT进行比较。
    表现不是很好 - 但应作为如何使用参考货币对USDT的示例。
    作者@: xmatthias
    Github@: https://github.com/freqtrade/freqtrade-strategies

    如何使用它?
    > python3 freqtrade -s InformativeSample
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
    trailing_stop_positive = RealParameter(0.01, 0.03, default=0.02, space='protection', optimize=True)
    trailing_stop_positive_offset = RealParameter(0.03, 0.05, default=0.04, space='protection', optimize=True)
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
    
    # Informative parameters
    inf_timeframe = CategoricalParameter(['5m', '15m', '1h'], default='15m', space='buy', optimize=True)
    inf_sma_period = IntParameter(15, 30, default=20, space='buy', optimize=True)

    def informative_pairs(self):
        """
        定义需要从交易所缓存的额外、信息性的交易对/时间间隔组合。
        这些交易对/时间间隔组合是不可交易的，除非它们也包含在白名单中。
        更多信息，请查阅文档。
        :return: (交易对, 时间间隔) 格式的元组列表
            示例: return [("ETH/USDT", "5m"),
                            ("BTC/USDT", "15m"),
                            ]
        """
        return [(f"BTC/USDT", self.inf_timeframe.value)]

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        向给定的DataFrame中添加几个不同的TA指标。

        性能提示: 为了获得最佳性能，请节约使用指标的数量。
        只保留您在策略或超参数优化配置中使用的指标，
        否则会浪费您的内存和CPU使用率。
        """

        dataframe['ema20'] = ta.EMA(dataframe, timeperiod=self.ema20_period.value)
        dataframe['ema50'] = ta.EMA(dataframe, timeperiod=self.ema50_period.value)
        dataframe['ema100'] = ta.EMA(dataframe, timeperiod=self.ema100_period.value)
        if self.dp:
            # 1. 获取信息对的OHLCV数据。
            inf_tf = self.inf_timeframe.value
            informative = self.dp.get_pair_dataframe(pair=f"BTC/USDT",
                                                     timeframe=inf_tf)

            # 2. 在信息对上计算SMA
            informative['sma20'] = informative['close'].rolling(self.inf_sma_period.value).mean()

            # 3. 合并两个DataFrame
            # 这将产生一个名为 'close_15m' 或 'sma20_15m' 的列
            dataframe = merge_informative_pair(dataframe, informative,
                                               self.timeframe, inf_tf, ffill=True)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        根据TA指标，为给定的dataframe填充买入信号
        :param dataframe: DataFrame
        :return: 带有买入列的DataFrame
        """
        dataframe.loc[
            (
                # 自身趋势条件: 5m周期的ema20 > ema50
                (dataframe['ema20'] > dataframe['ema50']) &
                # 大盘过滤条件: BTC/USDT 15m周期的收盘价 > 20周期SMA
                (dataframe['close_15m'] > dataframe['sma20_15m'])
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        根据TA指标，为给定的dataframe填充卖出信号
        :param dataframe: DataFrame
        :return: 带有卖出列的DataFrame
        """
        dataframe.loc[
            (
                # 自身趋势条件: 5m周期的ema20 < ema50
                (dataframe['ema20'] < dataframe['ema50']) &
                # 大盘过滤条件: BTC/USDT 15m周期的收盘价 < 20周期SMA
                (dataframe['close_15m'] < dataframe['sma20_15m'])
            ),
            'exit_long'] = 1
        return dataframe
