# --- Do not remove these libs ---
import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy as np
# --------------------------------
import talib.abstract as ta
from freqtrade.strategy import IStrategy, IntParameter, RealParameter
from pandas import DataFrame

# 自定义的布林带函数，专用于BinHV45子策略
def bollinger_bands(stock_price, window_size, num_of_std):
    rolling_mean = stock_price.rolling(window=window_size).mean()
    rolling_std = stock_price.rolling(window=window_size).std()
    lower_band = rolling_mean - (rolling_std * num_of_std)
    return np.nan_to_num(rolling_mean), np.nan_to_num(lower_band)


class CombinedBinHAndCluc(IStrategy):
    """
    策略名称: CombinedBinHAndCluc (BinH和Cluc组合策略)
    策略类型: 均值回归 / 组合策略

    ## 策略核心逻辑

    这是一个强大的组合策略，它融合了 `BinHV45` 和 `ClucMay72018` 这两个独立的"抢反弹"子策略。
    通过"或"逻辑将它们结合，策略旨在用两种不同的哲学思想去捕捉市场底部的交易机会。

    ### 子策略一: `BinHV45` (形态分析派)

    该子策略基于价格行为和波动率形态，寻找一个非常具体的"投降式抛售K线"作为买入信号。
    - **买入条件**: 在市场有一定波动性的前提下，当价格剧烈下跌，形成一根几乎没有下影线的、并跌破前期布林带下轨的阴线时，策略入场。
    - **逻辑解读**: `BinHV45` 认为，当一根没有买盘抵抗（下影线短）的大阴线将价格砸出正常波动范围时，表明空头力量可能在短期内耗尽，是反转的前兆。

    ### 子策略二: `ClucMay72018` (指标分析派)

    该子策略基于指标的极端状态，并增加了成交量过滤。
    - **买入条件**: 在短期下跌趋势中（价格低于50EMA），当价格严重跌穿布林带下轨（低于下轨1.5%），并且成交量正常（非PUMP行情）时，策略入场。
    - **逻辑解读**: `ClucMay72018` 等待一个由指标确认的、统计意义上的极端超卖信号，并确保这个信号不是由市场操纵引起的，从而安全地抢反弹。

    ### 统一的卖出逻辑

    - **卖出条件**: `收盘价 > 布林带中轨` (20周期均线)。
    - **逻辑解读**: 无论是由哪个子策略的信号开仓，其抢反弹的目标都是价格能"回归均值"。因此，一旦价格成功反弹回20周期均线，策略就认为目标已达成，立即止盈离场。

    ### 优点
    - 组合了两种不同的抄底逻辑，增加了交易机会，提高了策略的适应性。
    - 统一且简单的卖出逻辑清晰地定义了策略的盈利目标。
    - 每个子策略都有其精妙之处，是非常好的学习范例。

    ### 缺点
    - 所有抢反弹策略的通病：风险较高，可能买在"半山腰"。
    - 策略的参数（如 `0.008`, `0.0175`, `0.985` 等）都是"魔法数字"，可能存在过度拟合，需要谨慎测试。
    """
    INTERFACE_VERSION: int = 3
    minimal_roi = RealParameter(0.01, 0.1, default=0.05, space='roi', optimize=True)
    stoploss = RealParameter(-0.10, -0.03, default=-0.05, space='protection', optimize=True)
    timeframe = '5m'

    # 策略参数
    use_exit_signal = True
    exit_profit_only = True
    ignore_roi_if_entry_signal = False

    # --- BinHV45 Parameters ---
    bin_bb_window = IntParameter(20, 60, default=40, space='buy', optimize=True)
    bin_bb_std = RealParameter(1.5, 3.0, default=2.0, space='buy', optimize=True)
    bin_bbdelta_factor = RealParameter(0.005, 0.015, default=0.008, space='buy', optimize=True)
    bin_closedelta_factor = RealParameter(0.01, 0.03, default=0.0175, space='buy', optimize=True)
    bin_tail_factor = RealParameter(0.15, 0.35, default=0.25, space='buy', optimize=True)

    # --- ClucMay72018 Parameters ---
    cluc_bb_window = IntParameter(15, 30, default=20, space='buy', optimize=True)
    cluc_bb_std = RealParameter(1.5, 3.0, default=2.0, space='buy', optimize=True)
    cluc_ema_period = IntParameter(40, 60, default=50, space='buy', optimize=True)
    cluc_volume_rolling_window = IntParameter(20, 40, default=30, space='buy', optimize=True)
    cluc_bb_factor = RealParameter(0.97, 0.995, default=0.985, space='buy', optimize=True)
    cluc_volume_multiplier = IntParameter(10, 30, default=20, space='buy', optimize=True)


    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # --- 子策略 BinHV45 所需指标 ---
        mid, lower = bollinger_bands(dataframe['close'], window_size=self.bin_bb_window.value, num_of_std=self.bin_bb_std.value)
        dataframe['lower'] = lower
        dataframe['bbdelta'] = (mid - dataframe['lower']).abs() # 中轨和下轨的差值，衡量波动性
        dataframe['closedelta'] = (dataframe['close'] - dataframe['close'].shift()).abs() # K线收盘价的绝对变化
        dataframe['tail'] = (dataframe['close'] - dataframe['low']).abs() # 下影线长度

        # --- 子策略 ClucMay72018 所需指标 ---
        bollinger = qtpylib.bollinger_bands(qtpylib.typical_price(dataframe), window=self.cluc_bb_window.value, stds=self.cluc_bb_std.value)
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_middleband'] = bollinger['mid']
        dataframe['ema_slow'] = ta.EMA(dataframe, timeperiod=self.cluc_ema_period.value)
        dataframe['volume_mean_slow'] = dataframe['volume'].rolling(window=self.cluc_volume_rolling_window.value).mean()

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                # --- BinHV45 信号逻辑 ---
                dataframe['lower'].shift().gt(0) &
                (dataframe['bbdelta'] > (dataframe['close'] * self.bin_bbdelta_factor.value)) & # 波动率够大
                (dataframe['closedelta'] > (dataframe['close'] * self.bin_closedelta_factor.value)) & # 跌幅够大
                (dataframe['tail'] < (dataframe['bbdelta'] * self.bin_tail_factor.value)) & # 下影线够短 (无抵抗下跌)
                (dataframe['close'] < dataframe['lower'].shift()) & # 跌破前期下轨
                (dataframe['close'] <= dataframe['close'].shift()) # 当前是阴线
            ) 
            |
            (
                # --- ClucMay72018 信号逻辑 ---
                (dataframe['close'] < dataframe['ema_slow']) & # 处于短期下跌趋势
                (dataframe['close'] < self.cluc_bb_factor.value * dataframe['bb_lowerband']) & # 极端超跌
                (dataframe['volume'] < (dataframe['volume_mean_slow'].shift(1) * self.cluc_volume_multiplier.value)) # 过滤PUMP行情
            ),
            'enter_long'
        ] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        统一的卖出逻辑：当价格回归均值时卖出
        """
        dataframe.loc[
            (dataframe['close'] > dataframe['bb_middleband']),
            'exit_long'
        ] = 1
        return dataframe
