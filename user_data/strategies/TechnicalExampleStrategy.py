# --- Do not remove these libs ---
from pandas import DataFrame
from technical.indicators import cmf
from freqtrade.strategy import IStrategy, IntParameter, RealParameter
# --------------------------------
# Add your lib to import here
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib


#
# /r/CryptoCurrency/comments/5cya29/a_simple_trading_strategy_that_made_me_a_ton_of/
#
#
class TechnicalExampleStrategy(IStrategy):
    """
    策略名称: TechnicalExampleStrategy (技术指标示例策略)
    策略作者: freqtrade
    策略类型: 均值回归 (Mean Reversion)
    官方Repo: https://github.com/freqtrade/freqtrade-strategies

    ## 策略核心逻辑

    该策略完全基于蔡金资金流（Chaikin Money Flow, CMF）指标，执行逆向操作。

    ### 盈利逻辑

    CMF 指标衡量指定周期内的资金流入和流出情况。
    - 当 CMF > 0 时，表明市场处于买方主导（资金流入）的状态。
    - 当 CMF < 0 时，表明市场处于卖方主导（资金流出）的状态。

    本策略反其道而行之：
    - **买入**: 当 CMF < 0 时，即市场出现资金流出、价格可能处于低位时，策略进行买入。这是一种典型的"抄底"行为，押注于市场即将从卖压中反转回升。
    - **卖出**: 当 CMF > 0 时，即市场转为资金流入、价格可能已经上涨时，策略进行卖出。这可以理解为"见好就收"，在市场情绪变得乐观时离场。

    ### 优点

    - 逻辑极其简单，只有一个指标，非常容易理解，是学习如何构建策略的绝佳范例。
    - 在价格围绕某个中心反复波动的"震荡市"中，这种逆向操作可能会有较好的表现。

    ### 缺点

    - **逆势交易风险高**: 在强劲的单边趋势行情中（如暴涨或暴跌），该策略会持续亏损。例如，在长期下跌趋势中，CMF会长时间小于0，导致策略过早接盘并不断止损。
    - **信号单一**: 只依赖CMF一个指标，信号较为脆弱，容易受到市场噪音干扰而产生大量假信号。
    """
    INTERFACE_VERSION: int = 3
    # ROI table:
    minimal_roi = RealParameter(0.005, 0.05, default=0.01, space='roi', optimize=True)

    # Stoploss:
    stoploss = RealParameter(-0.10, -0.03, default=-0.05, space='protection', optimize=True)

    # Optimal timeframe for the strategy
    timeframe = '5m'

    # Indicator parameters
    cmf_period = IntParameter(15, 30, default=21, space='buy', optimize=True)

    # Logic thresholds
    buy_cmf_threshold = RealParameter(-0.1, 0.0, default=0.0, space='buy', optimize=True)
    sell_cmf_threshold = RealParameter(0.0, 0.1, default=0.0, space='sell', optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        计算策略所需的技术指标。
        :param dataframe: exchange提供的数据帧
        :param metadata: 包含交易对信息的字典
        :return: 带有指标列的数据帧
        """
        # 计算蔡金资金流（Chaikin Money Flow, CMF）
        # CMF结合了价格和成交量，衡量21周期内的资金流入和流出强度。
        dataframe['cmf'] = cmf(dataframe, self.cmf_period.value)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        根据指标数据，生成买入信号。
        :param dataframe: 带有指标的数据帧
        :param metadata: 包含交易对信息的字典
        :return: 带有买入信号的数据帧
        """
        dataframe.loc[
            (
                # 信号：CMF指标值小于阈值
                # 解释：当资金流为负，市场处于卖方主导时，逆势买入，押注反弹。
                (dataframe['cmf'] < self.buy_cmf_threshold.value)
            ),
            'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        根据指标数据，生成卖出信号。
        :param dataframe: 带有指标的数据帧
        :param metadata: 包含交易对信息的字典
        :return: 带有卖出信号的数据帧
        """
        dataframe.loc[
            (
                # 信号：CMF指标值大于阈值
                # 解释：当资金流转为正，市场情绪变得乐观时，卖出平仓。
                (dataframe['cmf'] > self.sell_cmf_threshold.value)
            ),
            'exit_long'] = 1
        return dataframe
