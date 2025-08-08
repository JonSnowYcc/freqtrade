# --- Do not remove these libs ---
import freqtrade.vendor.qtpylib.indicators as qtpylib
import talib.abstract as ta
from freqtrade.strategy import IStrategy
from freqtrade.strategy import IntParameter, RealParameter
from pandas import DataFrame
# --------------------------------


class CofiBitStrategy(IStrategy):
    """
    策略名称: CofiBitStrategy (CofiBit策略)
    策略作者: CofiBit (来自Slack用户)
    策略类型: 剥头皮 / 趋势回调 / 超参数优化

    ## 策略核心逻辑

    该策略可以被看作是 `Scalp.py` 策略的**可优化版本**。
    它实现了完全相同的"在强趋势中回调买入"的交易逻辑，但通过引入超参数优化（Hyperopt），
    将所有关键的决策阈值都转换为了可配置的参数，从而大大增强了策略的灵活性和适应性。

    ### 盈利逻辑: "可优化的趋势中回调买入"

    #### 买入条件:
    策略的买入逻辑是寻找趋势、价格和动量三者的共振点：

    1.  **趋势确认**: `ADX > buy_adx` - ADX指标高于一个**可优化**的阈值，表明市场存在强劲趋势。
    2.  **价格回调**: `开盘价 < 5周期EMA最低价` - 价格出现急剧回调。
    3.  **动能反转**: `随机指标(Stoch)金叉` 并且 `快慢线 < buy_fastx` - 随机指标在一个**可优化**的超卖区域内形成金叉。

    #### 卖出逻辑:
    卖出逻辑由两个"或"条件组成，体现了快速离场的思想：
    1.  `开盘价 >= 5周期EMA最高价` - 价格强力反弹。
    2.  `随机指标快线或慢线 > sell_fastx` - 随机指标进入一个**可优化**的超买区域。

    ### 优点
    - **高度灵活**: 核心参数均可优化，能更好地适应不同市场。
    - 逻辑清晰，是`Scalp.py`策略的一个优秀演进。

    ### 缺点
    - 性能高度依赖于超参数优化的结果。
    - 剥头皮策略对交易费用和滑点敏感。
    """

    INTERFACE_VERSION: int = 3
    # 优化后的参数示例
    buy_params = {
        "buy_fastx": 25,
        "buy_adx": 25,
    }
    sell_params = {
        "sell_fastx": 75,
    }

    # ROI table
    roi_p1 = RealParameter(0.08, 0.15, default=0.10, space='roi', optimize=True)
    roi_p2 = RealParameter(0.05, 0.10, default=0.07, space='roi', optimize=True)
    roi_p3 = RealParameter(0.04, 0.08, default=0.06, space='roi', optimize=True)
    roi_p4 = RealParameter(0.03, 0.06, default=0.05, space='roi', optimize=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.minimal_roi = {
            "40": self.roi_p4.value,
            "30": self.roi_p3.value,
            "20": self.roi_p2.value,
            "0": self.roi_p1.value
        }

    stoploss = RealParameter(-0.30, -0.15, default=-0.25, space='protection', optimize=True)
    timeframe = '5m'

    # 定义可优化的参数
    buy_fastx = IntParameter(20, 30, default=25, space='buy', optimize=True)
    buy_adx = IntParameter(20, 30, default=25, space='buy', optimize=True)
    sell_fastx = IntParameter(70, 80, default=75, space='sell', optimize=True)

    # Indicator periods
    stochf_k_period = IntParameter(3, 10, default=5, space='buy', optimize=True)
    stochf_d_period = IntParameter(2, 7, default=3, space='buy', optimize=True)
    ema_period = IntParameter(3, 10, default=5, space='buy', optimize=True)
    adx_period = IntParameter(10, 20, default=14, space='buy', optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # StochF - 快速随机指标
        stoch_fast = ta.STOCHF(
            dataframe,
            fastk_period=self.stochf_k_period.value,
            fastd_period=self.stochf_d_period.value,
            fastd_matype=0
        )
        dataframe['fastd'] = stoch_fast['fastd']
        dataframe['fastk'] = stoch_fast['fastk']
        
        # EMA - 指数移动平均线 (构成动态通道)
        dataframe['ema_high'] = ta.EMA(dataframe, timeperiod=self.ema_period.value, price='high')
        dataframe['ema_close'] = ta.EMA(dataframe, timeperiod=self.ema_period.value, price='close')
        dataframe['ema_low'] = ta.EMA(dataframe, timeperiod=self.ema_period.value, price='low')
        
        # ADX - 平均趋向指数
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=self.adx_period.value)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义买入信号
        """
        dataframe.loc[
            (
                # 1. 价格回调
                (dataframe['open'] < dataframe['ema_low']) &
                # 2. 随机指标在超卖区金叉
                (qtpylib.crossed_above(dataframe['fastk'], dataframe['fastd'])) &
                (dataframe['fastk'] < self.buy_fastx.value) &
                (dataframe['fastd'] < self.buy_fastx.value) &
                # 3. 存在强劲趋势
                (dataframe['adx'] > self.buy_adx.value)
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义卖出信号
        """
        dataframe.loc[
            (
                # 条件1: 价格大幅反弹
                (dataframe['open'] >= dataframe['ema_high'])
            ) |
            (
                # 条件2: 随机指标进入超买区
                (qtpylib.crossed_above(dataframe['fastk'], self.sell_fastx.value)) |
                (qtpylib.crossed_above(dataframe['fastd'], self.sell_fastx.value))
            ),
            'exit_long'] = 1

        return dataframe
