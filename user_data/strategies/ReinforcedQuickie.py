# --- Do not remove these libs ---
from freqtrade.strategy import IStrategy, IntParameter, RealParameter, BooleanParameter
from typing import Dict, List
from functools import reduce
from pandas import DataFrame, DatetimeIndex, merge
# --------------------------------

import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy  # noqa

class ReinforcedQuickie(IStrategy):
    """
    策略名称: ReinforcedQuickie (加强版快枪手)
    策略作者: Gert Wohlgemuth
    策略类型: 多时间周期 (MTF) / 趋势回调

    ## 策略核心逻辑

    这是一个以**多时间周期（MTF）分析**为绝对核心的策略，完美地诠释了"顺大势，逆小势"的交易思想。
    策略作者明确指出其理念是："只在上升趋势的市场中买入"。

    ### 关键特征: 自定义多时间周期（MTF）分析

    策略通过一个自定义的 `resample` 函数来实现MTF分析：
    1.  **数据重采样**: 将当前5分钟图表数据重采样为1小时（`5m * 12`）数据。
    2.  **计算大周期指标**: 在1小时这个"宏观"图表上计算一条25周期的SMA均线。
    3.  **合并回主图表**: 将这条"小时级"的均线数据合并回5分钟图表，使其在每一根5分钟K线上都有一个对应的、平滑的宏观趋势值。

    ### 盈利逻辑

    策略的买入逻辑分为 **"入场形态"** 和 **"安全过滤器"** 两部分，必须同时满足才能入场。

    #### 入场形态 (二选一):
    1.  **极端深蹲**: 寻找价格被极致打压的"接飞刀"机会。要求当前价格不仅低于短期和中期均线，而且是过去12根K线的最低价，并已跌破布林带下轨。
    2.  **V型反转**: 经典的V型价格形态识别，与 `SmoothOperator` 策略中的逻辑相同。

    #### 安全过滤器 (必须全部满足):
    1.  **成交量过滤**: 避免在成交量异常放大（可能是拉高出货）时入场。
    2.  **顺大势**: `当前价格 > 小时级SMA`。这是策略的灵魂，确保所有交易都顺应宏观趋势。
    3.  **大势确认**: `小时级SMA本身在上涨`。这进一步确认了宏观趋势是健康向上的，提供了双重保障。

    ### 卖出逻辑 (二选一):
    1.  **极端超买**: 与"极端深蹲"买入相对应，在价格达到极端强势（突破所有均线、创近期新高、冲破布林上轨、且MFI超买）时卖出。
    2.  **上涨衰竭**: 出现"八连阳"并且RSI超买，被认为是上涨行情即将力竭的信号。

    ### 优点
    - 强大的MTF趋势过滤器可以有效避免逆势交易，大大提高策略的稳定性和胜率。
    - 结合了多种入场和出场逻辑，覆盖了不同的市场情景。
    - 是学习如何构建和应用MTF策略的绝佳范例。

    ### 缺点
    - 逻辑较为复杂，特别是`resample`函数部分。
    - "极端深蹲"式的入场条件风险较高。
    - 性能高度依赖MTF趋势过滤的有效性，如果大周期判断失误，策略依然会亏损。
    """

    INTERFACE_VERSION: int = 3
    # Minimal ROI designed for the strategy.
    # This attribute will be overridden if the config file contains "minimal_roi"
    minimal_roi = RealParameter(0.005, 0.03, default=0.01, space='roi', optimize=True)

    # Optimal stoploss designed for the strategy
    # This attribute will be overridden if the config file contains "stoploss"
    stoploss = RealParameter(-0.10, -0.03, default=-0.05, space='protection', optimize=True)

    # Optimal timeframe for the strategy
    timeframe = '5m'

    # resample factor to establish our general trend. Basically don't buy if a trend is not given
    resample_factor = IntParameter(8, 20, default=12, space='buy', optimize=True)
    resample_sma_period = IntParameter(20, 40, default=25, space='buy', optimize=True)

    ema_short_term = IntParameter(3, 10, default=5, space='buy', optimize=True)
    ema_medium_term = IntParameter(10, 20, default=12, space='buy', optimize=True)
    ema_long_term = IntParameter(20, 30, default=21, space='buy', optimize=True)

    # Indicator periods
    bb_window = IntParameter(15, 30, default=20, space='buy', optimize=True)
    bb_std = RealParameter(1.5, 3.0, default=2.0, space='buy', optimize=True)
    cci_period = IntParameter(15, 30, default=20, space='buy', optimize=True)
    mfi_period = IntParameter(10, 20, default=14, space='buy', optimize=True)
    rsi_period = IntParameter(5, 15, default=7, space='buy', optimize=True)
    
    # Logic thresholds
    # Entry
    buy_cci_v_bottom = IntParameter(-150, -50, default=-100, space='buy', optimize=True)
    buy_rsi_v_bottom = IntParameter(10, 40, default=30, space='buy', optimize=True)
    buy_mfi_v_bottom = IntParameter(10, 40, default=30, space='buy', optimize=True)
    buy_volume_window = IntParameter(20, 40, default=30, space='buy', optimize=True)
    buy_volume_multiplier = IntParameter(10, 30, default=20, space='buy', optimize=True)

    # Exit
    sell_mfi_extreme = IntParameter(70, 90, default=80, space='sell', optimize=True)
    sell_rsi_green_candles = IntParameter(65, 85, default=70, space='sell', optimize=True)
    sell_green_candle_count = IntParameter(5, 12, default=8, space='sell', optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = self.resample(dataframe, self.timeframe, self.resample_factor.value)

        ##################################################################################
        # buy and sell indicators

        dataframe[f'ema_{self.ema_short_term.value}'] = ta.EMA(
            dataframe, timeperiod=self.ema_short_term.value
        )
        dataframe[f'ema_{self.ema_medium_term.value}'] = ta.EMA(
            dataframe, timeperiod=self.ema_medium_term.value
        )
        dataframe[f'ema_{self.ema_long_term.value}'] = ta.EMA(
            dataframe, timeperiod=self.ema_long_term.value
        )

        bollinger = qtpylib.bollinger_bands(
            qtpylib.typical_price(dataframe), window=self.bb_window.value, stds=self.bb_std.value
        )
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_middleband'] = bollinger['mid']
        dataframe['bb_upperband'] = bollinger['upper']

        dataframe['min'] = ta.MIN(dataframe, timeperiod=self.ema_medium_term.value)
        dataframe['max'] = ta.MAX(dataframe, timeperiod=self.ema_medium_term.value)

        dataframe['cci'] = ta.CCI(dataframe, timeperiod=self.cci_period.value)
        dataframe['mfi'] = ta.MFI(dataframe, timeperiod=self.mfi_period.value)
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=self.rsi_period.value)

        dataframe['average'] = (dataframe['close'] + dataframe['open'] + dataframe['high'] + dataframe['low']) / 4

        ##################################################################################
        # required for graphing
        bollinger = qtpylib.bollinger_bands(dataframe['close'], window=20, stds=2)
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_upperband'] = bollinger['upper']
        dataframe['bb_middleband'] = bollinger['mid']

        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        dataframe['macdhist'] = macd['macdhist']

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the buy signal for the given dataframe
        :param dataframe: DataFrame
        :return: DataFrame with buy column
        """
        dataframe.loc[
            (
                    (
                            (
                                    (dataframe['close'] < dataframe[f'ema_{self.ema_short_term.value}']) &
                                    (dataframe['close'] < dataframe[f'ema_{self.ema_medium_term.value}']) &
                                    (dataframe['close'] == dataframe['min']) &
                                    (dataframe['close'] <= dataframe['bb_lowerband'])
                            )
                            |
                            # simple v bottom shape (lopsided to the left to increase reactivity)
                            # which has to be below a very slow average
                            # this pattern only catches a few, but normally very good buy points
                            (
                                    (dataframe['average'].shift(5) > dataframe['average'].shift(4))
                                    & (dataframe['average'].shift(4) > dataframe['average'].shift(3))
                                    & (dataframe['average'].shift(3) > dataframe['average'].shift(2))
                                    & (dataframe['average'].shift(2) > dataframe['average'].shift(1))
                                    & (dataframe['average'].shift(1) < dataframe['average'].shift(0))
                                    & (dataframe['low'].shift(1) < dataframe['bb_middleband'])
                                    & (dataframe['cci'].shift(1) < self.buy_cci_v_bottom.value)
                                    & (dataframe['rsi'].shift(1) < self.buy_rsi_v_bottom.value)
                                    & (dataframe['mfi'].shift(1) < self.buy_mfi_v_bottom.value)

                            )
                    )
                    # safeguard against down trending markets and a pump and dump
                    &
                    (
                            (dataframe['volume'] < (dataframe['volume'].rolling(window=self.buy_volume_window.value).mean().shift(1) * self.buy_volume_multiplier.value)) &
                            (dataframe['resample_sma'] < dataframe['close']) &
                            (dataframe['resample_sma'].shift(1) < dataframe['resample_sma'])
                    )
            )
            ,
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the sell signal for the given dataframe
        :param dataframe: DataFrame
        :return: DataFrame with buy column
        """
        
        # Build consecutive green candle condition dynamically
        green_candles_conditions = []
        for i in range(self.sell_green_candle_count.value):
            green_candles_conditions.append(dataframe['open'].shift(i) < dataframe['close'].shift(i))
        
        green_candles_rule = reduce(lambda x, y: x & y, green_candles_conditions)


        dataframe.loc[
            (
                    (dataframe['close'] > dataframe[f'ema_{self.ema_short_term.value}']) &
                    (dataframe['close'] > dataframe[f'ema_{self.ema_medium_term.value}']) &
                    (dataframe['close'] >= dataframe['max']) &
                    (dataframe['close'] >= dataframe['bb_upperband']) &
                    (dataframe['mfi'] > self.sell_mfi_extreme.value)
            ) |

            # always sell on N green candles
            # with a high rsi
            (
                green_candles_rule &
                (dataframe['rsi'] > self.sell_rsi_green_candles.value)
            )
            ,
            'exit_long'
        ] = 1
        return dataframe

    def resample(self, dataframe, interval, factor):
        """
        自定义重采样函数，定义了"加强"逻辑
        将dataframe重采样到更高时间周期，以判断我们是处于上升、下降还是横盘趋势中
        """
        # 复制dataframe以避免修改原始数据
        df = dataframe.copy()
        # 将date列设为时间索引，这是重采样的前提
        df = df.set_index(DatetimeIndex(df['date']))
        # 定义重采样后的K线合成规则
        ohlc_dict = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last'
        }
        # 执行重采样: 例如 '5min' -> '60min'
        higher_tf_str = str(int(interval[:-1]) * factor) + 'min'
        df = df.resample(higher_tf_str, label="right").agg(ohlc_dict).dropna(how='any')

        # 在高时间周期上计算指标
        df['resample_sma'] = ta.SMA(df, timeperiod=self.resample_sma_period.value, price='close')
        
        # 删除不再需要的原始价格数据，只保留指标
        df = df.drop(columns=['open', 'high', 'low', 'close'])

        # 将高周期数据重新采样回原始的低周期，以便合并
        df = df.resample(interval[:-1] + 'min')
        # 使用时间插值法填充空值 (例如，1小时内的所有5分钟K线将共享相同的、平滑过渡的SMA值)
        df = df.interpolate(method='time')
        
        df['date'] = df.index
        df.index = range(len(df))
        
        # 将包含大周期指标的dataframe合并回原始dataframe
        dataframe = merge(dataframe, df, on='date', how='left')
        return dataframe
