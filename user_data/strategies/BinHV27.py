from freqtrade.strategy import IStrategy, IntParameter, RealParameter
from typing import Dict, List
from functools import reduce
from pandas import DataFrame
# --------------------------------

import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy  # noqa


class BinHV27(IStrategy):
    """
    策略名称: BinHV27
    策略作者: BinH
    策略类型: 状态机 / 多维市场判断

    ## 策略核心逻辑

    **警告：这是一个极其复杂的专家级策略，不建议初学者直接使用或修改。其复杂的规则有非常高的过度拟合风险。**

    本策略的核心思想是构建一个复杂的**市场状态机（State Machine）**。它没有使用简单的指标交叉，而是预先计算了大量描述市场状态的**自定义布尔型指标**（True/False），
    然后像搭积木一样，用这些"状态"组合出极其细致的、适用于不同"市场模式"的交易条件。

    ### 1. 自定义"状态"指标

    策略首先定义了一系列用于描述市场宏观状态的变量：
    - `bigup` / `bigdown`: 市场是否处于由120和240周期SMA定义的"大牛市"/"大熊市"？
    - `trend`: "大趋势"的强度（两条长周期SMA的差值）。
    - `preparechangetrend`: "大趋势"是否正在增强？
    - `preparechangetrendconfirm`: 上述状态是否得到"确认"？
    - `continueup`: "终极宏观趋势"（最长的SMA）是否持续向上？
    - `slowingdown`: 短期趋势的动能是否在"放缓"？

    ### 2. 买入逻辑: "在不同市场模式下，寻找特定回调点"

    买入逻辑由一个**通用前置条件**和**四个"或"关系的具体情景**组成。
    - **通用前置条件**: 要求价格处于回调位，卖方动能占优，但短期下跌动能已暂停。
    - **四个具体情景**: 这四个情景是上述各种"状态"指标的复杂排列组合，分别定义了在四种不同的"市场宏观状态组合"下的买入机会。例如：
        - **情景一**: 在"大熊市" + "终极熊市" + "趋势未准备反转"的状态下，如果RSI极度超卖，则买入。
        - **情景四**: 在"大牛市" + "终极牛市"的状态下，如果RSI超卖，则买入。

    ### 3. 卖出逻辑

    卖出逻辑甚至更复杂，包含了**五个"或"关系**的场景，为不同的入场情景匹配了对应的、由各种"状态"组合而成的退出条件。

    ### 总结与评价
    - **优点**: 试图对市场进行多维度、深层次的划分，思想非常精妙。
    - **缺点**:
        - **极度复杂**: 如果不是原作者，几乎不可能理解和维护。
        - **过拟合风险高**: 极有可能是针对特定历史数据的"完美"拟合，在未来市场中表现存疑。
        - **代码问题**: 滥用 `numpy.nan_to_num` 可能掩盖数据或计算的潜在问题。
    """
    INTERFACE_VERSION: int = 3
    minimal_roi = RealParameter(0.1, 1.0, default=0.5, space='roi', optimize=True)
    stoploss = RealParameter(-0.5, -0.1, default=-0.5, space='protection', optimize=True)
    timeframe = '5m'

    # Indicator periods
    rsi_period = IntParameter(3, 15, default=5, space='buy', optimize=True)
    emarsi_period = IntParameter(3, 15, default=5, space='buy', optimize=True)
    adx_period = IntParameter(10, 25, default=14, space='buy', optimize=True)
    minusdiema_period = IntParameter(15, 40, default=25, space='buy', optimize=True)
    plusdiema_period = IntParameter(3, 15, default=5, space='buy', optimize=True)
    lowsma_period = IntParameter(40, 80, default=60, space='buy', optimize=True)
    highsma_period = IntParameter(80, 160, default=120, space='buy', optimize=True)
    fastsma_period = IntParameter(80, 160, default=120, space='buy', optimize=True)
    slowsma_period = IntParameter(160, 300, default=240, space='buy', optimize=True)

    # Logic thresholds
    bigup_divisor = RealParameter(200.0, 400.0, default=300.0, space='buy', optimize=True)
    
    # Entry thresholds
    buy_adx_1 = IntParameter(20, 40, default=25, space='buy', optimize=True)
    buy_adx_2 = IntParameter(25, 45, default=30, space='buy', optimize=True)
    buy_adx_3 = IntParameter(30, 50, default=35, space='buy', optimize=True)
    buy_emarsi_1 = IntParameter(10, 30, default=20, space='buy', optimize=True)
    buy_emarsi_2 = IntParameter(20, 40, default=25, space='buy', optimize=True)

    # Exit thresholds
    sell_emarsi_1 = IntParameter(65, 85, default=75, space='sell', optimize=True)
    sell_emarsi_2 = IntParameter(70, 90, default=80, space='sell', optimize=True)
    sell_adx_1 = IntParameter(25, 45, default=30, space='sell', optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # --- 基础指标 ---
        dataframe['rsi'] = numpy.nan_to_num(ta.RSI(dataframe, timeperiod=self.rsi_period.value))
        rsiframe = DataFrame(dataframe['rsi']).rename(columns={'rsi': 'close'})
        dataframe['emarsi'] = numpy.nan_to_num(ta.EMA(rsiframe, timeperiod=self.emarsi_period.value)) # RSI的EMA平滑
        dataframe['adx'] = numpy.nan_to_num(ta.ADX(dataframe, timeperiod=self.adx_period.value))
        
        # DMI 指标
        dataframe['minusdi'] = numpy.nan_to_num(ta.MINUS_DI(dataframe))
        minusdiframe = DataFrame(dataframe['minusdi']).rename(columns={'minusdi': 'close'})
        dataframe['minusdiema'] = numpy.nan_to_num(ta.EMA(minusdiframe, timeperiod=self.minusdiema_period.value))
        dataframe['plusdi'] = numpy.nan_to_num(ta.PLUS_DI(dataframe))
        plusdiframe = DataFrame(dataframe['plusdi']).rename(columns={'plusdi': 'close'})
        dataframe['plusdiema'] = numpy.nan_to_num(ta.EMA(plusdiframe, timeperiod=self.plusdiema_period.value))
        
        # 多周期均线
        dataframe['lowsma'] = numpy.nan_to_num(ta.EMA(dataframe, timeperiod=self.lowsma_period.value))
        dataframe['highsma'] = numpy.nan_to_num(ta.EMA(dataframe, timeperiod=self.highsma_period.value))
        dataframe['fastsma'] = numpy.nan_to_num(ta.SMA(dataframe, timeperiod=self.fastsma_period.value))
        dataframe['slowsma'] = numpy.nan_to_num(ta.SMA(dataframe, timeperiod=self.slowsma_period.value))

        # --- 自定义状态指标 ---
        # 是否处于"大牛市"
        dataframe['bigup'] = dataframe['fastsma'].gt(dataframe['slowsma']) & ((dataframe['fastsma'] - dataframe['slowsma']) > dataframe['close'] / self.bigup_divisor.value)
        # 是否处于"大熊市"
        dataframe['bigdown'] = ~dataframe['bigup']
        # 大趋势强度
        dataframe['trend'] = dataframe['fastsma'] - dataframe['slowsma']
        # 趋势是否准备改变
        dataframe['preparechangetrend'] = dataframe['trend'].gt(dataframe['trend'].shift())
        # 趋势改变是否被"确认"
        dataframe['preparechangetrendconfirm'] = dataframe['preparechangetrend'] & dataframe['trend'].shift().gt(dataframe['trend'].shift(2))
        # 终极宏观趋势是否向上
        dataframe['continueup'] = dataframe['slowsma'].gt(dataframe['slowsma'].shift()) & dataframe['slowsma'].shift().gt(dataframe['slowsma'].shift(2))
        # 短期趋势动能变化
        dataframe['delta'] = dataframe['fastsma'] - dataframe['fastsma'].shift()
        # 短期趋势是否在放缓
        dataframe['slowingdown'] = dataframe['delta'].lt(dataframe['delta'].shift())
        
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            # --- 通用前置条件 ---
            dataframe['slowsma'].gt(0) &
            (dataframe['close'] < dataframe['highsma']) & # 价格回调
            (dataframe['close'] < dataframe['lowsma']) &
            (dataframe['minusdi'] > dataframe['minusdiema']) & # 卖方动能占优
            (dataframe['rsi'].ge(dataframe['rsi'].shift())) & # 但短期下跌动能暂停
            
            # --- 四个"或"关系的买入情景 ---
            (
              # 情景1: 大熊市 + 终极熊市 + 趋势未变 -> 极度超卖时买入
              (
                ~dataframe['preparechangetrend'] &
                ~dataframe['continueup'] &
                dataframe['adx'].gt(self.buy_adx_1.value) &
                dataframe['bigdown'] &
                dataframe['emarsi'].le(self.buy_emarsi_1.value)
              ) |
              # 情景2: 大熊市 + 终极牛市 + 趋势未变 -> 极度超卖时买入
              (
                ~dataframe['preparechangetrend'] &
                dataframe['continueup'] &
                dataframe['adx'].gt(self.buy_adx_2.value) &
                dataframe['bigdown'] &
                dataframe['emarsi'].le(self.buy_emarsi_1.value)
              ) |
              # 情景3: 大牛市 + 终极熊市 -> 极度超卖时买入
              (
                ~dataframe['continueup'] &
                dataframe['adx'].gt(self.buy_adx_3.value) &
                dataframe['bigup'] &
                dataframe['emarsi'].le(self.buy_emarsi_1.value)
              ) |
              # 情景4: 大牛市 + 终极牛市 -> 超卖时买入 (最理想情况)
              (
                dataframe['continueup'] &
                dataframe['adx'].gt(self.buy_adx_2.value) &
                dataframe['bigup'] &
                dataframe['emarsi'].le(self.buy_emarsi_2.value)
              )
            ),
            'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
              # --- 五个"或"关系的卖出情景 ---
              # 情景1: 熊市中，价格反弹至均线
              (
                ~dataframe['preparechangetrendconfirm'] &
                ~dataframe['continueup'] &
                (dataframe['close'].gt(dataframe['lowsma']) | dataframe['close'].gt(dataframe['highsma'])) &
                dataframe['highsma'].gt(0) &
                dataframe['bigdown']
              ) |
              # 情景2: 熊市中，价格反弹至更高均线或RSI超买
              (
                ~dataframe['preparechangetrendconfirm'] &
                ~dataframe['continueup'] &
                dataframe['close'].gt(dataframe['highsma']) &
                dataframe['highsma'].gt(0) &
                (dataframe['emarsi'].ge(self.sell_emarsi_1.value) | dataframe['close'].gt(dataframe['slowsma'])) &
                dataframe['bigdown']
              ) |
              # 情景3: 牛市中，RSI极度超买
              (
                ~dataframe['preparechangetrendconfirm'] &
                dataframe['close'].gt(dataframe['highsma']) &
                dataframe['highsma'].gt(0) &
                dataframe['adx'].gt(self.sell_adx_1.value) &
                dataframe['emarsi'].ge(self.sell_emarsi_2.value) &
                dataframe['bigup']
              ) |
              # 情景4: 趋势确认改变 + 终极熊市 + 动能放缓 + RSI超买
              (
                dataframe['preparechangetrendconfirm'] &
                ~dataframe['continueup'] &
                dataframe['slowingdown'] &
                dataframe['emarsi'].ge(self.sell_emarsi_1.value) &
                dataframe['slowsma'].gt(0)
              ) |
              # 情景5: 趋势确认改变 + 价格反弹
              (
                dataframe['preparechangetrendconfirm'] &
                dataframe['minusdi'].lt(dataframe['plusdi']) &
                dataframe['close'].gt(dataframe['lowsma']) &
                dataframe['slowsma'].gt(0)
              )
            ),
            'exit_long'] = 1
        return dataframe
