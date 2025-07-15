# --- 策略总结 ---
# 策略名称: BreakEven (盈亏平衡清仓)
# 策略类型: 工具型/管理型策略
#
# 核心功能:
# 此策略并非一个常规的交易策略，而是一个用于平仓管理的工具。它不产生任何买入信号。
# 其核心功能是通过 `minimal_roi` (最小投资回报率) 设置来清空所有持仓。
# 默认设置下，它会尝试以微小盈利（如1%）卖出仓位，或者在一段时间后以不亏损（0%利润）为目标卖出。
# 此策略的主要目的是在用户决定停止机器人或切换策略时，以一种有序、避免不必要亏损的方式清算所有现有头寸。
#
# 优点:
#   - 有序清仓: 相比于 `/forcesell all` (强制全部卖出) 可能导致大量亏损，该策略能更智能地等待亏损仓位回到成本价再卖出，最大程度减少离场时的损失。
#   - 目标明确: 逻辑非常简单，就是为了清仓，易于理解和使用。
#   - 风险可控: 可以通过调整 `minimal_roi` 和 `stoploss` 来精确控制离场条件。
#
# 缺点:
#   - 不能用于交易: 它没有入场逻辑，不能作为独立的盈利策略运行。
#   - 可能错失利润: 对于盈利中的仓位，它会很快地将其卖出以锁定微利，可能会错失后续更大的上涨行情。
#   - 不保证一定盈利: 如果某个亏损的仓位一直无法回到成本价，最终还是会由 `stoploss` 止损出场，或者需要用户手动干预。

# --- 原始文件说明 ---
# 本策略的逻辑是尽快将所有盈利的仓位平仓，以避免转盈为亏。
# 它不产生任何新的买入信号，而是通过设置最小投资回报率（minimal_roi）来管理现有持仓。
# 一旦仓位达到微利（例如0%或1%），就会被卖出。这对于希望快速清仓并锁定利润的用户非常有用。

# --- Do not remove these libs ---
from freqtrade.strategy import IStrategy
from pandas import DataFrame
from freqtrade.strategy.parameter import IntParameter, RealParameter

# --------------------------------


class BreakEven(IStrategy):
    """
    作者@: lenik

    有时我希望尽快关闭机器人，但不想让持仓浮动。

    我可以使用"/stopbuy"命令，然后等待机器人根据规则平仓，
    这通常需要等待一定的利润，过程可能会很长...

    我更希望的是，平掉所有利润超过0%的仓位以避免亏损。

    这是一个简单的策略，它没有买入/卖出信号，并且设置了 "minimal_roi = { 0 : 0 }"，
    它会卖掉所有已经盈利的仓位，并等待亏损的仓位回到盈亏平衡点（或者你在ROI表中设置的微小利润）。

    你可以通过命令行参数使用新策略重启机器人。

    另一种方法是在配置文件中指定原始策略，然后切换到这个策略，
    并简单地从Telegram机器人执行"/reload_config"命令。

    """

    INTERFACE_VERSION: int = 3
    # 如果配置文件中包含 "minimal_roi"，此属性将被覆盖
    @property
    def minimal_roi(self):
        return {
            self.roi_t2.value: self.roi_p2.value,
            self.roi_t1.value: self.roi_p1.value,
            0: 0.05 # start with a higher profit roi
        }
        
    roi_t1 = IntParameter(0, 20, default=10, space='roi', optimize=True)
    roi_p1 = RealParameter(0.0, 0.05, default=0.0, space='roi', optimize=True)
    roi_t2 = IntParameter(10, 30, default=20, space='roi', optimize=True)
    roi_p2 = RealParameter(-0.05, 0.0, default=0.0, space='roi', optimize=True)


    # 为该策略设计的优化止损
    stoploss = RealParameter(-0.1, -0.01, default=-0.05, space='protection', optimize=True)

    # 该策略的最佳时间框架
    timeframe = '5m'

    # 不生成任何买入或卖出信号，所有操作都由ROI和止损处理
    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
            ),
            'enter_long'] = 0
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe.loc[
            (
            ),
            'exit_long'] = 0
        return dataframe
