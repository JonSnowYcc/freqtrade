# --- 不要移除这些库 ---
from functools import reduce
from freqtrade.strategy import IStrategy
from freqtrade.strategy import timeframe_to_minutes
from freqtrade.strategy import BooleanParameter, IntParameter, RealParameter
from pandas import DataFrame
from technical.util import resample_to_interval, resampled_merge
import numpy  # noqa
# --------------------------------
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib


class ReinforcedSmoothScalp(IStrategy):
    """
    策略名称: ReinforcedSmoothScalp (加强版平滑剥头皮)
    策略作者: 未知
    策略类型: 剥头皮 / 多时间周期 / 超参数优化框架

    ## 策略核心逻辑

    这是一个极其先进和灵活的策略，是 `SmoothScalp` 的终极演进版。名称中的"Reinforced"(加强)并非指强化学习，
    而是通过引入**完全可优化的参数**和**多时间周期分析**，将一个固定的策略转变为一个可由数据驱动、自我加强的"策略框架"。

    ### 关键特征 1: 完全可优化的参数 (Hyperopt-driven)

    这是此策略与之前版本最根本的区别。它不再使用硬编码的"魔法数字"。
    - **可变阈值**: 所有指标的判断阈值(如 `ADX > 30`)都被定义为 `IntParameter`。这意味着可以通过Freqtrade的超参数优化功能，自动找到最适合特定市场的数值。
    - **可开关的规则**: 每一条入场/出场规则(如"是否使用MFI指标")都被定义为 `BooleanParameter`。这使得超参数优化可以**自动决定启用或禁用某些规则**，从而为不同的交易对或市场环境"量身定制"最佳的逻辑组合。

    ### 关键特征 2: 多时间周期 (MTF) 趋势过滤

    策略引入了更高时间周期的分析来作为趋势过滤器，这是对剥头皮策略一个巨大的改进。
    1.  **数据重采样**: 将当前时间周期(如1分钟)的数据，重新采样成一个更高的时间周期(如5分钟)。
    2.  **大周期均线**: 在这个5分钟的图表上计算一个长周期均线(50 SMA)。
    3.  **趋势过滤**: 在买入时，增加一个核心前提条件: `当前价格 > 5分钟周期的50 SMA`。这个条件确保了策略只在**宏观上升趋势**中寻找微观的买入机会，极大地避免了逆势交易的风险。

    ### 动态交易逻辑

    - **买入逻辑**: 核心条件是"大周期为上升趋势"+"随机指标金叉"。在此基础上，超参数优化会自动决定是否要额外附加 MFI、ADX 等指标作为过滤条件，以及它们的最佳阈值。
    - **卖出逻辑**: 核心条件是"价格大幅反弹"。在此基础上，超参数优化会自动决定是否要用CCI超买、随机指标超买等条件来加速退出。

    ### 优点
    - **极度灵活和自适应**: 可以通过超参数优化适应完全不同的市场环境。
    - **多时间周期分析**: 有效过滤掉逆势交易，提高了剥头皮策略的胜率。
    - **编程优雅**: 使用 `reduce` 动态构建交易逻辑，是非常值得学习的编程技巧。

    ### 缺点
    - **复杂性高**: 理解和修改该策略需要较高的水平。
    - **依赖优化**: 策略的性能高度依赖于超参数优化的质量。未经优化的默认参数可能表现平平。
    """

    INTERFACE_VERSION: int = 3

    # --- 可优化的ROI和止损 ---
    # 为策略设计的最小回报率(ROI)。
    # Freqtrade的超参数优化会自动寻找最佳值。
    minimal_roi_val = RealParameter(0.01, 0.05, default=0.02, space='roi')

    @property
    def minimal_roi(self):
        return {
            "0": self.minimal_roi_val.value
        }

    # 为策略设计的优化止损。
    # Freqtrade的超参数优化会自动寻找最佳值。
    stoploss = RealParameter(-0.20, -0.03, default=-0.1, space='protection')

    # 策略的最佳时间周期。
    # 时间周期越短越好。
    timeframe = '1m'

    # 用于确立总体趋势的重采样因子。
    # Freqtrade的超参数优化会自动寻找最佳值。
    resample_factor = IntParameter(2, 10, default=5, space='buy')

    buy_adx_enabled = BooleanParameter(default=True, space='buy')
    buy_adx = IntParameter(20, 50, default=32, space='buy')
    
    buy_fastd_enabled = BooleanParameter(default=True, space='buy')
    buy_fastd = IntParameter(15, 45, default=30, space='buy')
    
    buy_fastk_enabled = BooleanParameter(default=False, space='buy')
    buy_fastk = IntParameter(15, 45, default=26, space='buy')

    buy_mfi_enabled = BooleanParameter(default=True, space='buy')
    buy_mfi = IntParameter(10, 25, default=22, space='buy')

    sell_adx_enabled = BooleanParameter(default=False, space='sell')
    sell_adx = IntParameter(50, 100, default=53, space='sell')

    sell_cci_enabled = BooleanParameter(default=True, space='sell')
    sell_cci = IntParameter(100, 200, default=183, space='sell')

    sell_fastd_enabled = BooleanParameter(default=True, space='sell')
    sell_fastd = IntParameter(50, 100, default=79, space='sell')

    sell_fastk_enabled = BooleanParameter(default=True, space='sell')
    sell_fastk = IntParameter(50, 100, default=70, space='sell')

    sell_mfi_enabled = BooleanParameter(default=False, space='sell')
    sell_mfi = IntParameter(75, 100, default=92, space='sell')

    # Indicator parameters
    resample_sma_period = IntParameter(20, 100, default=50, space='buy')
    ema_period = IntParameter(3, 20, default=5, space='buy')
    stochf_k_period = IntParameter(3, 10, default=5, space='buy')
    stochf_d_period = IntParameter(2, 7, default=3, space='buy')
    adx_period = IntParameter(7, 21, default=14, space='buy')
    cci_period = IntParameter(14, 30, default=20, space='buy')
    rsi_period = IntParameter(7, 21, default=14, space='buy')

    # Bollinger Bands for plotting, but let's make them optimizable too
    bb_window = IntParameter(14, 30, default=20, space='buy')
    bb_stds = RealParameter(1.5, 3.0, default=2.0, space='buy')

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # --- 多时间周期分析 ---
        # 1. 计算重采样后的时间周期 (例如 1m * 5 -> 5m)
        tf_res = timeframe_to_minutes(self.timeframe) * self.resample_factor.value
        # 2. 获取重采样后的dataframe
        df_res = resample_to_interval(dataframe, tf_res)
        # 3. 在大周期上计算SMA均线
        df_res['sma'] = ta.SMA(df_res, timeperiod=int(self.resample_sma_period.value), price='close')
        # 4. 将大周期的指标合并回原始的dataframe
        dataframe = resampled_merge(dataframe, df_res, fill_na=True)
        # 命名合并后的列，用于后续判断
        dataframe['resample_sma'] = dataframe[f'resample_{tf_res}_sma']

        # --- 常规指标计算 ---
        dataframe['ema_high'] = ta.EMA(dataframe, timeperiod=int(self.ema_period.value), price='high')
        dataframe['ema_close'] = ta.EMA(dataframe, timeperiod=int(self.ema_period.value), price='close')
        dataframe['ema_low'] = ta.EMA(dataframe, timeperiod=int(self.ema_period.value), price='low')
        stoch_fast = ta.STOCHF(dataframe,
                             fastk_period=int(self.stochf_k_period.value),
                             fastd_period=int(self.stochf_d_period.value),
                             fastd_matype=0)
        dataframe['fastd'] = stoch_fast['fastd']
        dataframe['fastk'] = stoch_fast['fastk']
        dataframe['adx'] = ta.ADX(dataframe, timeperiod=int(self.adx_period.value))
        dataframe['cci'] = ta.CCI(dataframe, timeperiod=int(self.cci_period.value))
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=int(self.rsi_period.value))
        dataframe['mfi'] = ta.MFI(dataframe)

        # 绘图用指标
        bollinger = qtpylib.bollinger_bands(dataframe['close'], window=int(self.bb_window.value), stds=self.bb_stds.value)
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_upperband'] = bollinger['upper']

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 动态构建买入条件列表
        conditions = []

        # 根据hyperopt的结果，动态添加启用的规则
        if self.buy_mfi_enabled.value:
            conditions.append(dataframe['mfi'] < self.buy_mfi.value)
        if self.buy_fastd_enabled.value:
            conditions.append(dataframe['fastd'] < self.buy_fastd.value)
        if self.buy_fastk_enabled.value:
            conditions.append(dataframe['fastk'] < self.buy_fastk.value)
        if self.buy_adx_enabled.value:
            conditions.append(dataframe['adx'] > self.buy_adx.value)

        # 始终应用的静态条件
        conditions.append(qtpylib.crossed_above(dataframe['fastk'], dataframe['fastd'])) # 随机指标金叉
        conditions.append(dataframe['resample_sma'] < dataframe['close']) # 顺大势，逆小势

        conditions.append(dataframe['volume'] > 0) # 排除无交易量的市场

        if conditions:
            # 使用reduce函数将所有条件用"&"(逻辑与)连接起来
            dataframe.loc[
                reduce(lambda x, y: x & y, conditions),
                'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 动态构建卖出条件列表
        conditions = []

        # 始终应用的静态条件: 价格大幅反弹
        conditions.append(dataframe['open'] > dataframe['ema_high'])

        # 根据hyperopt的结果，动态添加启用的规则
        if self.sell_mfi_enabled.value:
            conditions.append(dataframe['mfi'] > self.sell_mfi.value)
        if self.sell_fastd_enabled.value:
            conditions.append(dataframe['fastd'] > self.sell_fastd.value)
        if self.sell_fastk_enabled.value:
            conditions.append(dataframe['fastk'] > self.sell_fastk.value)
        if self.sell_adx_enabled.value:
            conditions.append(dataframe['adx'] < self.sell_adx.value)
        if self.sell_cci_enabled.value:
            conditions.append(dataframe['cci'] > self.sell_cci.value)

        conditions.append(dataframe['volume'] > 0)

        if conditions:
            # 使用reduce函数将所有条件用"&"(逻辑与)连接起来
            dataframe.loc[
                reduce(lambda x, y: x & y, conditions),
                'exit_long'] = 1

        return dataframe
