# --- Do not remove these libs ---
from freqtrade.strategy import IStrategy, IntParameter, RealParameter
from typing import Dict, List
from functools import reduce
from pandas import DataFrame
# --------------------------------

import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy  # noqa

# 警告: 作者在代码中明确指出 -- "请勿使用，只是在玩平滑和图表!"
# (original: "DO NOT USE, just playing with smooting and graphs!")


class SmoothOperator(IStrategy):
    """
    策略名称: SmoothOperator (平滑算子)
    策略作者: Gert Wohlgemuth
    策略类型: 振荡器 / 形态识别 / 左侧交易

    ## 策略核心逻辑

    这是一个构思非常精妙的策略。其核心思想并非使用传统的指标金叉死叉，而是通过对多种常用振荡器指标（CCI, RSI, MFI）进行**深度平滑**处理，
    融合成一个自定义的超级平滑振荡器，并利用这个振荡器的**形态和拐点**来进行交易，旨在"探测一个尚未完成的顶底形态"，实现左侧交易。

    ### 关键特征: 指标的深度平滑

    1.  **初步平滑**: 首先计算常规的 CCI, RSI, MFI 指标。然后用11周期的EMA分别对它们进行平滑处理，得到 `cci_smooth`, `rsi_smooth`, `mfi_smooth`。
    2.  **加权融合**: 将三个平滑后的指标加权融合，得到一个复合指标。
    3.  **最终平滑**: 使用21周期的TEMA（三指数移动平均线，一种延迟更低的均线）对上述复合指标进行最终的深度平滑，得到策略的核心 `mfi_rsi_cci_smooth`。

    ### 盈利逻辑

    #### 买入条件 (三种情况任一满足即可):
    1.  **V型底识别**: 通过程序化方式寻找一个清晰的V型价格形态（连续4根K线的均价下跌后，第5根开始上涨），并要求此时处于超卖状态。
    2.  **常规超卖**: 更普遍的入场方式，要求CCI, RSI, MFI同时进入深度超卖区。
    3.  **极端超卖**: 针对某些"缓慢吸筹"币种的极端情况，要求MFI < 10, CCI < -150。
    - **最终过滤器**: 所有买入条件都必须满足 `收盘价 > 上一根收盘价`，作为最后的看涨确认。

    #### 卖出条件 (三种情况任一满足即可):
    1.  **核心卖点 - 平滑振荡器顶背离**: 策略监控 `mfi_rsi_cci_smooth` 指标。当该指标形成一个顶部并开始掉头时（即`指标值 > 前一根`但`前一根 < 再前一根`），策略会卖出。这是典型的利用指标拐点的左侧交易。
    2.  **连续阳线**: 出现连续8根绿色阳线，认为短期上涨过热，获利了结。
    3.  **常规超买**: CCI和RSI同时进入非常超买的区域。

    ### 优点
    - 深度平滑的自定义振荡器能有效过滤掉大量市场噪音，信号更稳定。
    - 试图通过指标拐点进行左侧交易，理论上可以获得更好的入场和出场点位。
    - 结合了多种入场和出场情景，适应性较强。

    ### 缺点
    - 策略逻辑非常复杂，可读性差，难以调试和优化。
    - 左侧交易的风险在于可能"抄在半山腰"或"逃顶过早"。
    - 大量使用了shift操作，计算量较大。
    """

    INTERFACE_VERSION: int = 3
    # 最小盈利预期
    # 除非卖点提前出现，否则我们只在10%盈利后卖出
    minimal_roi = RealParameter(0.05, 0.15, default=0.10, space='roi', optimize=True)

    # 优化的止损
    # 应该转换为移动止损
    stoploss = RealParameter(-0.10, -0.03, default=-0.05, space='protection', optimize=True)

    # 最佳时间框架
    timeframe = '5m'

    # Indicator periods
    cci_period = IntParameter(15, 30, default=20, space='buy', optimize=True)
    rsi_period = IntParameter(10, 20, default=14, space='buy', optimize=True)
    adx_period = IntParameter(10, 20, default=14, space='buy', optimize=True)
    mfi_period = IntParameter(10, 20, default=14, space='buy', optimize=True)
    smooth_ema_period = IntParameter(8, 15, default=11, space='buy', optimize=True)
    final_smooth_tema_period = IntParameter(15, 30, default=21, space='buy', optimize=True)
    
    # Plotting BB
    viz_bb_window = IntParameter(15, 30, default=20, space='buy', optimize=True)
    viz_bb_std = RealParameter(1.5, 3.0, default=2.0, space='buy', optimize=True)
    
    # Entry BB
    entry_bb_window = IntParameter(15, 30, default=20, space='buy', optimize=True)
    entry_bb_std = RealParameter(1.0, 2.5, default=1.6, space='buy', optimize=True)
    bsharp_slow_period = IntParameter(8, 15, default=11, space='buy', optimize=True)
    bsharp_medium_period = IntParameter(5, 12, default=8, space='buy', optimize=True)
    bsharp_fast_period = IntParameter(3, 8, default=5, space='buy', optimize=True)

    # SMA periods
    sma_slow_period = IntParameter(150, 250, default=200, space='buy', optimize=True)
    sma_medium_period = IntParameter(80, 120, default=100, space='buy', optimize=True)
    sma_fast_period = IntParameter(40, 60, default=50, space='buy', optimize=True)

    # Entry thresholds
    buy_cci_v_bottom = IntParameter(-150, -50, default=-100, space='buy', optimize=True)
    buy_rsi_v_bottom = IntParameter(20, 40, default=30, space='buy', optimize=True)
    buy_cci_regular = IntParameter(-250, -150, default=-200, space='buy', optimize=True)
    buy_rsi_regular = IntParameter(20, 40, default=30, space='buy', optimize=True)
    buy_mfi_regular = IntParameter(20, 40, default=30, space='buy', optimize=True)
    buy_mfi_extreme = IntParameter(5, 15, default=10, space='buy', optimize=True)
    buy_cci_extreme = IntParameter(-200, -100, default=-150, space='buy', optimize=True)

    # Exit thresholds
    sell_smooth_osc_level = IntParameter(80, 120, default=100, space='sell', optimize=True)
    sell_green_candle_count = IntParameter(5, 12, default=8, space='sell', optimize=True)
    sell_cci_regular = IntParameter(150, 250, default=200, space='sell', optimize=True)
    sell_rsi_regular = IntParameter(65, 85, default=70, space='sell', optimize=True)


    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        ##################################################################################
        # 核心指标计算

        # 1. 计算原始振荡器
        dataframe['cci'] = ta.CCI(dataframe, timeperiod=self.cci_period.value)
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=self.rsi_period.value)
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=self.adx_period.value)
        dataframe['mfi'] = ta.MFI(dataframe, timeperiod=self.mfi_period.value)

        # 2. 对振荡器进行初步EMA平滑
        dataframe['mfi_smooth'] = ta.EMA(dataframe, timeperiod=self.smooth_ema_period.value, price='mfi')
        dataframe['cci_smooth'] = ta.EMA(dataframe, timeperiod=self.smooth_ema_period.value, price='cci')
        dataframe['rsi_smooth'] = ta.EMA(dataframe, timeperiod=self.smooth_ema_period.value, price='rsi')

        ##################################################################################
        # 绘图用指标 (不参与核心逻辑)
        bollinger_viz = qtpylib.bollinger_bands(dataframe['close'], window=self.viz_bb_window.value, stds=self.viz_bb_std.value)
        dataframe['bb_lowerband_viz'] = bollinger_viz['lower']
        dataframe['bb_upperband_viz'] = bollinger_viz['upper']
        dataframe['bb_middleband_viz'] = bollinger_viz['mid']

        macd = ta.MACD(dataframe)
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        dataframe['macdhist'] = macd['macdhist']

        ##################################################################################
        # 入场用的布林带指标 (标准差与绘图用的不同)
        bollinger_entry = qtpylib.bollinger_bands(dataframe['close'], window=self.entry_bb_window.value, stds=self.entry_bb_std.value)
        dataframe['entry_bb_lowerband'] = bollinger_entry['lower']
        dataframe['entry_bb_upperband'] = bollinger_entry['upper']
        dataframe['entry_bb_middleband'] = bollinger_entry['mid']

        # 自定义指标 bsharp，衡量布林带宽度，用于判断波动性
        dataframe['bsharp'] = (dataframe['entry_bb_upperband'] - dataframe['entry_bb_lowerband']) / (
            dataframe['entry_bb_middleband'])
        dataframe['bsharp_slow'] = ta.SMA(dataframe, price='bsharp', timeperiod=self.bsharp_slow_period.value)
        dataframe['bsharp_medium'] = ta.SMA(dataframe, price='bsharp', timeperiod=self.bsharp_medium_period.value)
        dataframe['bsharp_fast'] = ta.SMA(dataframe, price='bsharp', timeperiod=self.bsharp_fast_period.value)

        ##################################################################################
        # 3. 融合与深度平滑，构建核心振荡器
        #    对rsi和mfi赋予稍高的权重
        dataframe['mfi_rsi_cci_smooth'] = (dataframe['rsi_smooth'] * 1.125 + dataframe['mfi_smooth'] * 1.125 +
                                           dataframe['cci_smooth']) / 3
        # 4. 使用TEMA进行最终的深度平滑
        dataframe['mfi_rsi_cci_smooth'] = ta.TEMA(dataframe, timeperiod=self.final_smooth_tema_period.value, price='mfi_rsi_cci_smooth')

        # 其他辅助指标
        dataframe['candle_size'] = (dataframe['close'] - dataframe['open']) * (
                dataframe['close'] - dataframe['open']) / 2

        # K线四价格平均值，用于形态识别
        dataframe['average'] = (dataframe['close'] + dataframe['open'] + dataframe['high'] + dataframe['low']) / 4
        dataframe['sma_slow'] = ta.SMA(dataframe, timeperiod=self.sma_slow_period.value, price='close')
        dataframe['sma_medium'] = ta.SMA(dataframe, timeperiod=self.sma_medium_period.value, price='close')
        dataframe['sma_fast'] = ta.SMA(dataframe, timeperiod=self.sma_fast_period.value, price='close')

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (
                    # 条件1: V型底形态识别
                    # 连续4根K线均价下跌，第5根上涨，形成V字
                    (
                            (dataframe['average'].shift(5) > dataframe['average'].shift(4))
                            & (dataframe['average'].shift(4) > dataframe['average'].shift(3))
                            & (dataframe['average'].shift(3) > dataframe['average'].shift(2))
                            & (dataframe['average'].shift(2) > dataframe['average'].shift(1))
                            & (dataframe['average'].shift(1) < dataframe['average'].shift(0))
                            & (dataframe['low'].shift(1) < dataframe['entry_bb_middleband']) # V字底部需低于布林中轨
                            & (dataframe['cci'].shift(1) < self.buy_cci_v_bottom.value) # 同时CCI和RSI超卖
                            & (dataframe['rsi'].shift(1) < self.buy_rsi_v_bottom.value)

                    )
                    |
                    # 条件2: 常规超卖情况
                    (
                            (dataframe['low'] < dataframe['entry_bb_middleband'])
                            & (dataframe['cci'] < self.buy_cci_regular.value)
                            & (dataframe['rsi'] < self.buy_rsi_regular.value)
                            & (dataframe['mfi'] < self.buy_mfi_regular.value)
                    )

                    |
                    # 条件3: 极端超卖情况 (针对缓慢吸筹币种)
                    (
                            (dataframe['mfi'] < self.buy_mfi_extreme.value)
                            & (dataframe['cci'] < self.buy_cci_extreme.value)
                            & (dataframe['rsi'] < dataframe['mfi']) # rsi比mfi更低
                    )

                )

                &
                # 最终确认: K线必须收高，确认上涨动能
                (dataframe['close'] > dataframe['close'].shift())
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                (
                    # 条件1 (核心): 自定义平滑振荡器形成顶部并掉头
                    (
                        (dataframe['mfi_rsi_cci_smooth'] > self.sell_smooth_osc_level.value) # 在超买区
                        & (dataframe['mfi_rsi_cci_smooth'].shift(1) > dataframe['mfi_rsi_cci_smooth']) # 当前值<前一根值
                        & (dataframe['mfi_rsi_cci_smooth'].shift(2) < dataframe['mfi_rsi_cci_smooth'].shift(1)) # 前一根值>前二根值 (确认顶峰)
                        & (dataframe['mfi_rsi_cci_smooth'].shift(3) < dataframe['mfi_rsi_cci_smooth'].shift(2))
                    )
                    |
                    # 条件2: 出现连续N根阳线，被视为短期过热
                    (
                        StrategyHelper.n_green_candles(dataframe, self.sell_green_candle_count.value)
                    )
                    |
                    # 条件3: 常规超买情况 (防止PUMP行情)
                    (
                        (dataframe['cci'] > self.sell_cci_regular.value)
                        & (dataframe['rsi'] > self.sell_rsi_regular.value)
                    )
                )

            ),
            'exit_long'] = 1
        return dataframe


