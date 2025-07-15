# --- 策略总结 ---
# 策略名称: HourBasedStrategy (基于小时的策略)
#
# 盈利逻辑:
# 该策略是一种纯粹的"时间模式"策略，它完全忽略了价格、成交量和任何传统的技术指标。
# 其唯一的交易依据是一天中的特定时间段。
# 策略的核心假设是：市场的行为在一天24小时内存在周期性规律，例如，亚洲、欧洲、美洲交易时段的活跃度不同，
# 可能导致在某些特定时间段内，价格上涨或下跌的概率更高。
#   - 买入(Entry): 如果当前K线的小时数(0-23)落在一个通过超参数优化找到的"最佳买入时间窗口"内 (例如，早上7点到下午6点之间)，则产生买入信号。
#   - 卖出(Exit): 如果当前小时数落在一个独立的"最佳卖出时间窗口"内，则产生卖出信号。
# 该策略完全依赖于大量的历史数据回测和超参数优化，来找出特定交易对在统计上最有利可图的买入和卖出小时区间。
#
# 优点:
#   - 逻辑极简: 策略逻辑非常简单，易于理解和实现。
#   - 捕捉周期性: 有可能捕捉到由市场参与者作息、宏观数据发布等因素造成的日内周期性规律，这是传统技术指标可能忽略的维度。
#   - 不受价格噪音干扰: 由于不看价格，可以避免被市场的短期随机波动（噪音）所迷惑。
#
# 缺点:
#   - 严重依赖历史数据: 策略的有效性完全建立在"历史会重演"的假设上。如果市场的日内周期性发生改变（例如，由于新的大型参与者入场或市场规则改变），策略将立即失效。
#   - 过拟合风险高: 非常容易在历史数据上找到看似完美的"时间窗口"，但这可能只是数据挖掘的巧合，在未来并不适用。
#   - 忽略关键信息: 完全忽略价格和成交量等市场关键信息，可能导致在明显不利的价格趋势中仅仅因为时间到了就进行买入。
#   - 适用性窄: 为某个交易对优化的时间窗口，几乎不可能适用于另一个交易对。

# Hour Strategy
# In this strategy we try to find the best hours to buy and sell in a day.(in hourly timeframe)
# Because of that you should just use 1h timeframe on this strategy.
# Author: @Mablue (Masoud Azizi)
# github: https://github.com/mablue/
# Requires hyperopt before running.
# freqtrade hyperopt --hyperopt-loss SharpeHyperOptLoss --strategy HourBasedStrategy -e 200


from freqtrade.strategy import IntParameter, IStrategy, RealParameter
from pandas import DataFrame

# --------------------------------
# Add your lib to import here
# No need to These imports. just for who want to add more conditions:
# import talib.abstract as ta
# import freqtrade.vendor.qtpylib.indicators as qtpylib


class HourBasedStrategy(IStrategy):
    # SHIB/USDT, 1000$x1:100days
    # 158/1000:     51 trades. 29/19/3 Wins/Draws/Losses. Avg profit   4.02%. Median profit   2.48%. Total profit  4867.53438466 USDT ( 486.75%). Avg duration 1 day, 19:38:00 min. Objective: -4.17276
    # buy_params = {"buy_hour_max": 18,"buy_hour_min": 7,}
    # sell_params = {"sell_hour_max": 9,"sell_hour_min": 21,}
    # minimal_roi = {"0": 0.18,"171": 0.155,"315": 0.075,"1035": 0}
    # stoploss = -0.292

    # SHIB/USDT, 1000$x1:100days
    # 36/1000:    113 trades. 55/14/44 Wins/Draws/Losses. Avg profit   2.06%. Median profit   0.00%. Total profit  5126.14785426 USDT ( 512.61%). Avg duration 16:48:00 min. Objective: -4.57837
    # buy_params = {"buy_hour_max": 21,"buy_hour_min": 6,}
    # sell_params = {"sell_hour_max": 6,"sell_hour_min": 4,}
    # minimal_roi = {"0": 0.247,"386": 0.186,"866": 0.052,"1119": 0}
    # stoploss = -0.302

    # SAND/USDT, 1000$x1:100days
    # 72/1000:    158 trades. 67/13/78 Wins/Draws/Losses. Avg profit   1.37%. Median profit   0.00%. Total profit  4274.73622346 USDT ( 427.47%). Avg duration 13:50:00 min. Objective: -4.87331
    # buy_params = {"buy_hour_max": 23,"buy_hour_min": 4,}
    # sell_params = {"sell_hour_max": 23,"sell_hour_min": 3,}
    # minimal_roi = {"0": 0.482,"266": 0.191,"474": 0.09,"1759": 0}
    # stoploss = -0.05

    # KDA/USDT, 1000$x1:100days
    # 7/1000:     65 trades. 40/23/2 Wins/Draws/Losses. Avg profit   6.42%. Median profit   7.59%. Total profit  41120.00939125 USDT ( 4112.00%). Avg duration 1 day, 9:40:00 min. Objective: -8.46089
    # buy_params = {"buy_hour_max": 22,"buy_hour_min": 9,}
    # sell_params = {"sell_hour_max": 1,"sell_hour_min": 7,}
    # minimal_roi = {"0": 0.517,"398": 0.206,"1003": 0.076,"1580": 0}
    # stoploss = -0.338

    # {KDA/USDT, BTC/USDT, DOGE/USDT, SAND/USDT, ETH/USDT, SOL/USDT}, 1000$x1:100days, ShuffleFilter42
    # 56/1000:     63 trades. 41/19/3 Wins/Draws/Losses. Avg profit   4.60%. Median profit   8.89%. Total profit  11596.50333022 USDT ( 1159.65%). Avg duration 1 day, 14:46:00 min. Objective: -5.76694

    INTERFACE_VERSION: int = 3
    # Buy hyperspace params:
    buy_params = {
        "buy_hour_max": 24,
        "buy_hour_min": 4,
    }

    # Sell hyperspace params:
    sell_params = {
        "sell_hour_max": 21,
        "sell_hour_min": 22,
    }

    # ROI table:
    @property
    def minimal_roi(self):
        return {
            "0": self.roi_p1.value,
            "169": self.roi_p2.value,
            "528": self.roi_p3.value,
            "1837": 0
        }
    roi_p1 = RealParameter(0.4, 0.7, default=0.528, space='roi', optimize=True)
    roi_p2 = RealParameter(0.08, 0.2, default=0.113, space='roi', optimize=True)
    roi_p3 = RealParameter(0.05, 0.1, default=0.089, space='roi', optimize=True)

    # Stoploss:
    stoploss = RealParameter(-0.15, -0.05, default=-0.10, space='protection', optimize=True)

    # Optimal timeframe
    timeframe = '1h'

    buy_hour_min = IntParameter(0, 23, default=4, space='buy', optimize=True)
    buy_hour_max = IntParameter(0, 23, default=21, space='buy', optimize=True)

    sell_hour_min = IntParameter(0, 23, default=21, space='sell', optimize=True)
    sell_hour_max = IntParameter(0, 23, default=9, space='sell', optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['hour'] = dataframe['date'].dt.hour
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['hour'].between(self.buy_hour_min.value, self.buy_hour_max.value))
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (dataframe['hour'].between(self.sell_hour_min.value, self.sell_hour_max.value))
            ),
            'exit_long'] = 1
        return dataframe
