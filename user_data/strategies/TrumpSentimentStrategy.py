import logging
import json
import csv
from pathlib import Path
from datetime import datetime, timezone, timedelta
from functools import wraps

# 新增: 导入阿里百炼SDK
import dashscope
import requests
from pandas import DataFrame
import pandas as pd

from freqtrade.persistence import Trade
from freqtrade.strategy import IStrategy

# 日志记录器
logger = logging.getLogger(__name__)

# --- 缓存配置 ---
# 定义缓存文件路径在 user_data 目录下
CACHE_DIR = Path(__file__).parent.parent / 'user_data'
CACHE_FILE = CACHE_DIR / 'twitter_cache.json'
# 缓存有效期（秒）
# 只有当缓存文件超过这个时间，我们才会再次调用推特API
# 60秒可以有效避免在测试或快速重启时触发速率限制
CACHE_TTL_SECONDS = 6000000000

# --- 常量配置 ---
# 唐纳德·特朗普在X（推特）上的用户ID
# 你可以访问 https://tweeterid.com/ 网站查找任何用户的ID
TRUMP_TWITTER_USER_ID = '25073877'
# 推特API V2的端点
TWITTER_API_URL = f'https://api.twitter.com/2/users/{TRUMP_TWITTER_USER_ID}/tweets'
# OpenAI API的端点 - 这行可以删掉或者留着作为参考
# OPENAI_API_URL = 'https://api.openai.com/v1/chat/completions'


