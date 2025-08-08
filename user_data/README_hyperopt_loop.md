# 策略超参优化和回测自动化脚本

## 概述

这个脚本系统可以自动为所有策略执行超参优化，然后用最优参数进行回测，最终生成完整的分析报告。

## 文件说明

### 1. `hyperopt_loop.py` - 主脚本
- **功能**: 遍历所有策略，执行超参优化和回测
- **输出**: 为每个策略生成 `.result.json` 文件

### 2. `analyze_results.py` - 结果分析脚本
- **功能**: 分析所有策略的结果，生成汇总报告
- **输出**: CSV文件和详细文本报告

## 使用方法

### 第一步：执行超参优化和回测

```bash
cd user_data
python hyperopt_loop.py
```

这个脚本会：
1. 遍历 `strategies/` 目录中的所有 `.py` 策略文件
2. 跳过 `STRATEGIES_TO_SKIP` 中列出的策略
3. 为每个策略执行超参优化
4. 提取最优参数
5. 使用最优参数执行回测
6. 保存结果到 `策略名.result.json` 文件

### 第二步：查看结果

```bash
# 查看所有策略的汇总结果
python analyze_results.py

# 查看特定策略的详细信息
python analyze_results.py 策略名称
```

## 配置说明

### 超参优化参数

在 `hyperopt_loop.py` 中可以修改：

```python
# 默认超参优化参数
DEFAULT_HYPEROPT_PARAMS = "--epochs 100 --spaces buy roi --hyperopt-loss DefaultHyperOptLoss"

# 要跳过的策略
STRATEGIES_TO_SKIP = [
    "SampleStrategy",
    "InformativeSample",
    "TechnicalExampleStrategy",
    "DoesNothingStrategy",
]
```

### 自定义策略参数

为特定策略创建 `.hyperopt` 文件：

```bash
# 创建 user_data/strategies/MyStrategy.hyperopt
echo "--epochs 200 --spaces buy sell roi --hyperopt-loss SharpeHyperOptLoss" > user_data/strategies/MyStrategy.hyperopt
```

## 输出文件说明

### 1. `.result.json` 文件结构

```json
{
  "strategy_name": "策略名称",
  "超参优化结果": {
    "最优参数": {
      "minimal_roi": {"0": 0.05, "20": 0.03, "40": 0.01},
      "stoploss": -0.05,
      "buy": {"rsi": 30},
      "sell": {"rsi": 70}
    },
    "完整输出": "超参优化的完整输出..."
  },
  "回测结果": {
    "total_profit": "0.00123456",
    "profit_rate": "12.34%",
    "total_trades": 50,
    "avg_profit": "2.45%",
    "win_rate": "65%"
  }
}
```

### 2. 分析报告文件

- `strategy_results_YYYYMMDD_HHMMSS.csv` - 汇总表格
- `detailed_report_YYYYMMDD_HHMMSS.txt` - 详细报告

## 故障排除

### 1. 策略属性错误

如果遇到 `AttributeError: property 'minimal_roi' of 'Strategy' object has no setter` 错误：

**解决方案**: 为策略中的 `@property` 添加 setter 方法：

```python
@property
def minimal_roi(self):
    return {"0": 0.05}

@minimal_roi.setter
def minimal_roi(self, value):
    pass  # 允许freqtrade设置值
```

### 2. 缺少依赖

如果遇到导入错误：

```bash
pip install -r requirements-hyperopt.txt
```

### 3. 数据问题

确保有足够的历史数据：

```bash
freqtrade download-data --exchange okx --pairs BTC/USDT ETH/USDT --timeframe 15m
```

## 高级用法

### 1. 批量修改策略参数

```python
# 在 hyperopt_loop.py 中添加
def modify_strategy_params(strategy_name):
    """为特定策略修改参数"""
    if strategy_name == "MyStrategy":
        return "--epochs 500 --spaces all"
    return None
```

### 2. 自定义结果分析

```python
# 在 analyze_results.py 中添加自定义分析
def custom_analysis(results):
    """自定义分析逻辑"""
    # 你的分析代码
    pass
```

## 注意事项

1. **时间消耗**: 超参优化需要大量时间，建议在服务器上运行
2. **资源使用**: 确保有足够的内存和CPU资源
3. **数据质量**: 确保历史数据完整且质量良好
4. **策略兼容性**: 确保所有策略都能正常加载和执行

## 示例输出

```
策略超参优化和回测结果汇总
================================================================================
策略名称    总收益        收益率    交易次数  平均收益  胜率    最优ROI          最优止损
Strategy1   0.00123456   12.34%    50       2.45%    65%    {0: 0.05}       -0.05
Strategy2   0.00098765   9.87%     30       3.29%    70%    {0: 0.03}       -0.03
Strategy3   0.00054321   5.43%     20       2.72%    60%    {0: 0.02}       -0.02
``` 