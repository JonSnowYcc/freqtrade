# --- 策略总结 ---
# 策略名称: PatternRecognition (K线形态识别)
#
# 盈利逻辑:
# 这是一个用于系统性地发现"哪种K线形态最赚钱"的策略模板。它利用了 `TA-Lib` 库中包含的数十种经典的K线形态识别功能
# (如"锤子线"、"乌云盖顶"等)。
#   - 海量形态计算: 策略在启动时，会遍历 `TA-Lib` 中所有可用的K线形态，并为每一种形态在数据帧中创建一个新列。
#     如果某个K线被识别为该形态，对应的值会被标记为 `100` (看涨形态) 或 `-100` (看跌形态)。
#   - 买入(Entry): 策略的核心逻辑非常简单："当 (某个K线形态) == (某个值) 时买入"。
#     具体是哪种K线形态，以及是顺着它买 (值=100) 还是逆着它买 (值=-100)，完全由超参数优化决定。
#     例如，超参数优化可能会发现"每当出现看涨的锤子线(`CDLHAMMER==100`)时买入"是盈利的；
#     或者，它也可能发现"每当出现看跌形态(`CDLHIGHWAVE==-100`)时买入"(一种反转策略)是盈利的。
#   - 卖出(Exit): 策略中没有主动的卖出逻辑，完全依赖于投资回报率(ROI)、止损或追踪止损来退出交易。
#
# 优点:
#   - 自动化测试: 无需人工回测，可以通过超参数优化自动地、系统性地检验几十种经典K线形态的有效性。
#   - 发现非直觉模式: 除了验证"看涨形态做多"外，还能发现"看跌形态做多"(即反转交易)这种非传统但可能有效的模式。
#   - 逻辑清晰: 策略模板的结构很简单，重点在于超参数的探索。
#
# 缺点:
#   - 过拟合风险: K线形态的有效性有很强的随机性，在历史数据上找到的"最佳"形态很可能在未来失效。
#   - 计算量较大: 在启动时计算所有K线形态会消耗一定的计算资源。
#   - 缺乏上下文: 单纯依赖一个K线形态作为入场信号，忽略了它在整个市场结构 (如趋势、支撑/阻力位) 中所处的位置，这通常是K线分析的关键部分。因此，信号的可靠性可能不高。
#   - 无主动退出机制: 缺少基于形态的退出逻辑，使得策略不够完整。

# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401

# --- 请勿删除这些库 ---
import numpy as np  # noqa
import pandas as pd  # noqa
from pandas import DataFrame

from freqtrade.strategy import (BooleanParameter, CategoricalParameter, DecimalParameter,
                                IStrategy, IntParameter, RealParameter)

# --------------------------------
# 在此导入您的库
import talib
import talib.abstract as ta
import pandas_ta as pta
import freqtrade.vendor.qtpylib.indicators as qtpylib
from technical.util import resample_to_interval, resampled_merge


class PatternRecognition(IStrategy):
    # K线形态识别策略
    # 作者: @Mablue
    # freqtrade hyperopt -s PatternRecognition --hyperopt-loss SharpeHyperOptLossDaily -e 1000
    #
    # 优化结果示例:
    # 173/1000:    510 trades. 408/14/88 Wins/Draws/Losses. Avg profit   2.35%. Median profit   5.60%. Total profit 5421.34509618 USDT ( 542.13%). Avg duration 7 days, 11:54:00 min. Objective: -1.60426

    INTERFACE_VERSION: int = 3
    # 买入超参数空间:
    buy_params = {
        "buy_pr1": "CDLHIGHWAVE",
        "buy_vol1": -100,
    }

    # 投资回报率 (ROI) 表:
    @property
    def minimal_roi(self):
        return {
            "0": self.roi_p1.value,
            "5271": self.roi_p2.value,
            "18147": self.roi_p3.value,
            "48152": 0
        }
    roi_p1 = RealParameter(0.5, 1.2, default=0.936, space='roi', optimize=True)
    roi_p2 = RealParameter(0.2, 0.5, default=0.332, space='roi', optimize=True)
    roi_p3 = RealParameter(0.05, 0.15, default=0.086, space='roi', optimize=True)

    # 止损:
    stoploss = RealParameter(-0.3, -0.2, default=-0.288, space='protection', optimize=True)

    # 追踪止损:
    trailing_stop = BooleanParameter(default=True, space='protection', optimize=True)
    trailing_stop_positive = RealParameter(0.01, 0.05, default=0.032, space='protection', optimize=True)
    trailing_stop_positive_offset = RealParameter(0.05, 0.1, default=0.084, space='protection', optimize=True)
    trailing_only_offset_is_reached = BooleanParameter(default=True, space='protection', optimize=True)

    # 策略的最佳时间框架
    timeframe = '1d'
    # 获取TA-Lib中所有"K线形态识别"类型的函数名称
    prs = talib.get_function_groups()['Pattern Recognition']

    # # 策略参数
    # K线形态名称，可选项为所有prs列表中的形态
    buy_pr1 = CategoricalParameter(prs, default=prs[0], space="buy", optimize=True)
    # 形态的值 (-100代表看跌, 100代表看涨)
    buy_vol1 = CategoricalParameter([-100,100], default=-100, space="buy", optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 遍历并计算TA-Lib中所有可用的K线形态
        for pr in self.prs:
            dataframe[pr] = getattr(ta, pr)(dataframe)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                # 条件: 某个由 `buy_pr1` 指定的K线形态，其值等于 `buy_vol1` (100或-100)
                (dataframe[self.buy_pr1.value]==self.buy_vol1.value)
                # |(dataframe[self.buy_pr2.value]==self.buy_vol2.value) # 可以扩展以包含更多条件
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
                # 卖出逻辑被注释掉了，当前完全依赖ROI和止损
                # (dataframe[self.sell_pr1.value]==self.sell_vol1.value)|
                # (dataframe[self.sell_pr2.value]==self.sell_vol2.value)
            ),
            'exit_long'] = 1

        return dataframe
