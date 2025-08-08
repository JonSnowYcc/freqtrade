# --- 策略总结 ---
# 策略名称: ADX 动量策略 (ADXMomentum)
#
# 盈利逻辑:
# 该策略结合了趋势强度和动量指标来寻找买入点。
# 它首先使用 ADX 指标判断当前是否存在足够强的趋势 (ADX > 25)。
# 在确认趋势存在后，它利用动量指标 (MOM > 0) 和 DMI 指标（+DI > -DI 且 +DI 高于一个阈值）来寻找上升动量强劲的精确入场时机。
# 策略的离场逻辑是，当趋势可能过度延伸（ADX > 43）且动量反转（MOM < 0, +DI < -DI）时卖出。
# 同时，该策略也设置了预定的盈利目标（ROI）和固定的止损。
#
# 优点:
#   - 多重指标确认，提高了信号的可靠性，避免在无趋势的市场中频繁交易。
#   - 结合了趋势和动量，试图在趋势形成的早期或中期进入，以捕捉一段价格上涨。
#   - 有明确的止盈和止损设置，有助于风险管理。
#
# 缺点:
#   - 参数是针对 '5m' 时间周期优化的，在其他时间周期上可能表现不佳。
#   - 在剧烈震荡的市场中，ADX 和 DMI 信号可能会滞后或产生误导，导致亏损。
#   - 固定的参数（如 `adx > 25`）可能无法适应所有市场状况。
#   - SAR 指标被计算但并未使用，属于冗余代码。
#
# --- 请勿删除这些库 ---
from freqtrade.strategy import IStrategy, IntParameter, RealParameter
from pandas import DataFrame
import talib.abstract as ta
# --- 库引用结束 ---


class ADXMomentum(IStrategy):
    """
    作者@: Gert Wohlgemuth
    转换自:
        https://github.com/sthewissen/Mynt/blob/master/src/Mynt.Core/Strategies/AdxMomentum.cs
    """
    INTERFACE_VERSION: int = 3

    # 通过 hyperopt 找到的优化参数
    
    # ROI table:
    roi_p1 = RealParameter(0.1, 0.2, default=0.143, space='roi', optimize=True)
    roi_p2 = RealParameter(0.05, 0.15, default=0.093, space='roi', optimize=True)
    roi_p3 = RealParameter(0.01, 0.05, default=0.032, space='roi', optimize=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.minimal_roi = {
            "0": self.roi_p1.value,
            "30": self.roi_p2.value,
            "51": self.roi_p3.value,
            "115": 0
        }

    # 止损:
    stoploss = RealParameter(-0.15, -0.05, default=-0.101, space='protection', optimize=True)

    # 策略的最佳时间框架。
    # 注意：这是针对 '5m' 时间周期优化的。
    timeframe = '5m'

    # 策略产生有效信号前需要的最少蜡烛图数量
    startup_candle_count: int = 48

    # Indicator periods
    adx_period = IntParameter(20, 35, default=25, space='buy', optimize=True)
    di_period = IntParameter(40, 60, default=48, space='buy', optimize=True)
    mom_period = IntParameter(25, 45, default=32, space='buy', optimize=True)
    sar_acceleration = RealParameter(0.01, 0.05, default=0.02, space='buy', optimize=True)
    sar_maximum = RealParameter(0.1, 0.3, default=0.2, space='buy', optimize=True)
    
    # Logic thresholds
    buy_adx_threshold = IntParameter(20, 35, default=25, space='buy', optimize=True)
    buy_plus_di_threshold = IntParameter(40, 60, default=50, space='buy', optimize=True)
    
    sell_adx_threshold = IntParameter(40, 55, default=43, space='sell', optimize=True)
    sell_minus_di_threshold = IntParameter(20, 35, default=26, space='sell', optimize=True)


    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        计算策略所需的技术指标
        """
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=self.adx_period.value)
        dataframe['plus_di'] = ta.PLUS_DI(dataframe, timeperiod=self.di_period.value)
        dataframe['minus_di'] = ta.MINUS_DI(dataframe, timeperiod=self.di_period.value)
        dataframe['sar'] = ta.SAR(dataframe, acceleration=self.sar_acceleration.value, maximum=self.sar_maximum.value)
        dataframe['mom'] = ta.MOM(dataframe, timeperiod=self.mom_period.value)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义买入信号的逻辑
        """
        dataframe.loc[
            (
                    (dataframe['adx'] > self.buy_adx_threshold.value) &  # 趋势强度足够
                    (dataframe['mom'] > 0) &  # 存在向上动量
                    (dataframe['plus_di'] > self.buy_plus_di_threshold.value) &  # 强烈的上升趋势信号
                    (dataframe['plus_di'] > dataframe['minus_di'])  # 确认上升趋势方向
            ),
            'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义卖出信号的逻辑
        """
        dataframe.loc[
            (
                    (dataframe['adx'] > self.sell_adx_threshold.value) &  # 趋势可能过热或衰竭
                    (dataframe['mom'] < 0) &  # 出现向下动量
                    (dataframe['minus_di'] > self.sell_minus_di_threshold.value) &  # 出现一定的下降压力
                    (dataframe['plus_di'] < dataframe['minus_di'])  # 确认下降趋势
            ),
            'exit_long'] = 1
        return dataframe
