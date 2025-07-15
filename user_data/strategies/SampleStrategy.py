# --- 策略总结 ---
# 策略名称: SampleStrategy (官方示例策略)
# 策略类型: 综合性教学/模板代码
#
# 盈利逻辑:
# 这是一个官方提供的、结构非常完整和清晰的策略模板，它演示了一种经典的"顺势回调"交易法，并展示了Freqtrade的多种核心功能。
#   - 核心交易逻辑 (顺势回调):
#       1. 判断大趋势: 使用一条长期EMA均线 (如200周期) 作为"牛熊分界线"。只有当价格在均线之上时，才认为市场处于上升趋势，并考虑买入。
#       2. 等待回调: 在确认上升趋势后，策略并不会立即追高买入，而是等待价格回调 (下跌) 触及或跌破布林带下轨。这是一种试图在上升趋势中寻找相对低点入场的技巧。
#       3. 动量确认: 在价格回调至布林带下轨后，策略会等待RSI指标重新上穿一个低位阈值 (如30)，以确认下跌动能已经耗尽、上涨动能回归，避免"接飞刀"。
#   - 卖出逻辑: 当RSI进入超买区，或价格向上突破布林带上轨时，认为行情可能短期见顶，产生卖出信号。
#
# 展示的核心功能:
#   - 清晰的结构: 完整地展示了一个策略文件应有的各个部分 (参数、指标、买卖逻辑、止盈止损等)。
#   - 超参数优化: 演示了如何为买入和卖出条件定义可优化的参数。
#   - 图表绘制: 通过 `plot_config` 展示了如何将所有用到的指标清晰地绘制在图表上。
#   - 高级回调函数: 通过 `order_filled_callback` 展示了如何在订单成交后执行自定义操作（如此处示例的发送邮件通知），这是非常高级和实用的功能。
#
# 总结:
# 这是一个绝佳的、教科书级别的Freqtrade策略范例。任何想要学习或开发自己策略的用户都应该从理解和模仿这个策略开始。
# 它本身提出的交易逻辑 (顺势回调) 也是一种非常经典和稳健的思路。

# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# isort: skip_file
# --- 请勿删除这些导入 ---
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pandas as pd
from pandas import DataFrame

from freqtrade.strategy import (
    IStrategy,
    BooleanParameter,
    IntParameter,
    RealParameter,
    Trade,
    Order
)

# --------------------------------
# 在此导入您的库
import talib.abstract as ta
from technical import qtpylib

logger = logging.getLogger(__name__)


