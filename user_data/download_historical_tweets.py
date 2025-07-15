import os
import json
import time
from pathlib import Path
from datetime import datetime, timezone

import requests
import dashscope
from tqdm import tqdm

# --- 配置 ---
# !!! 请确保您的API密钥在这里是正确的，或者从环境变量加载 !!!
# 从环境变量中获取密钥是更安全的做法
BAILIAN_API_KEY = os.getenv('BAILIAN_API_KEY', 'sk-b810649f5fc1465ab66c0a8c8bacbae3')
TWITTER_BEARER_TOKEN = os.getenv('TWITTER_BEARER_TOKEN', 'AAAAAAAAAAAAAAAAAAAAAIVI3AEAAAAALKZE2wZXqBD%2BZ6Rcknf2WHJWxRs%3DPM7POkSO8PtqbRSOcwl4bzZFv437c8A3UZKCa2bNWiVoPsD7pv')

# 唐纳德·特朗普在X（推特）上的用户ID
TRUMP_TWITTER_USER_ID = '25073877'
TWITTER_API_URL = f'https://api.twitter.com/2/users/{TRUMP_TWITTER_USER_ID}/tweets'

# 输出文件路径
# __file__ 是当前脚本的路径, .parent.parent 指向项目根目录
OUTPUT_DIR = Path(__file__).parent.parent / 'user_data'
OUTPUT_FILE = OUTPUT_DIR / 'historical_signals.json'

# --- API 调用封装 ---

def get_sentiment(text: str) -> dict:
    """使用阿里百炼API分析情绪，返回详细结果。"""
    prompt = (
        f"请分析以下来自唐纳德·特朗普的推文，判断它对 'TRUMP' 加密货币的情绪影响。"
        f"只用一个词回答：'BUY'（如果情绪非常积极），'SELL'（如果情绪非常消极），"
        f"或者 'HOLD'（如果情绪中性或无关）。\n\n"
        f"推文内容: \"{text}\"\n\n你的判断是："
    )
    try:
        response = dashscope.Generation.call(
            model=dashscope.Generation.Models.qwen_turbo,
            prompt=prompt,
            temperature=0,
        )
        if response.status_code == 200:
            sentiment = response.output.text.strip().upper()
            if sentiment in ['BUY', 'SELL', 'HOLD']:
                return {"status": "ok", "conclusion": sentiment}
        return {"status": "error", "conclusion": "HOLD", "raw": str(response)}
    except Exception as e:
        return {"status": "exception", "conclusion": "HOLD", "raw": str(e)}

def fetch_all_tweets():
    """获取并处理一个用户的所有可访问推文（最多3200条）。"""
    
    if not BAILIAN_API_KEY or not TWITTER_BEARER_TOKEN:
        print("错误：请设置 BAILIAN_API_KEY 和 TWITTER_BEARER_TOKEN 环境变量或在此脚本中硬编码。")
        return

    dashscope.api_key = BAILIAN_API_KEY
    headers = {'Authorization': f'Bearer {TWITTER_BEARER_TOKEN}'}
    params = {
        'max_results': 100,
        'exclude': 'replies,retweets',
        'tweet.fields': 'created_at'  # 确保返回推文创建时间
    }
    
    all_signals = []
    pagination_token = None
    
    print("开始获取历史推文和AI信号，这可能需要几分钟...")
    
    with tqdm(total=3200, desc="获取推文中") as pbar:
        while True:
            if pagination_token:
                params['pagination_token'] = pagination_token
            
            try:
                response = requests.get(TWITTER_API_URL, headers=headers, params=params, timeout=20)
                response.raise_for_status()
                data = response.json()
                
                tweets = data.get('data', [])
                if not tweets:
                    print("未找到更多推文。")
                    break

                for tweet in tweets:
                    pbar.update(1)
                    # 对每个推文进行AI分析
                    sentiment_result = get_sentiment(tweet['text'])
                    
                    # 格式化并存储信号
                    signal_entry = {
                        "timestamp": tweet['created_at'],
                        "tweet_text": tweet['text'],
                        "signal": sentiment_result['conclusion']
                    }
                    all_signals.append(signal_entry)
                    # 在AI调用之间稍作停顿，避免达到AI API的速率限制
                    time.sleep(0.5)

                meta = data.get('meta', {})
                pagination_token = meta.get('next_token')
                
                if not pagination_token or pbar.n >= 3200:
                    print("\n已达到推文获取上限（3200条）或已获取全部推文。")
                    break
                
                # 移除固定的等待时间，让速率限制处理器来决定是否需要等待
                # print(f"\n成功获取 {len(tweets)} 条推文，等待10秒以避免速率限制...")
                # time.sleep(10)

            except requests.exceptions.HTTPError as e:
                # 专门处理速率限制错误 (429)
                if e.response.status_code == 429:
                    reset_time_str = e.response.headers.get('x-rate-limit-reset')
                    wait_seconds = 900  # 如果API没有返回重置时间，则默认等待15分钟
                    if reset_time_str:
                        reset_timestamp = int(reset_time_str)
                        # 加上2秒的缓冲时间
                        wait_seconds = max(reset_timestamp - int(time.time()), 0) + 2
                    
                    print(f"\n达到API速率限制。Twitter要求等待 {wait_seconds} 秒...")
                    with tqdm(total=wait_seconds, desc="等待中", bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt}s') as wait_pbar:
                        for _ in range(wait_seconds):
                            time.sleep(1)
                            wait_pbar.update(1)
                    print("\n等待结束，继续获取。")
                    continue  # 继续下一次循环，重试请求
                else:
                    # 处理其他HTTP错误
                    print(f"\n发生HTTP错误: {e.response.status_code} - {e.response.reason}")
                    print("等待60秒后重试...")
                    time.sleep(60)

            except requests.exceptions.RequestException as e:
                print(f"\n发生网络连接错误: {e}")
                print("等待60秒后重试...")
                time.sleep(60)
            except Exception as e:
                print(f"\n发生未知错误: {e}")
                break

    # 保存到文件
    try:
        OUTPUT_DIR.mkdir(exist_ok=True)
        # 按时间戳从旧到新排序
        all_signals.sort(key=lambda x: datetime.fromisoformat(x['timestamp'].replace('Z', '+00:00')))

        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_signals, f, indent=4, ensure_ascii=False)
        print(f"\n成功！所有信号已保存至: {OUTPUT_FILE}")
        print(f"共获取并分析了 {len(all_signals)} 条推文。")
    except Exception as e:
        print(f"保存文件时出错: {e}")

if __name__ == '__main__':
    fetch_all_tweets() 