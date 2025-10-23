#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BTC网格策略 - 基于ETF拯救世界的网格策略思路
适用于比特币的网格交易策略，包含1.0基础版本和2.0高级版本

核心原则：
1. 只做不会死的品种（BTC作为数字黄金，符合条件）
2. 压力测试是最重要的
3. 低买高卖，吃波动利润
4. 长短策略结合

作者：基于ETF拯救世界的网格策略思路
版本：1.0
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional, Any, Callable
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import json
import logging
from abc import ABC, abstractmethod
import random

# 可选依赖
try:
    from scipy.optimize import minimize, differential_evolution
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False

try:
    from sklearn.model_selection import ParameterGrid
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class GridLevel:
    """网格层级配置"""
    price: float
    amount: float
    action: str  # 'buy' or 'sell'
    level: int
    grid_type: str  # 'small', 'medium', 'large'


@dataclass
class GridConfig:
    """网格策略配置"""
    # 基础配置
    initial_price: float  # 初始价格
    total_capital: float  # 总资金
    
    # 可优化超参数
    grid_spacing: float  # 网格间距（百分比）
    max_drawdown: float  # 最大回撤（百分比）
    max_grids: int  # 最大网格数量
    
    # 2.0版本可优化参数
    enable_profit_retention: bool = True  # 启用留利润
    enable_progressive_betting: bool = True  # 启用逐格加码
    enable_multi_grid: bool = True  # 启用多网格
    
    # 多网格可优化参数
    small_grid_spacing: float = 0.05  # 小网格间距
    medium_grid_spacing: float = 0.15  # 中网格间距
    large_grid_spacing: float = 0.30  # 大网格间距
    
    # 资金分配可优化参数
    small_grid_ratio: float = 0.5  # 小网格资金占比
    medium_grid_ratio: float = 0.3  # 中网格资金占比
    large_grid_ratio: float = 0.2  # 大网格资金占比
    
    # 高级可优化参数
    profit_retention_ratio: float = 0.5  # 利润保留比例
    progressive_betting_ratio: float = 0.05  # 逐格加码比例
    min_profit_threshold: float = 0.05  # 最小利润阈值
    max_position_ratio: float = 0.8  # 最大仓位比例


