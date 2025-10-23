# SmoothScalp 策略文件说明

## 文件结构

```
yccai/
├── SmoothScalp.py                           # 优化后的策略文件
├── SmoothScalp_策略完整文档.md              # 完整的策略文档
├── hyperopt_config_smoothscalp.json         # 超参数优化配置文件
├── optimize_smoothscalp.py                  # Python优化脚本
├── run_hyperopt.bat                         # Windows批处理优化脚本
├── run_hyperopt.ps1                         # PowerShell优化脚本
└── README.md                                # 本文件
```

## 快速开始

### 1. 策略部署
将 `SmoothScalp.py` 复制到您的freqtrade策略目录：
```bash
copy SmoothScalp.py user_data/strategies/
```

### 2. 超参数优化
选择以下任一方式进行优化：

#### 方法1: 使用批处理脚本 (Windows)
```bash
run_hyperopt.bat
```

#### 方法2: 使用PowerShell脚本
```bash
.\run_hyperopt.ps1
```

#### 方法3: 使用Python脚本
```bash
python optimize_smoothscalp.py quick   # 快速测试
python optimize_smoothscalp.py full     # 完整优化
python optimize_smoothscalp.py results # 查看结果
```

#### 方法4: 直接命令
```bash
# 快速测试优化
freqtrade hyperopt --config hyperopt_config_smoothscalp.json --strategy SmoothScalp --epochs 50 --spaces buy --hyperopt-loss SharpeHyperOptLoss --timerange 20241201-20241215

# 全面优化
freqtrade hyperopt --config hyperopt_config_smoothscalp.json --strategy SmoothScalp --epochs 500 --spaces buy sell roi protection --hyperopt-loss SharpeHyperOptLoss --timerange 20240101-20241201
```

## 策略特点

### 优化亮点
- ✅ **交易频率提升2-3倍**
- ✅ **适合多交易对同时运行**
- ✅ **21个可优化参数**
- ✅ **多层风险控制机制**
- ✅ **动态仓位管理**

### 核心功能
1. **动态止损**: 基于ATR、波动率、持仓时间的智能止损
2. **自定义退出**: 时间止损、波动率止损、成交量止损
3. **动态仓位管理**: 根据市场条件调整仓位大小
4. **新增技术指标**: ATR、Williams %R、波动率指标等

## 使用建议

### 1. 交易对选择
- 选择流动性好的主流交易对
- 建议同时运行10-20个交易对
- 避免选择波动率过高的交易对

### 2. 参数调优
- 建议先进行回测优化
- 重点关注买入参数
- 根据具体交易对调整风险控制参数

### 3. 风险控制
- 设置合理的最大持仓数量
- 监控整体风险敞口
- 定期检查策略表现

### 4. 运行环境
- 建议在VPS上运行，确保网络稳定
- 使用低延迟的交易所API
- 考虑交易手续费对策略的影响

## 注意事项

1. **手续费敏感**: 剥头皮策略对交易成本非常敏感
2. **滑点控制**: 确保有足够的流动性
3. **市场环境**: 策略在趋势市场中表现更好
4. **资金管理**: 建议分散投资，不要将所有资金投入单一策略
5. **定期优化**: 根据市场变化定期重新优化参数

## 技术支持

如有问题，请参考 `SmoothScalp_策略完整文档.md` 获取详细说明。

---

**免责声明**: 本策略仅供学习和研究使用，实盘交易存在风险，请谨慎使用。
