#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BTC网格策略使用示例
演示如何使用BTC网格策略进行交易
"""

from btc_grid_strategy import create_btc_grid_strategy, GridConfig, BTCGridStrategy
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


def demo_btc_grid_strategy():
    """演示BTC网格策略的使用"""
    
    print("=" * 60)
    print("BTC网格策略演示")
    print("=" * 60)
    
    # 1. 创建策略配置
    print("\n1. 创建策略配置...")
    
    # 假设BTC当前价格50000美元，总资金10万美元
    strategy = create_btc_grid_strategy(
        initial_price=50000,
        total_capital=100000,
        max_drawdown=0.6,  # 最大回撤60%
        strategy_version="2.0"
    )
    
    print(f"初始价格: ${strategy.config.initial_price:,.2f}")
    print(f"总资金: ${strategy.config.total_capital:,.2f}")
    print(f"最大回撤: {strategy.config.max_drawdown:.1%}")
    print(f"策略版本: 2.0 (多网格 + 留利润 + 逐格加码)")
    
    # 2. 压力测试
    print("\n2. 执行压力测试...")
    pressure_result = strategy.pressure_test()
    
    print(f"最坏情况价格: ${pressure_result['worst_case_price']:,.2f}")
    print(f"需要BTC数量: {pressure_result['total_btc_needed']:.6f} BTC")
    print(f"总成本: ${pressure_result['total_cost']:,.2f}")
    print(f"资金利用率: {pressure_result['capital_utilization']:.2%}")
    print(f"平均成本: ${pressure_result['avg_cost']:,.2f}")
    print(f"回本价格: ${pressure_result['break_even_price']:,.2f}")
    print(f"策略可行性: {'✓ 可行' if pressure_result['is_feasible'] else '✗ 不可行'}")
    
    # 3. 显示网格配置
    print("\n3. 网格配置概览...")
    
    # 按网格类型分组统计
    grid_stats = {}
    for level in strategy.grid_levels:
        if level.grid_type not in grid_stats:
            grid_stats[level.grid_type] = {'buy': 0, 'sell': 0, 'total_amount': 0}
        grid_stats[level.grid_type][level.action] += 1
        grid_stats[level.grid_type]['total_amount'] += level.amount
    
    for grid_type, stats in grid_stats.items():
        print(f"{grid_type}网格: 买入{stats['buy']}个, 卖出{stats['sell']}个, 总数量{stats['total_amount']:.6f} BTC")
    
    # 4. 模拟交易场景
    print("\n4. 模拟交易场景...")
    
    # 模拟价格波动
    price_scenarios = [
        (45000, "价格下跌10%"),
        (40000, "价格下跌20%"),
        (35000, "价格下跌30%"),
        (30000, "价格下跌40%"),
        (25000, "价格下跌50%"),
        (20000, "价格下跌60% (最坏情况)"),
        (25000, "价格反弹25%"),
        (30000, "价格反弹50%"),
        (40000, "价格反弹100%"),
        (50000, "价格回到初始"),
        (55000, "价格上涨10%"),
        (60000, "价格上涨20%")
    ]
    
    print("\n模拟价格波动和交易执行:")
    print("-" * 80)
    print(f"{'价格':<12} {'场景':<20} {'买入信号':<8} {'卖出信号':<8} {'累计收益':<12}")
    print("-" * 80)
    
    total_pnl = 0
    for price, scenario in price_scenarios:
        signals = strategy.get_trading_signals(price)
        buy_signals = [s for s in signals if s.action == 'buy']
        sell_signals = [s for s in signals if s.action == 'sell']
        
        # 执行交易
        for signal in signals:
            trade = strategy.execute_trade(price, signal)
            if signal.action == 'sell':
                total_pnl += trade.get('revenue', 0) - trade.get('cost', 0)
        
        print(f"${price:<11,.0f} {scenario:<20} {len(buy_signals):<8} {len(sell_signals):<8} ${total_pnl:<11,.2f}")
    
    # 5. 策略表现分析
    print("\n5. 策略表现分析...")
    performance = strategy.calculate_performance()
    
    print(f"总交易次数: {performance['total_trades']}")
    print(f"买入次数: {performance['buy_trades']}")
    print(f"卖出次数: {performance['sell_trades']}")
    print(f"已实现收益: ${performance['realized_pnl']:,.2f}")
    print(f"未实现收益: ${performance['unrealized_pnl']:,.2f}")
    print(f"总收益: ${performance['total_pnl']:,.2f}")
    print(f"收益率: {performance['total_pnl'] / strategy.config.total_capital:.2%}")
    
    # 6. 导出结果
    print("\n6. 导出结果...")
    
    # 导出网格表格
    grid_df = strategy.export_grid_table("btc_grid_table_demo.csv")
    print(f"网格表格已导出: btc_grid_table_demo.csv")
    
    # 导出交易历史
    if strategy.trade_history:
        trade_df = pd.DataFrame(strategy.trade_history)
        trade_df.to_csv("btc_trade_history_demo.csv", index=False, encoding='utf-8-sig')
        print(f"交易历史已导出: btc_trade_history_demo.csv")
    
    # 保存配置
    strategy.save_config("btc_grid_config_demo.json")
    print(f"策略配置已保存: btc_grid_config_demo.json")
    
    print("\n" + "=" * 60)
    print("演示完成！")
    print("=" * 60)


def compare_strategy_versions():
    """比较1.0和2.0版本策略"""
    
    print("\n" + "=" * 60)
    print("策略版本比较")
    print("=" * 60)
    
    # 创建1.0版本策略
    strategy_1_0 = create_btc_grid_strategy(
        initial_price=50000,
        total_capital=100000,
        max_drawdown=0.6,
        strategy_version="1.0"
    )
    
    # 创建2.0版本策略
    strategy_2_0 = create_btc_grid_strategy(
        initial_price=50000,
        total_capital=100000,
        max_drawdown=0.6,
        strategy_version="2.0"
    )
    
    print("\n版本对比:")
    print("-" * 50)
    print(f"{'特性':<20} {'1.0版本':<15} {'2.0版本'}")
    print("-" * 50)
    print(f"{'网格类型':<20} {'单网格':<15} {'多网格'}")
    print(f"{'网格间距':<20} {'5%':<15} {'5%/15%/30%'}")
    print(f"{'留利润':<20} {'否':<15} {'是'}")
    print(f"{'逐格加码':<20} {'否':<15} {'是'}")
    print(f"{'网格数量':<20} {len(strategy_1_0.grid_levels):<15} {len(strategy_2_0.grid_levels)}")
    
    # 压力测试对比
    print("\n压力测试对比:")
    print("-" * 50)
    
    pressure_1_0 = strategy_1_0.pressure_test()
    pressure_2_0 = strategy_2_0.pressure_test()
    
    print(f"{'指标':<20} {'1.0版本':<15} {'2.0版本'}")
    print("-" * 50)
    print(f"{'资金利用率':<20} {pressure_1_0['capital_utilization']:<15.2%} {pressure_2_0['capital_utilization']:.2%}")
    print(f"{'平均成本':<20} ${pressure_1_0['avg_cost']:<14,.2f} ${pressure_2_0['avg_cost']:,.2f}")
    print(f"{'回本价格':<20} ${pressure_1_0['break_even_price']:<14,.2f} ${pressure_2_0['break_even_price']:,.2f}")


def create_custom_strategy():
    """创建自定义策略配置"""
    
    print("\n" + "=" * 60)
    print("自定义策略配置")
    print("=" * 60)
    
    # 自定义配置
    custom_config = GridConfig(
        initial_price=45000,  # BTC价格45000
        total_capital=50000,  # 总资金5万
        grid_spacing=0.08,    # 8%网格间距
        max_drawdown=0.5,     # 最大回撤50%
        max_grids=15,         # 最大15个网格
        enable_profit_retention=True,
        enable_progressive_betting=True,
        enable_multi_grid=True,
        small_grid_spacing=0.08,   # 小网格8%
        medium_grid_spacing=0.20,  # 中网格20%
        large_grid_spacing=0.40,   # 大网格40%
        small_grid_ratio=0.6,      # 小网格占60%
        medium_grid_ratio=0.25,    # 中网格占25%
        large_grid_ratio=0.15      # 大网格占15%
    )
    
    strategy = BTCGridStrategy(custom_config)
    strategy.grid_levels = strategy.generate_grid_levels()
    
    print(f"自定义配置:")
    print(f"初始价格: ${custom_config.initial_price:,.2f}")
    print(f"总资金: ${custom_config.total_capital:,.2f}")
    print(f"网格间距: {custom_config.grid_spacing:.1%}")
    print(f"最大回撤: {custom_config.max_drawdown:.1%}")
    print(f"网格数量: {len(strategy.grid_levels)}")
    
    # 压力测试
    pressure_result = strategy.pressure_test()
    print(f"\n压力测试结果:")
    print(f"资金利用率: {pressure_result['capital_utilization']:.2%}")
    print(f"策略可行性: {'✓ 可行' if pressure_result['is_feasible'] else '✗ 不可行'}")


if __name__ == "__main__":
    # 运行演示
    demo_btc_grid_strategy()
    
    # 比较版本
    compare_strategy_versions()
    
    # 自定义配置
    create_custom_strategy()
    
    print("\n" + "=" * 60)
    print("重要提醒:")
    print("1. 压力测试是最重要的！")
    print("2. 只做不会死的品种（BTC符合条件）")
    print("3. 网格策略是波段策略，不是长期策略")
    print("4. 建议与长期持有策略结合使用")
    print("5. 请根据自身风险承受能力调整参数")
    print("=" * 60)