class BTCGridStrategy:
    """BTC网格策略主类"""
    
    def __init__(self, config: GridConfig):
        self.config = config
        self.grid_levels: List[GridLevel] = []
        self.trade_history: List[Dict] = []
        self.current_position: Dict = {
            'total_btc': 0.0,
            'total_cost': 0.0,
            'unrealized_pnl': 0.0,
            'realized_pnl': 0.0
        }
        
    def generate_grid_levels(self) -> List[GridLevel]:
        """生成网格层级"""
        levels = []
        
        if self.config.enable_multi_grid:
            # 多网格策略
            levels.extend(self._generate_small_grid())
            levels.extend(self._generate_medium_grid())
            levels.extend(self._generate_large_grid())
        else:
            # 单网格策略
            levels.extend(self._generate_single_grid())
            
        return sorted(levels, key=lambda x: x.price)
    
    def _generate_single_grid(self) -> List[GridLevel]:
        """生成单网格"""
        levels = []
        current_price = self.config.initial_price
        
        # 生成买入网格
        for i in range(self.config.max_grids):
            buy_price = current_price * (1 - self.config.grid_spacing * (i + 1))
            if buy_price <= current_price * (1 - self.config.max_drawdown):
                break
                
            amount = self.config.total_capital / self.config.max_grids / buy_price
            levels.append(GridLevel(
                price=buy_price,
                amount=amount,
                action='buy',
                level=i + 1,
                grid_type='single'
            ))
        
        # 生成卖出网格
        for i in range(self.config.max_grids):
            sell_price = current_price * (1 + self.config.grid_spacing * (i + 1))
            amount = self.config.total_capital / self.config.max_grids / current_price
            levels.append(GridLevel(
                price=sell_price,
                amount=amount,
                action='sell',
                level=i + 1,
                grid_type='single'
            ))
            
        return levels
    
    def _generate_small_grid(self) -> List[GridLevel]:
        """生成小网格（5%）"""
        levels = []
        current_price = self.config.initial_price
        capital = self.config.total_capital * self.config.small_grid_ratio
        
        # 生成买入网格
        for i in range(self.config.max_grids):
            buy_price = current_price * (1 - self.config.small_grid_spacing * (i + 1))
            if buy_price <= current_price * (1 - self.config.max_drawdown):
                break
                
            amount = capital / self.config.max_grids / buy_price
            levels.append(GridLevel(
                price=buy_price,
                amount=amount,
                action='buy',
                level=i + 1,
                grid_type='small'
            ))
        
        # 生成卖出网格
        for i in range(self.config.max_grids):
            sell_price = current_price * (1 + self.config.small_grid_spacing * (i + 1))
            amount = capital / self.config.max_grids / current_price
            levels.append(GridLevel(
                price=sell_price,
                amount=amount,
                action='sell',
                level=i + 1,
                grid_type='small'
            ))
            
        return levels
    
    def _generate_medium_grid(self) -> List[GridLevel]:
        """生成中网格（15%）"""
        levels = []
        current_price = self.config.initial_price
        capital = self.config.total_capital * self.config.medium_grid_ratio
        
        # 生成买入网格
        for i in range(self.config.max_grids // 2):  # 中网格数量减半
            buy_price = current_price * (1 - self.config.medium_grid_spacing * (i + 1))
            if buy_price <= current_price * (1 - self.config.max_drawdown):
                break
                
            amount = capital / (self.config.max_grids // 2) / buy_price
            levels.append(GridLevel(
                price=buy_price,
                amount=amount,
                action='buy',
                level=i + 1,
                grid_type='medium'
            ))
        
        # 生成卖出网格
        for i in range(self.config.max_grids // 2):
            sell_price = current_price * (1 + self.config.medium_grid_spacing * (i + 1))
            amount = capital / (self.config.max_grids // 2) / current_price
            levels.append(GridLevel(
                price=sell_price,
                amount=amount,
                action='sell',
                level=i + 1,
                grid_type='medium'
            ))
            
        return levels
    
    def _generate_large_grid(self) -> List[GridLevel]:
        """生成大网格（30%）"""
        levels = []
        current_price = self.config.initial_price
        capital = self.config.total_capital * self.config.large_grid_ratio
        
        # 生成买入网格
        for i in range(self.config.max_grids // 3):  # 大网格数量更少
            buy_price = current_price * (1 - self.config.large_grid_spacing * (i + 1))
            if buy_price <= current_price * (1 - self.config.max_drawdown):
                break
                
            amount = capital / (self.config.max_grids // 3) / buy_price
            levels.append(GridLevel(
                price=buy_price,
                amount=amount,
                action='buy',
                level=i + 1,
                grid_type='large'
            ))
        
        # 生成卖出网格
        for i in range(self.config.max_grids // 3):
            sell_price = current_price * (1 + self.config.large_grid_spacing * (i + 1))
            amount = capital / (self.config.max_grids // 3) / current_price
            levels.append(GridLevel(
                price=sell_price,
                amount=amount,
                action='sell',
                level=i + 1,
                grid_type='large'
            ))
            
        return levels
    
    def pressure_test(self) -> Dict:
        """压力测试 - 最重要的功能"""
        logger.info("开始压力测试...")
        
        # 模拟最大回撤情况
        worst_case_price = self.config.initial_price * (1 - self.config.max_drawdown)
        
        # 计算在最坏情况下的资金需求
        total_btc_needed = 0
        total_cost = 0
        
        for level in self.grid_levels:
            if level.action == 'buy' and level.price >= worst_case_price:
                total_btc_needed += level.amount
                total_cost += level.price * level.amount
        
        # 计算资金利用率
        capital_utilization = total_cost / self.config.total_capital
        
        # 计算平均成本
        avg_cost = total_cost / total_btc_needed if total_btc_needed > 0 else 0
        
        # 计算回本价格
        break_even_price = avg_cost * 1.05  # 假设5%的网格利润
        
        pressure_test_result = {
            'worst_case_price': worst_case_price,
            'total_btc_needed': total_btc_needed,
            'total_cost': total_cost,
            'capital_utilization': capital_utilization,
            'avg_cost': avg_cost,
            'break_even_price': break_even_price,
            'max_drawdown': self.config.max_drawdown,
            'is_feasible': capital_utilization <= 1.0
        }
        
        logger.info(f"压力测试结果: {pressure_test_result}")
        return pressure_test_result
    
    def execute_trade(self, current_price: float, level: GridLevel) -> Dict:
        """执行交易"""
        if level.action == 'buy':
            cost = level.price * level.amount
            self.current_position['total_btc'] += level.amount
            self.current_position['total_cost'] += cost
            
            trade_record = {
                'timestamp': datetime.now(),
                'action': 'buy',
                'price': level.price,
                'amount': level.amount,
                'cost': cost,
                'grid_type': level.grid_type,
                'level': level.level
            }
            
        else:  # sell
            revenue = level.price * level.amount
            
            # 2.0版本：留利润功能
            if self.config.enable_profit_retention:
                profit = revenue - (level.amount * self.current_position['total_cost'] / self.current_position['total_btc'])
                retained_profit = profit * 0.5  # 保留50%利润
                actual_sell_amount = level.amount - (retained_profit / level.price)
            else:
                actual_sell_amount = level.amount
            
            self.current_position['total_btc'] -= actual_sell_amount
            self.current_position['total_cost'] -= actual_sell_amount * (self.current_position['total_cost'] / self.current_position['total_btc'])
            self.current_position['realized_pnl'] += revenue - (actual_sell_amount * (self.current_position['total_cost'] / self.current_position['total_btc']))
            
            trade_record = {
                'timestamp': datetime.now(),
                'action': 'sell',
                'price': level.price,
                'amount': actual_sell_amount,
                'revenue': revenue,
                'grid_type': level.grid_type,
                'level': level.level,
                'retained_profit': retained_profit if self.config.enable_profit_retention else 0
            }
        
        self.trade_history.append(trade_record)
        return trade_record
    
    def get_trading_signals(self, current_price: float) -> List[GridLevel]:
        """获取交易信号"""
        signals = []
        
        for level in self.grid_levels:
            if level.action == 'buy' and current_price <= level.price:
                signals.append(level)
            elif level.action == 'sell' and current_price >= level.price:
                signals.append(level)
        
        return signals
    
    def calculate_performance(self) -> Dict:
        """计算策略表现"""
        if not self.trade_history:
            return {}
        
        total_trades = len(self.trade_history)
        buy_trades = len([t for t in self.trade_history if t['action'] == 'buy'])
        sell_trades = len([t for t in self.trade_history if t['action'] == 'sell'])
        
        total_realized_pnl = self.current_position['realized_pnl']
        current_unrealized_pnl = self.current_position['unrealized_pnl']
        
        return {
            'total_trades': total_trades,
            'buy_trades': buy_trades,
            'sell_trades': sell_trades,
            'realized_pnl': total_realized_pnl,
            'unrealized_pnl': current_unrealized_pnl,
            'total_pnl': total_realized_pnl + current_unrealized_pnl,
            'current_position': self.current_position
        }
    
    def export_grid_table(self, filename: str = None) -> pd.DataFrame:
        """导出网格表格"""
        if not filename:
            filename = f"btc_grid_strategy_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        grid_data = []
        for level in self.grid_levels:
            grid_data.append({
                '价格': level.price,
                '数量': level.amount,
                '操作': level.action,
                '层级': level.level,
                '网格类型': level.grid_type,
                '金额': level.price * level.amount
            })
        
        df = pd.DataFrame(grid_data)
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        logger.info(f"网格表格已导出到: {filename}")
        return df
    
    def save_config(self, filename: str = None):
        """保存配置"""
        if not filename:
            filename = f"btc_grid_config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        config_dict = {
            'initial_price': self.config.initial_price,
            'total_capital': self.config.total_capital,
            'grid_spacing': self.config.grid_spacing,
            'max_drawdown': self.config.max_drawdown,
            'max_grids': self.config.max_grids,
            'enable_profit_retention': self.config.enable_profit_retention,
            'enable_progressive_betting': self.config.enable_progressive_betting,
            'enable_multi_grid': self.config.enable_multi_grid,
            'small_grid_spacing': self.config.small_grid_spacing,
            'medium_grid_spacing': self.config.medium_grid_spacing,
            'large_grid_spacing': self.config.large_grid_spacing,
            'small_grid_ratio': self.config.small_grid_ratio,
            'medium_grid_ratio': self.config.medium_grid_ratio,
            'large_grid_ratio': self.config.large_grid_ratio
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, indent=2, ensure_ascii=False)
        
        logger.info(f"配置已保存到: {filename}")


def create_btc_grid_strategy(
    initial_price: float = 50000,  # BTC初始价格
    total_capital: float = 100000,  # 总资金10万
    max_drawdown: float = 0.6,  # 最大回撤60%
    strategy_version: str = "2.0"  # 策略版本
) -> BTCGridStrategy:
    """创建BTC网格策略的便捷函数"""
    
    if strategy_version == "1.0":
        # 1.0基础版本
        config = GridConfig(
            initial_price=initial_price,
            total_capital=total_capital,
            grid_spacing=0.05,  # 5%网格
            max_drawdown=max_drawdown,
            max_grids=20,
            enable_profit_retention=False,
            enable_progressive_betting=False,
            enable_multi_grid=False
        )
    else:
        # 2.0高级版本
        config = GridConfig(
            initial_price=initial_price,
            total_capital=total_capital,
            grid_spacing=0.05,
            max_drawdown=max_drawdown,
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
    
    strategy = BTCGridStrategy(config)
    strategy.grid_levels = strategy.generate_grid_levels()
    
    return strategy


@dataclass
class OptimizationResult:
    """超参优化结果"""
    best_params: Dict[str, Any]
    best_score: float
    optimization_history: List[Dict[str, Any]]
    execution_time: float
    convergence_info: Dict[str, Any]


class HyperparameterOptimizer:
    """超参优化器"""
    
    def __init__(self, 
                 initial_price: float,
                 total_capital: float,
                 historical_data: Optional[pd.DataFrame] = None):
        self.initial_price = initial_price
        self.total_capital = total_capital
        self.historical_data = historical_data
        
        # 定义参数搜索空间
        self.param_space = {
            'grid_spacing': (0.03, 0.12),  # 3%-12%
            'max_drawdown': (0.3, 0.8),    # 30%-80%
            'max_grids': (10, 30),         # 10-30个网格
            'small_grid_spacing': (0.03, 0.08),  # 3%-8%
            'medium_grid_spacing': (0.10, 0.25), # 10%-25%
            'large_grid_spacing': (0.20, 0.50),  # 20%-50%
            'small_grid_ratio': (0.3, 0.7),      # 30%-70%
            'medium_grid_ratio': (0.1, 0.4),     # 10%-40%
            'large_grid_ratio': (0.1, 0.3),      # 10%-30%
            'profit_retention_ratio': (0.2, 0.8), # 20%-80%
            'progressive_betting_ratio': (0.02, 0.10), # 2%-10%
            'min_profit_threshold': (0.03, 0.08), # 3%-8%
            'max_position_ratio': (0.6, 0.9)     # 60%-90%
        }
        
        # 布尔参数
        self.bool_params = [
            'enable_profit_retention',
            'enable_progressive_betting', 
            'enable_multi_grid'
        ]
    
    def create_strategy_from_params(self, params: Dict[str, Any]) -> BTCGridStrategy:
        """从参数创建策略实例"""
        # 确保资金分配比例和为1
        total_ratio = params['small_grid_ratio'] + params['medium_grid_ratio'] + params['large_grid_ratio']
        if total_ratio != 1.0:
            params['small_grid_ratio'] /= total_ratio
            params['medium_grid_ratio'] /= total_ratio
            params['large_grid_ratio'] /= total_ratio
        
        config = GridConfig(
            initial_price=self.initial_price,
            total_capital=self.total_capital,
            **params
        )
        
        strategy = BTCGridStrategy(config)
        strategy.grid_levels = strategy.generate_grid_levels()
        return strategy
    
    def objective_function(self, params: List[float], 
                          optimization_metric: str = 'sharpe_ratio') -> float:
        """目标函数"""
        try:
            # 转换参数
            param_dict = self._array_to_params(params)
            
            # 创建策略
            strategy = self.create_strategy_from_params(param_dict)
            
            # 压力测试
            pressure_result = strategy.pressure_test()
            
            # 检查可行性
            if not pressure_result['is_feasible']:
                return -1000  # 不可行策略返回极低分数
            
            # 计算优化指标
            if optimization_metric == 'sharpe_ratio':
                return self._calculate_sharpe_ratio(strategy, pressure_result)
            elif optimization_metric == 'profit_factor':
                return self._calculate_profit_factor(strategy, pressure_result)
            elif optimization_metric == 'max_drawdown_ratio':
                return self._calculate_max_drawdown_ratio(strategy, pressure_result)
            elif optimization_metric == 'composite_score':
                return self._calculate_composite_score(strategy, pressure_result)
            else:
                return self._calculate_composite_score(strategy, pressure_result)
                
        except Exception as e:
            logger.warning(f"目标函数计算失败: {e}")
            return -1000
    
    def _array_to_params(self, param_array: List[float]) -> Dict[str, Any]:
        """将参数数组转换为参数字典"""
        param_dict = {}
        
        for i, (name, (min_val, max_val)) in enumerate(self.param_space.items()):
            if name in ['max_grids']:
                param_dict[name] = int(param_array[i])
            else:
                param_dict[name] = param_array[i]
        
        # 添加布尔参数（随机选择）
        for bool_param in self.bool_params:
            param_dict[bool_param] = random.choice([True, False])
        
        return param_dict
    
    def _calculate_sharpe_ratio(self, strategy: BTCGridStrategy, 
                               pressure_result: Dict) -> float:
        """计算夏普比率"""
        if self.historical_data is not None:
            # 使用历史数据计算
            returns = self._simulate_strategy_returns(strategy)
            if len(returns) > 1:
                sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252)
                return sharpe
        
        # 使用压力测试结果估算
        expected_return = 0.1  # 假设年化收益10%
        volatility = pressure_result['max_drawdown'] * 0.5  # 估算波动率
        sharpe = expected_return / volatility if volatility > 0 else 0
        return sharpe
    
    def _calculate_profit_factor(self, strategy: BTCGridStrategy, 
                                pressure_result: Dict) -> float:
        """计算盈利因子"""
        # 基于网格间距和资金利用率估算
        grid_profit = strategy.config.grid_spacing
        capital_efficiency = 1 - pressure_result['capital_utilization']
        profit_factor = grid_profit * capital_efficiency * 10
        return profit_factor
    
    def _calculate_max_drawdown_ratio(self, strategy: BTCGridStrategy, 
                                     pressure_result: Dict) -> float:
        """计算最大回撤比率（越小越好，所以取负值）"""
        return -pressure_result['max_drawdown']
    
    def _calculate_composite_score(self, strategy: BTCGridStrategy, 
                                  pressure_result: Dict) -> float:
        """计算综合评分"""
        # 夏普比率权重40%
        sharpe_score = self._calculate_sharpe_ratio(strategy, pressure_result) * 0.4
        
        # 盈利因子权重30%
        profit_score = self._calculate_profit_factor(strategy, pressure_result) * 0.3
        
        # 资金利用率权重20%（利用率越低越好）
        capital_score = (1 - pressure_result['capital_utilization']) * 0.2
        
        # 网格数量权重10%（适中的网格数量）
        grid_count = len(strategy.grid_levels)
        optimal_grids = 20
        grid_score = 1 - abs(grid_count - optimal_grids) / optimal_grids * 0.1
        
        return sharpe_score + profit_score + capital_score + grid_score
    
    def _simulate_strategy_returns(self, strategy: BTCGridStrategy) -> List[float]:
        """模拟策略收益"""
        if self.historical_data is None:
            return []
        
        returns = []
        for _, row in self.historical_data.iterrows():
            price = row['close']
            signals = strategy.get_trading_signals(price)
            
            for signal in signals:
                trade = strategy.execute_trade(price, signal)
                if trade['action'] == 'sell':
                    profit = (trade['price'] - trade.get('cost', 0)) / trade.get('cost', 1)
                    returns.append(profit)
        
        return returns
    
    def optimize_grid_search(self, 
                           optimization_metric: str = 'composite_score',
                           max_combinations: int = 1000) -> OptimizationResult:
        """网格搜索优化"""
        if not SKLEARN_AVAILABLE:
            raise ImportError("需要安装sklearn库: pip install scikit-learn")
            
        logger.info("开始网格搜索优化...")
        start_time = datetime.now()
        
        # 生成参数组合
        param_grid = {}
        for param, (min_val, max_val) in self.param_space.items():
            if param == 'max_grids':
                param_grid[param] = list(range(int(min_val), int(max_val) + 1, 2))
            else:
                param_grid[param] = np.linspace(min_val, max_val, 5).tolist()
        
        # 限制组合数量
        if len(ParameterGrid(param_grid)) > max_combinations:
            # 随机采样
            all_combinations = list(ParameterGrid(param_grid))
            param_combinations = random.sample(all_combinations, max_combinations)
        else:
            param_combinations = list(ParameterGrid(param_grid))
        
        best_score = -float('inf')
        best_params = None
        optimization_history = []
        
        for i, params in enumerate(param_combinations):
            # 添加布尔参数
            for bool_param in self.bool_params:
                params[bool_param] = random.choice([True, False])
            
            try:
                strategy = self.create_strategy_from_params(params)
                pressure_result = strategy.pressure_test()
                
                if pressure_result['is_feasible']:
                    score = self._calculate_composite_score(strategy, pressure_result)
                    optimization_history.append({
                        'iteration': i,
                        'params': params.copy(),
                        'score': score,
                        'feasible': True
                    })
                    
                    if score > best_score:
                        best_score = score
                        best_params = params.copy()
                else:
                    optimization_history.append({
                        'iteration': i,
                        'params': params.copy(),
                        'score': -1000,
                        'feasible': False
                    })
                    
            except Exception as e:
                logger.warning(f"参数组合 {i} 计算失败: {e}")
                optimization_history.append({
                    'iteration': i,
                    'params': params.copy(),
                    'score': -1000,
                    'feasible': False,
                    'error': str(e)
                })
        
        execution_time = (datetime.now() - start_time).total_seconds()
        
        return OptimizationResult(
            best_params=best_params or {},
            best_score=best_score,
            optimization_history=optimization_history,
            execution_time=execution_time,
            convergence_info={'method': 'grid_search', 'total_combinations': len(param_combinations)}
        )
    
    def optimize_differential_evolution(self, 
                                      optimization_metric: str = 'composite_score',
                                      maxiter: int = 50,
                                      popsize: int = 15) -> OptimizationResult:
        """差分进化优化"""
        if not SCIPY_AVAILABLE:
            raise ImportError("需要安装scipy库: pip install scipy")
            
        logger.info("开始差分进化优化...")
        start_time = datetime.now()
        
        # 准备边界
        bounds = []
        for param, (min_val, max_val) in self.param_space.items():
            bounds.append((min_val, max_val))
        
        # 定义目标函数
        def objective(x):
            return -self.objective_function(x, optimization_metric)  # 最小化负值
        
        # 执行优化
        result = differential_evolution(
            objective,
            bounds,
            maxiter=maxiter,
            popsize=popsize,
            seed=42,
            workers=1
        )
        
        # 转换结果
        best_params = self._array_to_params(result.x)
        best_score = -result.fun
        
        execution_time = (datetime.now() - start_time).total_seconds()
        
        return OptimizationResult(
            best_params=best_params,
            best_score=best_score,
            optimization_history=[],  # 差分进化不保存历史
            execution_time=execution_time,
            convergence_info={
                'method': 'differential_evolution',
                'success': result.success,
                'nit': result.nit,
                'nfev': result.nfev
            }
        )
    
    def optimize_bayesian(self, 
                         optimization_metric: str = 'composite_score',
                         n_calls: int = 100) -> OptimizationResult:
        """贝叶斯优化（简化版本）"""
        logger.info("开始贝叶斯优化...")
        start_time = datetime.now()
        
        # 简化的贝叶斯优化实现
        best_score = -float('inf')
        best_params = None
        optimization_history = []
        
        # 随机搜索作为简化版本
        for i in range(n_calls):
            params = {}
            for param, (min_val, max_val) in self.param_space.items():
                if param == 'max_grids':
                    params[param] = random.randint(int(min_val), int(max_val))
                else:
                    params[param] = random.uniform(min_val, max_val)
            
            # 添加布尔参数
            for bool_param in self.bool_params:
                params[bool_param] = random.choice([True, False])
            
            try:
                strategy = self.create_strategy_from_params(params)
                pressure_result = strategy.pressure_test()
                
                if pressure_result['is_feasible']:
                    score = self._calculate_composite_score(strategy, pressure_result)
                    optimization_history.append({
                        'iteration': i,
                        'params': params.copy(),
                        'score': score,
                        'feasible': True
                    })
                    
                    if score > best_score:
                        best_score = score
                        best_params = params.copy()
                        
            except Exception as e:
                logger.warning(f"贝叶斯优化迭代 {i} 失败: {e}")
        
        execution_time = (datetime.now() - start_time).total_seconds()
        
        return OptimizationResult(
            best_params=best_params or {},
            best_score=best_score,
            optimization_history=optimization_history,
            execution_time=execution_time,
            convergence_info={'method': 'bayesian_simplified', 'n_calls': n_calls}
        )
    
    def save_optimization_result(self, result: OptimizationResult, 
                               filename: str = None) -> str:
        """保存优化结果"""
        if not filename:
            filename = f"btc_grid_optimization_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        # 准备保存数据
        save_data = {
            'best_params': result.best_params,
            'best_score': result.best_score,
            'execution_time': result.execution_time,
            'convergence_info': result.convergence_info,
            'optimization_history': result.optimization_history[:100]  # 只保存前100个
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"优化结果已保存到: {filename}")
        return filename


def create_optimized_strategy(initial_price: float = 50000,
                            total_capital: float = 100000,
                            optimization_method: str = 'differential_evolution',
                            optimization_metric: str = 'composite_score',
                            historical_data: Optional[pd.DataFrame] = None) -> Tuple[BTCGridStrategy, OptimizationResult]:
    """创建优化后的策略"""
    
    optimizer = HyperparameterOptimizer(
        initial_price=initial_price,
        total_capital=total_capital,
        historical_data=historical_data
    )
    
    if optimization_method == 'grid_search':
        result = optimizer.optimize_grid_search(optimization_metric)
    elif optimization_method == 'differential_evolution':
        result = optimizer.optimize_differential_evolution(optimization_metric)
    elif optimization_method == 'bayesian':
        result = optimizer.optimize_bayesian(optimization_metric)
    else:
        raise ValueError(f"不支持的优化方法: {optimization_method}")
    
    # 创建优化后的策略
    optimized_strategy = optimizer.create_strategy_from_params(result.best_params)
    
    # 保存优化结果
    optimizer.save_optimization_result(result)
    
    return optimized_strategy, result


if __name__ == "__main__":
    # 示例使用
    print("=== BTC网格策略示例 ===")
    
    # 创建2.0版本策略
    strategy = create_btc_grid_strategy(
        initial_price=50000,
        total_capital=100000,
        max_drawdown=0.6,
        strategy_version="2.0"
    )
    
    # 压力测试
    pressure_result = strategy.pressure_test()
    print("\n压力测试结果:")
    print(f"最坏情况价格: ${pressure_result['worst_case_price']:,.2f}")
    print(f"资金利用率: {pressure_result['capital_utilization']:.2%}")
    print(f"平均成本: ${pressure_result['avg_cost']:,.2f}")
    print(f"回本价格: ${pressure_result['break_even_price']:,.2f}")
    print(f"策略可行性: {'是' if pressure_result['is_feasible'] else '否'}")
    
    # 导出网格表格
    grid_df = strategy.export_grid_table()
    print(f"\n网格表格已生成，共{len(grid_df)}个网格点")
    
    # 保存配置
    strategy.save_config()
    
    print("\n=== 策略创建完成 ===")
    print("请仔细阅读网格表格，确认所有参数符合您的风险承受能力")
    print("记住：压力测试是最重要的！")
    
    # 超参优化示例
    print("\n=== 超参优化示例 ===")
    try:
        optimized_strategy, opt_result = create_optimized_strategy(
            initial_price=50000,
            total_capital=100000,
            optimization_method='differential_evolution',
            optimization_metric='composite_score'
        )
        
        print("优化完成！")
        print(f"最佳评分: {opt_result.best_score:.4f}")
        print(f"执行时间: {opt_result.execution_time:.2f}秒")
        print(f"最佳参数: {opt_result.best_params}")
        
    except Exception as e:
        print(f"超参优化失败: {e}")
        print("请确保安装了scipy和sklearn库")
