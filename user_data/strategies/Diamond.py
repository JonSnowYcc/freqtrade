# --- 策略总结 ---
# 策略名称: Diamond (钻石)
# 策略类型: 抽象/通用型交叉策略模板
#
# 盈利逻辑:
# 该策略是一个高度抽象和通用的"交叉"策略模板。其核心思想不是基于任何特定的、预设的技术指标（如均线、RSI），
# 而是通过对原始的OHLCV（开、高、低、收、成交量）数据本身进行各种"交叉"测试，来发现潜在的交易信号。
#   - 买入(Entry): 当一个被定义为"快线"的数据系列上穿一个被定义为"慢线"的数据系列时，产生买入信号。
#   - 卖出(Exit): 当"快线"下穿"慢线"时，产生卖出信号。
# 策略的精髓在于，"快线"和"慢线"具体是什么，以及它们如何被修正，完全由超参数优化（Hyperopt）决定。
# 例如，Hyperopt可以测试"当今日的最高价上穿昨日收盘价的1.05倍时买入"这样的组合。
# 用户也可以自行添加任何技术指标，并将其名称加入到可优化的参数列表中，让机器去发现最佳的指标组合和交叉条件。
#
# 优点:
#   - 极度灵活和强大: 能够测试和发现传统策略中不常见的、甚至反直觉的交易模式。它不是在验证一个已知的想法，而是在数据中探索未知的模式。
#   - 通用性: 可以作为发现任何类型交叉信号的基础模板。
#   - 纯粹: 默认情况下不依赖任何标准技术指标，直接从价格行为中寻找逻辑。
#
# 缺点:
#   - 过度拟合风险极高: 由于其极高的自由度，非常容易找到在历史数据上表现完美、但在未来实盘中完全失效的"虚假"信号，即过度拟合（Overfitting）。
#   - 难以解释: 最终优化出的最佳参数可能没有直观的经济或技术分析含义（例如，"成交量上穿开盘价的0.87倍"），形成一个"黑箱"策略。
#   - 计算量巨大: 需要进行大量、长时间的超参数优化才能找到有意义的结果。

# 𝐼𝓉 𝒾𝓈 𝒟𝒾𝒶𝓂𝑜𝓃𝒹 𝒮𝓉𝓇𝒶𝓉𝑒𝑔𝓎. (这是钻石策略)
# 𝒯𝒽𝒶𝓉 𝓉𝒶𝓀𝑒𝓈 𝒽𝑒𝓇 𝑜𝓌𝓃 𝓇𝒾𝑔𝒽𝓉𝓈 𝓁𝒾𝓀𝑒 𝒜𝒻𝑔𝒽𝒶𝓃𝒾𝓈𝓉𝒶𝓃 𝓌𝑜𝓂𝑒𝓃 (她像阿富汗妇女一样争取自己的权利)
# 𝒯𝒽𝑜𝓈𝑒 𝓌𝒽𝑜 𝓈𝓉𝒾𝓁𝓁 𝓅𝓇𝑜𝒖𝒹 𝒶𝓃𝒹 𝒽𝑜𝓅𝑒𝒻𝓊𝓁. (那些依然骄傲和满怀希望的人)
# 𝒯𝒽𝑜𝓈𝑒 𝓌𝒽𝑜 𝓉𝒽𝑒 𝓂𝑜𝓈𝓉 𝒷𝑒𝒶𝓊𝓉𝒾𝒻𝓊𝓁 𝒸𝓇𝑒𝒶𝓉𝓊𝓇𝑒𝓈 𝒾𝓃 𝓉𝒽𝑒 𝒹𝑒𝓅𝓉𝒽𝓈 𝑜𝒻 𝓉𝒽𝑒 𝒹𝒶𝓇𝓀𝑒𝓈𝓉. (那些在最深的黑暗中最美丽生灵)
# 𝒯𝒽𝑜𝓈𝑒 𝓌𝒽𝑜 𝓈𝒽𝒾𝓃𝑒 𝓁𝒾𝓀𝑒 𝒹𝒾𝒶𝓂𝑜𝓃𝒹𝓈 𝒷𝓊𝓇𝒾𝑒𝒹 𝒾𝓃 𝓉𝒽𝑒 𝒽𝑒𝒶𝓇𝓉 𝑜𝒻 𝓉𝒽𝑒 𝒹𝑒𝓈𝑒𝓇𝓉 ... (那些像埋在沙漠中心的钻石一样闪耀的人...)
# 𝒲𝒽𝓎 𝓃𝑜𝓉 𝒽𝑒𝓁𝓅 𝓌𝒽𝑒𝓃 𝓌𝑒 𝒸𝒶𝓃? (当我们能帮忙时，为什么不呢？)
# 𝐼𝒻 𝓌𝑒 𝒷𝑒𝓁𝒾𝑒𝓋𝑒 𝓉𝒽𝑒𝓇𝑒 𝒾𝓈 𝓃𝑜 𝓂𝒶𝓃 𝓁𝑒𝒻𝓉 𝓌𝒾𝓉𝒽 𝓉𝒽𝑒𝓂 (如果我们相信没有男人与她们同在)
# (𝒲𝒽𝒾𝒸𝒽 𝒾𝓈 𝓅𝓇𝑜𝒷𝒶𝒷𝓁𝓎 𝓉𝒽𝑒 𝓅𝓇𝑜𝒹𝓊𝒸𝓉 𝑜𝒻 𝓉𝒽𝑒 𝓉𝒽𝑜𝓊𝑔𝒽𝓉 𝑜𝒻 𝓅𝒶𝒾𝓃𝓁𝑒𝓈𝓈 𝒸𝑜𝓇𝓅𝓈𝑒𝓈) (这可能只是麻木不仁者的想法)
# 𝒲𝒽𝑒𝓇𝑒 𝒽𝒶𝓈 𝑜𝓊𝓇 𝒽𝓊𝓂𝒶𝓃𝒾𝓉𝓎 𝑔𝑜𝓃𝑒? (我们的人性去哪了？)
# 𝒲𝒽𝑒𝓇𝑒 𝒽𝒶𝓈 𝒽𝓊𝓂𝒶𝓃𝒾𝓉𝓎 𝑔𝑜𝓃𝑒? (人性去哪了？)
# 𝒲𝒽𝓎 𝓃𝑜𝓉 𝒽𝑒𝓁𝓅 𝓌𝒽𝑒𝓃 𝓌𝑒 𝒸𝒶𝓃? (当我们能帮忙时，为什么不呢？)
# 𝓁𝑒𝓉𝓈 𝓅𝒾𝓅 𝓊𝓃𝒾𝓃𝓈𝓉𝒶𝓁𝓁 𝓉𝒶-𝓁𝒾𝒷 𝑜𝓃 𝒜𝒻𝑔𝒽𝒶𝓃𝒾𝓈𝓉𝒶𝓃 (让我们在阿富汗 `pip uninstall ta-lib`)