class StrategyHelper:
    """
    一个简单的辅助类，为策略预定义一些K线形态模式
    注意: 以下定义的多种形态中，该策略实际只调用了 n_green_candles
    """

    @staticmethod
    def n_green_candles(dataframe, n):
        """
        判断是否连续出现N根阳线
        """
        conditions = []
        for i in range(n):
            conditions.append(dataframe['open'].shift(i) < dataframe['close'].shift(i))
        return reduce(lambda x, y: x & y, conditions)

    @staticmethod
    def seven_green_candles(dataframe):
        """
        判断是否连续出现7根阳线
        """
        return StrategyHelper.n_green_candles(dataframe, 7)

    @staticmethod
    def eight_green_candles(dataframe):
        """
        判断是否连续出现8根阳线
        """
        return StrategyHelper.n_green_candles(dataframe, 8)

    @staticmethod
    def eight_red_candles(dataframe, shift=0):
        """
            evaluates if we are having 8 red candles in a row
        :param self:
        :param dataframe:
        :param shift: shift the pattern by n
        :return:
        """
        return (
                (dataframe['open'].shift(shift) > dataframe['close'].shift(shift)) &
                (dataframe['open'].shift(1 + shift) > dataframe['close'].shift(1 + shift)) &
                (dataframe['open'].shift(2 + shift) > dataframe['close'].shift(2 + shift)) &
                (dataframe['open'].shift(3 + shift) > dataframe['close'].shift(3 + shift)) &
                (dataframe['open'].shift(4 + shift) > dataframe['close'].shift(4 + shift)) &
                (dataframe['open'].shift(5 + shift) > dataframe['close'].shift(5 + shift)) &
                (dataframe['open'].shift(6 + shift) > dataframe['close'].shift(6 + shift)) &
                (dataframe['open'].shift(7 + shift) > dataframe['close'].shift(7 + shift)) &
                (dataframe['open'].shift(8 + shift) > dataframe['close'].shift(8 + shift))
        )

    @staticmethod
    def four_green_one_red_candle(dataframe):
        """
            evaluates if we are having a red candle and 4 previous green
        :param self:
        :param dataframe:
        :return:
        """
        return (
                (dataframe['open'] > dataframe['close']) &
                (dataframe['open'].shift(1) < dataframe['close'].shift(1)) &
                (dataframe['open'].shift(2) < dataframe['close'].shift(2)) &
                (dataframe['open'].shift(3) < dataframe['close'].shift(3)) &
                (dataframe['open'].shift(4) < dataframe['close'].shift(4))
        )

    @staticmethod
    def four_red_one_green_candle(dataframe):
        """
            evaluates if we are having a green candle and 4 previous red
        :param self:
        :param dataframe:
        :return:
        """
        return (
                (dataframe['open'] < dataframe['close']) &
                (dataframe['open'].shift(1) > dataframe['close'].shift(1)) &
                (dataframe['open'].shift(2) > dataframe['close'].shift(2)) &
                (dataframe['open'].shift(3) > dataframe['close'].shift(3)) &
                (dataframe['open'].shift(4) > dataframe['close'].shift(4))
        )
