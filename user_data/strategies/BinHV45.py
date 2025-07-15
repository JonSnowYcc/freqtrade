# --- Do not remove these libs ---
from freqtrade.strategy import IStrategy
from freqtrade.strategy import IntParameter, RealParameter
from pandas import DataFrame
import numpy as np
# --------------------------------

import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib

# 该函数已定义但未在策略中使用，qtpylib.bollinger_bands 被实际调用
def bollinger_bands(stock_price, window_size, num_of_std):
    rolling_mean = stock_price.rolling(window=window_size).mean()
    rolling_std = stock_price.rolling(window=window_size).std()
    lower_band = rolling_mean - (rolling_std * num_of_std)

    return rolling_mean, lower_band


class BinHV45(IStrategy):
    """
    策略名称: BinHV45
    策略类型: 均值回归 / 形态识别 / 超参数优化

    ## 策略核心逻辑

    这是 `CombinedBinHAndCluc` 策略中 `BinHV45` 子策略的独立、可优化的高级版本。
    它是一个基于价格行为的均值回归策略，通过识别一个可被灵活定义的"恐慌抛售"或"投降式K线"形态来入场，
    然后将卖出决策完全交给止盈止损机制。

    ### 关键特征: 可优化的形态识别

    与组合策略中的硬编码版本不同，本策略将定义"投降K线"的关键阈值，如波动率大小、下跌幅度、下影线比例等，
    全部转换为了可通过超参数优化的 `IntParameter`。这使得策略能够通过机器学习来寻找最佳的形态定义。

    ### 盈利逻辑

    #### 买入条件: "寻找一根可被优化的投降式K线"
    1.  **波动率过滤**: `bbdelta > close * buy_bbdelta / 1000` - 要求市场波动率必须大于一个**可优化**的阈值。
    2.  **跌幅过滤**: `closedelta > close * buy_closedelta / 1000` - 要求单根K线的下跌幅度必须大于一个**可优化**的阈值。
    3.  **下影线过滤**: `tail < bbdelta * buy_tail / 1000` - 要求下影线长度必须小于波动率的一个**可优化**的比例，这意味着K线收于低位，几乎没有买盘抵抗。
    4.  **位置过滤**: `close < lower.shift()` - 当前收盘价必须低于**上一根K线**的布林带下轨。
    5.  **颜色过滤**: `close <= close.shift()` - 必须是一根阴线（或十字星）。

    #### 卖出条件: 无
    - `populate_exit_trend` 函数将卖出信号明确设为0，这意味着本策略**没有自定义的卖出逻辑**。
    - 所有平仓完全由 `minimal_roi` (止盈) 和 `stoploss` (止损) 参数控制。

    ### 优点
    - 逻辑清晰，专注于一种特定的、经过深思熟虑的市场形态。
    - 可优化的参数使得策略非常灵活，能适应不同市场。

    ### 缺点
    - 均值回归策略，风险较高。
    - 依赖于超参数优化的质量。
    - 信号可能非常稀少。
    """
    INTERFACE_VERSION: int = 3

    minimal_roi = RealParameter(0.005, 0.03, default=0.0125, space='roi', optimize=True)

    stoploss = RealParameter(-0.10, -0.03, default=-0.05, space='protection', optimize=True)
    timeframe = '1m'

    # 定义可优化的买入参数
    # 注意：这些值在使用时都除以了1000，所以它们代表的是千分之几
    buy_bbdelta = IntParameter(low=1, high=15, default=7, space='buy', optimize=True)
    buy_closedelta = IntParameter(low=15, high=20, default=17, space='buy', optimize=True)
    buy_tail = IntParameter(low=20, high=30, default=25, space='buy', optimize=True)

    # Indicator parameters
    buy_bb_window = IntParameter(low=20, high=60, default=40, space='buy', optimize=True)
    buy_bb_std = RealParameter(low=1.5, high=3.0, default=2.0, space='buy', optimize=True)

    # 优化后的参数示例
    buy_params = {
        "buy_bbdelta": 7,
        "buy_closedelta": 17,
        "buy_tail": 25,
    }

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 布林带 (40周期, 2倍标准差)
        bollinger = qtpylib.bollinger_bands(dataframe['close'], window=self.buy_bb_window.value, stds=self.buy_bb_std.value)
        dataframe['upper'] = bollinger['upper']
        dataframe['mid'] = bollinger['mid']
        dataframe['lower'] = bollinger['lower']
        
        # 衡量波动性: 中轨与下轨的距离
        dataframe['bbdelta'] = (dataframe['mid'] - dataframe['lower']).abs()
        # 衡量K线实体大小(未使用)
        dataframe['pricedelta'] = (dataframe['open'] - dataframe['close']).abs()
        # 衡量与前一根K线的收盘价差
        dataframe['closedelta'] = (dataframe['close'] - dataframe['close'].shift()).abs()
        # 衡量下影线长度
        dataframe['tail'] = (dataframe['close'] - dataframe['low']).abs()
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                dataframe['lower'].shift().gt(0) &
                # 条件1: 波动率过滤
                (dataframe['bbdelta'] > (dataframe['close'] * self.buy_bbdelta.value / 1000)) &
                # 条件2: 跌幅过滤
                (dataframe['closedelta'] > (dataframe['close'] * self.buy_closedelta.value / 1000)) &
                # 条件3: 下影线过滤 (要求为光脚阴线)
                (dataframe['tail'] < (dataframe['bbdelta'] * self.buy_tail.value / 1000)) &
                # 条件4: 位置过滤 (跌破前期下轨)
                (dataframe['close'] < dataframe['lower'].shift()) &
                # 条件5: 颜色过滤 (是阴线)
                (dataframe['close'] <= dataframe['close'].shift())
            ),
            'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        无卖出信号。
        这会禁用基于指标的卖出，让所有平仓由ROI和止损控制。
        """
        dataframe.loc[:, 'exit_long'] = 0
        return dataframe
