#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BTC网格策略高级回测系统
支持多策略比较、参数优化、风险分析等功能
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime, timedelta
import json
import logging
from dataclasses import dataclass, asdict
import matplotlib.pyplot as plt
import seaborn as sns
from btc_grid_strategy import BTCGridStrategy, GridConfig, GridLevel
from btc_grid_backtest import BTCGridBacktester, BacktestConfig, BacktestResult

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


@dataclass
class StrategyComparison:
    """策略比较结果"""
    strategy_name: str
    config: GridConfig
    backtest_result: BacktestResult
    risk_metrics: Dict[str, float]


class AdvancedBacktester:
    """高级回测器"""
    
    def __init__(self, backtest_config: BacktestConfig):
        self.backtest_config = backtest_config
        self.comparison_results: List[StrategyComparison] = []
        
    def create_strategy_variants(self, base_config: Dict[str, Any]) -> List[Tuple[str, GridConfig]]:
        """创建策略变体"""
        variants = []
        
        # 1. 保守型策略
        conservative_config = GridConfig(
            initial_price=base_config['initial_price'],
            total_capital=base_config['total_capital'],
            grid_spacing=0.03,  # 3%网格间距
            max_drawdown=0.4,   # 40%最大回撤
            max_grids=15,
            enable_profit_retention=True,
            enable_progressive_betting=False,
            enable_multi_grid=False,
            small_grid_spacing=0.03,
            medium_grid_spacing=0.10,
            large_grid_spacing=0.20,
            small_grid_ratio=0.6,
            medium_grid_ratio=0.3,
            large_grid_ratio=0.1
        )
        variants.append(("保守型策略", conservative_config))
        
        # 2. 平衡型策略
        balanced_config = GridConfig(
            initial_price=base_config['initial_price'],
            total_capital=base_config['total_capital'],
            grid_spacing=0.05,  # 5%网格间距
            max_drawdown=0.6,   # 60%最大回撤
            max_grids=20,
            enable_profit_retention=True,
            enable_progressive_betting=True,
            enable_multi_grid=True,
            small_grid_spacing=0.05,
            medium_grid_spacing=0.15,
            large_grid_spacing=0.30,
            small_grid_ratio=0.5,
            medium_grid_ratio=0.3,
            large_grid_ratio=0.2
        )
        variants.append(("平衡型策略", balanced_config))
        
        # 3. 激进型策略
        aggressive_config = GridConfig(
            initial_price=base_config['initial_price'],
            total_capital=base_config['total_capital'],
            grid_spacing=0.08,  # 8%网格间距
            max_drawdown=0.8,   # 80%最大回撤
            max_grids=25,
            enable_profit_retention=True,
            enable_progressive_betting=True,
            enable_multi_grid=True,
            small_grid_spacing=0.08,
            medium_grid_spacing=0.20,
            large_grid_spacing=0.40,
            small_grid_ratio=0.4,
            medium_grid_ratio=0.35,
            large_grid_ratio=0.25
        )
        variants.append(("激进型策略", aggressive_config))
        
        # 4. 单网格策略
        single_grid_config = GridConfig(
            initial_price=base_config['initial_price'],
            total_capital=base_config['total_capital'],
            grid_spacing=0.05,
            max_drawdown=0.6,
            max_grids=20,
            enable_profit_retention=False,
            enable_progressive_betting=False,
            enable_multi_grid=False
        )
        variants.append(("单网格策略", single_grid_config))
        
        # 5. 多网格策略（无留利润）
        multi_grid_no_retention_config = GridConfig(
            initial_price=base_config['initial_price'],
            total_capital=base_config['total_capital'],
            grid_spacing=0.05,
            max_drawdown=0.6,
            max_grids=20,
            enable_profit_retention=False,
            enable_progressive_betting=True,
            enable_multi_grid=True,
            small_grid_spacing=0.05,
            medium_grid_spacing=0.15,
            large_grid_spacing=0.30,
            small_grid_ratio=0.5,
            medium_grid_ratio=0.3,
            large_grid_ratio=0.2
        )
        variants.append(("多网格策略(无留利润)", multi_grid_no_retention_config))
        
        return variants
    
    def run_strategy_comparison(self, historical_data: pd.DataFrame, 
                              base_config: Dict[str, Any]) -> List[StrategyComparison]:
        """运行策略比较"""
        logger.info("开始策略比较回测...")
        
        # 创建策略变体
        strategy_variants = self.create_strategy_variants(base_config)
        
        comparison_results = []
        
        for strategy_name, config in strategy_variants:
            logger.info(f"回测策略: {strategy_name}")
            
            # 创建策略
            strategy = BTCGridStrategy(config)
            strategy.grid_levels = strategy.generate_grid_levels()
            
            # 创建回测器
            backtester = BTCGridBacktester(strategy, self.backtest_config)
            
            # 运行回测
            result = backtester.run_backtest(historical_data)
            
            # 计算风险指标
            risk_metrics = self.calculate_risk_metrics(result, backtester)
            
            # 创建比较结果
            comparison = StrategyComparison(
                strategy_name=strategy_name,
                config=config,
                backtest_result=result,
                risk_metrics=risk_metrics
            )
            
            comparison_results.append(comparison)
            logger.info(f"{strategy_name} 回测完成 - 总收益率: {result.total_return:.2%}")
        
        self.comparison_results = comparison_results
        return comparison_results
    
    def calculate_risk_metrics(self, result: BacktestResult, backtester: BTCGridBacktester) -> Dict[str, float]:
        """计算风险指标"""
        metrics = {}
        
        # 基础风险指标
        metrics['max_drawdown'] = result.max_drawdown
        metrics['sharpe_ratio'] = result.sharpe_ratio
        metrics['profit_factor'] = result.profit_factor
        metrics['win_rate'] = result.win_rate
        
        # 计算VaR (Value at Risk)
        if len(result.daily_returns) > 1:
            returns_array = np.array(result.daily_returns)
            metrics['var_95'] = np.percentile(returns_array, 5)  # 95% VaR
            metrics['var_99'] = np.percentile(returns_array, 1)  # 99% VaR
            
            # 计算CVaR (Conditional Value at Risk)
            metrics['cvar_95'] = returns_array[returns_array <= metrics['var_95']].mean()
            metrics['cvar_99'] = returns_array[returns_array <= metrics['var_99']].mean()
        
        # 计算波动率
        if len(result.daily_returns) > 1:
            metrics['volatility'] = np.std(result.daily_returns) * np.sqrt(365.25)
            metrics['downside_volatility'] = np.std([r for r in result.daily_returns if r < 0]) * np.sqrt(365.25)
        
        # 计算索提诺比率
        if metrics.get('downside_volatility', 0) > 0:
            metrics['sortino_ratio'] = (result.annual_return - 0.02) / metrics['downside_volatility']  # 假设无风险利率2%
        else:
            metrics['sortino_ratio'] = 0
        
        # 计算卡尔马比率
        if result.max_drawdown > 0:
            metrics['calmar_ratio'] = result.annual_return / result.max_drawdown
        else:
            metrics['calmar_ratio'] = 0
        
        # 计算最大连续亏损天数
        consecutive_loss_days = 0
        max_consecutive_loss_days = 0
        for ret in result.daily_returns:
            if ret < 0:
                consecutive_loss_days += 1
                max_consecutive_loss_days = max(max_consecutive_loss_days, consecutive_loss_days)
            else:
                consecutive_loss_days = 0
        metrics['max_consecutive_loss_days'] = max_consecutive_loss_days
        
        return metrics
    
    def generate_comparison_report(self) -> str:
        """生成比较报告"""
        if not self.comparison_results:
            return "没有比较结果"
        
        report = "=== BTC网格策略比较报告 ===\n\n"
        
        # 创建比较表格
        comparison_data = []
        for comp in self.comparison_results:
            result = comp.backtest_result
            risk = comp.risk_metrics
            
            comparison_data.append({
                '策略名称': comp.strategy_name,
                '总收益率': f"{result.total_return:.2%}",
                '年化收益率': f"{result.annual_return:.2%}",
                '最大回撤': f"{result.max_drawdown:.2%}",
                '夏普比率': f"{result.sharpe_ratio:.4f}",
                '索提诺比率': f"{risk.get('sortino_ratio', 0):.4f}",
                '卡尔马比率': f"{risk.get('calmar_ratio', 0):.4f}",
                '盈利因子': f"{result.profit_factor:.4f}",
                '胜率': f"{result.win_rate:.2%}",
                '总交易次数': result.total_trades,
                '波动率': f"{risk.get('volatility', 0):.2%}",
                'VaR(95%)': f"{risk.get('var_95', 0):.2%}",
                'CVaR(95%)': f"{risk.get('cvar_95', 0):.2%}"
            })
        
        # 转换为DataFrame并格式化
        df = pd.DataFrame(comparison_data)
        
        report += "策略表现比较:\n"
        report += df.to_string(index=False)
        report += "\n\n"
        
        # 找出最佳策略
        best_return = max(self.comparison_results, key=lambda x: x.backtest_result.total_return)
        best_sharpe = max(self.comparison_results, key=lambda x: x.risk_metrics.get('sharpe_ratio', 0))
        best_drawdown = min(self.comparison_results, key=lambda x: x.backtest_result.max_drawdown)
        
        report += "=== 最佳策略分析 ===\n"
        report += f"最高收益率: {best_return.strategy_name} ({best_return.backtest_result.total_return:.2%})\n"
        report += f"最佳夏普比率: {best_sharpe.strategy_name} ({best_sharpe.risk_metrics.get('sharpe_ratio', 0):.4f})\n"
        report += f"最小回撤: {best_drawdown.strategy_name} ({best_drawdown.backtest_result.max_drawdown:.2%})\n\n"
        
        # 策略配置对比
        report += "=== 策略配置对比 ===\n"
        for comp in self.comparison_results:
            config = comp.config
            report += f"\n{comp.strategy_name}:\n"
            report += f"  网格间距: {config.grid_spacing:.1%}\n"
            report += f"  最大回撤: {config.max_drawdown:.1%}\n"
            report += f"  最大网格数: {config.max_grids}\n"
            report += f"  多网格: {'是' if config.enable_multi_grid else '否'}\n"
            report += f"  留利润: {'是' if config.enable_profit_retention else '否'}\n"
            report += f"  逐格加码: {'是' if config.enable_progressive_betting else '否'}\n"
        
        return report
    
    def plot_comparison_charts(self, save_path: str = None):
        """绘制比较图表"""
        if not self.comparison_results:
            logger.warning("没有比较结果可以绘制")
            return
        
        try:
            fig, axes = plt.subplots(2, 3, figsize=(18, 12))
            fig.suptitle('BTC网格策略比较分析', fontsize=16)
            
            # 准备数据
            strategy_names = [comp.strategy_name for comp in self.comparison_results]
            total_returns = [comp.backtest_result.total_return for comp in self.comparison_results]
            annual_returns = [comp.backtest_result.annual_return for comp in self.comparison_results]
            max_drawdowns = [comp.backtest_result.max_drawdown for comp in self.comparison_results]
            sharpe_ratios = [comp.risk_metrics.get('sharpe_ratio', 0) for comp in self.comparison_results]
            profit_factors = [comp.backtest_result.profit_factor for comp in self.comparison_results]
            win_rates = [comp.backtest_result.win_rate for comp in self.comparison_results]
            
            # 1. 总收益率比较
            bars1 = axes[0, 0].bar(strategy_names, total_returns, color='skyblue', alpha=0.7)
            axes[0, 0].set_title('总收益率比较')
            axes[0, 0].set_ylabel('总收益率')
            axes[0, 0].tick_params(axis='x', rotation=45)
            axes[0, 0].grid(True, alpha=0.3)
            
            # 添加数值标签
            for bar, value in zip(bars1, total_returns):
                axes[0, 0].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.001,
                               f'{value:.1%}', ha='center', va='bottom')
            
            # 2. 年化收益率比较
            bars2 = axes[0, 1].bar(strategy_names, annual_returns, color='lightgreen', alpha=0.7)
            axes[0, 1].set_title('年化收益率比较')
            axes[0, 1].set_ylabel('年化收益率')
            axes[0, 1].tick_params(axis='x', rotation=45)
            axes[0, 1].grid(True, alpha=0.3)
            
            for bar, value in zip(bars2, annual_returns):
                axes[0, 1].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.001,
                               f'{value:.1%}', ha='center', va='bottom')
            
            # 3. 最大回撤比较
            bars3 = axes[0, 2].bar(strategy_names, max_drawdowns, color='lightcoral', alpha=0.7)
            axes[0, 2].set_title('最大回撤比较')
            axes[0, 2].set_ylabel('最大回撤')
            axes[0, 2].tick_params(axis='x', rotation=45)
            axes[0, 2].grid(True, alpha=0.3)
            
            for bar, value in zip(bars3, max_drawdowns):
                axes[0, 2].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.001,
                               f'{value:.1%}', ha='center', va='bottom')
            
            # 4. 夏普比率比较
            bars4 = axes[1, 0].bar(strategy_names, sharpe_ratios, color='gold', alpha=0.7)
            axes[1, 0].set_title('夏普比率比较')
            axes[1, 0].set_ylabel('夏普比率')
            axes[1, 0].tick_params(axis='x', rotation=45)
            axes[1, 0].grid(True, alpha=0.3)
            
            for bar, value in zip(bars4, sharpe_ratios):
                axes[1, 0].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                               f'{value:.3f}', ha='center', va='bottom')
            
            # 5. 盈利因子比较
            bars5 = axes[1, 1].bar(strategy_names, profit_factors, color='mediumpurple', alpha=0.7)
            axes[1, 1].set_title('盈利因子比较')
            axes[1, 1].set_ylabel('盈利因子')
            axes[1, 1].tick_params(axis='x', rotation=45)
            axes[1, 1].grid(True, alpha=0.3)
            
            for bar, value in zip(bars5, profit_factors):
                axes[1, 1].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                               f'{value:.2f}', ha='center', va='bottom')
            
            # 6. 胜率比较
            bars6 = axes[1, 2].bar(strategy_names, win_rates, color='orange', alpha=0.7)
            axes[1, 2].set_title('胜率比较')
            axes[1, 2].set_ylabel('胜率')
            axes[1, 2].tick_params(axis='x', rotation=45)
            axes[1, 2].grid(True, alpha=0.3)
            
            for bar, value in zip(bars6, win_rates):
                axes[1, 2].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.001,
                               f'{value:.1%}', ha='center', va='bottom')
            
            plt.tight_layout()
            
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                logger.info(f"比较图表已保存到: {save_path}")
            
            plt.show()
            
        except Exception as e:
            logger.error(f"绘制比较图表失败: {e}")
    
    def plot_equity_curves(self, save_path: str = None):
        """绘制权益曲线比较"""
        if not self.comparison_results:
            logger.warning("没有比较结果可以绘制")
            return
        
        try:
            plt.figure(figsize=(15, 8))
            
            colors = ['blue', 'red', 'green', 'orange', 'purple', 'brown']
            
            for i, comp in enumerate(self.comparison_results):
                # 这里需要从回测结果中获取权益曲线数据
                # 由于当前结构限制，我们使用简化的权益曲线
                result = comp.backtest_result
                
                # 生成简化的权益曲线（实际应用中应该从回测器中获取）
                days = len(result.daily_equity)
                if days > 0:
                    plt.plot(range(days), result.daily_equity, 
                            label=comp.strategy_name, linewidth=2, color=colors[i % len(colors)])
            
            plt.title('策略权益曲线比较', fontsize=16)
            plt.xlabel('交易天数')
            plt.ylabel('权益 ($)')
            plt.legend()
            plt.grid(True, alpha=0.3)
            
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                logger.info(f"权益曲线图已保存到: {save_path}")
            
            plt.show()
            
        except Exception as e:
            logger.error(f"绘制权益曲线失败: {e}")
    
    def save_comparison_results(self, filename: str = None):
        """保存比较结果"""
        if not self.comparison_results:
            logger.warning("没有比较结果可以保存")
            return
        
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"btc_grid_strategy_comparison_{timestamp}.json"
        
        # 准备保存的数据
        save_data = {
            'backtest_config': asdict(self.backtest_config),
            'comparison_results': []
        }
        
        for comp in self.comparison_results:
            comp_data = {
                'strategy_name': comp.strategy_name,
                'strategy_config': asdict(comp.config),
                'backtest_result': {
                    'total_trades': comp.backtest_result.total_trades,
                    'buy_trades': comp.backtest_result.buy_trades,
                    'sell_trades': comp.backtest_result.sell_trades,
                    'total_pnl': comp.backtest_result.total_pnl,
                    'realized_pnl': comp.backtest_result.realized_pnl,
                    'unrealized_pnl': comp.backtest_result.unrealized_pnl,
                    'total_return': comp.backtest_result.total_return,
                    'annual_return': comp.backtest_result.annual_return,
                    'max_drawdown': comp.backtest_result.max_drawdown,
                    'sharpe_ratio': comp.backtest_result.sharpe_ratio,
                    'profit_factor': comp.backtest_result.profit_factor,
                    'win_rate': comp.backtest_result.win_rate,
                    'avg_win': comp.backtest_result.avg_win,
                    'avg_loss': comp.backtest_result.avg_loss,
                    'max_consecutive_wins': comp.backtest_result.max_consecutive_wins,
                    'max_consecutive_losses': comp.backtest_result.max_consecutive_losses,
                    'total_commission': comp.backtest_result.total_commission,
                    'total_slippage': comp.backtest_result.total_slippage,
                    'final_capital': comp.backtest_result.final_capital,
                    'final_btc_holding': comp.backtest_result.final_btc_holding,
                    'backtest_period': comp.backtest_result.backtest_period
                },
                'risk_metrics': comp.risk_metrics
            }
            save_data['comparison_results'].append(comp_data)
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"比较结果已保存到: {filename}")
        return filename


