# --- 策略总结 ---
# 策略名称: mabStra (移动平均线带策略)
#
# 盈利逻辑:
# 这是一种相对复杂的移动平均线策略。它不是使用传统的"金叉/死叉"信号，而是通过计算三条不同周期的移动平均线
# (可称为超快线 `mojoMA`、快线 `fastMA`、慢线 `slowMA`) 之间的**比率**，来判断趋势的"健康度"和"强度"。
#   - 买入(Entry): 只有当以下两个条件**同时**满足时，才会触发买入：
#       1. `(超快线 / 快线)` 的比率，落在一个特定的、可优化的数值区间内。
#       2. `(快线 / 慢线)` 的比率，也落在这个数值区间内。
#   其本质是，当三条均线呈现出一种健康、稳定、向上发散的排列时 (例如，慢线在最下，快线居中，超快线在最上，且它们之间的距离既不过近也不过远)，
#   策略认为这是一个高质量的上升趋势，并产生买入信号。
#   - 卖出(Exit): 卖出逻辑类似，但使用一组独立的、可优化的卖出均线参数，寻找一个特定的、可能是下降趋势的均线排列形态。
#
# 优点:
#   - 量化趋势质量: 相比简单的交叉信号，通过均线比率，策略能更好地量化趋势的强度和稳定性，可能过滤掉一些弱趋势或即将反转的趋势。
#   - 灵活性高: 所有的均线周期和比率区间都是可优化的，使得策略能适应不同的市场和交易品种。
#   - 避免Whipsaws (拉锯): 由于它要求一个稳定的排列而非瞬时交叉，可能有助于过滤掉震荡市中的许多假信号。
#
# 缺点:
#   - 高度依赖优化: 策略的有效性完全取决于超参数优化的结果。没有好的参数，策略将毫无意义。
#   - 逻辑相对抽象: "均线比率在某个区间内"不如"金叉"那样直观，理解上需要一些思考。
#   - 信号可能滞后: 同样地，等待三条均线形成完美排列可能需要时间，可能会错过趋势的最初启动点。

# 作者: @Mablue (Masoud Azizi)
# github: https://github.com/mablue/
# 重要提示: 请勿在未进行超参数优化的情况下使用:
# freqtrade hyperopt --hyperopt-loss SharpeHyperOptLoss --spaces all --strategy mabStra --config config.json -e 100

# --- 请勿删除这些库 ---
from freqtrade.strategy import IntParameter, DecimalParameter, IStrategy, RealParameter
from pandas import DataFrame
# --------------------------------

# 在此导入您的库
import talib.abstract as ta


class mabStra(IStrategy):

    INTERFACE_VERSION: int = 3
    # #################### 结果粘贴区 ####################
    # 投资回报率 (ROI) 表:
    minimal_roi = {
        "0": 0.598,
        "644": 0.166,
        "3269": 0.115,
        "7289": 0
    }
    roi_p1 = RealParameter(0.4, 0.8, default=0.598, space='roi', optimize=True)
    roi_p2 = RealParameter(0.1, 0.3, default=0.166, space='roi', optimize=True)
    roi_p3 = RealParameter(0.05, 0.2, default=0.115, space='roi', optimize=True)


    # 止损:
    stoploss = RealParameter(-0.15, -0.1, default=-0.128, space='protection', optimize=True)
    # 时间框架
    timeframe = '4h'

    # #################### 结果粘贴区结束 ####################

    # 买入参数
    # 超快线周期
    buy_mojo_ma_timeframe = IntParameter(2, 100, default=7, space='buy', optimize=True)
    # 快线周期
    buy_fast_ma_timeframe = IntParameter(2, 100, default=14, space='buy', optimize=True)
    # 慢线周期
    buy_slow_ma_timeframe = IntParameter(2, 100, default=28, space='buy', optimize=True)
    # 比率区间的上限
    buy_div_max = DecimalParameter(
        0, 2, decimals=4, default=2.25446, space='buy', optimize=True)
    # 比率区间的下限
    buy_div_min = DecimalParameter(
        0, 2, decimals=4, default=0.29497, space='buy', optimize=True)
        
    # 卖出参数 (与买入参数独立)
    sell_mojo_ma_timeframe = IntParameter(2, 100, default=7, space='sell', optimize=True)
    sell_fast_ma_timeframe = IntParameter(2, 100, default=14, space='sell', optimize=True)
    sell_slow_ma_timeframe = IntParameter(2, 100, default=28, space='sell', optimize=True)
    # 修正了默认值，确保 min <= max
    sell_div_max = DecimalParameter(
        0, 2, decimals=4, default=1.54593, space='sell', optimize=True)
    sell_div_min = DecimalParameter(
        0, 2, decimals=4, default=0.81436, space='sell', optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # SMA - 简单移动平均线
        # 买入均线
        dataframe['buy-mojoMA'] = ta.SMA(dataframe,
                                         timeperiod=self.buy_mojo_ma_timeframe.value)
        dataframe['buy-fastMA'] = ta.SMA(dataframe,
                                         timeperiod=self.buy_fast_ma_timeframe.value)
        dataframe['buy-slowMA'] = ta.SMA(dataframe,
                                         timeperiod=self.buy_slow_ma_timeframe.value)
        # 卖出均线
        dataframe['sell-mojoMA'] = ta.SMA(dataframe,
                                          timeperiod=self.sell_mojo_ma_timeframe.value)
        dataframe['sell-fastMA'] = ta.SMA(dataframe,
                                          timeperiod=self.sell_fast_ma_timeframe.value)
        dataframe['sell-slowMA'] = ta.SMA(dataframe,
                                          timeperiod=self.sell_slow_ma_timeframe.value)
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义买入信号的逻辑
        """
        dataframe.loc[
            (
                # 条件1: (超快线 / 快线) 的比率在定义的区间内
                (dataframe['buy-mojoMA'].div(dataframe['buy-fastMA'])
                    > self.buy_div_min.value) &
                (dataframe['buy-mojoMA'].div(dataframe['buy-fastMA'])
                    < self.buy_div_max.value) &
                # 条件2: (快线 / 慢线) 的比率也在定义的区间内
                (dataframe['buy-fastMA'].div(dataframe['buy-slowMA'])
                    > self.buy_div_min.value) &
                (dataframe['buy-fastMA'].div(dataframe['buy-slowMA'])
                    < self.buy_div_max.value)
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义卖出信号的逻辑
        """
        dataframe.loc[
            (
                # 条件1: (卖出快线 / 卖出超快线) 的比率在定义的区间内
                (dataframe['sell-fastMA'].div(dataframe['sell-mojoMA'])
                    > self.sell_div_min.value) &
                (dataframe['sell-fastMA'].div(dataframe['sell-mojoMA'])
                    < self.sell_div_max.value) &
                # 条件2: (卖出慢线 / 卖出快线) 的比率也在定义的区间内
                (dataframe['sell-slowMA'].div(dataframe['sell-fastMA'])
                    > self.sell_div_min.value) &
                (dataframe['sell-slowMA'].div(dataframe['sell-fastMA'])
                    < self.sell_div_max.value)
            ),
            'exit_long'] = 1
        return dataframe