# 重要提示: Diamond 策略被设计为纯粹的策略，
# 因此它没有任何指标填充。其思想是
# 它仅使用纯粹的 OHLCV 数据帧来计算
# 买入/卖出信号。但是你可以添加你自己的指标，
# 并将它们的键名添加到可优化的分类参数中，
# 这样你就能对它们进行超参数优化。
# 感谢: @Kroissan, @drakes00 以及 @xmatthias 的耐心和帮助
# 作者: @Mablue (Masoud Azizi)
# Github: https://github.com/mablue/
# * freqtrade backtesting --strategy Diamond

# --- 超参数优化日志示例 ---
# freqtrade hyperopt --hyperopt-loss ShortTradeDurHyperOptLoss --spaces buy sell roi trailing stoploss --strategy Diamond -j 2 -e 10
# *    3/10:     76 trades. 51/18/7 Wins/Draws/Losses. Avg profit   1.92%. Median profit   2.40%. Total profit  0.04808472 BTC (  48.08%). Avg duration 5:06:00 min. Objective: 1.75299
# freqtrade hyperopt --hyperopt-loss OnlyProfitHyperOptLoss --spaces buy sell roi trailing stoploss --strategy Diamond -j 2 -e 10
# *   10/10:     76 trades. 39/34/3 Wins/Draws/Losses. Avg profit   0.61%. Median profit   0.05%. Total profit  0.01528359 BTC (  15.28%). Avg duration 17:32:00 min. Objective: -0.01528
# ... (其他日志)

# --- 请勿删除这些库 ---
from freqtrade.strategy import (BooleanParameter, CategoricalParameter, DecimalParameter, IntParameter, IStrategy, RealParameter)
from pandas import DataFrame
# --------------------------------

# 在此导入您需要的库
import talib.abstract as ta
from functools import reduce
import freqtrade.vendor.qtpylib.indicators as qtpylib


