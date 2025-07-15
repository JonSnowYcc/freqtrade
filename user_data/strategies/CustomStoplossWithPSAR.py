# --- 策略总结 ---
# 策略名称: CustomStoplossWithPSAR (使用PSAR自定义止损)
# 策略类型: 示例/模板代码
#
# 核心功能 (盈利逻辑):
# 该策略是一个示例，旨在演示如何使用抛物线转向指标 (Parabolic SAR, PSAR) 来实现一个动态的追踪止损。
# 它本身并非一个完整的、可用于实盘的交易策略。
# 其核心逻辑位于 `custom_stoploss` 函数中：它会持续地将止损位更新为最新的 PSAR 指标值。
# 当价格上涨时，PSAR 的值也会随之阶梯式上涨，从而形成一个追踪止损，以保护利润。
# 策略的平仓完全依赖于这个动态的 PSAR 止损位，而没有独立的卖出信号。
# 其内置的买入信号非常简单 (当前PSAR小于前一个PSAR值)，仅为示例目的而存在，并不稳健。
#
# 优点:
#   - 动态止损: 使用 PSAR 作为追踪止损，可以在行情顺利时让利润奔跑，同时在行情反转时及时止损/止盈，是一种有效的风险管理技术。
#   - 代码清晰: 很好地演示了在 Freqtrade 中实现自定义止损的方法，是学习和开发的好例子。
#
# 缺点:
#   - 不完整的策略: 它是一个功能"组件"而非完整策略。它没有可靠的入场和离场逻辑，不能直接用于交易。
#   - PSAR的固有缺陷: PSAR 在趋势明显的市场中效果很好，但在震荡市中，它会过于频繁地贴近价格，导致止损被过早触发。
#   - 依赖用户二次开发: 必须将此处的 `custom_stoploss` 逻辑整合到用户自己的策略中才能发挥作用。

# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# isort: skip_file
# --- 请勿删除这些库 ---
import numpy as np  # noqa
import pandas as pd  # noqa
from pandas import DataFrame

from freqtrade.strategy import IStrategy, RealParameter

# --------------------------------
# 在此导入您需要的库
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
from datetime import datetime
from freqtrade.persistence import Trade


class CustomStoplossWithPSAR(IStrategy):
    """
    这是一个示例类，实现了一个基于 PSAR 的追踪止损。
    您应该提取 `custom_stoploss()` 和 `populate_indicators()` 部分，
    并将其应用到您自己的策略中。

    populate_entry_trend() 函数中的逻辑是非常随意的，仅作示例。
    """
    INTERFACE_VERSION: int = 3
    timeframe = '1h'
    # 初始的固定止损，如果自定义止损逻辑未生效，则使用此值
    stoploss = RealParameter(-0.25, -0.15, default=-0.2, space='protection', optimize=True)
    
    # 启用自定义止损功能
    use_custom_stoploss = True

    startup_candle_count = 199

    # Indicator parameters
    sar_acceleration = RealParameter(0.01, 0.05, default=0.02, space='buy', optimize=True)
    sar_maximum = RealParameter(0.1, 0.3, default=0.2, space='buy', optimize=True)

    custom_info = {}

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:
        """
        自定义止损逻辑，此处使用 PSAR 作为追踪止损。
        返回值必须是一个负数，代表与当前价格的相对偏移量。
        例如: 返回 -0.05 代表止损位在当前价格下方 5%。
        """
        # 默认返回1，意味着禁用自定义止损（不设置任何止损位）
        result = 1
        if self.custom_info and pair in self.custom_info and trade:
            # 直接使用 current_time (如下所示) 仅在回测/超优中有效。
            # 在实时/模拟交易中，它将是真正的当前时间。
            relative_sl = None
            if self.dp:
                # 所以我们需要从 self.dp 获取分析后的数据帧(analyzed_dataframe)
                dataframe, _ = self.dp.get_analyzed_dataframe(pair=pair, timeframe=self.timeframe)
                # 仅在回调方法中使用 .iat[-1]，绝不在 "populate_*" 方法中使用。
                # 参见: https://www.freqtrade.io/en/latest/strategy-customization/#common-mistakes-when-developing-strategies
                last_candle = dataframe.iloc[-1].squeeze()
                # 获取最后一根K线的SAR值作为止损位
                relative_sl = last_candle['sar']

            if (relative_sl is not None):
                # 计算相对于当前价格的新的止损价
                # (当前价格 - SAR值) / 当前价格
                new_stoploss = (current_rate - relative_sl) / current_rate
                # 将其转换为 `custom_stoploss` 要求的负相对偏移量
                # 注意：官方要求返回一个负值。这里的实现方式 `new_stoploss - 1` 是一个技巧，
                # 当 relative_sl (即SAR) 低于 current_rate 时，new_stoploss < 1, 结果为负数。
                # 这等价于 `-(1 - new_stoploss)` 或 `-( (current_rate - (current_rate-new_stoploss*current_rate)) / current_rate )`
                # 最终结果是 `-(relative_sl / current_rate)` (这行是注释者的理解，原文代码是 new_stoploss - 1)
                # 简单来说，就是设置止损在 sar 点位。
                result = new_stoploss - 1

        return result

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['sar'] = ta.SAR(dataframe, acceleration=self.sar_acceleration.value, maximum=self.sar_maximum.value)
        # 在回测或超优模式下，缓存SAR数据以供 custom_stoploss 使用
        if self.dp.runmode.value in ('backtest', 'hyperopt'):
            if not hasattr(self, 'custom_info'):
                self.custom_info = {}
            self.custom_info[metadata['pair']] = dataframe[['date', 'sar']].copy().set_index('date')

        # 所有"普通"指标可以放在这里:
        # 例如:
        # dataframe['rsi'] = ta.RSI(dataframe)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        占位策略：当SAR值小于前一根K线的SAR值时买入。
        这是一个纯粹为了演示的逻辑。
        :param dataframe: DataFrame
        :return: DataFrame with buy column
        """
        dataframe.loc[
            (
                (dataframe['sar'] < dataframe['sar'].shift())
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        占位策略：什么也不做。
        让自定义止损来处理所有平仓操作。
        :param dataframe: DataFrame
        :return: DataFrame with buy column
        """
        # 停用常规的卖出信号，以允许自定义止损正常工作
        dataframe.loc[:, 'exit_long'] = 0
        return dataframe