def handle_api_errors(func):
    """一个装饰器，用于优雅地处理API请求中的异常。"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except requests.exceptions.RequestException as e:
            logger.warning(f"调用 {func.__name__} 时发生网络错误: {e}")
            return None
        # 新增: 捕获DashScope的API异常
        except dashscope.api_entities.errors.ApiException as e:
            logger.warning(f"调用阿里百炼API时发生错误: {e}")
            return None
        except Exception as e:
            logger.error(f"调用 {func.__name__} 时发生未知错误: {e}")
            return None
    return wrapper


class TrumpSentimentStrategy(IStrategy):
    """
    一个基于唐纳德·特朗普推文情绪进行交易的策略。

    工作流程:
    1. 在每个时间周期，策略会检查是否有新的推文（会优先使用本地缓存）。
    2. 如果有新推文，则调用阿里百炼API分析其情绪（买入/卖出/持有）。
    3. 根据情绪分析结果，对指定的交易对（如 'TRUMP/USDT'）执行买入或卖出操作。

    重要提示:
    - 这是一个高风险的实验性策略。
    - AI情绪分析的准确性无法保证。
    - 市场可能不会对推文做出预期的反应。
    - **请务必在模拟模式下进行充分测试，并自行承担风险。**
    """
    # --- 策略元数据 ---
    timeframe = '1h'  # 建议使用较长的时间框架，以减少API调用频率

    # --- ROI 和止损设置 ---
    minimal_roi = {"0": 100} # 禁用ROI退出，完全依赖卖出信号
    stoploss = -0.99 # 禁用止损，完全依赖卖出信号

    # --- 状态变量 ---
    # 使用类级别变量，确保在机器人运行期间，缓存和推文ID在内存中共享
    _twitter_cache = {"timestamp": 0, "data": None}
    last_tweet_ids = {}

    def __init__(self, config: dict) -> None:
        """
        初始化函数，在策略启动时调用一次。
        用于加载配置和缓存。
        """
        super().__init__(config)
        custom_info = config.get('custom_info', {})

        self.twitter_bearer_token = custom_info.get('twitter_bearer_token')
        self.bailian_api_key = custom_info.get('bailian_api_key')
        self.target_pair = custom_info.get('target_pair', 'TRUMP/USDT')

        if not self.twitter_bearer_token or not self.bailian_api_key:
            raise ValueError(
                "请在您的 config.json 文件中配置 "
                "'twitter_bearer_token' 和 'bailian_api_key'。"
            )
        
        # 配置DashScope的API Key
        dashscope.api_key = self.bailian_api_key
        
        # --- 模式判断与数据加载 ---
        self.historical_signals = None
        if self.config['runmode'] == 'backtest':
            historical_signals_file = Path(self.config['user_data_dir']) / 'historical_signals.json'
            if historical_signals_file.exists():
                logger.info(f"回测模式：正在从 {historical_signals_file} 加载历史信号。")
                with open(historical_signals_file, 'r') as f:
                    # 将加载的信号转换为以时间戳为键的字典，方便快速查找
                    signals_list = json.load(f)
                    self.historical_signals = {}
                    for signal in signals_list:
                        ts = pd.to_datetime(signal['timestamp']).floor('1min')
                        self.historical_signals[ts] = signal['signal']
                logger.info(f"已加载 {len(self.historical_signals)} 条历史信号。")
            else:
                logger.warning("回测模式：未找到 historical_signals.json 文件。")
                logger.warning("请先运行 user_data/download_historical_tweets.py 脚本。")
        else: # 实盘或模拟盘
            # 确保缓存目录存在并加载初始缓存 (仅实盘需要)
            CACHE_DIR.mkdir(exist_ok=True)
            self._load_cache()
        
        logger.info(f"特朗普情绪策略已初始化。目标交易对: {self.target_pair}，运行模式: {self.config['runmode']}。")

    def _init_backtest_log(self):
        """如果日志不存在，则创建并写入CSV表头。"""
        if self.backtest_log_file.exists():
            logger.info(f"回测日志文件已存在: {self.backtest_log_file}")
            self.backtest_log_initialized = True
            return
        try:
            with open(self.backtest_log_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'timestamp', 'tweet_text', 'ai_prompt', 
                    'ai_raw_response', 'ai_conclusion', 'price_at_signal'
                ])
            self.backtest_log_initialized = True
            logger.info(f"回测日志已初始化: {self.backtest_log_file}")
        except Exception as e:
            logger.error(f"无法初始化回测日志: {e}")

    def _log_backtest_record(self, record: dict):
        """向CSV日志文件追加一条记录。"""
        if not self.backtest_log_initialized:
            logger.error("无法写入日志，因为日志文件未初始化。")
            return
        try:
            with open(self.backtest_log_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    record.get('timestamp'),
                    record.get('tweet_text'),
                    record.get('ai_prompt'),
                    record.get('ai_raw_response'),
                    record.get('ai_conclusion'),
                    record.get('price_at_signal')
                ])
        except Exception as e:
            logger.error(f"写入回测日志失败: {e}")

    def _load_cache(self):
        """如果缓存文件存在，则从中加载推文数据到内存。"""
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, 'r') as f:
                    self.__class__._twitter_cache = json.load(f)
                    logger.info(f"已从以下文件加载推特缓存: {CACHE_FILE}")
            except Exception as e:
                logger.warning(f"无法加载缓存文件，将重新获取: {e}")

    def _save_cache(self, data: list):
        """将新的推文数据保存到缓存文件和内存中。"""
        cache_content = {
            "timestamp": datetime.now(timezone.utc).timestamp(),
            "data": data
        }
        try:
            with open(CACHE_FILE, 'w') as f:
                json.dump(cache_content, f)
            self.__class__._twitter_cache = cache_content
            logger.info(f"已将推特API响应保存至缓存: {CACHE_FILE}")
        except Exception as e:
            logger.warning(f"无法保存缓存文件: {e}")

    @handle_api_errors
    def get_latest_tweet(self, pair: str) -> dict | None:
        """
        获取最新的推文，优先使用缓存以避免不必要的API调用。
        """
        now_ts = datetime.now(timezone.utc).timestamp()
        cache_ts = self.__class__._twitter_cache.get("timestamp", 0)
        tweets = None

        # 检查缓存是否有效
        if (now_ts - cache_ts) < CACHE_TTL_SECONDS:
            logger.info("推特缓存有效，正在使用缓存数据。")
            tweets = self.__class__._twitter_cache.get("data")
        else:
            # 缓存过期或不存在，调用API
            logger.info("推特缓存已过期或不存在，正在调用API。")
            headers = {'Authorization': f'Bearer {self.twitter_bearer_token}'}
            params = {'max_results': 5, 'exclude': 'replies,retweets'}
            
            response = requests.get(TWITTER_API_URL, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            
            api_response = response.json()
            tweets = api_response.get('data', [])
            
            # 保存新数据到缓存
            self._save_cache(tweets)
            
        if not tweets:
            return None

        latest_tweet = tweets[0]
        tweet_id = latest_tweet['id']

        # 避免重复处理同一条推文的逻辑保持不变
        last_tweet_id = self.last_tweet_ids.get(pair)

        if tweet_id != last_tweet_id:
            logger.info(f"检测到新推文 (ID: {tweet_id}): {latest_tweet['text'][:80]}...")
            self.last_tweet_ids[pair] = tweet_id
            return latest_tweet
        
        logger.info(f"未检测到新推文。已处理的最新推文ID: {last_tweet_id}")
        return None

    @handle_api_errors
    def get_sentiment(self, text: str) -> str | None:
        """
        使用阿里百炼(DashScope)API分析推文的情绪。
        返回一个包含AI交互详细信息的字典。
        """
        prompt = (
            f"请分析以下来自唐纳德·特朗普的推文，判断它对 'TRUMP' 加密货币的情绪影响。"
            f"只用一个词回答：'BUY'（如果情绪非常积极，可能导致价格上涨），"
            f"'SELL'（如果情绪非常消极，可能导致价格下跌），"
            f"或者 'HOLD'（如果情绪中性或无关）。\n\n"
            f"推文内容: \"{text}\"\n\n"
            f"你的判断是："
        )

        # 使用阿里百炼的qwen-turbo模型进行调用
        response = dashscope.Generation.call(
            model=dashscope.Generation.Models.qwen_turbo,
            prompt=prompt,
            temperature=0, # 我们需要确定性的结果
        )

        # 构造包含详细信息的返回结果
        result = {
            "prompt": prompt,
            "raw_response": f"Status: {response.status_code}, Output: {response.output}, Message: {response.message}",
            "conclusion_internal": "HOLD"  # 默认为HOLD
        }

        # 检查API调用是否成功
        if response.status_code == 200:
            sentiment = response.output.text.strip().upper()
            if sentiment in ['BUY', 'SELL', 'HOLD']:
                logger.info(f"AI情绪分析结果: {sentiment}")
                result["conclusion_internal"] = sentiment
            else:
                logger.warning(f"收到未知的AI情绪分析结果: {sentiment}")
        else:
            logger.error(f"阿里百炼API请求失败: Code: {response.status_code}, "
                         f"Message: {response.message}")
            return None # API失败时返回None
            
        return result

    def populate_indicators(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        这是策略的主要逻辑部分。
        根据运行模式，选择不同的信号生成方式。
        """
        # 只对我们指定的目标交易对执行逻辑
        if metadata['pair'] != self.target_pair:
            dataframe['sentiment_signal'] = 0
            return dataframe

        dataframe['sentiment_signal'] = 0  # 默认为'HOLD' (0)

        # --- 根据运行模式选择逻辑 ---
        if self.config['runmode'] == 'backtest':
            # --- 回测逻辑：使用预先生成的历史信号 ---
            if self.historical_signals:
                # 将DataFrame的索引（K线时间）也对齐到分钟，以便匹配
                dataframe_ts_min = dataframe['date'].dt.floor('1min')
                # 使用map高效地将信号应用到DataFrame
                dataframe['signal_lookup'] = dataframe_ts_min.map(self.historical_signals)
                
                signal_map = {'BUY': 1, 'SELL': -1}
                dataframe['sentiment_signal'] = dataframe['signal_lookup'].map(signal_map).fillna(0)
                dataframe.drop(columns=['signal_lookup'], inplace=True)
        
        else:
            # --- 实盘/模拟盘逻辑：使用实时"哨兵"模式 ---
            new_tweet = self.get_latest_tweet(metadata['pair'])
            if new_tweet:
                sentiment_details = self.get_sentiment(new_tweet['text'])
                if sentiment_details:
                    signal = 0
                    conclusion_internal = sentiment_details.get('conclusion_internal', 'HOLD')
                    if conclusion_internal == 'BUY':
                        signal = 1
                    elif conclusion_internal == 'SELL':
                        signal = -1
                    dataframe.loc[dataframe.index[-1], 'sentiment_signal'] = signal

        # 回测日志记录逻辑保持不变，但现在应在回测模式下工作
        if self.config['runmode'] == 'backtest':
            self._log_backtest_records_from_dataframe(dataframe)
            
        return dataframe
    
    def _log_backtest_records_from_dataframe(self, dataframe: DataFrame):
        """在回测中，从匹配到信号的dataframe行记录日志。"""
        if not self.backtest_log_initialized:
            return

        # 筛选出有信号的行
        signalled_df = dataframe[dataframe['sentiment_signal'] != 0].copy()

        for _, row in signalled_df.iterrows():
            ts = row['date'].floor('1min')
            signal_text = self.historical_signals.get(ts, "UNKNOWN") # 这里我们没有原文和prompt，需要简化日志
            
            conclusion_map = {'BUY': '看多合约', 'SELL': '看空合约'}
            log_record = {
                "timestamp": row['date'],
                "tweet_text": "N/A in backtest (see historical_signals.json)",
                "ai_prompt": "N/A in backtest",
                "ai_raw_response": "N/A in backtest",
                "ai_conclusion": conclusion_map.get(signal_text, '未知'),
                "price_at_signal": row['close']
            }
            self._log_backtest_record(log_record)

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        根据情绪信号决定买入条件。
        """
        if metadata['pair'] != self.target_pair:
            return dataframe

        dataframe.loc[
            (dataframe['sentiment_signal'] == 1), # 1 代表 'BUY'
            'enter_long'] = 1
        
        return dataframe

    def populate_exit_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        """
        根据情绪信号决定卖出条件。
        """
        if metadata['pair'] != self.target_pair:
            return dataframe

        dataframe.loc[
            (dataframe['sentiment_signal'] == -1), # -1 代表 'SELL'
            'exit_long'] = 1
            
        return dataframe

    def confirm_trade_exit(self, pair: str, trade: Trade, order_type: str, amount: float,
                             rate: float, time_in_force: str, exit_reason: str,
                             current_time: datetime, **kwargs) -> bool:
        """
        在卖出时打印日志，方便追踪。
        """
        logger.info(
            f"交易退出确认: {pair}, "
            f"退出原因: {exit_reason}, "
            f"利润: {trade.calc_profit_ratio(rate):.2%}"
        )
        return True 