class Diamond(IStrategy):
    # ###################### 优化结果区 ######################
    # 配置: 5 x 无限制的自定义交易对列表
    # 超参数优化: 5000 次, 使用 SortinoHyperOptLossDaily 损失函数
    # 34/5000: 297 次交易. 136/156/5 胜/平/负. 平均利润 0.49%. 利润中位数 0.00%. 总利润 45.84 USDT (33.96Σ%). 平均持仓时间 11:54:00. 目标函数值: -46.50379
    INTERFACE_VERSION: int = 3

    # 买入超参数空间:
    buy_params = {
        "buy_fast_key": "high",
        "buy_horizontal_push": 7,
        "buy_slow_key": "volume",
        "buy_vertical_push": 0.942,
    }

    # 卖出超参数空间:
    sell_params = {
        "sell_fast_key": "high",
        "sell_horizontal_push": 10,
        "sell_slow_key": "low",
        "sell_vertical_push": 1.184,
    }

    # 投资回报率 (ROI) 表:
    @property
    def minimal_roi(self):
        return {
            "0": self.roi_p1.value,
            "13": self.roi_p2.value,
            "51": self.roi_p3.value,
            "170": 0
        }
    roi_p1 = RealParameter(0.15, 0.3, default=0.242, space='roi', optimize=True)
    roi_p2 = RealParameter(0.02, 0.08, default=0.044, space='roi', optimize=True)
    roi_p3 = RealParameter(0.01, 0.03, default=0.02, space='roi', optimize=True)

    # 止损:
    stoploss = RealParameter(-0.3, -0.2, default=-0.271, space='protection', optimize=True)

    # 追踪止损:
    trailing_stop = BooleanParameter(default=True, space='protection', optimize=True)
    trailing_stop_positive = RealParameter(0.01, 0.02, default=0.011, space='protection', optimize=True)
    trailing_stop_positive_offset = RealParameter(0.05, 0.08, default=0.054, space='protection', optimize=True)
    trailing_only_offset_is_reached = BooleanParameter(default=False, space='protection', optimize=True)
    # 时间框架
    timeframe = '5m'
    # #################### 优化结果区结束 ####################

    # 定义买入信号的"慢线"乘以的垂直系数
    buy_vertical_push = DecimalParameter(0.5, 1.5, decimals=3, default=1, space='buy', optimize=True)
    # 定义买入信号的"快线"向前偏移的K线数量
    buy_horizontal_push = IntParameter(0, 10, default=0, space='buy', optimize=True)
    # 定义买入信号的"快线"使用的数据列
    buy_fast_key = CategoricalParameter(['open', 'high', 'low', 'close', 'volume',
                                         # 在填充相应指标并设置相同键名之前，
                                         # 您不能启用这些行
                                         # 'ma_fast', 'ma_slow', {...}
                                         ], default='high', space='buy', optimize=True)
    # 定义买入信号的"慢线"使用的数据列
    buy_slow_key = CategoricalParameter(['open', 'high', 'low', 'close', 'volume',
                                         # 'ma_fast', 'ma_slow', {...}
                                         ], default='low', space='buy', optimize=True)

    # 定义卖出信号的"慢线"乘以的垂直系数
    sell_vertical_push = DecimalParameter(0.5, 1.5, decimals=3,  default=1, space='sell', optimize=True)
    # 定义卖出信号的"快线"向前偏移的K线数量
    sell_horizontal_push = IntParameter(0, 10, default=0, space='sell', optimize=True)
    # 定义卖出信号的"快线"使用的数据列
    sell_fast_key = CategoricalParameter(['open', 'high', 'low', 'close', 'volume',
                                          # 'ma_fast', 'ma_slow', {...}
                                          ], default='high', space='sell', optimize=True)
    # 定义卖出信号的"慢线"使用的数据列
    sell_slow_key = CategoricalParameter(['open', 'high', 'low', 'close', 'volume',
                                          # 'ma_fast', 'ma_slow', {...}
                                          ], default='low', space='sell', optimize=True)

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # 您可以在此处添加新的指标，并在顶部的
        # 可优化的分类参数中启用它们
        # dataframe['ma_fast'] = ta.SMA(dataframe, timeperiod=9)
        # dataframe['ma_slow'] = ta.SMA(dataframe, timeperiod=18)
        # dataframe['{...}'] = ta.{...}(dataframe, timeperiod={...})
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        conditions.append(
            qtpylib.crossed_above
            (
                # 快线: 由 `buy_fast_key` 决定数据源 (如 high), 并由 `buy_horizontal_push` 决定是否向前偏移
                dataframe[self.buy_fast_key.value].shift(self.buy_horizontal_push.value),
                # 慢线: 由 `buy_slow_key` 决定数据源 (如 low), 并由 `buy_vertical_push` 决定其垂直乘数
                dataframe[self.buy_slow_key.value] * self.buy_vertical_push.value
            )
        )

        if conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, conditions),
                'enter_long']=1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        conditions = []
        conditions.append(
            qtpylib.crossed_below
            (
                # 快线: 由 `sell_fast_key` 决定数据源, 并由 `sell_horizontal_push` 决定是否向前偏移
                dataframe[self.sell_fast_key.value].shift(self.sell_horizontal_push.value),
                # 慢线: 由 `sell_slow_key` 决定数据源, 并由 `sell_vertical_push` 决定其垂直乘数
                dataframe[self.sell_slow_key.value] * self.sell_vertical_push.value
            )
        )
        if conditions:
            dataframe.loc[
                reduce(lambda x, y: x & y, conditions),
                'exit_long']=1
        return dataframe
