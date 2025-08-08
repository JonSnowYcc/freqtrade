# --- 策略总结 ---
# 策略名称: GodStra (上帝策略)
# 策略类型: 遗传算法 / 自动化策略发现模板
#
# 盈利逻辑:
# 此策略是一个用于"自动发现交易规则"的超高级模板，可以看作是遗传算法在策略生成上的应用。
# 其核心思想是，它不预设任何交易逻辑，而是定义一套可以组合成交易规则的"基因"，然后通过超参数优化来寻找最佳的"基因组合"。
# 1. 海量指标生成: 策略首先使用 `add_all_ta_features` 函数一次性计算出几十种不同类型的技术指标 (趋势、动量、波动率等)，创建一个巨大的信号池。
# 2. "基因"定义规则: 每一条买入或卖出规则由一组"基因" (`buy_params`, `sell_params`) 决定。每个基因包含：
#    - 一个主指标 (`indicator`)
#    - 一个比较操作符 (`oper`)
#    - 一个用于交叉的副指标 (`cross`)
#    - 一个整数 (`int`) 和一个浮点数 (`real`)
# 3. 动态规则生成: 策略会根据 `oper` 的值，将主指标与副指标、整数或浮点数进行比较 (如 `>`, `<`, `交叉`, `等于`等)，动态地生成一条条交易条件。
#
# 最终，通过大量的超参数优化，机器可以自行从海量指标中挑选出最有效的几个，并确定它们之间最佳的数学关系 (是大于、小于还是交叉？)，从而"进化"出一套完整的、有利可图的交易策略。
#
# 优点:
#   - 自动化探索: 真正意义上的自动化策略发现，能够探索人类交易员可能从未想过的复杂规则组合。
#   - 潜力巨大: 理论上可以从数据中发现任何基于技术指标的模式，潜力上限非常高。
#
# 缺点:
#   - 极度复杂的"黑箱": 生成的策略逻辑可能非常复杂且反直觉，几乎无法人工理解和解释，完全是一个黑箱。
#   - 史诗级的过拟合风险: 这是所有自动化策略发现方法面临的最大挑战。由于自由度过高，非常容易找到完美契合历史数据的"虚假"规律，在实盘中迅速失效。
#   - 对算力要求极高: 需要极其庞大的计算资源和非常复杂的超参数优化设置才能有效运行。
#   - 代码可读性差: 代码本身是为了实现这种动态性而编写的，对于不熟悉其设计思想的人来说难以阅读和修改。

# GodStra 策略
# 作者: @Mablue (Masoud Azizi)
# Github: https://github.com/mablue/
# 重要提示: 在 config.json 的 StaticPairList 下添加到您的交易对列表:
#   {
#       "method": "AgeFilter",
#       "min_days_listed": 30
#   },
# 重要提示: 运行前请安装 TA 库 (pip install ta)
# 重要提示: 在 config.json 中使用较小的 "max_open_trades" 以获得最佳结果

# --- 请勿删除这些库 ---
import logging
from functools import reduce

import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy as np
# 在此导入您的库
# import talib.abstract as ta
import pandas as pd
from freqtrade.strategy import IStrategy, RealParameter, BooleanParameter
from numpy.lib import math
from pandas import DataFrame
# import talib.abstract as ta
from ta import add_all_ta_features
from ta.utils import dropna

# --------------------------------

