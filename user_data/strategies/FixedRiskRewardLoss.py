# --- 策略总结 ---
# 策略名称: FixedRiskRewardLoss (固定风险回报比)
# 策略类型: 示例/模板代码
#
# 核心功能 (盈利逻辑):
# 这是一个高级的示例策略，旨在演示如何在 `custom_stoploss` 中实现一个复杂的多阶段风险管理系统，
# 以强制执行一个固定的风险回报比 (Risk/Reward Ratio)。
# 其核心逻辑如下：
# 1. 动态初始止损: 在入场时，策略使用ATR指标（平均真实波幅）来计算一个动态的初始止损位 (例如：收盘价 - 2*ATR)。
#    这个止损位反映了当时市场的波动性。这个初始止损决定了这笔交易的"初始风险单位"。
# 2. 设置止盈目标: 根据预设的风险回报比（如 3.5:1），计算出止盈价格 (`止盈价格 = 开仓价格 + 初始风险单位 * 3.5`)。
# 3. 多阶段止损管理:
#    - 阶段一 (初始): 止损位维持在初始的ATR位置。
#    - 阶段二 (保本): 当利润达到某个阈值时 (例如，当利润等于1倍的初始风险单位时)，止损位被移动到开仓成本价 (盈亏平衡点)，确保此交易不会亏损。
#    - 阶段三 (止盈): 当利润达到预设的止盈目标时，止损位被上移到止盈价格，从而锁定利润，并在下一个价格tick时完成平仓。
# 该策略的买入信号仅为占位符，目的是为了演示上述止损逻辑。
#
# 优点:
#   - 纪律性强: 严格执行风险回报比，避免了情绪化交易，是系统化交易的核心思想。
#   - 动态风险评估: 使用ATR来设定初始止损，比固定的百分比止损更能适应市场波动性的变化。
#   - 结构清晰: 是一个绝佳的学习范本，展示了如何在Freqtrade中实现复杂的、分阶段的追踪止损和风险管理。
#
# 缺点:
#   - 不完整的策略: 这是一个功能"组件"，其买入逻辑 (`Always buys`) 毫无意义，不能直接用于实盘交易。必须将其风险管理逻辑集成到用户自己的有效入场策略中。
#   - 依赖二次开发: 需要用户深刻理解其逻辑，并将其与自己的策略相结合。

# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# isort: skip_file
# --- 请勿删除这些库 ---
import numpy as np  # noqa
import pandas as pd  # noqa
from pandas import DataFrame

from freqtrade.strategy import IStrategy, RealParameter, IntParameter

# --------------------------------
# 在此导入您需要的库
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
from datetime import datetime
from freqtrade.persistence import Trade

import logging
logger = logging.getLogger(__name__)

