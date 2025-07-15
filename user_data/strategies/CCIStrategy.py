# --- Do not remove these libs ---
from freqtrade.strategy import IStrategy, IntParameter, RealParameter
from typing import Dict, List
from functools import reduce
from pandas import DataFrame, Series, DatetimeIndex, merge
# --------------------------------

import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib


class CCIStrategy(IStrategy):
    """
    策略名称: CCIStrategy (增强版CCI策略)
    策略作者: 未知
    策略类型: 多时间周期 (MTF) / 均值回归 / 振荡器共振

    ## 策略核心逻辑

    这是一个高度复杂、逻辑严谨的多时间周期均值回归策略。它通过一个更高时间周期（5分钟）的多重均线来构建一个非常稳固的"宏观牛市"判断，
    只有在这个宏观牛市的背景下，它才会在主交易周期（1分钟）上，去寻找一个由多个振荡器共振产生的深度回调机会来入场。

    ### 盈利逻辑: "在宏观牛市中，寻找微观共振回调点"

    #### 1. 构建多时间周期趋势过滤器 (MTF)
    策略通过一个自定义的 `resample` 函数，将1分钟数据提升到5分钟周期，并在这个5分钟图表上计算多条SMA均线（25, 50, 100, 200），作为判断宏观趋势的"保险丝"。

    #### 2. 买入条件 (振荡器共振 + 趋势过滤)
    - **振荡器共振**: 在1分钟图上，要求长周期CCI(170)、中周期CCI(34)、资金流CMF、资金流量指标MFI **全部**进入各自的深度超卖区域。
    - **【核心】趋势过滤**:
        - **中期趋势**: 在5分钟图上，必须处于 `50 SMA > 25 SMA` 的"金叉"状态。
        - **长期趋势**: 在1分钟图上，当前价格必须高于"5分钟图上的200周期SMA"。
    - **买入解读**: 只有当宏观趋势（中期和长期）都确认是牛市时，才去捕捉微观周期（1分钟）上由多个指标共振产生的深度回调机会。

    #### 3. 卖出条件 (振荡器超买 + 趋势衰竭)
    - **振荡器超买**: 在1分钟图上，长、中周期CCI进入超买区，并且CMF资金流非常强劲（市场过热）。
    - **【核心】趋势衰竭**: 在5分钟图上，均线形成 `100 SMA < 50 SMA < 25 SMA` 的"死亡交叉"排列。
    - **卖出解读**: 这是一个非常保守和稳健的退出条件。它不仅要求当前价格过热，还要求更高时间周期上的上升趋势已经出现了明确的**瓦解迹象**，才会选择平仓。

    ### 优点
    - **逻辑严谨**: 多层次的MTF趋势过滤大大提高了信号的质量，有效规避了熊市风险。
    - **共振信号**: 多指标共振的入场条件，过滤掉了大量噪音。
    - **退出稳健**: 结合趋势衰竭的退出机制，有助于避免过早平仓。

    ### 缺点
    - **极度复杂**: 策略的理解和修改门槛非常高。
    - **信号稀少**: 由于条件极其苛刻，可能会错过大量交易机会。
    """
    INTERFACE_VERSION: int = 3
    # Minimal ROI designed for the strategy.
    # This attribute will be overridden if the config file contains "minimal_roi"
    minimal_roi = RealParameter(0.01, 0.1, default=0.1, space='roi', optimize=True)

    # Optimal stoploss designed for the strategy
    # This attribute will be overridden if the config file contains "stoploss"
    stoploss = RealParameter(-0.10, -0.01, default=-0.02, space='protection', optimize=True)

    # Optimal timeframe for the strategy
    timeframe = '1m'

    # --- 超参数定义 ---
    # 买入/卖出阈值
    buy_cci1_threshold = IntParameter(-200, -80, default=-100, space='buy', optimize=True)
    buy_cci2_threshold = IntParameter(-200, -80, default=-100, space='buy', optimize=True)
    buy_cmf_threshold = RealParameter(-0.5, 0.0, default=-0.1, space='buy', optimize=True)
    buy_mfi_threshold = IntParameter(10, 40, default=25, space='buy', optimize=True)
    sell_cci1_threshold = IntParameter(80, 200, default=100, space='sell', optimize=True)
    sell_cci2_threshold = IntParameter(80, 200, default=100, space='sell', optimize=True)
    sell_cmf_threshold = RealParameter(0.0, 0.6, default=0.3, space='sell', optimize=True)

    # 指标周期 (1m 时间框架)
    cci1_period = IntParameter(150, 250, default=170, space='buy', optimize=True)
    cci2_period = IntParameter(20, 50, default=34, space='buy', optimize=True)
    cmf_period = IntParameter(15, 30, default=20, space='buy', optimize=True)
    mfi_period = IntParameter(10, 25, default=14, space='buy', optimize=True)
    rsi_period = IntParameter(10, 25, default=14, space='buy', optimize=True)

    # 绘图指标周期
    bb_window = IntParameter(15, 30, default=20, space='buy', optimize=True)
    bb_stds = RealParameter(1.5, 3.0, default=2.0, space='buy', optimize=True)

    # 指标周期 (重采样时间框架)
    resample_factor = IntParameter(2, 10, default=5, space='buy', optimize=True)
    res_sma_period = IntParameter(80, 120, default=100, space='buy', optimize=True)
    res_medium_period = IntParameter(40, 60, default=50, space='buy', optimize=True)
    res_short_period = IntParameter(20, 35, default=25, space='buy', optimize=True)
    res_long_period = IntParameter(150, 250, default=200, space='buy', optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 1. 通过自定义函数获取包含大周期指标的dataframe
        dataframe = self.resample(dataframe, self.timeframe, self.resample_factor.value)

        # 2. 在主图表(1m)上计算振荡器指标
        dataframe['cci_one'] = ta.CCI(dataframe, timeperiod=self.cci1_period.value) # 长周期CCI
        dataframe['cci_two'] = ta.CCI(dataframe, timeperiod=self.cci2_period.value)  # 中周期CCI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=self.rsi_period.value)
        dataframe['mfi'] = ta.MFI(dataframe, timeperiod=self.mfi_period.value)
        dataframe['cmf'] = self.chaikin_mf(dataframe, periods=self.cmf_period.value) # 自定义蔡金资金流

        # 3. 绘图用指标
        bollinger = qtpylib.bollinger_bands(dataframe['close'], window=self.bb_window.value, stds=self.bb_stds.value)
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_upperband'] = bollinger['upper']
        dataframe['bb_middleband'] = bollinger['mid']

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义买入信号
        """
        dataframe.loc[
            (
                # --- 第一部分: 振荡器共振超卖 ---
                (dataframe['cci_one'] < self.buy_cci1_threshold.value)
                & (dataframe['cci_two'] < self.buy_cci2_threshold.value)
                & (dataframe['cmf'] < self.buy_cmf_threshold.value)
                & (dataframe['mfi'] < self.buy_mfi_threshold.value)

                # --- 第二部分: MTF趋势过滤 ("保险丝") ---
                # 中期趋势(5m)看涨
                & (dataframe['resample_medium'] > dataframe['resample_short'])
                # 长期趋势(5m)看涨
                & (dataframe['resample_long'] < dataframe['close'])
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义卖出信号
        """
        dataframe.loc[
            (
                # --- 第一部分: 振荡器共振超买 ---
                (dataframe['cci_one'] > self.sell_cci1_threshold.value)
                & (dataframe['cci_two'] > self.sell_cci2_threshold.value)
                & (dataframe['cmf'] > self.sell_cmf_threshold.value)
                # --- 第二部分: MTF趋势衰竭 ---
                & (dataframe['resample_sma'] < dataframe['resample_medium'])
                & (dataframe['resample_medium'] < dataframe['resample_short'])
            ),
            'exit_long'] = 1
        return dataframe

    def chaikin_mf(self, df, periods=20):
        """自定义蔡金资金流函数"""
        close = df['close']
        low = df['low']
        high = df['high']
        volume = df['volume']

        mfv = ((close - low) - (high - close)) / (high - low)
        mfv = mfv.fillna(0.0)
        mfv *= volume
        cmf = mfv.rolling(periods).sum() / volume.rolling(periods).sum()

        return Series(cmf, name='cmf')

    def resample(self, dataframe, interval, factor):
        """
        自定义重采样函数，定义了"加强"逻辑
        将dataframe重采样到更高时间周期，以建立多层次的趋势判断
        """
        df = dataframe.copy()
        df = df.set_index(DatetimeIndex(df['date']))
        ohlc_dict = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last'
        }
        # 重采样到 1m * 5 = 5m
        higher_tf_str = str(int(interval[:-1]) * factor) + 'min'
        df = df.resample(higher_tf_str, label="right").agg(ohlc_dict)
        
        # 在5m周期上计算多条SMA均线
        df['resample_sma'] = ta.SMA(df, timeperiod=self.res_sma_period.value, price='close')
        df['resample_medium'] = ta.SMA(df, timeperiod=self.res_medium_period.value, price='close')
        df['resample_short'] = ta.SMA(df, timeperiod=self.res_short_period.value, price='close')
        df['resample_long'] = ta.SMA(df, timeperiod=self.res_long_period.value, price='close')
        
        df = df.drop(columns=['open', 'high', 'low', 'close'])
        df = df.resample(interval[:-1] + 'min')
        df = df.interpolate(method='time')
        df['date'] = df.index
        df.index = range(len(df))
        dataframe = merge(dataframe, df, on='date', how='left')
        return dataframe
