# BTC网格策略

基于ETF拯救世界的网格策略思路，专门为比特币设计的网格交易策略。

## 📋 目录

- [策略概述](#策略概述)
- [核心原则](#核心原则)
- [策略版本](#策略版本)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [使用示例](#使用示例)
- [风险提示](#风险提示)
- [文件说明](#文件说明)

## 🎯 策略概述

网格策略是一种在震荡市中获取收益的波段交易策略。通过在预设的价格区间内设置买入和卖出网格，实现低买高卖，获取波动利润。

### 核心思想
- **低买高卖**：在价格下跌时买入，上涨时卖出
- **机械化交易**：按照预设规则执行，避免情绪化操作
- **压力测试**：提前计算最坏情况下的资金需求

## 🏗️ 核心原则

1. **只做不会死的品种**：BTC作为数字黄金，符合条件
2. **压力测试是最重要的**：必须计算最坏情况下的资金需求
3. **波段策略定位**：不是长期策略，是波段策略
4. **长短结合**：与长期持有策略结合使用

## 📊 策略版本

### 1.0版本（基础版）
- 单网格策略
- 固定网格间距（5%）
- 简单易用，适合初学者

### 2.0版本（高级版）
- **多网格策略**：小网格（5%）、中网格（15%）、大网格（30%）
- **留利润功能**：卖出时保留部分利润长期持有
- **逐格加码**：价格越低，投入越多
- **一网打尽**：大小网格结合，捕获不同级别的波动

## 🚀 快速开始

### 1. 安装依赖
```bash
# 基础依赖（必需）
pip install pandas numpy

# 超参优化依赖（可选）
pip install scipy scikit-learn

# 可视化依赖（可选）
pip install matplotlib seaborn
```

### 2. 基础使用
```python
from btc_grid_strategy import create_btc_grid_strategy

# 创建2.0版本策略
strategy = create_btc_grid_strategy(
    initial_price=50000,      # BTC初始价格
    total_capital=100000,     # 总资金10万
    max_drawdown=0.6,         # 最大回撤60%
    strategy_version="2.0"
)

# 压力测试
pressure_result = strategy.pressure_test()
print(f"资金利用率: {pressure_result['capital_utilization']:.2%}")
print(f"策略可行性: {'可行' if pressure_result['is_feasible'] else '不可行'}")

# 导出网格表格
grid_df = strategy.export_grid_table()
```

### 3. 超参优化使用
```python
from btc_grid_strategy import create_optimized_strategy

# 创建优化后的策略
optimized_strategy, opt_result = create_optimized_strategy(
    initial_price=50000,
    total_capital=100000,
    optimization_method='differential_evolution',  # 优化方法
    optimization_metric='composite_score'          # 优化指标
)

print(f"最佳评分: {opt_result.best_score:.4f}")
print(f"最佳参数: {opt_result.best_params}")
```

### 4. 运行完整示例
```bash
# 基础示例
python btc_grid_example.py

# 超参优化示例
python btc_grid_optimization.py
```

## ⚙️ 配置说明

### 基础参数
- `initial_price`: BTC初始价格（美元）
- `total_capital`: 总资金（美元）
- `max_drawdown`: 最大回撤比例（0.6表示60%）
- `max_grids`: 最大网格数量

### 2.0版本参数
- `small_grid_spacing`: 小网格间距（5%）
- `medium_grid_spacing`: 中网格间距（15%）
- `large_grid_spacing`: 大网格间距（30%）
- `small_grid_ratio`: 小网格资金占比（50%）
- `medium_grid_ratio`: 中网格资金占比（30%）
- `large_grid_ratio`: 大网格资金占比（20%）

### 风险控制参数
- **保守型**：最大回撤40%，网格间距3-5%
- **平衡型**：最大回撤60%，网格间距5-8%
- **激进型**：最大回撤80%，网格间距8-12%

## 📈 使用示例

### 示例1：基础使用
```python
# 创建策略
strategy = create_btc_grid_strategy(
    initial_price=50000,
    total_capital=100000,
    max_drawdown=0.6,
    strategy_version="2.0"
)

# 获取交易信号
current_price = 45000
signals = strategy.get_trading_signals(current_price)
print(f"当前价格 ${current_price} 的交易信号: {len(signals)} 个")

# 执行交易
for signal in signals:
    trade = strategy.execute_trade(current_price, signal)
    print(f"执行交易: {trade['action']} {trade['amount']:.6f} BTC @ ${trade['price']:,.2f}")
```

### 示例2：自定义配置
```python
from btc_grid_strategy import GridConfig, BTCGridStrategy

# 自定义配置
config = GridConfig(
    initial_price=45000,
    total_capital=50000,
    grid_spacing=0.08,
    max_drawdown=0.5,
    max_grids=15,
    enable_multi_grid=True,
    small_grid_spacing=0.08,
    medium_grid_spacing=0.20,
    large_grid_spacing=0.40
)

strategy = BTCGridStrategy(config)
strategy.grid_levels = strategy.generate_grid_levels()
```

## ⚠️ 风险提示

### 重要提醒
1. **压力测试是最重要的**：必须计算最坏情况下的资金需求
2. **只做不会死的品种**：BTC符合条件，但仍有风险
3. **波段策略定位**：不是长期策略，是波段策略
4. **长短结合**：建议与长期持有策略结合使用
5. **风险控制**：请根据自身风险承受能力调整参数

### 策略局限性
- **单边上涨**：可能错失大牛市收益
- **单边下跌**：可能面临较大回撤
- **震荡不足**：如果市场长期横盘，收益有限

### 适用场景
- ✅ 震荡市
- ✅ 波动较大的市场
- ✅ 与长期持有策略结合
- ❌ 单边上涨趋势
- ❌ 单边下跌趋势

## 📁 文件说明

- `btc_grid_strategy.py`: 主策略文件
- `btc_grid_example.py`: 使用示例和演示
- `btc_grid_config.json`: 配置文件模板
- `README.md`: 说明文档

## 🔧 高级功能

### 压力测试
```python
pressure_result = strategy.pressure_test()
print(f"最坏情况价格: ${pressure_result['worst_case_price']:,.2f}")
print(f"资金利用率: {pressure_result['capital_utilization']:.2%}")
print(f"平均成本: ${pressure_result['avg_cost']:,.2f}")
```

### 策略表现分析
```python
performance = strategy.calculate_performance()
print(f"总交易次数: {performance['total_trades']}")
print(f"已实现收益: ${performance['realized_pnl']:,.2f}")
print(f"收益率: {performance['total_pnl'] / strategy.config.total_capital:.2%}")
```

### 超参优化
```python
from btc_grid_strategy import HyperparameterOptimizer

# 创建优化器
optimizer = HyperparameterOptimizer(
    initial_price=50000,
    total_capital=100000,
    historical_data=your_historical_data  # 可选
)

# 网格搜索优化
grid_result = optimizer.optimize_grid_search(
    optimization_metric='composite_score',
    max_combinations=1000
)

# 差分进化优化
de_result = optimizer.optimize_differential_evolution(
    optimization_metric='composite_score',
    maxiter=50,
    popsize=15
)

# 贝叶斯优化
bayesian_result = optimizer.optimize_bayesian(
    optimization_metric='composite_score',
    n_calls=100
)
```

### 导出结果
```python
# 导出网格表格
grid_df = strategy.export_grid_table("my_grid_table.csv")

# 保存配置
strategy.save_config("my_config.json")

# 保存优化结果
optimizer.save_optimization_result(opt_result, "optimization_result.json")
```

## 🎯 超参优化详解

### 优化方法对比

| 方法 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| 网格搜索 | 全局最优，结果稳定 | 计算量大，耗时长 | 参数空间较小，追求最优解 |
| 差分进化 | 收敛快，适合连续优化 | 可能陷入局部最优 | 参数空间较大，平衡效果和效率 |
| 贝叶斯优化 | 效率高，适合昂贵目标函数 | 实现复杂，需要先验知识 | 计算资源有限，快速优化 |

### 优化指标说明

- **夏普比率**: 风险调整后收益，关注风险调整后收益
- **盈利因子**: 总盈利/总亏损，关注盈利稳定性
- **最大回撤比率**: 风险控制优先
- **综合评分**: 多指标加权，平衡多个目标

### 参数搜索空间

```python
param_space = {
    'grid_spacing': (0.03, 0.12),        # 3%-12%
    'max_drawdown': (0.3, 0.8),          # 30%-80%
    'max_grids': (10, 30),               # 10-30个网格
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
```

### 优化流程

1. **准备数据**: 准备历史价格数据（可选）
2. **选择方法**: 根据需求选择优化方法
3. **设置指标**: 选择优化目标指标
4. **运行优化**: 执行优化算法
5. **验证结果**: 进行压力测试验证
6. **实盘测试**: 在实盘前进行充分回测

## 📚 参考资源

- [ETF拯救世界 - 网格策略系列文章](https://mp.weixin.qq.com/s/xxx)
- [网格策略理论基础](https://example.com)
- [BTC市场分析](https://example.com)

## 🤝 贡献

欢迎提交Issue和Pull Request来改进这个策略。

## 📄 许可证

MIT License

---

**免责声明**：本策略仅供学习和研究使用，不构成投资建议。投资有风险，入市需谨慎。请根据自身风险承受能力谨慎使用。
