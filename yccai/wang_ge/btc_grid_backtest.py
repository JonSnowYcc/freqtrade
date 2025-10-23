#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BTC网格策略回测系统
使用历史数据对BTC网格策略进行回测分析
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

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


@dataclass
class BacktestConfig:
    """回测配置"""
    start_date: str
    end_date: str
    initial_capital: float
    commission_rate: float = 0.001  # 手续费率0.1%
    slippage_rate: float = 0.0005   # 滑点0.05%
    enable_commission: bool = True
    enable_slippage: bool = True


@dataclass
class TradeRecord:
    """交易记录"""
    timestamp: datetime
    price: float
    amount: float
    action: str  # 'buy' or 'sell'
    cost: float
    commission: float
    slippage: float
    grid_level: int
    grid_type: str


@dataclass
class BacktestResult:
    """回测结果"""
    total_trades: int
    buy_trades: int
    sell_trades: int
    total_pnl: float
    realized_pnl: float
    unrealized_pnl: float
    total_return: float
    annual_return: float
    max_drawdown: float
    sharpe_ratio: float
    profit_factor: float
    win_rate: float
    avg_win: float
    avg_loss: float
    max_consecutive_wins: int
    max_consecutive_losses: int
    total_commission: float
    total_slippage: float
    final_capital: float
    final_btc_holding: float
    backtest_period: str
    trade_records: List[TradeRecord]
    daily_returns: List[float]
    daily_equity: List[float]
    daily_dates: List[datetime]


