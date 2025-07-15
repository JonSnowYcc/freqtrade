import talib.abstract as ta
from pandas import DataFrame
import scipy.signal
import freqtrade.vendor.qtpylib.indicators as qtpylib
from freqtrade.strategy import IStrategy, IntParameter, RealParameter, BooleanParameter


class TDSequentialStrategy(IStrategy):
    """
    策略名称: TDSequentialStrategy (TD序列策略)
    策略作者: @bmoulkaf
    策略类型: 趋势耗尽 / 反转 (Trend Exhaustion / Reversal)
    Github: https://github.com/freqtrade/freqtrade-strategies/blob/main/user_data/strategies/berlinguyinca/TDSequentialStrategy.py
    文章来源: https://hackernoon.com/how-to-buy-sell-cryptocurrency-with-number-indicator-td-sequential-5af46f0ebce1

    ## 策略核心逻辑

    该策略基于著名的市场择时指标 **TD序列（Tom DeMark Sequential）**，旨在识别趋势力竭的潜在反转点。

    ### 盈利逻辑

    TD序列的核心是寻找趋势的"衰竭区"。
    - **TD买入结构 (Buy Setup)**: 策略会寻找一个由9根K线组成的序列，其中每一根K线的收盘价都**低于**其前方第4根K线的收盘价。当这个序列计数达到9时，被认为是一个潜在的买入机会，表明下降趋势可能即将结束。
    - **TD卖出结构 (Sell Setup)**: 与买入结构相反，寻找一个9根K线的序列，每根K线的收盘价都**高于**其前方第4根K线的收盘价。计数达到9时，被认为是一个潜在的卖出机会，表明上升趋势可能即将结束。

    为了提高信号质量，策略还引入了"理想形态"作为过滤条件：
    - **理想买入 (Ideal Buy)**: 在买入结构的第8或第9根K线，其**最低价**必须**低于**第6和第7根K线的最低价。这被视为一个"恐慌性"或"衰竭式"的下跌，增加了反转的可能性。
    - **理想卖出 (Ideal Sell)**: 在卖出结构的第8或第9根K线，其**最高价**必须**高于**第6和第7根K线的最高价。

    - **买入信号**: 当"TD买入结构"计数达到9 **并且** 满足"理想买入"条件时，策略开仓买入。
    - **卖出信号**: 当"TD卖出结构"计数达到9 **或者** 满足"理想卖出"条件时，策略平仓卖出。

    ### 优点
    - TD序列是一个经过市场长期考验的经典择时工具，对于识别波段的顶部和底部有一定参考价值。
    - "理想形态"的加入，可以过滤掉一些较弱的信号，提高入场的精确度。

    ### 缺点
    - **严重性能问题**: `populate_indicators` 中使用了 for 循环来逐行计算指标 (`for index, row in dataframe.iterrows():`)。在处理大量历史数据时，这种方式**效率极低，会非常非常缓慢**。专业的实现应该完全使用Pandas的向量化操作（如 `.shift()` 和条件赋值）来避免循环。
    - TD结构在趋势强劲时可能连续出现，导致过早逆势入场而被套。
    - 逻辑较为复杂，可能出现计数中断的情况，从而错过交易机会。
    """
    INTERFACE_VERSION: int = 3

    # 为策略设计的最小盈利预期
    minimal_roi = RealParameter(1.0, 10.0, default=5.0, space='roi', optimize=True)

    # 为策略设计的止损
    stoploss = RealParameter(-0.1, -0.01, default=-0.05, space='protection', optimize=True)

    # 移动止损
    trailing_stop = BooleanParameter(default=False, space='protection', optimize=True)
    trailing_stop_positive = RealParameter(0.005, 0.05, default=0.01, space='protection', optimize=True)
    trailing_stop_positive_offset = RealParameter(0.0, 0.05, default=0.0, space='protection', optimize=True)
    trailing_only_offset_is_reached = BooleanParameter(default=False, space='protection', optimize=True)

    # 策略的最佳时间周期
    timeframe = '1h'

    # 可以在config中 "ask_strategy" 部分覆盖这些值
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # 可选的订单类型映射
    order_types = {
        'entry': 'limit',
        'exit': 'limit',
        'stoploss': 'limit',
        'stoploss_on_exchange': False
    }

    # 策略产生有效信号前需要的最少K线数量
    startup_candle_count: int = 30

    # 可选的订单有效时间
    order_time_in_force = {
        'entry': 'gtc',
        'exit': 'gtc',
    }

    # TD Sequential Parameters
    td_seq_buy_period = IntParameter(2, 6, default=4, space='buy', optimize=True)
    td_seq_sell_period = IntParameter(2, 6, default=4, space='sell', optimize=True)
    td_seq_buy_count = IntParameter(7, 10, default=8, space='buy', optimize=True) # > 8 means 9
    td_seq_sell_count = IntParameter(7, 10, default=8, space='sell', optimize=True) # > 8 means 9
    
    # Ideal setup parameters
    ideal_buy_low_shift1 = IntParameter(1, 4, default=2, space='buy', optimize=True)
    ideal_buy_low_shift2 = IntParameter(1, 4, default=1, space='buy', optimize=True)
    ideal_sell_high_shift1 = IntParameter(1, 4, default=2, space='sell', optimize=True)
    ideal_sell_high_shift2 = IntParameter(1, 4, default=1, space='sell', optimize=True)

    def informative_pairs(self):
        """
        Define additional, informative pair/interval combinations to be cached from the exchange.
        These pair/interval combinations are non-tradeable, unless they are part
        of the whitelist as well.
        For more information, please consult the documentation
        :return: List of tuples in the format (pair, interval)
            Sample: return [("ETH/USDT", "5m"),
                            ("BTC/USDT", "15m"),
                            ]
        """
        return []

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        计算所有必需的指标
        警告: 为了获得最佳性能，请不要在这里使用太多指标。
              只保留策略或超参数优化中实际用到的指标，否则会浪费内存和CPU。
        """

        dataframe['exceed_high'] = False
        dataframe['exceed_low'] = False

        # 计算TD买入结构: 连续N根K线，每根的收盘价都低于M根K线前的收盘价
        # 1. 判断条件是否成立，生成布尔序列 (True/False)
        buy_setup_condition = dataframe['close'] < dataframe['close'].shift(self.td_seq_buy_period.value)
        # 2. 将布尔值乘以连续计数，得到TD买入结构的计数值
        dataframe['seq_buy'] = buy_setup_condition * (buy_setup_condition.groupby(
            (buy_setup_condition != buy_setup_condition.shift()).cumsum()).cumcount() + 1)

        # 计算TD卖出结构: 连续N根K线，每根的收盘价都高于M根K线前的收盘价
        sell_setup_condition = dataframe['close'] > dataframe['close'].shift(self.td_seq_sell_period.value)
        dataframe['seq_sell'] = sell_setup_condition * (sell_setup_condition.groupby(
            (sell_setup_condition != sell_setup_condition.shift()).cumsum()).cumcount() + 1)
        
        # ----------------------------------------------------------------------------------
        # 警告：下面的 for 循环是严重的性能瓶颈！
        # 在处理大量数据时，逐行迭代 (iterrows) 会非常缓慢。
        # 更高效的方法是使用向量化操作，例如 .shift() 来比较不同行的值。
        # ----------------------------------------------------------------------------------
        for index, row in dataframe.iterrows():
            # 检查理想买入条件：计数中的第8或第9根K线的最低价是否低于第6和第7根的最低价。
            seq_b = row['seq_buy']
            if seq_b == self.td_seq_buy_count.value:
                dataframe.loc[index, 'exceed_low'] = (row['low'] < dataframe.loc[index - self.ideal_buy_low_shift1.value, 'low']) | \
                                    (row['low'] < dataframe.loc[index - self.ideal_buy_low_shift2.value, 'low'])
            if seq_b > self.td_seq_buy_count.value:
                dataframe.loc[index, 'exceed_low'] = (row['low'] < dataframe.loc[index - (self.ideal_buy_low_shift1.value + 1) - (seq_b - (self.td_seq_buy_count.value+1)), 'low']) | \
                                    (row['low'] < dataframe.loc[index - (self.ideal_buy_low_shift2.value+1) - (seq_b - (self.td_seq_buy_count.value+1)), 'low'])
                if seq_b == (self.td_seq_buy_count.value+1):
                    dataframe.loc[index, 'exceed_low'] = row['exceed_low'] | dataframe.loc[index-1, 'exceed_low']

            # 检查理想卖出条件：计数中的第8或第9根K线的最高价是否高于第6和第7根的最高价。
            seq_s = row['seq_sell']
            if seq_s == self.td_seq_sell_count.value:
                dataframe.loc[index, 'exceed_high'] = (row['high'] > dataframe.loc[index - self.ideal_sell_high_shift1.value, 'high']) | \
                                    (row['high'] > dataframe.loc[index - self.ideal_sell_high_shift2.value, 'high'])
            if seq_s > self.td_seq_sell_count.value:
                dataframe.loc[index, 'exceed_high'] = (row['high'] > dataframe.loc[index - (self.ideal_sell_high_shift1.value+1) - (seq_s - (self.td_seq_sell_count.value+1)), 'high']) | \
                                    (row['high'] > dataframe.loc[index - (self.ideal_sell_high_shift2.value+1) - (seq_s - (self.td_seq_sell_count.value+1)), 'high'])
                if seq_s == (self.td_seq_sell_count.value+1):
                    dataframe.loc[index, 'exceed_high'] = row['exceed_high'] | dataframe.loc[index-1, 'exceed_high']

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        根据技术分析指标，为给定的数据帧填充买入信号
        """
        dataframe["enter_long"] = 0
        dataframe.loc[
            (
                # 信号：TD买入结构计数达到N，并且满足"理想买入"的条件
                (dataframe['exceed_low']) &
                (dataframe['seq_buy'] > self.td_seq_buy_count.value)
            ), 
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        根据技术分析指标，为给定的数据帧填充卖出信号
        """
        dataframe["exit_long"] = 0
        dataframe.loc[
            (
                # 信号：满足"理想卖出"条件，或者TD卖出结构计数达到N
                (dataframe['exceed_high']) |
                (dataframe['seq_sell'] > self.td_seq_sell_count.value)
            ),
            'exit_long'] = 1
        return dataframe
