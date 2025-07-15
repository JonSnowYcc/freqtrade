# --- 策略总结 ---
# 策略名称: MultiMa (多重均线策略)
#
# 盈利逻辑:
# 这是一个反转 (Mean Reversion) 策略，其逻辑非常独特。它通过构建一束或一捆移动平均线 (称为"均线带"或"Ribbon")，
# 并根据整个均线带的排列形态来寻找交易机会。
#   - 买入(Entry): 策略定义了一个由 `N` 条等间距周期的TEMA (三重指数移动平均线) 组成的"买入均线带"。
#     只有当这个均线带中的**所有**均线都呈现出完美的"空头排列" (即周期更长的均线值小于周期更短的均线值，例如 `TEMA(30) < TEMA(15)` ) 时，策略才会买入。
#     这代表着市场处于一个极度超卖的、完美的下降趋势中，策略在此刻入场，赌一个价格向上的反弹或反转。
#   - 卖出(Exit): 策略使用另一组独立的"卖出均线带"。与买入不同，只要卖出均线带中**任何**一对相邻的均线呈现出"多头排列"
#     (`TEMA(长周期) > TEMA(短周期)`)，策略就会立即卖出。这是一个非常灵敏的离场信号，旨在捕捉到趋势反转的最早迹象。
#
# 简单来说，策略是："在最完美的下跌中买入，在最轻微的上涨迹象出现时卖出"。
#
# 优点:
#   - 强烈的信号确认: 要求所有均线完美排列，可以过滤掉大量不明确的行情，只在形态最极端时入场。
#   - 灵敏的退出机制: 只要趋势有任何反转迹象就退出，有助于保护利润或减少亏损。
#   - 独特的反转逻辑: 提供了一种不同于传统超买超卖指标的、基于趋势形态的反转交易思路。
#
# 缺点:
#   - 计算量巨大: 策略在启动时会预先计算大量（可能上百条）的TEMA均线，非常消耗CPU和内存资源。
#   - 典型的反转策略风险: 在持续的强下跌趋势中"接飞刀" (Catching a falling knife) 风险很高。完美的空头排列可能持续很长时间，导致过早入场并持续亏损。
#   - 高度依赖优化: 均线带的数量 (count) 和周期差距 (gap) 需要通过超参数优化来确定，否则策略无法有效运行。

# MultiMa 策略 V2
# 作者: @Mablue (Masoud Azizi)
# github: https://github.com/mablue/

# --- 请勿删除这些库 ---
from freqtrade.strategy import IntParameter, IStrategy, RealParameter, BooleanParameter
from pandas import DataFrame

# --------------------------------

# 在此导入您的库
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
from functools import reduce


class MultiMa(IStrategy):
    # 优化结果示例:
    # 111/2000:     18 trades. 12/4/2 Wins/Draws/Losses. Avg profit   9.72%. Median profit   3.01%. Total profit  733.01234143 USDT (  73.30%). Avg duration 2 days, 18:40:00 min. Objective: 1.67048

    INTERFACE_VERSION: int = 3
    # 买入超参数空间:
    buy_params = {
        "buy_ma_count": 4, # 买入均线带中的均线数量
        "buy_ma_gap": 15,  # 买入均线之间的周期差距
    }

    # 卖出超参数空间:
    sell_params = {
        "sell_ma_count": 12, # 卖出均线带中的均线数量
        "sell_ma_gap": 68,   # 卖出均线之间的周期差距
    }

    # 投资回报率 (ROI) 表:
    @property
    def minimal_roi(self):
        return {
            "0": self.roi_p1.value,
            "1553": self.roi_p2.value,
            "2332": self.roi_p3.value,
            "3169": 0
        }
    roi_p1 = RealParameter(0.4, 0.7, default=0.523, space='roi', optimize=True)
    roi_p2 = RealParameter(0.1, 0.2, default=0.123, space='roi', optimize=True)
    roi_p3 = RealParameter(0.05, 0.1, default=0.076, space='roi', optimize=True)

    # 止损:
    stoploss = RealParameter(-0.4, -0.3, default=-0.345, space='protection', optimize=True)

    # 追踪止损:
    trailing_stop = BooleanParameter(default=False, space='protection', optimize=True)
    trailing_stop_positive = RealParameter(0.005, 0.05, default=0.01, space='protection', optimize=True)
    trailing_stop_positive_offset = RealParameter(0.0, 0.05, default=0.0, space='protection', optimize=True)
    trailing_only_offset_is_reached = BooleanParameter(default=False, space='protection', optimize=True)

    # 最佳时间框架
    timeframe = "4h"

    # 预计算指标时的最大数量和间距，会影响性能
    count_max = 20
    gap_max = 100

    buy_ma_count = IntParameter(1, 8, default=4, space="buy", optimize=True)
    buy_ma_gap = IntParameter(1, 20, default=15, space="buy", optimize=True)

    sell_ma_count = IntParameter(1, 15, default=12, space="sell", optimize=True)
    sell_ma_gap = IntParameter(20, 80, default=68, space="sell", optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 只计算当前优化步骤所需的指标
        
        # Buy indicators
        for i in range(1, self.buy_ma_count.value + 1):
            period = i * self.buy_ma_gap.value
            dataframe[f'buy_tema_{period}'] = ta.TEMA(dataframe, timeperiod=period)
            
        # Sell indicators
        for i in range(1, self.sell_ma_count.value + 1):
            period = i * self.sell_ma_gap.value
            dataframe[f'sell_tema_{period}'] = ta.TEMA(dataframe, timeperiod=period)
            
        print(" ", metadata['pair'], end="\t\r")

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        # 作者注释: 我使用了 range(self.buy_ma_count.value) 而不是 self.buy_ma_count.range
        # 因为后者返回 range(7,8)，但我们需要 range(8) 以便在所有模式下（超参数优化、回测等）都能工作。

        # 循环构建"买入均线带"的排列条件
        for i in range(2, self.buy_ma_count.value + 1):
            # 当前均线的周期
            key = i * self.buy_ma_gap.value
            # 上一条均线的周期
            past_key = (i - 1) * self.buy_ma_gap.value
            # 条件: 较长周期的均线 < 较短周期的均线 (空头排列)
            conditions.append(dataframe[f'buy_tema_{key}'] < dataframe[f'buy_tema_{past_key}'])

        if conditions:
            # 使用 `&` 连接所有条件，意味着所有均线对都必须满足空头排列条件
            dataframe.loc[reduce(lambda x, y: x & y, conditions), "enter_long"] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        
        # 循环构建"卖出均线带"的排列条件
        for i in range(2, self.sell_ma_count.value + 1):
            key = i * self.sell_ma_gap.value
            past_key = (i - 1) * self.sell_ma_gap.value
            # 条件: 较长周期的均线 > 较短周期的均线 (多头排列)
            conditions.append(dataframe[f'sell_tema_{key}'] > dataframe[f'sell_tema_{past_key}'])

        if conditions:
            # 使用 `|` 连接所有条件，意味着只要有一对均线满足多头排列条件，就触发卖出
            dataframe.loc[reduce(lambda x, y: x | y, conditions), "exit_long"] = 1
        return dataframe
