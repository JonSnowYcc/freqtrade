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
    """
    获取并处理一个用户的所有可访问推文（最多3200条）。
    此函数支持增量更新。
    """
    
    if not BAILIAN_API_KEY or not TWITTER_BEARER_TOKEN:
        print("错误：请设置 BAILIAN_API_KEY 和 TWITTER_BEARER_TOKEN 环境变量或在此脚本中硬编码。")
        return

    dashscope.api_key = BAILIAN_API_KEY
    
    all_signals = []
    since_id = None

    # --- 增量加载逻辑 ---
    if OUTPUT_FILE.exists():
        print(f"检测到现有信号文件: {OUTPUT_FILE}")
        try:
            with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
                all_signals = json.load(f)
            
            if all_signals:
                # 假设文件中的推文ID叫 "tweet_id"
                since_id = max(s['tweet_id'] for s in all_signals if 'tweet_id' in s)
                print(f"将进行增量更新，只获取比 {since_id} 更新的推文。")
            else:
                print("信号文件为空，将进行完整下载。")
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            print(f"无法解析现有信号文件，将重新进行完整下载。错误: {e}")
            all_signals = []
            since_id = None
    
    headers = {'Authorization': f'Bearer {TWITTER_BEARER_TOKEN}'}
    params = {
        'max_results': 100,
        'exclude': 'replies,retweets',
        'tweet.fields': 'created_at'  # 确保返回推文创建时间
    }
    # 如果找到了since_id，则添加到API请求参数中
    if since_id:
        params['since_id'] = since_id
    
    newly_fetched_signals = []
    pagination_token = None
    
    print("开始获取历史推文和AI信号...")
    
    initial_count = len(all_signals)
    with tqdm(initial=initial_count, total=3200, desc="获取推文中") as pbar:
        while True:
            if pagination_token:
                params['pagination_token'] = pagination_token
            
            try:
                # 将超时时间从20秒增加到60秒，以应对网络波动或API响应缓慢
                response = requests.get(TWITTER_API_URL, headers=headers, params=params, timeout=60)
                response.raise_for_status()
                data = response.json()
                
                tweets = data.get('data', [])
                if not tweets:
                    break

                for tweet in tweets:
                    pbar.update(1)
                    # 对每个推文进行AI分析
                    sentiment_result = get_sentiment(tweet['text'])
                    
                    # 新增了 tweet_id 字段
                    signal_entry = {
                        "tweet_id": tweet['id'],
                        "timestamp": tweet['created_at'],
                        "tweet_text": tweet['text'],
                        "signal": sentiment_result['conclusion']
                    }
                    newly_fetched_signals.append(signal_entry)
                    # 在AI调用之间稍作停顿，避免达到AI API的速率限制
                    time.sleep(0.5)

                meta = data.get('meta', {})
                pagination_token = meta.get('next_token')
                
                if not pagination_token or pbar.n >= 3200:
                    break
                
                # 新增：在每次成功获取一页后，增加一个固定的5秒延迟，以降低请求频率
                print(f"\n成功获取 {len(tweets)} 条推文，等待5秒再获取下一页...")
                time.sleep(5)

            except requests.exceptions.HTTPError as e:
                # 专门处理速率限制错误 (429)
                if e.response.status_code == 429:
                    reset_time_str = e.response.headers.get('x-rate-limit-reset')
                    wait_seconds = 900  # 如果API没有返回重置时间，则默认等待15分钟
                    if reset_time_str:
                        reset_timestamp = int(reset_time_str)
                        # 将缓冲时间从2秒增加到10秒，以更保守地应对时钟偏差或API延迟
                        wait_seconds = max(reset_timestamp - int(time.time()), 0) + 10
                    
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

    if not newly_fetched_signals:
        print("\n没有获取到新的推文。本地文件已是最新。")
        return

    print(f"\n获取了 {len(newly_fetched_signals)} 条新推文。正在合并与保存...")
    all_signals.extend(newly_fetched_signals)

    # 保存到文件
    try:
        OUTPUT_DIR.mkdir(exist_ok=True)
        # 按时间戳从旧到新排序
        all_signals.sort(key=lambda x: datetime.fromisoformat(x['timestamp'].replace('Z', '+00:00')))
        
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_signals, f, indent=4, ensure_ascii=False)
        print(f"\n成功！所有信号已保存至: {OUTPUT_FILE}")
        print(f"文件中总共包含 {len(all_signals)} 条推文。")
    except Exception as e:
        print(f"保存文件时出错: {e}")

if __name__ == '__main__':
    fetch_all_tweets() 