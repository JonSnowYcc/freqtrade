# 激进型ROI策略

<cite>
**本文档引用的文件**
- [BTCGridStrategy.py](file://yccai/wang_ge/BTCGridStrategy.py)
- [btc_grid_strategy.py](file://yccai/wang_ge/btc_grid_strategy.py)
- [FixedRiskRewardLoss.py](file://user_data/strategies/FixedRiskRewardLoss.py)
- [CustomStoplossWithPSAR.py](file://user_data/strategies/CustomStoplossWithPSAR.py)
- [config.json](file://user_data/config.json)
</cite>

## 目录
1. [激进型ROI策略配置逻辑](#激进型roi策略配置逻辑)
2. [高收益率与短时间窗口组合](#高收益率与短时间窗口组合)
3. [与网格交易策略的协同配置](#与网格交易策略的协同配置)
4. [高杠杆环境下的风险控制](#高杠杆环境下的风险控制)
5. [参数优化方法](#参数优化方法)

## 激进型ROI策略配置逻辑

激进型ROI策略的核心在于通过高收益率目标与短时间窗口的组合，捕捉短期价格波动。在Freqtrade框架中，ROI（Return on Investment）策略通过`minimal_roi`参数进行配置，该参数定义了在不同持有时间下期望的收益率。激进型ROI策略通常设置较高的收益率目标和较短的时间窗口，以快速锁定利润。

在`config.json`文件中，`minimal_roi`参数的配置示例如下：
```json
"minimal_roi": {
    "0": 0.01
}
```
这表示在0分钟时期望的收益率为1%。对于激进型策略，可以设置更高的收益率目标和更短的时间窗口，例如`{1800: 0.1, 900: 0.05}`，表示在30分钟内期望10%的收益率，在15分钟内期望5%的收益率。

**Section sources**
- [config.json](file://user_data/config.json#L10-L13)

## 高收益率与短时间窗口组合

高收益率目标与短时间窗口的组合配置方式，如`{1800: 0.1, 900: 0.05}`，在捕捉短期价格波动方面具有显著优势。这种配置方式能够快速响应市场变化，及时锁定利润，避免因市场反转而导致的利润回吐。

在`BTCGridStrategy.py`文件中，`BTCGridStrategy`类的`minimal_roi`参数配置如下：
```python
def __init__(self, config: dict) -> None:
    super().__init__(config)
    self.minimal_roi = {
        "0": self.roi_p1.value,
        "27": self.roi_p2.value,
        "60": self.roi_p3.value,
        "164": 0
    }
```
通过调整`roi_p1`、`roi_p2`和`roi_p3`的值，可以实现不同的ROI策略配置。例如，将`roi_p1`设置为0.1，`roi_p2`设置为0.05，`roi_p3`设置为0，可以实现`{0: 0.1, 27: 0.05, 60: 0}`的激进型ROI策略。

**Section sources**
- [BTCGridStrategy.py](file://yccai/wang_ge/BTCGridStrategy.py#L71-L79)

## 与网格交易策略的协同配置

激进型ROI策略可以与多级网格资金分配（small_grid_ratio, medium_grid_ratio等）协同配置，以提高资金利用效率和风险控制能力。在`BTCGridStrategy.py`文件中，`BTCGridStrategy`类的`small_grid_ratio`、`medium_grid_ratio`和`large_grid_ratio`参数用于配置多级网格的资金分配比例。

```python
small_grid_ratio = DecimalParameter(0.3, 0.7, default=0.5, space="buy", optimize=True)
medium_grid_ratio = DecimalParameter(0.1, 0.4, default=0.3, space="buy", optimize=True)
large_grid_ratio = DecimalParameter(0.1, 0.3, default=0.2, space="buy", optimize=True)
```
通过调整这些参数，可以实现不同级别的网格资金分配。例如，将`small_grid_ratio`设置为0.5，`medium_grid_ratio`设置为0.3，`large_grid_ratio`设置为0.2，可以实现50%的资金用于小网格，30%的资金用于中网格，20%的资金用于大网格。

**Section sources**
- [BTCGridStrategy.py](file://yccai/wang_ge/BTCGridStrategy.py#L64-L66)

## 高杠杆环境下的风险控制

在高杠杆环境下，风险控制尤为重要。激进型ROI策略可以通过与`stoploss`和`trailing_stop`的联动设置，实现有效的风险控制。在`FixedRiskRewardLoss.py`文件中，`FixedRiskRewardLoss`类的`stoploss`和`trailing_stop`参数用于配置止损和追踪止损。

```python
stoploss = RealParameter(-0.99, -0.5, default=-0.9, space='protection', optimize=True)
trailing_stop = BooleanParameter(default=False, space='protection', optimize=True)
```
通过调整`stoploss`和`trailing_stop`的值，可以实现不同的风险控制策略。例如，将`stoploss`设置为-0.1，`trailing_stop`设置为True，可以实现10%的止损和追踪止损。

**Section sources**
- [FixedRiskRewardLoss.py](file://user_data/strategies/FixedRiskRewardLoss.py#L71-L72)

## 参数优化方法

为了防止过度拟合历史数据，需要采用合理的参数优化方法。在`btc_grid_strategy.py`文件中，`HyperparameterOptimizer`类提供了多种超参数优化方法，包括网格搜索、差分进化和贝叶斯优化。

```python
def optimize_grid_search(self, 
                       optimization_metric: str = 'composite_score',
                       max_combinations: int = 1000) -> OptimizationResult:
    # 网格搜索优化
    pass

def optimize_differential_evolution(self, 
                                  optimization_metric: str = 'composite_score',
                                  maxiter: int = 50,
                                  popsize: int = 15) -> OptimizationResult:
    # 差分进化优化
    pass

def optimize_bayesian(self, 
                     optimization_metric: str = 'composite_score',
                     n_calls: int = 100) -> OptimizationResult:
    # 贝叶斯优化
    pass
```
通过使用这些优化方法，可以找到最优的参数组合，避免过度拟合历史数据，提高策略的泛化能力。

**Section sources**
- [btc_grid_strategy.py](file://yccai/wang_ge/btc_grid_strategy.py#L500-L600)