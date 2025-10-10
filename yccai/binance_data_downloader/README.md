# USD-M Futures 数据下载工具

这是一个优化的 Binance USD-M Futures（U本位合约）数据下载工具，支持代理、并发下载和断点续传。

## 功能特点

- ✅ **代理支持**: 自动使用本地代理 (127.0.0.1:7897)
- ✅ **并发下载**: 16个线程并发下载，大幅提升速度
- ✅ **断点续传**: 自动跳过已存在的文件
- ✅ **重试机制**: 网络失败自动重试，指数退避策略
- ✅ **进度显示**: 实时显示下载进度和统计信息
- ✅ **数据完整性**: 可选下载校验和文件验证数据
- ✅ **增量下载**: 智能扫描缺失文件，只下载需要的数据

## 支持的数据类型

1. **klines** - K线数据（所有时间间隔）
2. **trades** - 交易数据
3. **aggTrades** - 聚合交易数据
4. **indexPriceKlines** - 指数价格K线
5. **markPriceKlines** - 标记价格K线
6. **premiumIndexKlines** - 溢价指数K线

## 快速开始

### 1. 下载所有daily数据（推荐）
```bash
cd yccai
python download_all_um_futures.py
```

### 2. 指定特定交易对
```bash
python download_all_um_futures.py -s BTCUSDT ETHUSDT
```

### 3. 指定特定数据类型
```bash
python download_all_um_futures.py -d klines trades
```

### 4. 指定时间范围
```bash
python download_all_um_futures.py --start-date 2024-01-01 --end-date 2024-12-31
```

### 5. 预览模式（不实际下载）
```bash
python download_all_um_futures.py --dry-run
```


## 命令行参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `-s, --symbols` | 指定交易对符号 | 所有符号 |
| `-d, --data-types` | 指定数据类型 | 所有类型 |
| `-i, --intervals` | 指定时间间隔 | 所有间隔 |
| `-y, --years` | 指定年份 | 所有年份 |
| `-m, --months` | 指定月份 | 所有月份 |
| `--start-date` | 开始日期 (YYYY-MM-DD) | 2020-01-01 |
| `--end-date` | 结束日期 (YYYY-MM-DD) | 今天 |
| `--skip-monthly` | 跳过月度数据 | False |
| `--skip-daily` | 跳过日度数据 | False |
| `--include-checksum` | 下载校验和文件 | False |
| `--dry-run` | 预览模式 | False |


## 配置说明

编辑 `config.py` 文件可以调整以下设置：

- **代理配置**: 启用/禁用代理，修改代理地址
- **并发设置**: 调整最大线程数 (默认16)
- **重试设置**: 调整重试次数和延迟
- **存储路径**: 修改数据存储目录

## 数据存储

下载的数据将保存在 `data/` 目录下，按以下结构组织：

```
data/
├── data/futures/um/
│   ├── monthly/
│   │   ├── klines/
│   │   ├── trades/
│   │   └── ...
│   └── daily/
│       ├── klines/
│       ├── trades/
│       └── ...
```

## 性能优化

- 使用16个并发线程下载
- 自动跳过已存在的文件
- 网络失败自动重试
- 支持代理加速访问

## 增量下载模式

本工具默认使用增量下载模式，智能扫描缺失文件，只下载需要的数据。

### 工作原理
1. **智能扫描**: 遍历每个币种的所有文件夹，检查文件是否存在且完整
2. **精确统计**: 按币种和数据类型统计缺失文件数量
3. **高效下载**: 只下载缺失的文件，避免重复下载

### 增量下载优势
- 🚀 **更高效**: 只下载缺失文件，节省时间和带宽
- 🎯 **更精确**: 自动检测已存在文件，避免重复下载
- 📊 **更清晰**: 提供详细的扫描统计信息
- 🔧 **更灵活**: 支持所有参数（币种、数据类型、时间间隔等）

### 使用示例
```bash
# 增量下载所有币种的daily数据缺失文件
python download_all_um_futures.py

# 只下载BTC和ETH的daily数据缺失文件
python download_all_um_futures.py -s BTCUSDT ETHUSDT

# 只下载klines数据的daily数据缺失文件
python download_all_um_futures.py -d klines

# 包含monthly数据（如果需要）
python download_all_um_futures.py --include-monthly

# 预览将要下载的缺失文件
python download_all_um_futures.py --dry-run
```

## 注意事项

1. 确保代理服务 (端口7897) 正在运行
2. 首次下载数据量较大，建议在网络状况良好时进行
3. 可以使用 `--dry-run` 先预览要下载的文件数量
4. 建议定期运行以获取最新数据
5. **默认使用增量下载模式**，自动检测并只下载缺失的文件
6. **默认只下载daily数据**，如需monthly数据请使用 `--include-monthly` 参数

## 故障排除

### 代理连接失败
- 检查代理服务是否运行在 127.0.0.1:7897
- 在 `config.py` 中设置 `PROXY_CONFIG['enabled'] = False` 禁用代理

### 下载速度慢
- 增加 `DOWNLOAD_CONFIG['max_workers']` 的值
- 检查网络连接和代理设置

### 内存不足
- 减少 `DOWNLOAD_CONFIG['max_workers']` 的值
- 分批下载特定交易对或时间段
