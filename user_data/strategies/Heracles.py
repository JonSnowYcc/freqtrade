# --- 策略总结 ---
# 策略名称: Heracles (海格力斯, 大力神)
# 策略类型: 特定模式识别策略 (由自动化发现产生)
#
# 盈利逻辑:
# 该策略是 "GodStra" (上帝策略) 的一个"儿子"，意即它是通过类似 `GodStra` 的自动化、遗传算法式的探索过程后，
# 发现并固化下来的一个具体、有效的交易规则（作者称之为"单基因细菌"）。
# 它不再进行宽泛的搜索，而是执行一个非常具体的任务：
# 1. 计算两个波动率指标: 肯特纳通道宽度 (`volatility_kcw`) 和 唐奇安通道位置 (`volatility_dcp`)。
# 2. 寻找特定模式: 策略的核心买入条件是，计算一个特定比率 `d = (向前偏移N根K线的唐奇安通道位置) / (向前偏移M根K线的肯特纳通道宽度)`。
# 3. 触发买入: 只有当这个比率 `d` 落在一个预设的、极窄的区间内时，才会触发买入信号。
#
# 本质上，该策略是在寻找这两种波动率指标在历史上形成的一种特定的、有利可图的数学形态或"足迹"。
# 策略没有主动的卖出信号，完全依赖于投资回报率(ROI)、止损和追踪止损来退出交易。
#
# 优点:
#   - 规则明确: 策略逻辑被固化下来，简单明了，没有 `GodStra` 那样的复杂性。
#   - 历史验证: 这是一个从海量可能性中筛选出来的、在历史数据上表现优异的特定模式，具有一定的统计学基础。
#
# 缺点:
#   - 过拟合风险依然存在: 虽然是从 `GodStra` 中提炼出来的，但它仍然是一个在历史数据上找到的复杂模式。这种模式在未来市场中可能失效，过拟合风险是其主要风险。
#   - 逻辑难以直观解释: "为何唐奇安通道位置除以肯特纳通道宽度会是一个有效的信号？" 这个问题很难从传统技术分析的角度得到直观解释，使其带有"黑箱"色彩。
#   - 依赖退出机制: 策略本身不决定何时卖出，因此其表现高度依赖于止盈、止损等退出参数的设置。

# Heracles 策略: GodStra 最强的儿子
# (只有一个基因！它是个细菌 :D)
# 作者: @Mablue (Masoud Azizi)
# github: https://github.com/mablue/
# 重要提示: 在 config.json 的 StaticPairList 下添加到您的交易对列表:
#   {
#       "method": "AgeFilter",
#       "min_days_listed": 100
#   },
# 重要提示: 运行前请安装 TA 库 (pip install ta)
#
# freqtrade hyperopt --hyperopt-loss SharpeHyperOptLoss --spaces roi buy --strategy Heracles
# ######################################################################
# --- 请勿删除这些库 ---
from freqtrade.strategy import IntParameter, DecimalParameter, IStrategy, RealParameter
from pandas import DataFrame
# --------------------------------
# 在此导入您需要的库
# import talib.abstract as ta
import pandas as pd
import ta
from ta.utils import dropna
import freqtrade.vendor.qtpylib.indicators as qtpylib
from functools import reduce
import numpy as np
from numpy.lib import math


class Heracles(IStrategy):
    ########################################## 结果粘贴区 ##########################################
    # 10/100:     25 trades. 18/4/3 Wins/Draws/Losses. Avg profit   5.92%. Median profit   6.33%. Total profit  0.04888306 BTC (  48.88Σ%). Avg duration 4 days, 6:24:00 min. Objective: -11.42103

    INTERFACE_VERSION: int = 3
    # 买入超参数空间:
    buy_params = {
        "buy_crossed_indicator_shift": 9,
        "buy_div_max": 0.75,
        "buy_div_min": 0.16,
        "buy_indicator_shift": 15,
    }

    # 卖出超参数空间:
    sell_params = {
    }

    # 投资回报率 (ROI) 表:
    minimal_roi = {
        "0": 0.598,
        "644": 0.166,
        "3269": 0.115,
        "7289": 0
    }
    roi_p1 = RealParameter(0.4, 0.8, default=0.598, space='roi', optimize=True)
    roi_p2 = RealParameter(0.1, 0.3, default=0.166, space='roi', optimize=True)
    roi_p3 = RealParameter(0.05, 0.2, default=0.115, space='roi', optimize=True)

    # 止损:
    stoploss = RealParameter(-0.3, -0.2, default=-0.256, space='protection', optimize=True)

    # 最佳时间框架，请在您的配置中使用
    timeframe = '4h'

    ########################################## 结果粘贴区结束 ######################################

    # 买入参数
    # 区间下限
    buy_div_min = DecimalParameter(0, 1, default=0.16, decimals=2, space='buy')
    # 区间上限
    buy_div_max = DecimalParameter(0, 1, default=0.75, decimals=2, space='buy')
    # 主指标的偏移量
    buy_indicator_shift = IntParameter(0, 20, default=16, space='buy', optimize=True)
    # 交叉指标的偏移量
    buy_crossed_indicator_shift = IntParameter(0, 20, default=9, space='buy', optimize=True)

    # Indicator parameters
    keltner_window = IntParameter(10, 30, default=20, space='buy', optimize=True)
    keltner_atr_window = IntParameter(5, 20, default=10, space='buy', optimize=True)
    donchian_window = IntParameter(5, 20, default=10, space='buy', optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = dropna(dataframe)

        # 计算肯特纳通道宽度 (Keltner Channel Width)
        dataframe['volatility_kcw'] = ta.volatility.keltner_channel_wband(
            dataframe['high'],
            dataframe['low'],
            dataframe['close'],
            window=self.keltner_window.value,
            window_atr=self.keltner_atr_window.value,
            fillna=False,
            original_version=True
        )

        # 计算唐奇安通道位置 (Donchian Channel P-Band)
        dataframe['volatility_dcp'] = ta.volatility.donchian_channel_pband(
            dataframe['high'],
            dataframe['low'],
            dataframe['close'],
            window=self.donchian_window.value,
            offset=0,
            fillna=False
        )

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Hyperopt 将会构建和使用的买入策略。
        """
        conditions = []

        # 定义主指标和交叉指标
        IND = 'volatility_dcp' # 唐奇安通道位置
        CRS = 'volatility_kcw' # 肯特纳通道宽度
        DFIND = dataframe[IND]
        DFCRS = dataframe[CRS]

        # 计算核心比率 d
        # d = (向前偏移N根K线的唐奇安通道位置) / (向前偏移M根K线的肯特纳通道宽度)
        d = DFIND.shift(self.buy_indicator_shift.value).div(
            DFCRS.shift(self.buy_crossed_indicator_shift.value))

        # 核心条件：判断比率 d 是否落在 [buy_div_min, buy_div_max] 区间内
        conditions.append(
            d.between(self.buy_div_min.value, self.buy_div_max.value))

        if conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, conditions),
                'enter_long']=1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Hyperopt 将会构建和使用的卖出策略。
        此策略中，卖出信号被禁用，完全依赖ROI和止损。
        """
        dataframe.loc[:, 'exit_long'] = 0
        return dataframe
