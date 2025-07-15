# --- Do not remove these libs ---
from freqtrade.strategy import IStrategy, IntParameter, RealParameter
from typing import Dict, List
from functools import reduce
from pandas import DataFrame
# --------------------------------
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib

class Scalp(IStrategy):
    """
    策略名称: Scalp (剥头皮)
    策略作者: 未知
    策略类型: 剥头皮 / 趋势回调
    官方Repo: https://github.com/freqtrade/freqtrade-strategies/blob/main/user_data/strategies/berlinguyinca/Scalp.py

    ## 策略核心逻辑

    这是一个经典的"剥头皮"策略，专为1分钟等短时间周期设计。其核心思想是在一个已确认的强势趋势中，捕捉价格短暂回调的机会入场，
    然后在价格小幅反弹后迅速离场，赚取微利。策略建议同时运行大量交易对以分散风险。

    值得注意的是，策略的注释建议"仅基于ROI进行卖出"，这意味着`minimal_roi`是主要的止盈方式，而`populate_exit_trend`中的逻辑更多是作为一种保护性的退出机制。

    ### 盈利逻辑: "趋势中回调买入"

    策略的买入条件结合了趋势、价格和动量三个维度的判断：

    1.  **趋势确认**: `ADX > 30` - ADX（平均趋向指数）高于30，表明当前市场处于一个明显的趋势行情中（上涨或下跌），而非盘整。这是策略运作的前提。
    2.  **价格回调**: `开盘价 < 5周期EMA最低价` - K线的开盘价直接低于近期K线低点的移动平均线，这是一个强烈的价格回调或急跌信号。
    3.  **动能反转**: `随机指标(Stoch)金叉` - 快速随机指标(Stoch)在30下方的超卖区形成"金叉"（快线上穿慢线），这是经典的动能见底反转信号，为抄底提供了精确的时机。

    ### 卖出逻辑

    卖出逻辑由三个"或"条件组成，满足任意一个即可离场，体现了"快速离场"的剥头皮思想：
    - `开盘价 >= 5周期EMA最高价`：价格强力反弹，已经触及甚至超过了近期高点的移动平均线。
    - `随机指标快线 > 70` 或 `随机指标慢线 > 70`：随机指标的任一线路进入70上方的超买区，表明反弹可能即将结束。

    ### 与 `SmoothScalp` 策略的对比
    - 本策略可以看作是 `SmoothScalp` 的简化版。它省略了`CCI`和`MFI`指标作为过滤条件，使得入场信号更频繁。
    - 同时，它的卖出条件也更宽松，不要求CCI超买作为前置条件，因此会比`SmoothScalp`更早地退出交易。
    """

    INTERFACE_VERSION: int = 3
    # 最小盈利预期。对于此策略，建议仅基于ROI卖出。
    minimal_roi = RealParameter(0.005, 0.03, default=0.01, space='roi', optimize=True)
    # 优化的止损位，不应低于-3%
    stoploss = RealParameter(-0.05, -0.02, default=-0.04, space='protection', optimize=True)

    # 最佳时间周期，越短越好
    timeframe = '1m'

    # --- 超参数定义 ---
    # 买入参数
    buy_adx = IntParameter(20, 40, default=30, space='buy', optimize=True)
    buy_stoch_threshold = IntParameter(15, 45, default=30, space='buy', optimize=True)

    # 卖出参数
    sell_stoch_threshold = IntParameter(60, 90, default=70, space='sell', optimize=True)

    # 指标周期参数
    ema_period = IntParameter(3, 15, default=5, space='buy', optimize=True)
    stoch_k_period = IntParameter(3, 10, default=5, space='buy', optimize=True)
    stoch_d_period = IntParameter(2, 7, default=3, space='buy', optimize=True)
    adx_period = IntParameter(10, 25, default=14, space='buy', optimize=True)

    # 绘图指标参数
    bb_window = IntParameter(15, 30, default=20, space='buy', optimize=True)
    bb_std = RealParameter(1.5, 3.0, default=2.0, space='buy', optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # EMA 指数移动平均线，构成一个动态价格通道
        dataframe['ema_high'] = ta.EMA(dataframe, timeperiod=self.ema_period.value, price='high')
        dataframe['ema_close'] = ta.EMA(dataframe, timeperiod=self.ema_period.value, price='close')
        dataframe['ema_low'] = ta.EMA(dataframe, timeperiod=self.ema_period.value, price='low')
        
        # StochF - 快速随机指标，用于判断超买超卖和动能
        stoch_fast = ta.STOCHF(dataframe,
                             fastk_period=self.stoch_k_period.value,
                             fastd_period=self.stoch_d_period.value,
                             fastd_matype=0)
        dataframe['fastd'] = stoch_fast['fastd']
        dataframe['fastk'] = stoch_fast['fastk']
        
        # ADX - 平均趋向指数，用于衡量趋势的强度
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=self.adx_period.value)

        # 仅用于绘图的布林带指标
        bollinger = qtpylib.bollinger_bands(dataframe['close'], window=self.bb_window.value, stds=self.bb_std.value)
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_upperband'] = bollinger['upper']
        dataframe['bb_middleband'] = bollinger['mid']

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义买入信号的条件
        """
        dataframe.loc[
            (
                # 1. 价格急跌，低于EMA通道下轨
                (dataframe['open'] < dataframe['ema_low']) &
                # 2. 存在强劲趋势
                (dataframe['adx'] > self.buy_adx.value) &
                # 3. 随机指标在超卖区金叉，确认反转时机
                (
                    (dataframe['fastk'] < self.buy_stoch_threshold.value) &
                    (dataframe['fastd'] < self.buy_stoch_threshold.value) &
                    (qtpylib.crossed_above(dataframe['fastk'], dataframe['fastd']))
                )
            ),
            'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义卖出信号的条件（保护性退出）
        """
        dataframe.loc[
            (
                # 条件1: 价格强力反弹至EMA通道上轨
                (dataframe['open'] >= dataframe['ema_high'])
            ) |
            (
                # 条件2: 随机指标进入超买区
                (qtpylib.crossed_above(dataframe['fastk'], self.sell_stoch_threshold.value)) |
                (qtpylib.crossed_above(dataframe['fastd'], self.sell_stoch_threshold.value))
            ),
            'exit_long'] = 1
        return dataframe
