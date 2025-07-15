# Freqtrade_backtest_validation_freqtrade1.py
# 这个脚本是配对脚本中的一个，另一个是 freqtrade_backtest_validation_tradingview1
# 这两个脚本应该在它们各自的平台（Freqtrade, TradingView）上，针对相同的币种/周期/分辨率进行执行。
# 其目的是为了测试 Freqtrade 的回测是否能提供与一个已知的行业平台（TradingView）相似的结果。
#
# --- Do not remove these libs ---
from freqtrade.strategy import IStrategy
from pandas import DataFrame
# --------------------------------

# Add your lib to import here
import talib.abstract as ta
import freqtrade.vendor.qtpylib.indicators as qtpylib


class Freqtrade_backtest_validation_freqtrade1(IStrategy):
    """
    策略名称: Freqtrade回测验证策略1
    策略类型: 基准测试 / 软件验证

    ## 策略核心目的

    **警告：这是一个纯粹用于软件功能验证的策略，并非为盈利而设计。**

    本策略的唯一目的是作为一个**基准测试工具**，用于验证 Freqtrade 的回测引擎。
    通过在 Freqtrade 和另一个行业标准平台（如TradingView）上运行完全相同的、最简单的交易逻辑，
    并比对两者的回测结果是否相似，可以判断 Freqtrade 回测引擎的准确性和可靠性。

    ### 策略逻辑: 经典SMA均线交叉

    为了确保结果的纯粹性和可比性，策略采用了最广为人知、最无歧义的交易逻辑：
    - **指标**: 14周期SMA（快线）和28周期SMA（慢线）。
    - **买入条件**: 当 `快线 > 慢线` 时（金叉状态）。
    - **卖出条件**: 当 `快线 < 慢线` 时（死叉状态）。

    ### 参数设置

    策略的止盈（`minimal_roi`）和止损（`stoploss`）都被设置成了极端的、几乎不可能达到的值。
    这是为了确保在回测中，绝大多数交易的开平仓都**仅仅**由均线交叉信号触发，从而排除其他变量的干扰，
    使得在不同平台间的核心逻辑对比尽可能"干净"。
    """
    INTERFACE_VERSION: int = 3
    # 一个极端的ROI表，确保它基本不会被触发
    minimal_roi = {
        "40": 2.0,
        "30": 2.01,
        "20": 2.02,
        "0": 2.04
    }
    # 一个极端的止损，确保它基本不会被触发
    stoploss = -0.90
    timeframe = '1h'

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        # SMA - 简单移动平均线
        dataframe['fastMA'] = ta.SMA(dataframe, timeperiod=14) # 快线
        dataframe['slowMA'] = ta.SMA(dataframe, timeperiod=28) # 慢线
        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义买入信号: 快线处于慢线上方
        """
        dataframe.loc[
            (
                (dataframe['fastMA'] > dataframe['slowMA'])
            ),
            'enter_long'] = 1

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        定义卖出信号: 快线处于慢线下方
        """
        dataframe.loc[
            (
                (dataframe['fastMA'] < dataframe['slowMA'])
            ),
            'exit_long'] = 1
        return dataframe
