# --- 策略总结 ---
# 策略名称: Strategy004
#
# 盈利逻辑:
# 这是一个精密的"趋势中回调买入"策略。它的核心思想是，首先确认市场存在一个足够强劲的趋势，
# 然后等待价格在该趋势中发生深度回调 (超卖)，并在回调结束、上涨动能初现时买入。
#   - 买入(Entry): 策略的入场条件非常严格，要求以下所有条件组同时成立：
#       1. 趋势强度过滤: ADX指标显示当前存在一个强劲的趋势。
#       2. 深度超卖共振: CCI指标、一个快速随机指标(StochF)和一个慢速随机指标必须**同时**处于超卖区域。
#       3. 精确的入场触发: 快速随机指标在前一根K线是死叉 (看跌)，而在当前K线刚刚发生金叉 (看涨)。这个条件精确地捕捉了从回调到反弹的转折点。
#       4. 成交量和价格过滤: 对成交量和价格有最低要求。
#   - 卖出(Exit): 卖出逻辑较为复杂，大致条件为：当长期趋势强度 (慢速ADX) 消失，并且短期动量 (快速Stoch) 进入超买区时退出。
#
# 优点:
#   - 高精度入场: 结合了趋势、多重超卖和精确的交叉点作为触发器，旨在找到高质量的回调买点，理论上胜率较高。
#   - 顺势而为: ADX过滤器确保了策略只在有趋势的市场中运行，避免了在震荡市中被来回洗盘。
#
# 缺点:
#   - 信号稀少: 同时满足如此多的苛刻条件会非常困难，导致交易机会很少。
#   - 逻辑复杂: 入场和特别是出场的逻辑链条很长，不易理解，且部分条件组合 (如卖出时的Stoch条件) 可能不符合常规逻辑。
#   - 参数固定: 策略中的许多阈值 (如ADX>50, CCI<-100, Stoch<20等) 都是硬编码的，在不同市场环境下可能需要大量优化。

# --- 请勿删除这些库 ---
from freqtrade.strategy import IStrategy, IntParameter, RealParameter, BooleanParameter
from typing import Dict, List
from functools import reduce
from pandas import DataFrame
# --------------------------------

import talib.abstract as ta


class Strategy004(IStrategy):

    """
    策略 004
    作者@: Gerald Lonlas
    Github@: https://github.com/freqtrade/freqtrade-strategies

    如何使用它?
    > python3 ./freqtrade/main.py -s Strategy004
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
    adx_period = IntParameter(10, 20, default=14, space='buy', optimize=True)
    slowadx_period = IntParameter(30, 50, default=35, space='buy', optimize=True)
    cci_period = IntParameter(15, 30, default=20, space='buy', optimize=True)
    stochf_k_period = IntParameter(3, 10, default=5, space='buy', optimize=True)
    slow_stochf_k_period = IntParameter(40, 60, default=50, space='buy', optimize=True)
    ema_period = IntParameter(3, 10, default=5, space='buy', optimize=True)
    volume_rolling_period = IntParameter(8, 16, default=12, space='buy', optimize=True)

    # Logic thresholds
    buy_adx_threshold = IntParameter(40, 60, default=50, space='buy', optimize=True)
    buy_slowadx_threshold = IntParameter(20, 35, default=26, space='buy', optimize=True)
    buy_cci_threshold = IntParameter(-150, -50, default=-100, space='buy', optimize=True)
    buy_fast_stoch_threshold = IntParameter(15, 30, default=20, space='buy', optimize=True)
    buy_slow_stoch_threshold = IntParameter(20, 40, default=30, space='buy', optimize=True)
    buy_min_volume = RealParameter(0.5, 1.0, default=0.75, space='buy', optimize=True)
    buy_min_price = RealParameter(0.0000005, 0.000002, default=0.00000100, space='buy', optimize=True)
    
    sell_slowadx_threshold = IntParameter(20, 35, default=25, space='sell', optimize=True)
    sell_stoch_threshold = IntParameter(60, 80, default=70, space='sell', optimize=True)

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

        # ADX 平均动向指数
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=self.adx_period.value)
        dataframe['slowadx'] = ta.ADX(dataframe, timeperiod=self.slowadx_period.value)

        # CCI 商品通道指标: 超卖:<-100, 超买:>100
        dataframe['cci'] = ta.CCI(dataframe, timeperiod=self.cci_period.value)

        # Stoch 随机指标
        stoch = ta.STOCHF(dataframe, self.stochf_k_period.value)
        dataframe['fastd'] = stoch['fastd']
        dataframe['fastk'] = stoch['fastk']
        dataframe['fastk-previous'] = dataframe.fastk.shift(1)
        dataframe['fastd-previous'] = dataframe.fastd.shift(1)

        # Slow Stoch 慢速随机指标
        slowstoch = ta.STOCHF(dataframe, self.slow_stochf_k_period.value)
        dataframe['slowfastd'] = slowstoch['fastd']
        dataframe['slowfastk'] = slowstoch['fastk']
        dataframe['slowfastk-previous'] = dataframe.slowfastk.shift(1)
        dataframe['slowfastd-previous'] = dataframe.slowfastd.shift(1)

        # EMA - 指数移动平均线
        dataframe['ema5'] = ta.EMA(dataframe, timeperiod=self.ema_period.value)
        
        # 获取最近N根K线的滚动平均成交量
        dataframe['mean-volume'] = dataframe['volume'].rolling(self.volume_rolling_period.value).mean()

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        基于TA指标，为给定的dataframe填充买入信号
        """
        dataframe.loc[
            (
                # 1. 趋势强度过滤: 要求当前趋势强劲
                (
                    (dataframe['adx'] > self.buy_adx_threshold.value) |
                    (dataframe['slowadx'] > self.buy_slowadx_threshold.value)
                ) &
                # 2. 深度超卖共振: CCI和两种速度的Stoch都处于超卖状态
                (dataframe['cci'] < self.buy_cci_threshold.value) &
                (
                    (dataframe['fastk-previous'] < self.buy_fast_stoch_threshold.value) &
                    (dataframe['fastd-previous'] < self.buy_fast_stoch_threshold.value)
                ) &
                (
                    (dataframe['slowfastk-previous'] < self.buy_slow_stoch_threshold.value) &
                    (dataframe['slowfastd-previous'] < self.buy_slow_stoch_threshold.value)
                ) &
                # 3. 精确入场触发: 快速Stoch在前一根K线为死叉，当前K线为金叉
                (dataframe['fastk-previous'] < dataframe['fastd-previous']) &
                (dataframe['fastk'] > dataframe['fastd']) &
                # 4. 其他过滤条件
                (dataframe['mean-volume'] > self.buy_min_volume.value) &
                (dataframe['close'] > self.buy_min_price.value)
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        基于TA指标，为给定的dataframe填充卖出信号
        """
        dataframe.loc[
            (
                # 长期趋势强度消失
                (dataframe['slowadx'] < self.sell_slowadx_threshold.value) &
                # 快速Stoch进入超买区
                ((dataframe['fastk'] > self.sell_stoch_threshold.value) | (dataframe['fastd'] > self.sell_stoch_threshold.value)) &
                # Stoch死叉 (此条件较为可疑)
                (dataframe['fastk-previous'] < dataframe['fastd-previous']) &
                # 价格仍在快速EMA之上
                (dataframe['close'] > dataframe['ema5'])
            ),
            'exit_long'] = 1
        return dataframe