class BTCGridBacktester:
    """BTC网格策略回测器"""
    
    def __init__(self, strategy: BTCGridStrategy, backtest_config: BacktestConfig):
        self.strategy = strategy
        self.config = backtest_config
        self.trade_records: List[TradeRecord] = []
        self.current_capital = backtest_config.initial_capital
        self.current_btc = 0.0
        self.daily_equity: List[float] = []
        self.daily_returns: List[float] = []
        self.daily_dates: List[datetime] = []
        self.equity_curve: List[float] = []
        self.max_equity = backtest_config.initial_capital
        self.drawdown_curve: List[float] = []
        
    def generate_sample_data(self, start_price: float = 50000, 
                           days: int = 365,
                           volatility: float = 0.03) -> pd.DataFrame:
        """生成模拟的BTC价格数据"""
        start_date = datetime.strptime(self.config.start_date, '%Y-%m-%d')
        end_date = datetime.strptime(self.config.end_date, '%Y-%m-%d')
        
        # 计算实际天数
        actual_days = (end_date - start_date).days
        dates = pd.date_range(start=start_date, end=end_date, freq='D')
        
        # 生成随机游走价格数据，加入趋势和周期性
        np.random.seed(42)  # 固定随机种子以便复现
        
        # 基础随机游走
        returns = np.random.normal(0, volatility, len(dates))
        
        # 添加趋势（轻微上涨趋势）
        trend = np.linspace(0, 0.2, len(dates))  # 20%的年化趋势
        returns += trend / len(dates)
        
        # 添加周期性波动
        cycle = 0.1 * np.sin(2 * np.pi * np.arange(len(dates)) / 30)  # 30天周期
        returns += cycle / len(dates)
        
        # 添加一些极端波动事件
        extreme_days = np.random.choice(len(dates), size=int(len(dates) * 0.05), replace=False)
        for day in extreme_days:
            returns[day] += np.random.choice([-0.1, 0.1])  # ±10%的极端波动
        
        # 计算价格序列
        prices = [start_price]
        for ret in returns[1:]:
            new_price = prices[-1] * (1 + ret)
            prices.append(max(new_price, 1000))  # 最低价格1000美元
        
        # 生成OHLC数据
        df = pd.DataFrame({
            'date': dates,
            'close': prices,
            'open': prices,
            'high': [p * (1 + abs(np.random.normal(0, 0.02))) for p in prices],
            'low': [p * (1 - abs(np.random.normal(0, 0.02))) for p in prices],
            'volume': np.random.uniform(1000, 10000, len(dates))
        })
        
        # 确保high >= max(open, close), low <= min(open, close)
        df['high'] = df[['open', 'close', 'high']].max(axis=1)
        df['low'] = df[['open', 'close', 'low']].min(axis=1)
        
        return df
    
    def load_historical_data(self, data_source: str = 'sample') -> pd.DataFrame:
        """加载历史数据"""
        if data_source == 'sample':
            logger.info("生成模拟BTC价格数据...")
            return self.generate_sample_data()
        else:
            # 这里可以添加从其他数据源加载真实数据的逻辑
            # 比如从CSV文件、API等加载
            raise NotImplementedError("暂不支持其他数据源，请使用'sample'")
    
    def calculate_commission(self, trade_value: float) -> float:
        """计算手续费"""
        if not self.config.enable_commission:
            return 0.0
        return trade_value * self.config.commission_rate
    
    def calculate_slippage(self, trade_value: float) -> float:
        """计算滑点成本"""
        if not self.config.enable_slippage:
            return 0.0
        return trade_value * self.config.slippage_rate
    
    def execute_trade(self, timestamp: datetime, price: float, 
                     amount: float, action: str, grid_level: int, 
                     grid_type: str) -> TradeRecord:
        """执行交易"""
        trade_value = price * amount
        commission = self.calculate_commission(trade_value)
        slippage = self.calculate_slippage(trade_value)
        
        # 计算实际成交价格（考虑滑点）
        if action == 'buy':
            actual_price = price * (1 + self.config.slippage_rate)
            total_cost = trade_value + commission + slippage
        else:  # sell
            actual_price = price * (1 - self.config.slippage_rate)
            total_cost = trade_value - commission - slippage
        
        # 更新持仓
        if action == 'buy':
            if total_cost <= self.current_capital:
                self.current_capital -= total_cost
                self.current_btc += amount
            else:
                # 资金不足，调整交易数量
                available_capital = self.current_capital
                adjusted_amount = available_capital / (actual_price * (1 + self.config.commission_rate + self.config.slippage_rate))
                if adjusted_amount > 0:
                    self.current_capital = 0
                    self.current_btc += adjusted_amount
                    amount = adjusted_amount
                    total_cost = available_capital
                else:
                    return None  # 无法执行交易
        else:  # sell
            if amount <= self.current_btc:
                self.current_btc -= amount
                self.current_capital += total_cost
            else:
                # BTC不足，调整交易数量
                available_btc = self.current_btc
                if available_btc > 0:
                    self.current_btc = 0
                    self.current_capital += available_btc * actual_price - commission - slippage
                    amount = available_btc
                    total_cost = available_btc * actual_price - commission - slippage
                else:
                    return None  # 无法执行交易
        
        # 创建交易记录
        trade_record = TradeRecord(
            timestamp=timestamp,
            price=actual_price,
            amount=amount,
            action=action,
            cost=total_cost,
            commission=commission,
            slippage=slippage,
            grid_level=grid_level,
            grid_type=grid_type
        )
        
        self.trade_records.append(trade_record)
        return trade_record
    
    def run_backtest(self, historical_data: pd.DataFrame) -> BacktestResult:
        """运行回测"""
        logger.info(f"开始回测，数据期间: {historical_data['date'].min()} 到 {historical_data['date'].max()}")
        logger.info(f"初始资金: ${self.config.initial_capital:,.2f}")
        
        # 重置策略状态
        self.strategy.trade_history = []
        self.strategy.current_position = {
            'total_btc': 0.0,
            'total_cost': 0.0,
            'unrealized_pnl': 0.0,
            'realized_pnl': 0.0
        }
        
        # 重置回测器状态
        self.current_capital = self.config.initial_capital
        self.current_btc = 0.0
        self.trade_records = []
        self.daily_equity = []
        self.daily_returns = []
        self.daily_dates = []
        self.equity_curve = []
        self.max_equity = self.config.initial_capital
        self.drawdown_curve = []
        
        # 逐日回测
        for idx, row in historical_data.iterrows():
            current_date = row['date']
            current_price = row['close']
            
            # 获取交易信号
            signals = self.strategy.get_trading_signals(current_price)
            
            # 执行交易
            for signal in signals:
                trade_record = self.execute_trade(
                    timestamp=current_date,
                    price=current_price,
                    amount=signal.amount,
                    action=signal.action,
                    grid_level=signal.level,
                    grid_type=signal.grid_type
                )
                
                if trade_record:
                    # 更新策略状态
                    self.strategy.execute_trade(current_price, signal)
            
            # 计算当日权益
            current_equity = self.current_capital + self.current_btc * current_price
            
            # 更新最大权益和回撤
            if current_equity > self.max_equity:
                self.max_equity = current_equity
            
            current_drawdown = (self.max_equity - current_equity) / self.max_equity
            
            # 记录数据
            self.daily_equity.append(current_equity)
            self.daily_returns.append((current_equity - (self.daily_equity[-2] if len(self.daily_equity) > 1 else self.config.initial_capital)) / (self.daily_equity[-2] if len(self.daily_equity) > 1 else self.config.initial_capital))
            self.daily_dates.append(current_date)
            self.equity_curve.append(current_equity)
            self.drawdown_curve.append(current_drawdown)
        
        # 计算回测结果
        result = self.calculate_backtest_results(historical_data)
        logger.info("回测完成")
        
        return result
    
    def calculate_backtest_results(self, historical_data: pd.DataFrame) -> BacktestResult:
        """计算回测结果"""
        if not self.daily_equity:
            raise ValueError("没有回测数据")
        
        # 基础统计
        total_trades = len(self.trade_records)
        buy_trades = len([t for t in self.trade_records if t.action == 'buy'])
        sell_trades = len([t for t in self.trade_records if t.action == 'sell'])
        
        # 计算收益
        initial_capital = self.config.initial_capital
        final_capital = self.daily_equity[-1]
        total_pnl = final_capital - initial_capital
        total_return = total_pnl / initial_capital
        
        # 计算年化收益率
        days = len(self.daily_equity)
        years = days / 365.25
        annual_return = (final_capital / initial_capital) ** (1 / years) - 1 if years > 0 else 0
        
        # 计算最大回撤
        max_drawdown = max(self.drawdown_curve) if self.drawdown_curve else 0
        
        # 计算夏普比率
        if len(self.daily_returns) > 1:
            returns_std = np.std(self.daily_returns)
            returns_mean = np.mean(self.daily_returns)
            sharpe_ratio = (returns_mean * 365.25) / (returns_std * np.sqrt(365.25)) if returns_std > 0 else 0
        else:
            sharpe_ratio = 0
        
        # 计算盈利因子
        total_commission = sum(t.commission for t in self.trade_records)
        total_slippage = sum(t.slippage for t in self.trade_records)
        
        # 计算胜率
        profitable_trades = 0
        total_profit = 0
        total_loss = 0
        consecutive_wins = 0
        consecutive_losses = 0
        max_consecutive_wins = 0
        max_consecutive_losses = 0
        
        # 分析交易记录
        for i, trade in enumerate(self.trade_records):
            if trade.action == 'sell' and i > 0:
                # 找到对应的买入交易
                for j in range(i-1, -1, -1):
                    if self.trade_records[j].action == 'buy':
                        buy_trade = self.trade_records[j]
                        profit = trade.cost - buy_trade.cost
                        
                        if profit > 0:
                            profitable_trades += 1
                            total_profit += profit
                            consecutive_wins += 1
                            consecutive_losses = 0
                            max_consecutive_wins = max(max_consecutive_wins, consecutive_wins)
                        else:
                            total_loss += abs(profit)
                            consecutive_losses += 1
                            consecutive_wins = 0
                            max_consecutive_losses = max(max_consecutive_losses, consecutive_losses)
                        break
        
        win_rate = profitable_trades / sell_trades if sell_trades > 0 else 0
        profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
        
        # 计算平均盈亏
        avg_win = total_profit / profitable_trades if profitable_trades > 0 else 0
        avg_loss = total_loss / (sell_trades - profitable_trades) if (sell_trades - profitable_trades) > 0 else 0
        
        # 计算未实现收益
        final_price = historical_data['close'].iloc[-1]
        final_btc_holding = self.current_btc
        unrealized_pnl = final_btc_holding * final_price - (final_btc_holding * self.strategy.config.initial_price if final_btc_holding > 0 else 0)
        realized_pnl = total_pnl - unrealized_pnl
        
        return BacktestResult(
            total_trades=total_trades,
            buy_trades=buy_trades,
            sell_trades=sell_trades,
            total_pnl=total_pnl,
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
            total_return=total_return,
            annual_return=annual_return,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            profit_factor=profit_factor,
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            max_consecutive_wins=max_consecutive_wins,
            max_consecutive_losses=max_consecutive_losses,
            total_commission=total_commission,
            total_slippage=total_slippage,
            final_capital=final_capital,
            final_btc_holding=final_btc_holding,
            backtest_period=f"{historical_data['date'].min().strftime('%Y-%m-%d')} 到 {historical_data['date'].max().strftime('%Y-%m-%d')}",
            trade_records=self.trade_records,
            daily_returns=self.daily_returns,
            daily_equity=self.daily_equity,
            daily_dates=self.daily_dates
        )
    
    def generate_backtest_report(self, result: BacktestResult) -> str:
        """生成回测报告"""
        report = f"""
=== BTC网格策略回测报告 ===

回测期间: {result.backtest_period}
初始资金: ${self.config.initial_capital:,.2f}
最终资金: ${result.final_capital:,.2f}
最终BTC持仓: {result.final_btc_holding:.6f} BTC

=== 收益指标 ===
总收益: ${result.total_pnl:,.2f}
总收益率: {result.total_return:.2%}
年化收益率: {result.annual_return:.2%}
已实现收益: ${result.realized_pnl:,.2f}
未实现收益: ${result.unrealized_pnl:,.2f}

=== 风险指标 ===
最大回撤: {result.max_drawdown:.2%}
夏普比率: {result.sharpe_ratio:.4f}
盈利因子: {result.profit_factor:.4f}

=== 交易统计 ===
总交易次数: {result.total_trades}
买入次数: {result.buy_trades}
卖出次数: {result.sell_trades}
胜率: {result.win_rate:.2%}
平均盈利: ${result.avg_win:,.2f}
平均亏损: ${result.avg_loss:,.2f}
最大连续盈利: {result.max_consecutive_wins}次
最大连续亏损: {result.max_consecutive_losses}次

=== 成本统计 ===
总手续费: ${result.total_commission:,.2f}
总滑点成本: ${result.total_slippage:,.2f}
总交易成本: ${result.total_commission + result.total_slippage:,.2f}

=== 策略配置 ===
初始价格: ${self.strategy.config.initial_price:,.2f}
网格间距: {self.strategy.config.grid_spacing:.1%}
最大回撤: {self.strategy.config.max_drawdown:.1%}
最大网格数: {self.strategy.config.max_grids}
多网格策略: {'启用' if self.strategy.config.enable_multi_grid else '禁用'}
留利润功能: {'启用' if self.strategy.config.enable_profit_retention else '禁用'}
逐格加码: {'启用' if self.strategy.config.enable_progressive_betting else '禁用'}
"""
        return report
    
    def plot_backtest_results(self, result: BacktestResult, save_path: str = None):
        """绘制回测结果图表"""
        try:
            fig, axes = plt.subplots(2, 2, figsize=(15, 12))
            fig.suptitle('BTC网格策略回测结果', fontsize=16)
            
            # 1. 权益曲线
            axes[0, 0].plot(self.daily_dates, self.daily_equity, label='策略权益', linewidth=2)
            axes[0, 0].axhline(y=self.config.initial_capital, color='r', linestyle='--', label='初始资金')
            axes[0, 0].set_title('权益曲线')
            axes[0, 0].set_ylabel('权益 ($)')
            axes[0, 0].legend()
            axes[0, 0].grid(True, alpha=0.3)
            
            # 2. 回撤曲线
            axes[0, 1].fill_between(self.daily_dates, self.drawdown_curve, 0, 
                                   color='red', alpha=0.3, label='回撤')
            axes[0, 1].set_title('回撤曲线')
            axes[0, 1].set_ylabel('回撤比例')
            axes[0, 1].legend()
            axes[0, 1].grid(True, alpha=0.3)
            
            # 3. 日收益率分布
            if len(self.daily_returns) > 1:
                axes[1, 0].hist(self.daily_returns, bins=30, alpha=0.7, edgecolor='black')
                axes[1, 0].set_title('日收益率分布')
                axes[1, 0].set_xlabel('日收益率')
                axes[1, 0].set_ylabel('频次')
                axes[1, 0].grid(True, alpha=0.3)
            
            # 4. 交易统计
            trade_stats = {
                '买入': result.buy_trades,
                '卖出': result.sell_trades,
                '总交易': result.total_trades
            }
            axes[1, 1].bar(trade_stats.keys(), trade_stats.values(), 
                          color=['green', 'red', 'blue'], alpha=0.7)
            axes[1, 1].set_title('交易统计')
            axes[1, 1].set_ylabel('交易次数')
            axes[1, 1].grid(True, alpha=0.3)
            
            plt.tight_layout()
            
            if save_path:
                plt.savefig(save_path, dpi=300, bbox_inches='tight')
                logger.info(f"回测图表已保存到: {save_path}")
            
            plt.show()
            
        except Exception as e:
            logger.error(f"绘制图表失败: {e}")
    
    def save_backtest_result(self, result: BacktestResult, filename: str = None):
        """保存回测结果"""
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"btc_grid_backtest_result_{timestamp}.json"
        
        # 准备保存的数据
        save_data = {
            'backtest_config': asdict(self.config),
            'strategy_config': asdict(self.strategy.config),
            'backtest_result': {
                'total_trades': result.total_trades,
                'buy_trades': result.buy_trades,
                'sell_trades': result.sell_trades,
                'total_pnl': result.total_pnl,
                'realized_pnl': result.realized_pnl,
                'unrealized_pnl': result.unrealized_pnl,
                'total_return': result.total_return,
                'annual_return': result.annual_return,
                'max_drawdown': result.max_drawdown,
                'sharpe_ratio': result.sharpe_ratio,
                'profit_factor': result.profit_factor,
                'win_rate': result.win_rate,
                'avg_win': result.avg_win,
                'avg_loss': result.avg_loss,
                'max_consecutive_wins': result.max_consecutive_wins,
                'max_consecutive_losses': result.max_consecutive_losses,
                'total_commission': result.total_commission,
                'total_slippage': result.total_slippage,
                'final_capital': result.final_capital,
                'final_btc_holding': result.final_btc_holding,
                'backtest_period': result.backtest_period
            },
            'trade_records': [asdict(trade) for trade in result.trade_records],
            'daily_equity': self.daily_equity,
            'daily_returns': self.daily_returns,
            'daily_dates': [d.isoformat() for d in self.daily_dates]
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, indent=2, ensure_ascii=False, default=str)
        
        logger.info(f"回测结果已保存到: {filename}")
        return filename


