#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单的BTC网格策略超参优化演示
不依赖scipy和sklearn，使用随机搜索进行优化
"""

from btc_grid_strategy import BTCGridStrategy, GridConfig
import random
import json
from datetime import datetime
from typing import Dict, List, Any


def random_search_optimization(initial_price: float = 50000,
                             total_capital: float = 100000,
                             n_trials: int = 100) -> Dict[str, Any]:
    """随机搜索优化"""
    
    print("=== 随机搜索超参优化演示 ===")
    print(f"初始价格: ${initial_price:,.2f}")
    print(f"总资金: ${total_capital:,.2f}")
    print(f"搜索次数: {n_trials}")
    
    # 参数搜索空间
    param_space = {
        'grid_spacing': (0.03, 0.12),
        'max_drawdown': (0.3, 0.8),
        'max_grids': (10, 30),
        'small_grid_spacing': (0.03, 0.08),
        'medium_grid_spacing': (0.10, 0.25),
        'large_grid_spacing': (0.20, 0.50),
        'small_grid_ratio': (0.3, 0.7),
        'medium_grid_ratio': (0.1, 0.4),
        'large_grid_ratio': (0.1, 0.3),
        'profit_retention_ratio': (0.2, 0.8),
        'progressive_betting_ratio': (0.02, 0.10),
        'min_profit_threshold': (0.03, 0.08),
        'max_position_ratio': (0.6, 0.9)
    }
    
    best_score = -float('inf')
    best_params = None
    optimization_history = []
    
    for i in range(n_trials):
        # 生成随机参数
        params = {}
        for param, (min_val, max_val) in param_space.items():
            if param == 'max_grids':
                params[param] = random.randint(int(min_val), int(max_val))
            else:
                params[param] = random.uniform(min_val, max_val)
        
        # 添加布尔参数
        params['enable_profit_retention'] = random.choice([True, False])
        params['enable_progressive_betting'] = random.choice([True, False])
        params['enable_multi_grid'] = random.choice([True, False])
        
        # 确保资金分配比例和为1
        total_ratio = params['small_grid_ratio'] + params['medium_grid_ratio'] + params['large_grid_ratio']
        if total_ratio != 1.0:
            params['small_grid_ratio'] /= total_ratio
            params['medium_grid_ratio'] /= total_ratio
            params['large_grid_ratio'] /= total_ratio
        
        try:
            # 创建策略
            config = GridConfig(
                initial_price=initial_price,
                total_capital=total_capital,
                **params
            )
            
            strategy = BTCGridStrategy(config)
            strategy.grid_levels = strategy.generate_grid_levels()
            
            # 压力测试
            pressure_result = strategy.pressure_test()
            
            if pressure_result['is_feasible']:
                # 计算综合评分
                score = calculate_composite_score(strategy, pressure_result)
                
                optimization_history.append({
                    'trial': i + 1,
                    'params': params.copy(),
                    'score': score,
                    'feasible': True
                })
                
                if score > best_score:
                    best_score = score
                    best_params = params.copy()
                    
                if (i + 1) % 20 == 0:
                    print(f"已完成 {i + 1}/{n_trials} 次搜索，当前最佳评分: {best_score:.4f}")
            else:
                optimization_history.append({
                    'trial': i + 1,
                    'params': params.copy(),
                    'score': -1000,
                    'feasible': False
                })
                
        except Exception as e:
            print(f"第 {i + 1} 次搜索失败: {e}")
            optimization_history.append({
                'trial': i + 1,
                'params': params.copy(),
                'score': -1000,
                'feasible': False,
                'error': str(e)
            })
    
    return {
        'best_params': best_params,
        'best_score': best_score,
        'optimization_history': optimization_history,
        'total_trials': n_trials
    }


def calculate_composite_score(strategy: BTCGridStrategy, pressure_result: Dict) -> float:
    """计算综合评分"""
    # 夏普比率权重40%
    expected_return = 0.1  # 假设年化收益10%
    volatility = pressure_result['max_drawdown'] * 0.5  # 估算波动率
    sharpe_score = (expected_return / volatility if volatility > 0 else 0) * 0.4
    
    # 盈利因子权重30%
    grid_profit = strategy.config.grid_spacing
    capital_efficiency = 1 - pressure_result['capital_utilization']
    profit_score = grid_profit * capital_efficiency * 10 * 0.3
    
    # 资金利用率权重20%（利用率越低越好）
    capital_score = (1 - pressure_result['capital_utilization']) * 0.2
    
    # 网格数量权重10%（适中的网格数量）
    grid_count = len(strategy.grid_levels)
    optimal_grids = 20
    grid_score = (1 - abs(grid_count - optimal_grids) / optimal_grids) * 0.1
    
    return sharpe_score + profit_score + capital_score + grid_score


def analyze_optimization_result(result: Dict[str, Any]) -> None:
    """分析优化结果"""
    
    print("\n=== 优化结果分析 ===")
    
    if result['best_params'] is None:
        print("未找到可行的参数组合")
        return
    
    print(f"最佳评分: {result['best_score']:.4f}")
    print(f"总搜索次数: {result['total_trials']}")
    
    # 统计可行性
    feasible_count = sum(1 for h in result['optimization_history'] if h['feasible'])
    print(f"可行参数组合: {feasible_count}/{result['total_trials']} ({feasible_count/result['total_trials']:.1%})")
    
    print("\n最佳参数配置:")
    for param, value in result['best_params'].items():
        if isinstance(value, float):
            print(f"  {param}: {value:.4f}")
        else:
            print(f"  {param}: {value}")
    
    # 参数分析
    params = result['best_params']
    print("\n参数分析:")
    
    if 'grid_spacing' in params:
        spacing_type = '保守' if params['grid_spacing'] < 0.05 else '平衡' if params['grid_spacing'] < 0.08 else '激进'
        print(f"  网格间距: {params['grid_spacing']:.1%} - {spacing_type}")
    
    if 'max_drawdown' in params:
        risk_type = '保守' if params['max_drawdown'] < 0.5 else '平衡' if params['max_drawdown'] < 0.7 else '激进'
        print(f"  最大回撤: {params['max_drawdown']:.1%} - {risk_type}")
    
    if 'enable_multi_grid' in params:
        print(f"  多网格策略: {'启用' if params['enable_multi_grid'] else '禁用'}")
    
    if 'enable_profit_retention' in params:
        print(f"  留利润功能: {'启用' if params['enable_profit_retention'] else '禁用'}")


def create_optimized_strategy_from_result(result: Dict[str, Any], 
                                        initial_price: float = 50000,
                                        total_capital: float = 100000) -> BTCGridStrategy:
    """从优化结果创建策略"""
    
    if result['best_params'] is None:
        raise ValueError("没有可用的优化结果")
    
    config = GridConfig(
        initial_price=initial_price,
        total_capital=total_capital,
        **result['best_params']
    )
    
    strategy = BTCGridStrategy(config)
    strategy.grid_levels = strategy.generate_grid_levels()
    
    return strategy


def save_optimization_result(result: Dict[str, Any], filename: str = None) -> str:
    """保存优化结果"""
    
    if not filename:
        filename = f"btc_grid_random_search_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    # 准备保存数据
    save_data = {
        'best_params': result['best_params'],
        'best_score': result['best_score'],
        'total_trials': result['total_trials'],
        'optimization_history': result['optimization_history'][:50]  # 只保存前50个
    }
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n优化结果已保存到: {filename}")
    return filename


def main():
    """主函数"""
    
    print("=== BTC网格策略随机搜索优化演示 ===")
    
    # 设置参数
    initial_price = 50000
    total_capital = 100000
    n_trials = 200
    
    # 执行优化
    result = random_search_optimization(
        initial_price=initial_price,
        total_capital=total_capital,
        n_trials=n_trials
    )
    
    # 分析结果
    analyze_optimization_result(result)
    
    # 创建优化后的策略
    if result['best_params']:
        print("\n=== 创建优化后的策略 ===")
        optimized_strategy = create_optimized_strategy_from_result(
            result, initial_price, total_capital
        )
        
        # 压力测试
        pressure_result = optimized_strategy.pressure_test()
        print(f"优化后策略压力测试:")
        print(f"  资金利用率: {pressure_result['capital_utilization']:.2%}")
        print(f"  平均成本: ${pressure_result['avg_cost']:,.2f}")
        print(f"  策略可行性: {'是' if pressure_result['is_feasible'] else '否'}")
        
        # 导出网格表格
        grid_df = optimized_strategy.export_grid_table()
        print(f"  网格数量: {len(grid_df)}")
        
        # 保存配置
        optimized_strategy.save_config()
    
    # 保存优化结果
    save_optimization_result(result)
    
    print("\n=== 优化演示完成 ===")
    print("建议:")
    print("1. 根据优化结果调整策略参数")
    print("2. 在实盘前进行充分的回测验证")
    print("3. 定期重新优化参数以适应市场变化")
    print("4. 注意过拟合风险，保持策略的稳健性")


if __name__ == "__main__":
    main()
