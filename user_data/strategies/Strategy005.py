# --- 策略总结 ---
# 策略名称: Strategy005
#
# 盈利逻辑:
# 这是一个精密的"恐慌性抛售抄底"反转策略。其核心思想是通过识别一次成交量巨大的下跌 (通常被认为是"投降式抛售"或"洗盘")，
# 并在动能指标确认的超卖点入场，以捕捉随后的V型反弹。策略的卖出逻辑是可配置的，可以通过超参数优化选择。
#   - 买入(Entry): 策略的入场条件非常独特，结合了成交量、价格位置和动量指标：
#       1. 天量成交: 当前K线的成交量必须是近期平均成交量的数倍 (默认为4倍) 以上，这是识别"恐慌盘"的关键信号。
#       2. 处于下跌趋势: 价格必须低于40周期SMA均线。
#       3. 动量超卖: 费雪RSI(Fisher RSI)指标处于低位。
#       4. 特定形态: 随机指标(Stochastic)处于一个特定的看跌形态中，这可能旨在捕捉恐慌情绪达到顶峰的瞬间。
#   - 卖出(Exit): 策略可以通过超参数优化，在两种不同的退出逻辑中选择其一：
#       - 模式一 (`rsi-macd-minusdi`): 一个保守的快速止盈模式。当RSI进入超买区，但MACD和DMI指标显示大趋势尚未完全转强时，就立即卖出。
#       - 模式二 (`sar-fisherRsi`): 一个更偏向于追踪趋势的模式 (与Strategy002/003的退出逻辑相同)。当抛物线SAR指标反转，并且费雪RSI显示反弹动能达到一定水平时退出。
#
# 优点:
#   - 独特的成交量信号: 将成交量作为核心入场条件，可以有效识别市场情绪的极端转折点，这是许多策略所忽略的。
#   - 可配置的退出逻辑: 允许通过优化来选择最适合当前市场环境的退出方式，增加了策略的灵活性和适应性。
#
# 缺点:
#   - 成交量信号的可靠性: 天量成交不一定都意味着反转，也可能是下跌中继，因此存在"接飞刀"的风险。
#   - 逻辑复杂: 入场条件组合了多个指标的特定状态，较为复杂。
#   - 高度依赖优化: 策略的表现严重依赖于买入阈值和卖出模式的选择，需要大量优化工作。

# --- 请勿删除这些库 ---
from freqtrade.strategy import IStrategy
from freqtrade.strategy import CategoricalParameter, IntParameter, RealParameter, BooleanParameter
from functools import reduce
from pandas import DataFrame
# --------------------------------

import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy # noqa