class SampleStrategy(IStrategy):
    """
    这是一个基于趋势跟踪和回调入场的策略模板。

    策略买入条件:
    - 资产处于一个已建立的上升趋势中 (收盘价高于一条慢速EMA)。
    - 价格经历了一次回调至布林带下轨。
    - RSI确认资产不处于强烈的下跌动能中。

    策略卖出条件:
    - RSI上穿进入超买区域。
    - 价格向上突破布林带上轨。
    - 触发追踪止损。
    - 触发基于ROI的止盈。
    """
    # 策略接口版本 - 允许策略接口的新迭代。
    # 查看文档或示例策略以获取最新版本。
    INTERFACE_VERSION = 3

    # 策略的最佳时间框架。
    timeframe = "5m"

    # 该策略是否可以做空？
    can_short: bool = False

    # 为该策略设计的最小投资回报率(ROI)。
    # 如果配置文件中包含 "minimal_roi"，此属性将被覆盖。
    @property
    def minimal_roi(self):
        return {
            "60": self.roi_p1.value,
            "30": self.roi_p2.value,
            "0": self.roi_p3.value
        }
    roi_p1 = RealParameter(0.03, 0.08, default=0.05, space='roi', optimize=True)
    roi_p2 = RealParameter(0.08, 0.15, default=0.1, space='roi', optimize=True)
    roi_p3 = RealParameter(0.15, 0.25, default=0.2, space='roi', optimize=True)

    # 为该策略设计的优化止损。
    # 如果配置文件中包含 "stoploss"，此属性将被覆盖。
    stoploss = RealParameter(-0.15, -0.05, default=-0.10, space='protection', optimize=True)

    # 追踪止损
    trailing_stop = BooleanParameter(default=True, space='protection', optimize=True)
    trailing_stop_positive = RealParameter(0.005, 0.02, default=0.01, space='protection', optimize=True)
    trailing_stop_positive_offset = RealParameter(0.03, 0.08, default=0.05, space='protection', optimize=True)
    trailing_only_offset_is_reached = BooleanParameter(default=True, space='protection', optimize=True)

    # 仅在新蜡烛图上运行 "populate_indicators()"。
    process_only_new_candles = True

    # 这些值可以在配置中被覆盖。
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # 策略产生有效信号前需要的最少蜡烛图数量
    startup_candle_count: int = 200

    # --- 策略的可超参数优化参数 ---

    # 入场参数
    buy_ema_slow_period = IntParameter(100, 200, default=200, space="buy", optimize=True)
    buy_rsi_value = IntParameter(20, 40, default=30, space="buy", optimize=True)
    buy_rsi_period = IntParameter(10, 20, default=14, space="buy", optimize=True)
    buy_bb_window = IntParameter(10, 50, default=20, space="buy", optimize=True)
    buy_bb_std = RealParameter(1.5, 3.0, default=2.0, space="buy", optimize=True)

    # 退场参数
    sell_rsi_value = IntParameter(60, 80, default=75, space="sell")
    
    # 可选的订单类型映射。
    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": False
    }

    # 可选的订单有效时间。
    order_time_in_force = {
        "entry": "GTC",
        "exit": "GTC"
    }
    
    @property
    def plot_config(self):
        """图表绘制配置"""
        return {
            # 主图指标 (移动平均线, ...)
            "main_plot": {
                "ema_slow": {"color": "red"},
                "bb_upperband": {"color": "grey"},
                "bb_middleband": {"color": "orange"},
                "bb_lowerband": {"color": "grey"},
            },
            "subplots": {
                "RSI": {
                    "rsi": {"color": "red"},
                }
            }
        }

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        向给定的DataFrame中添加必要的指标
        :param dataframe: 来自交易所的数据帧
        :param metadata: 附加信息，如当前交易对
        :return: 包含所有策略所需指标的数据帧
        """
        # --- 用于入场的指标 ---

        # 用于趋势确认的EMA
        dataframe['ema_slow'] = ta.EMA(dataframe, timeperiod=self.buy_ema_slow_period.value)

        # 用于回调检测的布林带
        bollinger = qtpylib.bollinger_bands(
            qtpylib.typical_price(dataframe),
            window=self.buy_bb_window.value,
            stds=self.buy_bb_std.value
        )
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_middleband'] = bollinger['mid']
        dataframe['bb_upperband'] = bollinger['upper']

        # 用于动量确认的RSI
        dataframe['rsi'] = ta.RSI(dataframe, timeperiod=self.buy_rsi_period.value)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        基于TA指标，为给定的dataframe填充入场信号
        :param dataframe: DataFrame
        :param metadata: 附加信息，如当前交易对
        :return: 填充了入场信号列的DataFrame
        """
        dataframe.loc[
            (
                (dataframe['close'] > dataframe['ema_slow']) &          # 1. 主趋势看涨 (价格 > 慢速EMA)
                (dataframe['close'] < dataframe['bb_lowerband']) &      # 2. 价格回调至布林带下轨之下
                (qtpylib.crossed_above(dataframe['rsi'], self.buy_rsi_value.value)) &  # 3. RSI上穿指定值，确认动能回归
                (dataframe['volume'] > 0)                               # 确保交易量不为0
            ),
            "enter_long"] = 1
        
        # 记录当前价格和目标价格 (用于调试或分析)
        last_candle = dataframe.iloc[-1].copy()
        current_price = last_candle['close']
        buy_target_price = last_candle['bb_lowerband']
        
        # 确保买入目标价不为NaN，否则计算会失败
        if pd.notna(buy_target_price):
            price_diff = current_price - buy_target_price
            direction = "下跌" if price_diff > 0 else "上涨"
            distance_percentage = (abs(price_diff) / current_price) * 100

            logger.info(
                f"[{metadata['pair']}] "
                f"当前价格: {current_price:.4f}, "
                f"买入目标 (bb_lowerband): {buy_target_price:.4f}. "
                f"需要 {direction} {abs(price_diff):.4f} ({distance_percentage:.2f}%) 才能考虑入场。"
            )

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        基于TA指标，为给定的dataframe填充退场信号
        :param dataframe: DataFrame
        :param metadata: 附加信息，如当前交易对
        :return: 填充了退场信号列的DataFrame
        """
        dataframe.loc[
            (
                # 信号1: RSI 上穿进入超买区
                (qtpylib.crossed_above(dataframe["rsi"], self.sell_rsi_value.value)) |
                # 信号2: 价格上穿布林带上轨
                (qtpylib.crossed_above(dataframe["close"], dataframe["bb_upperband"]))
            ),
            "exit_long"] = 1
        return dataframe

    def order_filled_callback(self, pair: str, trade: Trade, order: Order, **kwargs) -> None:
        """
        当一个订单被成交时调用。
        此示例中，用于为开仓订单发送邮件通知。
        注意: 要使用此功能, 你需要在 `config.json` 的 `custom_info` 中配置email相关信息。
        """
        super().order_filled_callback(pair, trade, order, **kwargs)

        # 我们只希望在开仓交易的入场订单成交时发送通知
        if not trade.is_open or order.ft_order_type != 'entry':
            return

        # 避免为同一次入场发送多次邮件 (例如，由部分成交引起)
        if trade.custom_info.get('entry_notified'):
            return

        email_config = self.config.get('custom_info', {}).get('email')

        if not email_config:
            logger.warning("在 'config.json' 的 'custom_info' 下未找到email配置。跳过邮件通知。")
            return

        msg = MIMEMultipart()
        msg['From'] = email_config['username']
        msg['To'] = email_config['recipient']
        msg['Subject'] = f"Freqtrade 买入信号执行: {pair}"

        body = (
            f"一个买入订单已成功成交: {pair}。\n\n"
            f"交易ID: {trade.id}\n"
            f"数量: {order.amount_filled}\n"
            f"开仓价格: {order.average}\n"
            f"开仓日期 (UTC): {trade.open_date_utc}\n\n"
            "这是一条来自您的Freqtrade机器人的自动通知。"
        )
        msg.attach(MIMEText(body, 'plain'))

        try:
            # 使用 SMTP_SSL 建立安全连接
            with smtplib.SMTP_SSL(email_config['smtp_server'], email_config['smtp_port']) as server:
                server.login(email_config['username'], email_config['password'])
                server.send_message(msg)
                logger.info(f"成功发送 {pair} 的买入通知邮件。")
                # 标记我们已为此入场发送了通知
                trade.custom_info['entry_notified'] = True
        except Exception as e:
            logger.error(f"发送 {pair} 的邮件通知失败: {e}")