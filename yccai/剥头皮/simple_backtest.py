#!/usr/bin/env python3
"""
SmoothScalp策略简化回测脚本
使用现有数据文件进行回测分析
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# 添加freqtrade路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

def load_data():
    """加载现有数据"""
    print("📊 加载数据文件...")
    
    # 加载BTC/USDT数据
    btc_data = pd.read_feather('../../user_data/data/okx/BTC_USDT-1m.feather')
    eth_data = pd.read_feather('../../user_data/data/okx/ETH_USDT-1m.feather')
    
    print(f"BTC/USDT数据: {len(btc_data)} 条记录")
    print(f"ETH/USDT数据: {len(eth_data)} 条记录")
    
    # 设置日期索引
    btc_data['date'] = pd.to_datetime(btc_data['date'])
    eth_data['date'] = pd.to_datetime(eth_data['date'])
    
    btc_data.set_index('date', inplace=True)
    eth_data.set_index('date', inplace=True)
    
    return btc_data, eth_data

def calculate_indicators(df):
    """计算技术指标"""
    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['rsi'] = 100 - (100 / (1 + rs))
    
    # EMA
    df['ema_12'] = df['close'].ewm(span=12).mean()
    df['ema_26'] = df['close'].ewm(span=26).mean()
    df['ema_50'] = df['close'].ewm(span=50).mean()
    
    # MACD
    df['macd'] = df['ema_12'] - df['ema_26']
    df['macd_signal'] = df['macd'].ewm(span=9).mean()
    df['macd_histogram'] = df['macd'] - df['macd_signal']
    
    # Bollinger Bands
    df['bb_middle'] = df['close'].rolling(window=20).mean()
    bb_std = df['close'].rolling(window=20).std()
    df['bb_upper'] = df['bb_middle'] + (bb_std * 2)
    df['bb_lower'] = df['bb_middle'] - (bb_std * 2)
    df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
    
    # Volume indicators
    df['volume_sma'] = df['volume'].rolling(window=20).mean()
    df['volume_ratio'] = df['volume'] / df['volume_sma']
    
    # Price change
    df['price_change'] = df['close'].pct_change()
    df['volatility'] = df['price_change'].rolling(window=20).std()
    
    return df

def smoothscalp_signals(df):
    """SmoothScalp策略信号"""
    signals = pd.DataFrame(index=df.index)
    signals['buy_signal'] = False
    signals['sell_signal'] = False
    signals['exit_reason'] = ''
    
    # 买入条件
    buy_condition = (
        (df['rsi'] > 30) & (df['rsi'] < 70) &  # RSI在合理范围
        (df['close'] > df['ema_50']) &  # 价格在EMA50之上
        (df['macd'] > df['macd_signal']) &  # MACD金叉
        (df['volume_ratio'] > 1.2) &  # 成交量放大
        (df['bb_width'] > 0.02) &  # 波动率足够
        (df['volatility'] > df['volatility'].rolling(50).mean())  # 波动率上升
    )
    
    signals.loc[buy_condition, 'buy_signal'] = True
    
    # 卖出条件
    # ROI退出
    roi_condition = (
        (df['close'] / df['close'].shift(1) - 1) > 0.005  # 0.5%收益
    )
    signals.loc[roi_condition, 'sell_signal'] = True
    signals.loc[roi_condition, 'exit_reason'] = 'roi'
    
    # 止损退出
    stoploss_condition = (
        (df['close'] / df['close'].shift(1) - 1) < -0.002  # 0.2%止损
    )
    signals.loc[stoploss_condition, 'sell_signal'] = True
    signals.loc[stoploss_condition, 'exit_reason'] = 'stoploss'
    
    # 波动率退出
    volatility_condition = (
        (df['volatility'] < df['volatility'].rolling(20).mean() * 0.8)
    )
    signals.loc[volatility_condition, 'sell_signal'] = True
    signals.loc[volatility_condition, 'exit_reason'] = 'volatility_stop'
    
    return signals

def simulate_trades(df, signals, pair_name):
    """模拟交易"""
    trades = []
    position = None
    
    for i in range(1, len(df)):
        current_price = df.iloc[i]['close']
        current_time = df.index[i]
        
        # 检查买入信号
        if signals.iloc[i]['buy_signal'] and position is None:
            position = {
                'entry_time': current_time,
                'entry_price': current_price,
                'pair': pair_name
            }
        
        # 检查卖出信号
        elif signals.iloc[i]['sell_signal'] and position is not None:
            exit_reason = signals.iloc[i]['exit_reason']
            profit_pct = (current_price - position['entry_price']) / position['entry_price']
            profit_abs = profit_pct * 100  # 假设100USDT仓位
            
            trade = {
                'pair': pair_name,
                'entry_time': position['entry_time'],
                'exit_time': current_time,
                'entry_price': position['entry_price'],
                'exit_price': current_price,
                'profit_pct': profit_pct,
                'profit_abs': profit_abs,
                'exit_reason': exit_reason,
                'hold_time_minutes': (current_time - position['entry_time']).total_seconds() / 60
            }
            
            trades.append(trade)
            position = None
    
    return trades

def analyze_results(trades):
    """分析回测结果"""
    if not trades:
        print("❌ 没有找到任何交易")
        return
    
    df_trades = pd.DataFrame(trades)
    
    print("\n" + "="*60)
    print("📈 SmoothScalp策略回测结果")
    print("="*60)
    
    # 基础统计
    total_trades = len(df_trades)
    winning_trades = len(df_trades[df_trades['profit_abs'] > 0])
    losing_trades = len(df_trades[df_trades['profit_abs'] < 0])
    win_rate = winning_trades / total_trades * 100
    
    total_profit = df_trades['profit_abs'].sum()
    avg_profit = df_trades['profit_abs'].mean()
    max_profit = df_trades['profit_abs'].max()
    max_loss = df_trades['profit_abs'].min()
    
    avg_hold_time = df_trades['hold_time_minutes'].mean()
    
    print(f"📊 基础统计:")
    print(f"   总交易次数: {total_trades}")
    print(f"   盈利交易: {winning_trades} ({win_rate:.1f}%)")
    print(f"   亏损交易: {losing_trades} ({100-win_rate:.1f}%)")
    print(f"   总收益: {total_profit:.2f} USDT")
    print(f"   平均收益: {avg_profit:.2f} USDT/笔")
    print(f"   最大盈利: {max_profit:.2f} USDT")
    print(f"   最大亏损: {max_loss:.2f} USDT")
    print(f"   平均持仓时间: {avg_hold_time:.1f} 分钟")
    
    # 按交易对分析
    print(f"\n📈 按交易对分析:")
    for pair in df_trades['pair'].unique():
        pair_trades = df_trades[df_trades['pair'] == pair]
        pair_profit = pair_trades['profit_abs'].sum()
        pair_win_rate = len(pair_trades[pair_trades['profit_abs'] > 0]) / len(pair_trades) * 100
        print(f"   {pair}: {len(pair_trades)}笔交易, 收益{pair_profit:.2f}USDT, 胜率{pair_win_rate:.1f}%")
    
    # 按退出原因分析
    print(f"\n🚪 按退出原因分析:")
    for reason in df_trades['exit_reason'].unique():
        reason_trades = df_trades[df_trades['exit_reason'] == reason]
        reason_profit = reason_trades['profit_abs'].sum()
        reason_win_rate = len(reason_trades[reason_trades['profit_abs'] > 0]) / len(reason_trades) * 100
        print(f"   {reason}: {len(reason_trades)}笔交易, 收益{reason_profit:.2f}USDT, 胜率{reason_win_rate:.1f}%")
    
    # 风险指标
    if len(df_trades) > 1:
        sharpe_ratio = df_trades['profit_abs'].mean() / df_trades['profit_abs'].std() * np.sqrt(252*24*60)  # 年化夏普比率
        print(f"\n📊 风险指标:")
        print(f"   夏普比率: {sharpe_ratio:.2f}")
        print(f"   收益标准差: {df_trades['profit_abs'].std():.2f} USDT")
    
    # 保存详细结果
    df_trades.to_csv('SmoothScalp_真实回测结果.csv', index=False, encoding='utf-8-sig')
    print(f"\n💾 详细交易数据已保存为: SmoothScalp_真实回测结果.csv")
    
    return df_trades

def main():
    """主函数"""
    print("🚀 开始SmoothScalp策略真实回测...")
    
    try:
        # 加载数据
        btc_data, eth_data = load_data()
        
        # 计算技术指标
        print("🔧 计算技术指标...")
        btc_data = calculate_indicators(btc_data)
        eth_data = calculate_indicators(eth_data)
        
        # 生成交易信号
        print("📡 生成交易信号...")
        btc_signals = smoothscalp_signals(btc_data)
        eth_signals = smoothscalp_signals(eth_data)
        
        # 模拟交易
        print("💰 模拟交易...")
        btc_trades = simulate_trades(btc_data, btc_signals, 'BTC/USDT')
        eth_trades = simulate_trades(eth_data, eth_signals, 'ETH/USDT')
        
        # 合并所有交易
        all_trades = btc_trades + eth_trades
        
        # 分析结果
        analyze_results(all_trades)
        
        print("\n✅ 回测完成！")
        
    except Exception as e:
        print(f"❌ 回测过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
