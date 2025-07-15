# --- Do not remove these libs ---
from freqtrade.strategy import IStrategy, IntParameter, RealParameter
from pandas import DataFrame
# --------------------------------
import talib.abstract as ta
from technical.util import resample_to_interval, resampled_merge


class MultiRSI(IStrategy):
    """
    策略名称: MultiRSI (多时间周期RSI)
    策略作者: Gert Wohlgemuth (基于 Creslin 的工作)
    策略类型: 多时间周期 (MTF) / 均值回归

    ## 策略核心逻辑

    这是一个构思非常精巧的**多时间周期RSI均值回归**策略。它完美地展示了如何利用不同时间周期指标的"差异"来寻找交易机会。
    其核心思想是在一个确定的上升趋势中，利用短期动量的急剧回调作为买入点。

    ### 盈利逻辑: "上升趋势中的回调"

    1.  **构建多时间周期RSI**:
        - 策略在主图表（5分钟）的基础上，额外创建了10分钟和40分钟两个更高的时间周期。
        - 它分别计算了5m, 10m, 40m三个周期上的RSI值。这使得策略在任一时刻都能同时洞察短期、中期和长期的市场动量。

    2.  **买入条件**:
        - **趋势过滤**: `5周期SMA > 200周期SMA`。这确保了市场处于一个宏观的**上升趋势**中。（注意：原代码中此处的注释"must be bearish"是完全错误的）。
        - **动量背离**: `5分钟RSI < (40分钟RSI - 20)`。这是策略的精髓。它寻找一个"抄底"机会，即在长期动能（40m RSI）依然强劲的情况下，短期动能（5m RSI）已经大幅回落，形成一个显著的"坑"。这通常是健康回调的标志。

    3.  **卖出条件**:
        - `5分钟RSI > 10分钟RSI` **并且** `5分钟RSI > 40分钟RSI`。
        - 当短期动量从回调中完全恢复，甚至强于中长期动量时，策略认为反弹已经到位，选择获利了结。

    ### 优点
    - 逻辑非常清晰、健全，是MTF策略的优秀范例。
    - 通过比较不同周期的RSI，能够更精确地定义"回调"和"反弹到位"。
    - SMA趋势过滤器能有效避免在熊市中交易。

    ### 缺点
    - 在剧烈的单边行情中，可能等不到足够深的回调，从而错过机会。
    - 依赖于不同周期RSI之间能产生有效差异。在某些横盘行情中可能失效。
    """
    INTERFACE_VERSION: int = 3
    minimal_roi = RealParameter(0.005, 0.05, default=0.01, space='roi', optimize=True)

    # Optimal stoploss designed for the strategy
    stoploss = RealParameter(-0.10, -0.03, default=-0.05, space='protection', optimize=True)

    # Optimal timeframe for the strategy
    timeframe = '5m'

    # Indicator periods
    sma_fast_period = IntParameter(3, 15, default=5, space='buy', optimize=True)
    sma_slow_period = IntParameter(150, 250, default=200, space='buy', optimize=True)
    rsi_main_period = IntParameter(10, 25, default=14, space='buy', optimize=True)
    rsi_short_period = IntParameter(10, 25, default=14, space='buy', optimize=True)
    rsi_long_period = IntParameter(10, 25, default=14, space='buy', optimize=True)

    # MTF multipliers
    short_res_multiplier = IntParameter(2, 5, default=2, space='buy', optimize=True)
    long_res_multiplier = IntParameter(6, 12, default=8, space='buy', optimize=True)

    # Buy threshold
    buy_rsi_diff = IntParameter(10, 30, default=20, space='buy', optimize=True)

    def get_ticker_indicator(self):
        return int(self.timeframe[:-1])

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # --- 主图表指标 ---
        dataframe['sma5'] = ta.SMA(dataframe, timeperiod=self.sma_fast_period.value)
        dataframe['sma200'] = ta.SMA(dataframe, timeperiod=self.sma_slow_period.value)
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=self.rsi_main_period.value)

        # --- 多时间周期指标 ---
        # 1. 重采样到10分钟(5m*2)和40分钟(5m*8)周期
        dataframe_short = resample_to_interval(dataframe, self.get_ticker_indicator() * self.short_res_multiplier.value)
        dataframe_long = resample_to_interval(dataframe, self.get_ticker_indicator() * self.long_res_multiplier.value)

        # 2. 在更高周期上计算RSI
        dataframe_short['rsi'] = ta.RSI(dataframe_short, timeperiod=self.rsi_short_period.value)
        dataframe_long['rsi'] = ta.RSI(dataframe_long, timeperiod=self.rsi_long_period.value)

        # 3. 将高周期指标合并回主dataframe
        # resampled_merge会自动重命名列，例如 'rsi' -> 'resample_10_rsi'
        dataframe = resampled_merge(dataframe, dataframe_short)
        dataframe = resampled_merge(dataframe, dataframe_long)

        # 填充因重采样产生的NaN值
        dataframe.fillna(method='ffill', inplace=True)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 获取重采样后的列名
        rsi_long_res_name = f"resample_{self.get_ticker_indicator() * self.long_res_multiplier.value}_rsi"
        
        dataframe.loc[
            (
                # 条件1: 必须是牛市 (原代码注释错误，已修正)
                (dataframe['sma5'] >= dataframe['sma200']) &
                # 条件2: 短期RSI远低于长期RSI，形成"黄金坑"
                (dataframe['rsi'] < (dataframe[rsi_long_res_name] - self.buy_rsi_diff.value))
            ),
            'enter_long'] = 1
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 获取重采样后的列名
        rsi_short_res_name = f"resample_{self.get_ticker_indicator() * self.short_res_multiplier.value}_rsi"
        rsi_long_res_name = f"resample_{self.get_ticker_indicator() * self.long_res_multiplier.value}_rsi"

        dataframe.loc[
            (
                # 条件: 短期RSI动能已经超越了中长期动能，表明反弹到位
                (dataframe['rsi'] > dataframe[rsi_short_res_name]) &
                (dataframe['rsi'] > dataframe[rsi_long_res_name])
            ),
            'exit_long'] = 1
        return dataframe
