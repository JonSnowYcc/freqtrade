# --- 策略总结 ---
# 策略名称: Supertrend (超级趋势)
#
# 盈利逻辑:
# 这是一个经典的、基于"超级趋势"(Supertrend) 指标的趋势跟踪策略。为了提高信号的稳定性和可靠性，
# 它采用了一种"三重确认"的方法：即同时使用三组不同参数的超级趋势指标，只有当这三条指标都发出同向信号时，才进行交易。
#   - 买入(Entry): 策略定义了三组独立的"买入超级趋势"指标 (每组都有自己的周期`p`和乘数`m`参数)。
#     只有当这三条指标的趋势方向**同时**为`up` (向上) 时，策略才会产生买入信号。
#     这确保了短期、中期、长期的趋势 (具体取决于参数优化结果) 形成了共振，确认了上升趋势的强度。
#   - 卖出(Exit): 相应的，策略也定义了三组独立的"卖出超级趋势"指标。只有当这三条指标的趋势方向**同时**变为`down` (向下) 时，
#     策略才会产生卖出信号，确认趋势反转。
#
# 优点:
#   - 可靠性高: 三重指标共振过滤掉了大量的市场噪音和短暂的假突破，只在趋势非常明确时才入场，提高了信号质量。
#   - 逻辑清晰: 策略思想简单直观，即"三线同向，顺势而为"。
#   - 参数灵活: 买入和卖出的三组指标参数可以被独立优化，使策略能更好地适应不同市场的节奏。
#
# 缺点:
#   - 指标计算效率极低: 当前的`populate_indicators`实现方式非常低效。它会预先计算出所有可能的参数组合下的超级趋势指标，
#     而不是只计算当前优化选用的那几组。这将导致策略启动非常缓慢，并占用大量内存。
#   - 信号滞后: 超级趋势指标本身具有滞后性，三重确认会进一步加剧这种滞后，可能导致在趋势中后段才入场，错失部分利润。

"""
超级趋势策略:
* 描述: 为'买入'策略生成3个超级趋势指标 & 为'卖出'策略生成3个超级趋势指标
         如果3个'买入'指标都为'up'，则买入
         如果3个'卖出'指标都为'down'，则卖出
* 作者: @juankysoriano (Juan Carlos Soriano)
* github: https://github.com/juankysoriano/

*** 注意: 这个超级趋势策略只是使用`Supertrend`作为指标的众多可能策略之一。您使用此策略需自担风险。
          它至少有以下几个注意事项：
            1. `supertrend`指标的实现基于以下讨论: https://github.com/freqtrade/freqtrade-strategies/issues/30 。具体是 https://github.com/freqtrade/freqtrade-strategies/issues/30#issuecomment-853042401
            2. 此策略中`supertrend`的实现未经证实；这意味着它未被证明与最初引入它的论文或任何其他可信的学术资源的结果相匹配。
"""

import logging
from numpy.lib import math
from freqtrade.strategy import IStrategy, IntParameter, RealParameter, BooleanParameter
from pandas import DataFrame
import talib.abstract as ta
import numpy as np

