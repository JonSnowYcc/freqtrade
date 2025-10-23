#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BTC网格策略超参优化示例
演示如何使用不同的优化算法来优化网格策略参数
"""

from btc_grid_strategy import (
    HyperparameterOptimizer, 
    create_optimized_strategy,
    OptimizationResult
)
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List, Any
import json


def generate_sample_data(start_price: float = 50000, 
                        days: int = 365,
                        volatility: float = 0.02) -> pd.DataFrame:
    """生成模拟的BTC价格数据"""
    dates = pd.date_range(start=datetime.now() - timedelta(days=days), 
                         end=datetime.now(), freq='D')
    
    # 生成随机游走价格数据
    returns = np.random.normal(0, volatility, len(dates))
    prices = [start_price]
    
    for ret in returns[1:]:
        new_price = prices[-1] * (1 + ret)
        prices.append(max(new_price, 1000))  # 最低价格1000美元
    
    df = pd.DataFrame({
        'date': dates,
        'close': prices,
        'open': prices,
        'high': [p * (1 + abs(np.random.normal(0, 0.01))) for p in prices],
        'low': [p * (1 - abs(np.random.normal(0, 0.01))) for p in prices],
        'volume': np.random.uniform(1000, 10000, len(dates))
    })
    
    return df


def compare_optimization_methods(initial_price: float = 50000,
                               total_capital: float = 100000,
                               historical_data: pd.DataFrame = None) -> Dict[str, OptimizationResult]:
    """比较不同优化方法"""
    
    print("=== 比较不同优化方法 ===")
    
    if historical_data is None:
        historical_data = generate_sample_data(initial_price)
    
    optimizer = HyperparameterOptimizer(
        initial_price=initial_price,
        total_capital=total_capital,
        historical_data=historical_data
    )
    
    results = {}
    
    # 1. 网格搜索
    print("\n1. 网格搜索优化...")
    try:
        grid_result = optimizer.optimize_grid_search(
            optimization_metric='composite_score',
            max_combinations=500
        )
        results['grid_search'] = grid_result
        print(f"网格搜索完成 - 最佳评分: {grid_result.best_score:.4f}")
    except Exception as e:
        print(f"网格搜索失败: {e}")
    
    # 2. 差分进化
    print("\n2. 差分进化优化...")
    try:
        de_result = optimizer.optimize_differential_evolution(
            optimization_metric='composite_score',
            maxiter=30,
            popsize=10
        )
        results['differential_evolution'] = de_result
        print(f"差分进化完成 - 最佳评分: {de_result.best_score:.4f}")
    except Exception as e:
        print(f"差分进化失败: {e}")
    
    # 3. 贝叶斯优化
    print("\n3. 贝叶斯优化...")
    try:
        bayesian_result = optimizer.optimize_bayesian(
            optimization_metric='composite_score',
            n_calls=100
        )
        results['bayesian'] = bayesian_result
        print(f"贝叶斯优化完成 - 最佳评分: {bayesian_result.best_score:.4f}")
    except Exception as e:
        print(f"贝叶斯优化失败: {e}")
    
    return results


def analyze_optimization_results(results: Dict[str, OptimizationResult]) -> None:
    """分析优化结果"""
    
    print("\n=== 优化结果分析 ===")
    
    # 创建比较表格
    comparison_data = []
    for method, result in results.items():
        comparison_data.append({
            '优化方法': method,
            '最佳评分': result.best_score,
            '执行时间(秒)': result.execution_time,
            '收敛信息': result.convergence_info
        })
    
    comparison_df = pd.DataFrame(comparison_data)
    print("\n优化方法比较:")
    print(comparison_df.to_string(index=False))
    
    # 找出最佳方法
    best_method = max(results.keys(), key=lambda k: results[k].best_score)
    best_result = results[best_method]
    
    print(f"\n最佳优化方法: {best_method}")
    print(f"最佳评分: {best_result.best_score:.4f}")
    print(f"最佳参数:")
    for param, value in best_result.best_params.items():
        print(f"  {param}: {value}")
    
    # 保存详细结果
    save_optimization_comparison(results)


def save_optimization_comparison(results: Dict[str, OptimizationResult]) -> None:
    """保存优化比较结果"""
    
    filename = f"btc_grid_optimization_comparison_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    comparison_data = {}
    for method, result in results.items():
        comparison_data[method] = {
            'best_params': result.best_params,
            'best_score': result.best_score,
            'execution_time': result.execution_time,
            'convergence_info': result.convergence_info
        }
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(comparison_data, f, indent=2, ensure_ascii=False, default=str)
    
    print(f"\n优化比较结果已保存到: {filename}")


def optimize_with_different_metrics(initial_price: float = 50000,
                                  total_capital: float = 100000) -> Dict[str, OptimizationResult]:
    """使用不同优化指标进行优化"""
    
    print("\n=== 使用不同优化指标 ===")
    
    historical_data = generate_sample_data(initial_price)
    optimizer = HyperparameterOptimizer(
        initial_price=initial_price,
        total_capital=total_capital,
        historical_data=historical_data
    )
    
    metrics = ['sharpe_ratio', 'profit_factor', 'max_drawdown_ratio', 'composite_score']
    results = {}
    
    for metric in metrics:
        print(f"\n优化指标: {metric}")
        try:
            result = optimizer.optimize_differential_evolution(
                optimization_metric=metric,
                maxiter=20,
                popsize=8
            )
            results[metric] = result
            print(f"最佳评分: {result.best_score:.4f}")
        except Exception as e:
            print(f"优化失败: {e}")
    
    return results


def create_optimization_report(results: Dict[str, OptimizationResult]) -> None:
    """创建优化报告"""
    
    print("\n=== 优化报告 ===")
    
    # 找出最佳结果
    best_method = max(results.keys(), key=lambda k: results[k].best_score)
    best_result = results[best_method]
    
    print(f"推荐优化方法: {best_method}")
    print(f"最佳评分: {best_result.best_score:.4f}")
    print(f"执行时间: {best_result.execution_time:.2f}秒")
    
    print(f"\n推荐参数配置:")
    for param, value in best_result.best_params.items():
        if isinstance(value, float):
            print(f"  {param}: {value:.4f}")
        else:
            print(f"  {param}: {value}")
    
    # 参数分析
    print(f"\n参数分析:")
    params = best_result.best_params
    
    if 'grid_spacing' in params:
        print(f"  网格间距: {params['grid_spacing']:.1%} - {'保守' if params['grid_spacing'] < 0.05 else '平衡' if params['grid_spacing'] < 0.08 else '激进'}")
    
    if 'max_drawdown' in params:
        print(f"  最大回撤: {params['max_drawdown']:.1%} - {'保守' if params['max_drawdown'] < 0.5 else '平衡' if params['max_drawdown'] < 0.7 else '激进'}")
    
    if 'enable_multi_grid' in params:
        print(f"  多网格策略: {'启用' if params['enable_multi_grid'] else '禁用'}")
    
    if 'enable_profit_retention' in params:
        print(f"  留利润功能: {'启用' if params['enable_profit_retention'] else '禁用'}")


def visualize_optimization_results(results: Dict[str, OptimizationResult]) -> None:
    """可视化优化结果"""
    
    try:
        import matplotlib.pyplot as plt
        import seaborn as sns
        
        # 设置中文字体
        plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS']
        plt.rcParams['axes.unicode_minus'] = False
        
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle('BTC网格策略优化结果分析', fontsize=16)
        
        # 1. 优化方法比较
        methods = list(results.keys())
        scores = [results[method].best_score for method in methods]
        times = [results[method].execution_time for method in methods]
        
        axes[0, 0].bar(methods, scores)
        axes[0, 0].set_title('最佳评分比较')
        axes[0, 0].set_ylabel('评分')
        axes[0, 0].tick_params(axis='x', rotation=45)
        
        axes[0, 1].bar(methods, times)
        axes[0, 1].set_title('执行时间比较')
        axes[0, 1].set_ylabel('时间(秒)')
        axes[0, 1].tick_params(axis='x', rotation=45)
        
        # 2. 参数分布（如果有历史数据）
        if any(len(result.optimization_history) > 0 for result in results.values()):
            # 找到有历史数据的结果
            result_with_history = next((r for r in results.values() if len(r.optimization_history) > 0), None)
            
            if result_with_history:
                history = result_with_history.optimization_history
                scores_history = [h['score'] for h in history if h['feasible']]
                
                axes[1, 0].plot(scores_history)
                axes[1, 0].set_title('优化过程')
                axes[1, 0].set_xlabel('迭代次数')
                axes[1, 0].set_ylabel('评分')
        
        # 3. 参数重要性分析
        best_result = max(results.values(), key=lambda r: r.best_score)
        params = best_result.best_params
        
        # 选择数值型参数进行可视化
        numeric_params = {k: v for k, v in params.items() if isinstance(v, (int, float))}
        
        if numeric_params:
            param_names = list(numeric_params.keys())[:6]  # 最多显示6个参数
            param_values = [numeric_params[name] for name in param_names]
            
            axes[1, 1].barh(param_names, param_values)
            axes[1, 1].set_title('最佳参数值')
            axes[1, 1].set_xlabel('参数值')
        
        plt.tight_layout()
        
        # 保存图表
        filename = f"btc_grid_optimization_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        plt.savefig(filename, dpi=300, bbox_inches='tight')
        print(f"\n优化分析图表已保存到: {filename}")
        
        plt.show()
        
    except ImportError:
        print("\n注意: 需要安装matplotlib和seaborn来生成可视化图表")
    except Exception as e:
        print(f"\n可视化失败: {e}")


def main():
    """主函数"""
    
    print("=== BTC网格策略超参优化演示 ===")
    
    # 设置参数
    initial_price = 50000
    total_capital = 100000
    
    # 生成模拟数据
    print("生成模拟BTC价格数据...")
    historical_data = generate_sample_data(initial_price, days=365, volatility=0.03)
    print(f"生成了{len(historical_data)}天的价格数据")
    
    # 比较不同优化方法
    optimization_results = compare_optimization_methods(
        initial_price=initial_price,
        total_capital=total_capital,
        historical_data=historical_data
    )
    
    if optimization_results:
        # 分析结果
        analyze_optimization_results(optimization_results)
        
        # 创建报告
        create_optimization_report(optimization_results)
        
        # 可视化结果
        visualize_optimization_results(optimization_results)
        
        # 使用不同指标优化
        print("\n" + "="*60)
        metric_results = optimize_with_different_metrics(initial_price, total_capital)
        
        if metric_results:
            print("\n不同优化指标结果:")
            for metric, result in metric_results.items():
                print(f"  {metric}: {result.best_score:.4f}")
    
    print("\n=== 优化演示完成 ===")
    print("建议:")
    print("1. 根据优化结果调整策略参数")
    print("2. 在实盘前进行充分的回测验证")
    print("3. 定期重新优化参数以适应市场变化")
    print("4. 注意过拟合风险，保持策略的稳健性")
    


if __name__ == "__main__":
    main()