class Strategy005(IStrategy):
    """
    策略 005
    作者@: Gerald Lonlas
    Github@: https://github.com/freqtrade/freqtrade-strategies

    如何使用它?
    > python3 ./freqtrade/main.py -s Strategy005
    """
    INTERFACE_VERSION = 3

    # 为该策略设计的最小投资回报率(ROI)。
    # 如果配置文件中包含 "minimal_roi"，此属性将被覆盖。
    @property
    def minimal_roi(self):
        return {
            "1440": self.roi_p1.value,
            "80": self.roi_p2.value,
            "40": self.roi_p3.value,
            "20": self.roi_p4.value,
            "0": self.roi_p5.value
        }
    roi_p1 = RealParameter(0.005, 0.02, default=0.01, space='roi', optimize=True)
    roi_p2 = RealParameter(0.01, 0.03, default=0.02, space='roi', optimize=True)
    roi_p3 = RealParameter(0.02, 0.04, default=0.03, space='roi', optimize=True)
    roi_p4 = RealParameter(0.03, 0.05, default=0.04, space='roi', optimize=True)
    roi_p5 = RealParameter(0.04, 0.08, default=0.05, space='roi', optimize=True)

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

    # --- 可优化的策略参数 ---
    buy_volumeAVG = IntParameter(low=50, high=300, default=70, space='buy', optimize=True)
    buy_rsi = IntParameter(low=1, high=100, default=30, space='buy', optimize=True)
    buy_fastd = IntParameter(low=1, high=100, default=30, space='buy', optimize=True)
    buy_fishRsiNorma = IntParameter(low=1, high=100, default=30, space='buy', optimize=True)

    sell_rsi = IntParameter(low=1, high=100, default=70, space='sell', optimize=True)
    sell_minusDI = IntParameter(low=1, high=100, default=50, space='sell', optimize=True)
    sell_fishRsiNorma = IntParameter(low=1, high=100, default=50, space='sell', optimize=True)
    # 退出策略触发器
    sell_trigger = CategoricalParameter(["rsi-macd-minusdi", "sar-fisherRsi"],
                                        default="rsi-macd-minusdi", space='sell', optimize=True)

    # Indicator parameters
    macd_fast = IntParameter(10, 20, default=12, space='buy', optimize=True)
    macd_slow = IntParameter(20, 35, default=26, space='buy', optimize=True)
    macd_signal = IntParameter(7, 15, default=9, space='buy', optimize=True)
    minus_di_period = IntParameter(10, 20, default=14, space='buy', optimize=True)
    rsi_period = IntParameter(10, 20, default=14, space='buy', optimize=True)
    fisher_rsi_multiplier = RealParameter(0.05, 0.2, default=0.1, space='buy', optimize=True)
    stochf_k_period = IntParameter(3, 10, default=5, space='buy', optimize=True)
    stochf_d_period = IntParameter(2, 7, default=3, space='buy', optimize=True)
    sar_acceleration = RealParameter(0.01, 0.05, default=0.02, space='buy', optimize=True)
    sar_maximum = RealParameter(0.1, 0.3, default=0.2, space='buy', optimize=True)
    sma_period = IntParameter(30, 50, default=40, space='buy', optimize=True)

    # Logic parameters
    buy_min_price = RealParameter(0.000001, 0.00001, default=0.00000200, space='buy', optimize=True)
    buy_volume_multiplier = IntParameter(2, 8, default=4, space='buy', optimize=True)

    # 买入超参数空间:
    buy_params = {
        "buy_fastd": 1,
        "buy_fishRsiNorma": 5,
        "buy_rsi": 26,
        "buy_volumeAVG": 150,
    }

    # 卖出超参数空间:
    sell_params = {
        "sell_fishRsiNorma": 30,
        "sell_minusDI": 4,
        "sell_rsi": 74,
        "sell_trigger": "rsi-macd-minusdi",
    }

    def informative_pairs(self):
        """
        定义需要从交易所缓存的额外、信息性的交易对/时间间隔组合。
        """
        return []

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        向给定的DataFrame中添加几个不同的TA指标。
        """

        # MACD
        macd = ta.MACD(dataframe, fastperiod=self.macd_fast.value, slowperiod=self.macd_slow.value, signalperiod=self.macd_signal.value)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']

        # Minus Directional Indicator / Movement (负向方向指标)
        dataframe['minus_di'] = ta.MINUS_DI(dataframe, timeperiod=self.minus_di_period.value)

        # RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=self.rsi_period.value)

        # Fisher RSI (反费雪变换RSI), 值域 [-1.0, 1.0]
        rsi = self.fisher_rsi_multiplier.value * (dataframe['rsi'] - 50)
        dataframe['fisher_rsi'] = (numpy.exp(2 * rsi) - 1) / (numpy.exp(2 * rsi) + 1)
        # 归一化后的 Fisher RSI, 值域 [0.0, 100.0]
        dataframe['fisher_rsi_norma'] = 50 * (dataframe['fisher_rsi'] + 1)

        # Stoch fast (快速随机指标)
        stoch_fast = ta.STOCHF(dataframe, fastk_period=self.stochf_k_period.value, fastd_period=self.stochf_d_period.value)
        dataframe['fastd'] = stoch_fast['fastd']
        dataframe['fastk'] = stoch_fast['fastk']

        # SAR Parabol (抛物线转向指标)
        dataframe['sar'] = ta.SAR(dataframe, acceleration=self.sar_acceleration.value, maximum=self.sar_maximum.value)

        # SMA - Simple Moving Average (简单移动平均线)
        dataframe['sma'] = ta.SMA(dataframe, timeperiod=self.sma_period.value)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        基于TA指标，为给定的dataframe填充买入信号
        """
        dataframe.loc[
            (
                (dataframe['close'] > self.buy_min_price.value) &
                # 关键条件: 寻找成交量暴增的K线 (恐慌盘)
                (dataframe['volume'] > dataframe['volume'].rolling(self.buy_volumeAVG.value).mean() * self.buy_volume_multiplier.value) &
                # 价格处于下跌趋势中
                (dataframe['close'] < dataframe['sma']) &
                # 随机指标看跌 (捕捉下跌末端)
                (dataframe['fastd'] > dataframe['fastk']) &
                # RSI 和 Fisher RSI 确认超卖但仍有动能
                (dataframe['rsi'] > self.buy_rsi.value) &
                (dataframe['fastd'] > self.buy_fastd.value) &
                (dataframe['fisher_rsi_norma'] < self.buy_fishRsiNorma.value)
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        基于TA指标，为给定的dataframe填充卖出信号
        """

        conditions = []
        # --- 模式一：保守的快速止盈 ---
        if self.sell_trigger.value == 'rsi-macd-minusdi':
            conditions.append(qtpylib.crossed_above(dataframe['rsi'], self.sell_rsi.value)) # RSI 超买
            conditions.append(dataframe['macd'] < 0) # MACD 显示中期趋势仍弱
            conditions.append(dataframe['minus_di'] > self.sell_minusDI.value) # DMI 显示仍有卖压

        # --- 模式二：偏追踪止损的退出 ---
        if self.sell_trigger.value == 'sar-fisherRsi':
            conditions.append(dataframe['sar'] > dataframe['close']) # 抛物线SAR反转
            conditions.append(dataframe['fisher_rsi'] > self.sell_fishRsiNorma.value) # Fisher RSI 显示反弹动能已强

        # 如果任一模式的条件被满足，则构建最终的退出信号
        if conditions:
            dataframe.loc[reduce(lambda x, y: x & y, conditions), 'exit_long'] = 1

        return dataframe