def run_advanced_backtest_demo():
    """运行高级回测演示"""
    print("=== BTC网格策略高级回测演示 ===")
    
    # 1. 创建回测配置
    backtest_config = BacktestConfig(
        start_date='2023-01-01',
        end_date='2024-01-01',
        initial_capital=100000,
        commission_rate=0.001,
        slippage_rate=0.0005,
        enable_commission=True,
        enable_slippage=True
    )
    
    # 2. 创建高级回测器
    advanced_backtester = AdvancedBacktester(backtest_config)
    
    # 3. 基础配置
    base_config = {
        'initial_price': 50000,
        'total_capital': 100000
    }
    
    # 4. 生成历史数据
    from btc_grid_backtest import BTCGridBacktester
    temp_strategy = BTCGridStrategy(GridConfig(
        initial_price=50000,
        total_capital=100000,
        grid_spacing=0.05,
        max_drawdown=0.6,
        max_grids=20
    ))
    temp_backtester = BTCGridBacktester(temp_strategy, backtest_config)
    historical_data = temp_backtester.load_historical_data('sample')
    
    print(f"生成了{len(historical_data)}天的历史数据")
    
    # 5. 运行策略比较
    comparison_results = advanced_backtester.run_strategy_comparison(historical_data, base_config)
    
    # 6. 生成比较报告
    report = advanced_backtester.generate_comparison_report()
    print(report)
    
    # 7. 绘制比较图表
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    comparison_chart_path = f"btc_grid_strategy_comparison_{timestamp}.png"
    advanced_backtester.plot_comparison_charts(comparison_chart_path)
    
    # 8. 绘制权益曲线
    equity_curve_path = f"btc_grid_equity_curves_{timestamp}.png"
    advanced_backtester.plot_equity_curves(equity_curve_path)
    
    # 9. 保存比较结果
    result_path = advanced_backtester.save_comparison_results()
    
    print(f"\n高级回测完成！")
    print(f"比较图表: {comparison_chart_path}")
    print(f"权益曲线图: {equity_curve_path}")
    print(f"比较结果: {result_path}")


if __name__ == "__main__":
    run_advanced_backtest_demo()

