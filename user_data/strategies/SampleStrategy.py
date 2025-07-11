# pragma pylint: disable=missing-docstring, invalid-name, pointless-string-statement
# flake8: noqa: F401
# isort: skip_file
# --- Do not remove these imports ---
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
# Add your lib to import here
import talib.abstract as ta
from technical import qtpylib

logger = logging.getLogger(__name__)


class SampleStrategy(IStrategy):
    """
    This is a strategy template based on trend following and pullback entries.

    The strategy buys when:
    - The asset is in an established uptrend (close price is above a slow EMA).
    - The price experiences a pullback to the lower Bollinger Band.
    - The RSI confirms that the asset is not in a strong downtrend momentum.

    The strategy sells when:
    - The RSI crosses into the overbought territory.
    - The price breaks out above the upper Bollinger Band.
    - A trailing stop-loss is hit.
    - A ROI-based take-profit is hit.
    """
    # Strategy interface version - allow new iterations of the strategy interface.
    # Check the documentation or the Sample strategy to get the latest version.
    INTERFACE_VERSION = 3

    # Optimal timeframe for the strategy.
    timeframe = "5m"

    # Can this strategy go short?
    can_short: bool = False

    # Minimal ROI designed for the strategy.
    # This attribute will be overridden if the config file contains "minimal_roi".
    minimal_roi = {
        "60": 0.05,
        "30": 0.1,
        "0": 0.2
    }

    # Optimal stoploss designed for the strategy.
    # This attribute will be overridden if the config file contains "stoploss".
    stoploss = -0.10

    # Trailing stoploss
    trailing_stop = True
    trailing_stop_positive = 0.01
    trailing_stop_positive_offset = 0.05
    trailing_only_offset_is_reached = True

    # Run "populate_indicators()" only for new candle.
    process_only_new_candles = True

    # These values can be overridden in the config.
    use_exit_signal = True
    exit_profit_only = False
    ignore_roi_if_entry_signal = False

    # Number of candles the strategy requires before producing valid signals
    startup_candle_count: int = 200

    # --- Strategy Hyperoptable Parameters ---

    # Entry Parameters
    buy_ema_slow_period = IntParameter(100, 200, default=200, space="buy")
    buy_rsi_value = IntParameter(20, 40, default=30, space="buy")
    buy_bb_window = IntParameter(10, 50, default=20, space="buy")
    buy_bb_std = RealParameter(1.5, 3.0, default=2.0, space="buy")

    # Exit Parameters
    sell_rsi_value = IntParameter(60, 80, default=75, space="sell")
    # Optional order type mapping.
    order_types = {
        "entry": "limit",
        "exit": "limit",
        "stoploss": "market",
        "stoploss_on_exchange": False
    }

    # Optional order time in force.
    order_time_in_force = {
        "entry": "GTC",
        "exit": "GTC"
    }
    @property
    def plot_config(self):
        return {
            # Main plot indicators (Moving averages, ...)
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
        Adds the necessary indicators to the given DataFrame
        :param dataframe: Dataframe with data from the exchange
        :param metadata: Additional information, like the currently traded pair
        :return: a Dataframe with all mandatory indicators for the strategies
        """
        # --- Indicators for entry ---

        # EMA for trend confirmation
        dataframe['ema_slow'] = ta.EMA(dataframe, timeperiod=self.buy_ema_slow_period.value)

        # Bollinger Bands for pullback detection
        bollinger = qtpylib.bollinger_bands(
            qtpylib.typical_price(dataframe),
            window=self.buy_bb_window.value,
            stds=self.buy_bb_std.value
        )
        dataframe['bb_lowerband'] = bollinger['lower']
        dataframe['bb_middleband'] = bollinger['mid']
        dataframe['bb_upperband'] = bollinger['upper']

        # RSI for momentum
        dataframe['rsi'] = ta.RSI(dataframe)

        return dataframe

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the entry signal for the given dataframe
        :param dataframe: DataFrame
        :param metadata: Additional information, like the currently traded pair
        :return: DataFrame with entry columns populated
        """
        dataframe.loc[
            (
                (dataframe['close'] > dataframe['ema_slow']) &  # Main trend is bullish
                (dataframe['close'] < dataframe['bb_lowerband']) &  # Price is in a pullback
                (qtpylib.crossed_above(dataframe['rsi'], self.buy_rsi_value.value)) &  # Momentum confirmation
                (dataframe['volume'] > 0)  # Make sure Volume is not 0
            ),
            "enter_long"] = 1
        
        # Log current price and target
        last_candle = dataframe.iloc[-1].copy()
        current_price = last_candle['close']
        buy_target_price = last_candle['bb_lowerband']
        # Ensure buy_target_price is not NaN, otherwise calculations will fail
        if pd.notna(buy_target_price):
            price_diff = current_price - buy_target_price
            direction = "fall" if price_diff > 0 else "rise"
            distance_percentage = (abs(price_diff) / current_price) * 100

            logger.info(
                f"[{metadata['pair']}] "
                f"Current price: {current_price:.4f}, "
                f"Buy Target (bb_lowerband): {buy_target_price:.4f}. "
                f"Needs to {direction} by {abs(price_diff):.4f} ({distance_percentage:.2f}%) to be considered for entry."
            )

        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        Based on TA indicators, populates the exit signal for the given dataframe
        :param dataframe: DataFrame
        :param metadata: Additional information, like the currently traded pair
        :return: DataFrame with exit columns populated
        """
        dataframe.loc[
            (
                # Signal: RSI crosses above sell_rsi
                (qtpylib.crossed_above(dataframe["rsi"], self.sell_rsi_value.value)) |
                # Signal: Price crosses above upper BB
                (qtpylib.crossed_above(dataframe["close"], dataframe["bb_upperband"]))
            ),
            "exit_long"] = 1
        return dataframe

    def order_filled_callback(self, pair: str, trade: Trade, order: Order, **kwargs) -> None:
        """
        Called when an order is filled.
        Sends an email notification for entry orders.
        """
        super().order_filled_callback(pair, trade, order, **kwargs)

        # We only want to notify for entry orders that open a trade
        if not trade.is_open or order.ft_order_type != 'entry':
            return

        # Avoid sending multiple emails for the same entry (e.g. from partial fills)
        if trade.custom_info.get('entry_notified'):
            return

        email_config = self.config.get('custom_info', {}).get('email')

        if not email_config:
            logger.warning("Email config not found in 'config.json' under 'custom_info'. Skipping email notification.")
            return

        msg = MIMEMultipart()
        msg['From'] = email_config['username']
        msg['To'] = email_config['recipient']
        msg['Subject'] = f"Freqtrade Buy Signal Executed: {pair}"

        body = (
            f"A buy order has been successfully filled for {pair}.\n\n"
            f"Trade ID: {trade.id}\n"
            f"Amount: {order.amount_filled}\n"
            f"Open Rate: {order.average}\n"
            f"Open Date (UTC): {trade.open_date_utc}\n\n"
            "This is an automated notification from your Freqtrade bot."
        )
        msg.attach(MIMEText(body, 'plain'))

        try:
            # Use SMTP_SSL for a secure connection
            with smtplib.SMTP_SSL(email_config['smtp_server'], email_config['smtp_port']) as server:
                server.login(email_config['username'], email_config['password'])
                server.send_message(msg)
                logger.info(f"Successfully sent buy notification email for {pair}.")
                # Mark that we have notified for this entry
                trade.custom_info['entry_notified'] = True
        except Exception as e:
            logger.error(f"Failed to send email notification for {pair}: {e}")