def run_backtest_demo():
    """运行回测演示"""
    print("=== BTC网格策略回测演示 ===")
    
    # 1. 创建策略
    from btc_grid_strategy import create_btc_grid_strategy
    
    strategy = create_btc_grid_strategy(
        initial_price=50000,
        total_capital=100000,
        max_drawdown=0.6,
        strategy_version="2.0"
    )
    
    # 2. 创建回测配置
    backtest_config = BacktestConfig(
        start_date='2023-01-01',
        end_date='2024-01-01',
        initial_capital=100000,
        commission_rate=0.001,
        slippage_rate=0.0005,
        enable_commission=True,
        enable_slippage=True
    )
    
    # 3. 创建回测器
    backtester = BTCGridBacktester(strategy, backtest_config)
    
    # 4. 加载数据
    historical_data = backtester.load_historical_data('sample')
    print(f"加载了{len(historical_data)}天的历史数据")
    
    # 5. 运行回测
    result = backtester.run_backtest(historical_data)
    
    # 6. 生成报告
    report = backtester.generate_backtest_report(result)
    print(report)
    
    # 7. 绘制图表
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    chart_path = f"btc_grid_backtest_chart_{timestamp}.png"
    backtester.plot_backtest_results(result, chart_path)
    
    # 8. 保存结果
    result_path = backtester.save_backtest_result(result)
    
    print(f"\n回测完成！")
    print(f"图表保存路径: {chart_path}")
    print(f"结果保存路径: {result_path}")


if __name__ == "__main__":
    run_backtest_demo()

