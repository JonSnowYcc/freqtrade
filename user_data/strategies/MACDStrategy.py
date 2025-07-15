# --- Do not remove these libs ---
from freqtrade.strategy import IStrategy
from freqtrade.strategy import IntParameter, RealParameter
from pandas import DataFrame
# --------------------------------

import talib.abstract as ta


class MACDStrategy(IStrategy):
    """
    策略名称: MACDStrategy (可优化的MACD状态策略)
    策略作者: Gert Wohlgemuth
    策略类型: 动量 / 均值回归 / 超参数优化

    ## 策略核心逻辑

    这是 `MACDStrategy_crossed` 策略的一个更灵活、更强大的演进版本。
    它不再仅仅依赖于"交叉"这一瞬时事件，而是基于MACD的持续"状态"进行交易，并通过可优化的CCI阈值来寻找最佳的买卖点。

    ### 关键区别与改进

    1.  **"交叉" vs "状态"**:
        - `_crossed` 版本使用 `crossed_above` 函数，只在交叉发生的那一根K线上触发信号，这是一个**事件(Event)驱动**的策略。
        - 本策略使用 `macd > macdsignal` 的判断，只要MACD快线在慢线上方，条件就持续成立，这是一个**状态(State)驱动**的策略，更具普遍性。
    2.  **可优化的参数**:
        - 本策略引入了 `IntParameter`，使得CCI的买入和卖出阈值（`buy_cci`, `sell_cci`）可以被超参数优化功能自动寻找，从而让策略能更好地适应不同市场。

    ### 盈利逻辑: "在看涨状态中逢低买，在看跌状态中逢高卖"

    #### 买入条件:
    1.  **MACD看涨状态**: `macd > macdsignal`。要求市场处于一个由MACD确认的、持续的看涨动能状态中。
    2.  **CCI超卖过滤**: `cci <= buy_cci`。在上述看涨状态下，等待价格回调，使得CCI进入一个可被优化的"超卖"区域。

    #### 卖出条件:
    1.  **MACD看跌状态**: `macd < macdsignal`。要求市场进入一个持续的看跌动能状态。
    2.  **CCI超买过滤**: `cci >= sell_cci`。在上述看跌状态下，等待价格反弹，使得CCI进入一个可被优化的"超买"区域。

    ### 优点
    - **高度灵活**: 可优化的CCI参数使策略能更好地适应市场变化。
    - **状态驱动**: 比事件驱动更稳定，能更好地捕捉持续的趋势和机会。
    - 是构建和优化"指标组合"策略的绝佳范例。

    ### 缺点
    - 性能高度依赖于超参数优化的结果。
    - 在没有明显趋势的横盘市场中，可能会因MACD的频繁上下波动而产生过多无效信号。
    """
    INTERFACE_VERSION: int = 3

    # ROI table
    roi_p1 = RealParameter(0.02, 0.06, default=0.05, space='roi', optimize=True)
    roi_p2 = RealParameter(0.02, 0.05, default=0.04, space='roi', optimize=True)
    roi_p3 = RealParameter(0.01, 0.04, default=0.03, space='roi', optimize=True)
    roi_p4 = RealParameter(0.005, 0.02, default=0.01, space='roi', optimize=True)

    @property
    def minimal_roi(self):
        return {
            "60": self.roi_p4.value,
            "30": self.roi_p3.value,
            "20": self.roi_p2.value,
            "0": self.roi_p1.value
        }

    # Optimal stoploss
    stoploss = RealParameter(-0.35, -0.15, default=-0.3, space='protection', optimize=True)

    # Optimal timeframe for the strategy
    timeframe = '5m'

    # --- 超参数定义 ---
    # CCI 阈值
    buy_cci = IntParameter(low=-700, high=0, default=-50, space='buy', optimize=True)
    sell_cci = IntParameter(low=0, high=700, default=100, space='sell', optimize=True)

    # 指标周期
    macd_fast_period = IntParameter(low=10, high=25, default=12, space='buy', optimize=True)
    macd_slow_period = IntParameter(low=20, high=40, default=26, space='buy', optimize=True)
    macd_signal_period = IntParameter(low=7, high=15, default=9, space='buy', optimize=True)
    cci_period = IntParameter(low=15, high=30, default=20, space='buy', optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # MACD - 异同移动平均线
        macd = ta.MACD(
            dataframe,
            fastperiod=self.macd_fast_period.value,
            slowperiod=self.macd_slow_period.value,
            signalperiod=self.macd_signal_period.value
        )
        dataframe['macd'] = macd['macd']
        dataframe['macdsignal'] = macd['macdsignal']
        dataframe['macdhist'] = macd['macdhist']
        
        # CCI - 商品通道指标
        dataframe['cci'] = ta.CCI(dataframe, timeperiod=self.cci_period.value)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义买入信号
        """
        dataframe.loc[
            (
                # 条件1: 市场处于MACD看涨状态
                (dataframe['macd'] > dataframe['macdsignal']) &
                # 条件2: CCI回调至超卖区 (阈值可优化)
                (dataframe['cci'] <= self.buy_cci.value) &
                (dataframe['volume'] > 0)
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义卖出信号
        """
        dataframe.loc[
            (
                # 条件1: 市场处于MACD看跌状态
                (dataframe['macd'] < dataframe['macdsignal']) &
                # 条件2: CCI反弹至超买区 (阈值可优化)
                (dataframe['cci'] >= self.sell_cci.value) &
                (dataframe['volume'] > 0)
            ),
            'exit_long'] = 1

        return dataframe