class GodStra(IStrategy):
    # --- 超参数优化结果日志示例 ---
    # 5/66:      9 trades. 8/0/1 Wins/Draws/Losses. Avg profit  21.83%. Median profit  35.52%. Total profit  1060.11476586 USDT ( 196.50Σ%). Avg duration 3440.0 min. Objective: -7.06960
    # +--------+---------+----------+------------------+--------------+-------------------------------+----------------+-------------+
    # |   Best |   Epoch |   Trades |    Win Draw Loss |   Avg profit |                        Profit |   Avg duration |   Objective |
    # |--------+---------+----------+------------------+--------------+-------------------------------+----------------+-------------|
    # | * Best |   1/500 |       11 |      2    1    8 |        5.22% |  280.74230393 USDT   (57.40%) |      2,421.8 m |    -2.85206 |
    # | * Best |   2/500 |       10 |      7    0    3 |       18.76% |  983.46414442 USDT  (187.58%) |        360.0 m |    -4.32665 |
    # | * Best |   5/500 |        9 |      8    0    1 |       21.83% | 1,060.11476586 USDT  (196.50%) |      3,440.0 m |     -7.0696 |

    INTERFACE_VERSION: int = 3
    # 买入超参数空间:
    buy_params = {
        'buy-cross-0': 'volatility_kcc',
        'buy-indicator-0': 'trend_ichimoku_base',
        'buy-int-0': 42,
        'buy-oper-0': '<R',
        'buy-real-0': 0.06295
    }

    # 卖出超参数空间:
    sell_params = {
        'sell-cross-0': 'volume_mfi',
        'sell-indicator-0': 'trend_kst_diff',
        'sell-int-0': 98,
        'sell-oper-0': '=R',
        'sell-real-0': 0.8779
    }

    # 投资回报率 (ROI) 表:
    minimal_roi = {
        "0": 0.3556,
        "4818": 0.21275,
        "6395": 0.09024,
        "22372": 0
    }
    roi_p1 = RealParameter(0.2, 0.5, default=0.3556, space='roi', optimize=True)
    roi_p2 = RealParameter(0.1, 0.3, default=0.21275, space='roi', optimize=True)
    roi_p3 = RealParameter(0.05, 0.15, default=0.09024, space='roi', optimize=True)

    # 止损:
    stoploss = RealParameter(-0.4, -0.3, default=-0.34549, space='protection', optimize=True)

    # 追踪止损:
    trailing_stop = BooleanParameter(default=True, space='protection', optimize=True)
    trailing_stop_positive = RealParameter(0.1, 0.3, default=0.22673, space='protection', optimize=True)
    trailing_stop_positive_offset = RealParameter(0.2, 0.4, default=0.2684, space='protection', optimize=True)
    trailing_only_offset_is_reached = BooleanParameter(default=True, space='protection', optimize=True)
    
    # 时间框架
    timeframe = '12h'
    print('请在您的配置文件(config.json)的 pairlists (StaticPairList下) 添加以下内容:\n{\n\t"method": "AgeFilter",\n\t"min_days_listed": 30\n},')

    def dna_size(self, dct: dict):
        """
        计算"基因"的数量。
        通过提取字典键中的数字来确定有多少组独立的参数。
        例如：{'buy-oper-0': ..., 'buy-oper-1': ...} -> size = 2
        """
        def int_from_str(st: str):
            str_int = ''.join([d for d in st if d.isdigit()])
            if str_int:
                return int(str_int)
            return -1  # 以防参数没有索引
        return len({int_from_str(digit) for digit in dct.keys()})

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 添加所有ta库中的技术指标特征
        dataframe = dropna(dataframe)
        dataframe = add_all_ta_features(
            dataframe, open="open", high="high", low="low", close="close", volume="volume",
            fillna=True) # fillna=True 会用0填充无法计算的指标值
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = list()
        # 遍历所有"基因组"来构建交易条件
        for i in range(self.dna_size(self.buy_params)):
            # 从 buy_params 中获取第 i 组基因
            OPR = self.buy_params[f'buy-oper-{i}']      # 操作符 (>, <, CA, CB, >I, <R, 等)
            IND = self.buy_params[f'buy-indicator-{i}'] # 主指标名称
            CRS = self.buy_params[f'buy-cross-{i}']     # 交叉指标名称
            INT = self.buy_params[f'buy-int-{i}']       # 整数比较值
            REAL = self.buy_params[f'buy-real-{i}']     # 浮点数比较值
            DFIND = dataframe[IND]
            DFCRS = dataframe[CRS]

            # 根据操作符(OPR)动态生成条件
            if OPR == ">":
                conditions.append(DFIND > DFCRS)
            elif OPR == "=":
                conditions.append(np.isclose(DFIND, DFCRS))
            elif OPR == "<":
                conditions.append(DFIND < DFCRS)
            elif OPR == "CA": # Crossed Above
                conditions.append(qtpylib.crossed_above(DFIND, DFCRS))
            elif OPR == "CB": # Crossed Below
                conditions.append(qtpylib.crossed_below(DFIND, DFCRS))
            elif OPR == ">I":
                conditions.append(DFIND > INT)
            elif OPR == "=I":
                conditions.append(DFIND == INT)
            elif OPR == "<I":
                conditions.append(DFIND < INT)
            elif OPR == ">R":
                conditions.append(DFIND > REAL)
            elif OPR == "=R":
                conditions.append(np.isclose(DFIND, REAL))
            elif OPR == "<R":
                conditions.append(DFIND < REAL)

        if conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, conditions),
                'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = list()
        # 遍历所有"基因组"来构建交易条件
        for i in range(self.dna_size(self.sell_params)):
            # 从 sell_params 中获取第 i 组基因
            OPR = self.sell_params[f'sell-oper-{i}']
            IND = self.sell_params[f'sell-indicator-{i}']
            CRS = self.sell_params[f'sell-cross-{i}']
            INT = self.sell_params[f'sell-int-{i}']
            REAL = self.sell_params[f'sell-real-{i}']
            DFIND = dataframe[IND]
            DFCRS = dataframe[CRS]
            
            # 根据操作符(OPR)动态生成条件
            if OPR == ">":
                conditions.append(DFIND > DFCRS)
            elif OPR == "=":
                conditions.append(np.isclose(DFIND, DFCRS))
            elif OPR == "<":
                conditions.append(DFIND < DFCRS)
            elif OPR == "CA":
                conditions.append(qtpylib.crossed_above(DFIND, DFCRS))
            elif OPR == "CB":
                conditions.append(qtpylib.crossed_below(DFIND, DFCRS))
            elif OPR == ">I":
                conditions.append(DFIND > INT)
            elif OPR == "=I":
                conditions.append(DFIND == INT)
            elif OPR == "<I":
                conditions.append(DFIND < INT)
            elif OPR == ">R":
                conditions.append(DFIND > REAL)
            elif OPR == "=R":
                conditions.append(np.isclose(DFIND, REAL))
            elif OPR == "<R":
                conditions.append(DFIND < REAL)
        
        if conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, conditions),
                'exit_long'] = 1

        return dataframe