class FixedRiskRewardLoss(IStrategy):
    """
    该策略使用 custom_stoploss() 来强制执行一个固定的风险/回报比。
    它首先通过 ATR 计算出一个动态的初始止损位。

    之后，我们计算出这个初始风险，并将其乘以一个 risk_reward_ratio (风险回报比)。
    一旦价格达到这个目标，止损位就会被设置到该位置，并发出卖出信号。

    此外，还有一个盈亏平衡比率。一旦达到这个比率，止损位将被调整到开仓价+手续费，以最小化损失。
    """

    INTERFACE_VERSION: int = 3

    # --- 可优化的风险管理参数 ---
    # 风险回报比
    risk_reward_ratio = RealParameter(1.0, 5.0, default=3.5, space='sell', optimize=True)
    # 当利润达到 N 倍初始风险时，移动止损至盈亏平衡点
    set_to_break_even_at_profit = RealParameter(0.5, 2.0, default=1.0, space='sell', optimize=True)
    
    # --- 指标参数 ---
    atr_period = IntParameter(10, 20, default=14, space='buy', optimize=True)
    atr_multiplier = RealParameter(1.0, 4.0, default=2.0, space='buy', optimize=True)

    # 启用自定义止损
    use_custom_stoploss = True
    # 设置一个非常大的初始止损，以确保自定义止损逻辑优先执行
    stoploss = RealParameter(-0.99, -0.5, default=-0.9, space='protection', optimize=True)

    def custom_stoploss(self, pair: str, trade: 'Trade', current_time: datetime,
                        current_rate: float, current_profit: float, **kwargs) -> float:
        """
        使用风险/回报比的自定义止损逻辑。
        """
        # 设置默认返回值，-1意味着不更新当前止损
        result = break_even_sl = takeprofit_sl = -1
        custom_info_pair = self.custom_info.get(pair)
        if custom_info_pair is not None:
            # 在实时/模拟交易中，我们必须搜索交易开仓时间之前的最近一行数据
            open_date_mask = custom_info_pair.index.unique().get_loc(trade.open_date_utc, method='ffill')
            open_df = custom_info_pair.iloc[open_date_mask]

            # 如果交易开仓时间太长，可能找不到对应的开仓K线
            if(len(open_df) != 1):
                return -1 # 不更新当前止损

            # 1. 获取这笔交易在开仓时的初始止损价 (绝对价格)
            initial_sl_abs = open_df['stoploss_rate']

            # 2. 计算初始止损相对于当前价格的百分比
            initial_sl = initial_sl_abs/current_rate-1

            # --- 计算止盈目标 ---
            # 3. 计算初始风险距离 (开仓价 - 初始止损价)
            risk_distance = trade.open_rate-initial_sl_abs
            # 4. 根据风险回报比计算盈利距离
            reward_distance = risk_distance*self.risk_reward_ratio.value
            # 5. 计算绝对的止盈价格
            take_profit_price_abs = trade.open_rate+reward_distance
            # 6. 计算触发止盈的利润百分比
            take_profit_pct = take_profit_price_abs/trade.open_rate-1

            # --- 计算盈亏平衡目标 ---
            # 7. 计算触发盈亏平衡的盈利距离
            break_even_profit_distance = risk_distance*self.set_to_break_even_at_profit.value
            # 8. 计算触发盈亏平衡的利润百分比
            break_even_profit_pct = (break_even_profit_distance+trade.open_rate)/trade.open_rate-1

            # --- 应用多阶段止损逻辑 ---
            # 默认情况下，使用初始ATR止损
            result = initial_sl
            # 如果当前利润已经达到"盈亏平衡"触发点
            if(current_profit >= break_even_profit_pct):
                # 计算盈亏平衡点的止损位 (开仓价 + 双边手续费)
                break_even_sl = (trade.open_rate*(1+trade.fee_open+trade.fee_close) / current_rate)-1
                result = break_even_sl

            # 如果当前利润已经达到"止盈"触发点
            if(current_profit >= take_profit_pct):
                # 计算止盈点的止损位
                takeprofit_sl = take_profit_price_abs/current_rate-1
                result = takeprofit_sl

        return result

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe['atr'] = ta.ATR(dataframe, timeperiod=self.atr_period.value)
        # 计算基于ATR的动态止损价格
        dataframe['stoploss_rate'] = dataframe['close']-(dataframe['atr']*self.atr_multiplier.value)
        # 缓存止损价格数据以供 custom_stoploss 使用
        if not hasattr(self, 'custom_info_pair'):
             self.custom_info_pair = {}
        self.custom_info_pair[metadata['pair']] = dataframe[['date', 'stoploss_rate']].copy().set_index('date')

        # 所有"普通"指标可以放在这里:
        # e.g.
        # dataframe['rsi'] = ta.RSI(dataframe)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        占位策略：总是买入，以演示止损逻辑。
        """
        # 总是买入
        dataframe.loc[:, 'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        占位策略：从不卖出，让自定义止损处理一切。
        """
        # 从不卖出
        dataframe.loc[:, 'exit_long'] = 0
        return dataframe