class Supertrend(IStrategy):
    # 买入参数、卖出参数、ROI、止损和追踪止损都是通过 'freqtrade hyperopt ...' 生成的值。
    # 鼓励您找到更适合您需求和风险管理策略的值。

    INTERFACE_VERSION: int = 3
    # 买入超参数空间:
    buy_params = {
        "buy_m1": 4,
        "buy_m2": 7,
        "buy_m3": 1,
        "buy_p1": 8,
        "buy_p2": 9,
        "buy_p3": 8,
    }

    # 卖出超参数空间:
    sell_params = {
        "sell_m1": 1,
        "sell_m2": 3,
        "sell_m3": 6,
        "sell_p1": 16,
        "sell_p2": 18,
        "sell_p3": 18,
    }

    # 投资回报率 (ROI) 表:
    @property
    def minimal_roi(self):
        return {
            "0": self.roi_p1.value,
            "372": self.roi_p2.value,
            "861": self.roi_p3.value,
            "2221": 0
        }
    roi_p1 = RealParameter(0.05, 0.1, default=0.087, space='roi', optimize=True)
    roi_p2 = RealParameter(0.03, 0.08, default=0.058, space='roi', optimize=True)
    roi_p3 = RealParameter(0.01, 0.05, default=0.029, space='roi', optimize=True)

    # 止损:
    stoploss = RealParameter(-0.3, -0.2, default=-0.265, space='protection', optimize=True)

    # 追踪止损:
    trailing_stop = BooleanParameter(default=True, space='protection', optimize=True)
    trailing_stop_positive = RealParameter(0.01, 0.08, default=0.05, space='protection', optimize=True)
    trailing_stop_positive_offset = RealParameter(0.1, 0.18, default=0.144, space='protection', optimize=True)
    trailing_only_offset_is_reached = BooleanParameter(default=False, space='protection', optimize=True)

    timeframe = '1h'

    startup_candle_count = 199

    buy_m1 = IntParameter(1, 7, default=4, space='buy', optimize=True)
    buy_m2 = IntParameter(1, 7, default=4, space='buy', optimize=True)
    buy_m3 = IntParameter(1, 7, default=4, space='buy', optimize=True)
    buy_p1 = IntParameter(7, 21, default=14, space='buy', optimize=True)
    buy_p2 = IntParameter(7, 21, default=14, space='buy', optimize=True)
    buy_p3 = IntParameter(7, 21, default=14, space='buy', optimize=True)

    sell_m1 = IntParameter(1, 7, default=4, space='sell', optimize=True)
    sell_m2 = IntParameter(1, 7, default=4, space='sell', optimize=True)
    sell_m3 = IntParameter(1, 7, default=4, space='sell', optimize=True)
    sell_p1 = IntParameter(7, 21, default=14, space='sell', optimize=True)
    sell_p2 = IntParameter(7, 21, default=14, space='sell', optimize=True)
    sell_p3 = IntParameter(7, 21, default=14, space='sell', optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 只计算当前优化步骤所需的指标
        dataframe['supertrend_1_buy'] = self.supertrend(dataframe, self.buy_m1.value, self.buy_p1.value)['STX']
        dataframe['supertrend_2_buy'] = self.supertrend(dataframe, self.buy_m2.value, self.buy_p2.value)['STX']
        dataframe['supertrend_3_buy'] = self.supertrend(dataframe, self.buy_m3.value, self.buy_p3.value)['STX']

        dataframe['supertrend_1_sell'] = self.supertrend(dataframe, self.sell_m1.value, self.sell_p1.value)['STX']
        dataframe['supertrend_2_sell'] = self.supertrend(dataframe, self.sell_m2.value, self.sell_p2.value)['STX']
        dataframe['supertrend_3_sell'] = self.supertrend(dataframe, self.sell_m3.value, self.sell_p3.value)['STX']
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
               # 条件：三组独立的"买入超级趋势"指标必须同时为'up'
               (dataframe['supertrend_1_buy'] == 'up') &
               (dataframe['supertrend_2_buy'] == 'up') &
               (dataframe['supertrend_3_buy'] == 'up') &
               (dataframe['volume'] > 0) # 确保有成交量
        ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
               # 条件：三组独立的"卖出超级趋势"指标必须同时为'down'
               (dataframe['supertrend_1_sell'] == 'down') &
               (dataframe['supertrend_2_sell'] == 'down') &
               (dataframe['supertrend_3_sell'] == 'down') &
               (dataframe['volume'] > 0) # 确保有成交量
            ),
            'exit_long'] = 1

        return dataframe



    """
        超级趋势指标；为freqtrade适配
        来自: https://github.com/freqtrade/freqtrade-strategies/issues/30
    """
    def supertrend(self, dataframe: DataFrame, multiplier, period):
        df = dataframe.copy()

        df['TR'] = ta.TRANGE(df)
        df['ATR'] = ta.SMA(df['TR'], period)

        st = 'ST_' + str(period) + '_' + str(multiplier)
        stx = 'STX_' + str(period) + '_' + str(multiplier)

        # 计算基础的上下轨
        df['basic_ub'] = (df['high'] + df['low']) / 2 + multiplier * df['ATR']
        df['basic_lb'] = (df['high'] + df['low']) / 2 - multiplier * df['ATR']

        # 计算最终的上下轨
        df['final_ub'] = 0.00
        df['final_lb'] = 0.00
        for i in range(period, len(df)):
            df['final_ub'].iat[i] = df['basic_ub'].iat[i] if df['basic_ub'].iat[i] < df['final_ub'].iat[i - 1] or df['close'].iat[i - 1] > df['final_ub'].iat[i - 1] else df['final_ub'].iat[i - 1]
            df['final_lb'].iat[i] = df['basic_lb'].iat[i] if df['basic_lb'].iat[i] > df['final_lb'].iat[i - 1] or df['close'].iat[i - 1] < df['final_lb'].iat[i - 1] else df['final_lb'].iat[i - 1]

        # 设置超级趋势线的值
        df[st] = 0.00
        for i in range(period, len(df)):
            df[st].iat[i] = df['final_ub'].iat[i] if df[st].iat[i - 1] == df['final_ub'].iat[i - 1] and df['close'].iat[i] <= df['final_ub'].iat[i] else \
                            df['final_lb'].iat[i] if df[st].iat[i - 1] == df['final_ub'].iat[i - 1] and df['close'].iat[i] >  df['final_ub'].iat[i] else \
                            df['final_lb'].iat[i] if df[st].iat[i - 1] == df['final_lb'].iat[i - 1] and df['close'].iat[i] >= df['final_lb'].iat[i] else \
                            df['final_ub'].iat[i] if df[st].iat[i - 1] == df['final_lb'].iat[i - 1] and df['close'].iat[i] <  df['final_lb'].iat[i] else 0.00
        # 标记趋势方向 up/down
        df[stx] = np.where((df[st] > 0.00), np.where((df['close'] < df[st]), 'down',  'up'), np.NaN)

        # 从列中删除基础和最终的上下轨
        df.drop(['basic_ub', 'basic_lb', 'final_ub', 'final_lb'], inplace=True, axis=1)

        df.fillna(0, inplace=True)

        return DataFrame(index=df.index, data={
            'ST' : df[st],
            'STX' : df[stx]
        })
