# --- Do not remove these libs ---
from freqtrade.strategy import IStrategy, IntParameter, RealParameter
from typing import Dict, List
from functools import reduce
from pandas import DataFrame
# --------------------------------
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy  # noqa


class SmoothScalp(IStrategy):
    """
    策略名称: SmoothScalp (平滑剥头皮)
    策略作者: 未知
    策略类型: 剥头皮 / 共振抄底
    官方Repo: https://github.com/freqtrade/freqtrade-strategies/blob/main/user_data/strategies/berlinguyinca/SmoothScalp.py

    ## 策略核心逻辑

    这是一个专为1分钟等超短周期设计的"剥头皮"策略。其核心思想是通过寻找多个技术指标同时发出的"超跌"信号作为买入点（指标共振），
    然后在价格小幅反弹后快速卖出，积少成多。策略建议同时运行大量交易对（如60个）以分散风险。

    ### 盈利逻辑: "共振抄底"

    策略的买入条件非常苛刻，要求以下五个条件**同时满足**，形成强烈的看涨共振信号：

    1.  **价格超跌**: `开盘价 < 5周期EMA最低价` - K线开盘价直接低于近期K线低点的移动平均线，表明价格出现了急跌。
    2.  **趋势确认**: `ADX > 30` - ADX指标显示当前市场处于趋势行情中（无论是上涨还是下跌），而非盘整。策略旨在"在趋势中抓回调"，而不是在无趋势市场中交易。
    3.  **资金超卖**: `MFI < 30` - 资金流量指标显示市场处于超卖状态。
    4.  **动能反转**: `随机指标(Stoch)金叉` - 快速随机指标(Stoch)在30下方的超卖区形成"金叉"（快线上穿慢线），这是经典的动能反转信号。
    5.  **情绪超卖**: `CCI < -150` - CCI指标显示市场情绪极度悲观，处于深度超卖区域。

    ### 卖出逻辑

    卖出条件同样是复合的，要求CCI进入超买区，并且满足另外两个条件之一：
    - `CCI > 150` **并且** (`价格大幅反弹` **或者** `随机指标进入超买区`)

    ### 优点
    - 多指标共振可以有效过滤掉大量市场噪音，提高信号的胜率。
    - 剥头皮策略在特定市场环境下可以获得稳定收益。

    ### 缺点
    - 对交易滑点、手续费非常敏感，微小的成本差异可能导致策略从盈利变为亏损。
    - 1分钟周期信号频繁，容易产生过多交易，增加交易成本和风险。
    - **止损设置疑问**: 策略中设置了`stoploss = -0.5` (即-50%)，这对于一个旨在微利的剥头皮策略来说非常不合逻辑，可能是一个笔误或需要通过超参数优化来寻找一个更合理的值（如 -3%）。
    """

    INTERFACE_VERSION: int = 3
    # 最小盈利预期.
    minimal_roi = RealParameter(0.005, 0.03, default=0.01, space='roi', optimize=True)
    # 策略的优化止损位
    # 注意：-0.5 (-50%)对于剥头皮策略来说风险极高，建议调整
    stoploss = RealParameter(-0.10, -0.02, default=-0.05, space='protection', optimize=True)
    
    # 策略的最佳时间周期
    # 越短越好
    timeframe = '1m'

    # --- 超参数定义 ---
    # 买入参数
    buy_adx = IntParameter(20, 50, default=30, space='buy', optimize=True)
    buy_mfi = IntParameter(15, 45, default=30, space='buy', optimize=True)
    buy_stoch_threshold = IntParameter(15, 45, default=30, space='buy', optimize=True)
    buy_cci = IntParameter(-200, -100, default=-150, space='buy', optimize=True)

    # 卖出参数
    sell_cci = IntParameter(100, 200, default=150, space='sell', optimize=True)
    sell_stoch_threshold = IntParameter(60, 90, default=70, space='sell', optimize=True)

    # 指标周期参数
    ema_period = IntParameter(3, 15, default=5, space='buy', optimize=True)
    stoch_k_period = IntParameter(3, 10, default=5, space='buy', optimize=True)
    stoch_d_period = IntParameter(2, 7, default=3, space='buy', optimize=True)
    adx_period = IntParameter(10, 25, default=14, space='buy', optimize=True)
    cci_period = IntParameter(15, 30, default=20, space='buy', optimize=True)
    mfi_period = IntParameter(10, 25, default=14, space='buy', optimize=True)
    rsi_period = IntParameter(10, 25, default=14, space='buy', optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        计算所有策略所需的技术指标
        """
        # EMA 指数移动平均线，构成一个动态通道
        dataframe['ema_high'] = ta.EMA(dataframe, timeperiod=self.ema_period.value, price='high')
        dataframe['ema_close'] = ta.EMA(dataframe, timeperiod=self.ema_period.value, price='close')
        dataframe['ema_low'] = ta.EMA(dataframe, timeperiod=self.ema_period.value, price='low')
        
        # StochF - 快速随机指标
        stoch_fast = ta.STOCHF(dataframe,
                             fastk_period=self.stoch_k_period.value,
                             fastd_period=self.stoch_d_period.value,
                             fastd_matype=0)
        dataframe['fastd'] = stoch_fast['fastd']
        dataframe['fastk'] = stoch_fast['fastk']
        
        # ADX - 平均趋向指数，衡量趋势强度
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=self.adx_period.value)
        
        # CCI - 商品通道指标，衡量价格与统计平均值的偏离
        dataframe['cci'] = ta.CCI(dataframe, timeperiod=self.cci_period.value)
        
        # RSI - 相对强弱指数
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=self.rsi_period.value)
        
        # MFI - 资金流量指标，成交量加权的RSI
        dataframe['mfi'] = ta.MFI(dataframe, timeperiod=self.mfi_period.value)

        # --- 以下为绘图所需指标，不参与策略逻辑 ---
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
        定义买入信号的条件
        """
        dataframe.loc[
            (
                # --- 五个条件必须全部满足 (共振) ---
                # 1. 价格急跌，开盘价低于EMA通道下轨
                (dataframe['open'] < dataframe['ema_low']) &
                # 2. 市场处于趋势行情中
                (dataframe['adx'] > self.buy_adx.value) &
                # 3. 资金流量指标显示超卖
                (dataframe['mfi'] < self.buy_mfi.value) &
                # 4. 随机指标在超卖区形成金叉 (动能反转)
                (
                    (dataframe['fastk'] < self.buy_stoch_threshold.value) &
                    (dataframe['fastd'] < self.buy_stoch_threshold.value) &
                    (qtpylib.crossed_above(dataframe['fastk'], dataframe['fastd']))
                ) &
                # 5. CCI指标显示极度超卖
                (dataframe['cci'] < self.buy_cci.value)
            ),
            'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义卖出信号的条件
        """
        dataframe.loc[
            (
                # 主条件：CCI必须显示超买
                (dataframe['cci'] > self.sell_cci.value) &
                (
                    # 附加条件1：价格大幅反弹，开盘价高于EMA通道上轨
                    (dataframe['open'] >= dataframe['ema_high']) |
                    # 附加条件2：随机指标进入超买区
                    (
                        (qtpylib.crossed_above(dataframe['fastk'], self.sell_stoch_threshold.value)) |
                        (qtpylib.crossed_above(dataframe['fastd'], self.sell_stoch_threshold.value))
                    )
                )
            ),
            'exit_long'] = 1
        return dataframe
