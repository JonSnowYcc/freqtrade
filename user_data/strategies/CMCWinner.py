# --- Do not remove these libs ---
from freqtrade.strategy import IStrategy, IntParameter, RealParameter
from pandas import DataFrame
# --------------------------------

# Add your lib to import here
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib
import numpy # noqa


class CMCWinner(IStrategy):
    """
    策略名称: CMCWinner (CMC冠军策略)
    策略类型: 均值回归 / 振荡器共振

    ## 策略核心逻辑

    这是一个非常经典的**振荡器共振**均值回归策略。策略名称中的"CMC"很可能就是其使用的三个核心指标的首字母缩写：
    - **C**CI (商品通道指标)
    - **M**FI (资金流量指标)
    - **C**MO (钱德动量振荡器)

    其核心思想是，只有当这三个不同类型的振荡器指标**同时**发出信号时，才进行交易，以此来过滤掉单一指标的噪音，提高信号的可靠性。

    ### 盈利逻辑: "三指共振，否极泰来"

    #### 买入条件:
    策略要求在**上一根K线**收盘时，三个指标必须**同时**处于各自的深度超卖区域：
    1.  `CCI < -100`: 价格相对其统计均值已严重超卖。
    2.  `MFI < 20`: 成交量加权的动能显示资金严重流出。
    3.  `CMO < -50`: 纯粹的动量指标显示市场处于下行动能的极端。

    - **组合解读**: 这是一个非常强烈的"共振"抄底信号。它要求市场不仅在价格上，在资金上，在动能上都达到一个极端的悲观状态，从而增加后续反弹的概率。

    #### 卖出条件:
    卖出逻辑是买入的完美镜像。要求在**上一根K线**收盘时，三个指标**同时**进入各自的超买区域：
    1.  `CCI > 100`
    2.  `MFI > 80`
    3.  `CMO > 50`

    ### 优点
    - **信号可靠性高**: 多指标共振可以有效过滤掉大量虚假信号。
    - **逻辑清晰**: 易于理解，是学习指标组合策略的绝佳范例。
    - **代码严谨**: 使用 `.shift(1)` 来判断信号，避免了未来函数，是专业策略的典范。

    ### 缺点
    - **交易机会少**: 因为条件非常苛刻，可能会错过很多不是极端情况的交易机会。
    - **可能钝化**: 在强烈的单边趋势中，振荡器可能长时间在超买/超卖区徘徊，导致过早平仓或无法入场。
    """

    INTERFACE_VERSION: int = 3
    # ROI table
    roi_p1 = RealParameter(0.03, 0.08, default=0.05, space='roi', optimize=True)
    roi_p2 = RealParameter(0.02, 0.05, default=0.03, space='roi', optimize=True)
    roi_p3 = RealParameter(0.01, 0.03, default=0.02, space='roi', optimize=True)
    
    @property
    def minimal_roi(self):
        return {
            "40": 0.0,
            "30": self.roi_p3.value,
            "20": self.roi_p2.value,
            "0": self.roi_p1.value
        }
        
    stoploss = RealParameter(-0.10, -0.03, default=-0.05, space='protection', optimize=True)
    timeframe = '15m'

    # Indicator periods
    cci_period = IntParameter(15, 30, default=20, space='buy', optimize=True)
    mfi_period = IntParameter(10, 20, default=14, space='buy', optimize=True)
    cmo_period = IntParameter(10, 20, default=14, space='buy', optimize=True)

    # Buy thresholds
    buy_cci = IntParameter(-150, -50, default=-100, space='buy', optimize=True)
    buy_mfi = IntParameter(10, 30, default=20, space='buy', optimize=True)
    buy_cmo = IntParameter(-60, -40, default=-50, space='buy', optimize=True)

    # Sell thresholds
    sell_cci = IntParameter(50, 150, default=100, space='sell', optimize=True)
    sell_mfi = IntParameter(70, 90, default=80, space='sell', optimize=True)
    sell_cmo = IntParameter(40, 60, default=50, space='sell', optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        计算所需的技术指标
        """
        # CCI - 商品通道指标: Oversold:<-100, Overbought:>100
        dataframe['cci'] = ta.CCI(dataframe, timeperiod=self.cci_period.value)

        # MFI - 资金流量指标: Oversold:<20, Overbought:>80
        dataframe['mfi'] = ta.MFI(dataframe, timeperiod=self.mfi_period.value)

        # CMO - 钱德动量振荡器: Oversold:<-50, Overbought:>50
        dataframe['cmo'] = ta.CMO(dataframe, timeperiod=self.cmo_period.value)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义买入信号：三个指标在上一个周期同时超卖
        """
        dataframe.loc[
            (
                (dataframe['cci'].shift(1) < self.buy_cci.value) &
                (dataframe['mfi'].shift(1) < self.buy_mfi.value) &
                (dataframe['cmo'].shift(1) < self.buy_cmo.value)
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义卖出信号：三个指标在上一个周期同时超买
        """
        dataframe.loc[
            (
                (dataframe['cci'].shift(1) > self.sell_cci.value) &
                (dataframe['mfi'].shift(1) > self.sell_mfi.value) &
                (dataframe['cmo'].shift(1) > self.sell_cmo.value)
            ),
            'exit_long'] = 1
        return dataframe
