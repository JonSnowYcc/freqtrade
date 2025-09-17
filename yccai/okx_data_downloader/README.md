# OKX合约数据下载器

专门下载OKX所有合约币种2025年1月1日后的分钟级数据，支持断点续传和智能频率控制。

## 功能特点

- ✅ **专门下载合约数据** - 只下载USDT现货交易对
- ✅ **断点续传** - 中断后可继续下载，不会重复下载
- ✅ **智能频率控制** - 自动测试OKX限制，避免触发限制
- ✅ **进度跟踪** - 实时显示下载进度和状态
- ✅ **数据完整性** - 自动检查数据质量，去重排序

## 快速开始

### 1. 配置API密钥

确保 `../../user_data/config.json` 包含正确的OKX API配置：

```json
{
    "exchange": {
        "name": "okx",
        "key": "你的API密钥",
        "secret": "你的密钥",
        "password": "你的密码",
        "ccxt_config": {
            "hostname": "okx.com",
            "proxies": {
                "http": "socks5://127.0.0.1:7897",
                "https": "socks5://127.0.0.1:7897"
            }
        }
    }
}
```

### 2. 开始下载

```bash
# 下载所有合约数据
python okx_contract_downloader.py

# 检查数据状态
python okx_contract_downloader.py --status

# 重试失败的交易对
python okx_contract_downloader.py --retry

# 下载指定交易对
python okx_contract_downloader.py --pair BTC/USDT
```

## 智能特性

### 断点续传
- 自动保存下载进度到 `download_progress.json`
- 中断后重新运行会自动跳过已完成的交易对
- 支持检查数据新鲜度，自动更新过期数据

### 频率控制
- 动态调整请求频率，避免触发OKX API限制
- 基础延迟200ms，根据请求频率自动调整
- 每60秒最多50个请求，超出会自动增加延迟

### 数据质量
- 自动去重和排序
- 检查数据完整性
- Feather格式存储，高效压缩

## 输出文件

- **数据文件**: `../../user_data/data/okx/` (每个交易对一个.feather文件)
- **进度文件**: `download_progress.json` (下载进度和状态)
- **日志**: 控制台实时输出

## 注意事项

1. **API限制**: 已内置智能频率控制，无需担心触发限制
2. **网络稳定**: 支持代理，建议在网络稳定时运行
3. **存储空间**: 每个交易对约占用几MB空间
4. **中断恢复**: 随时可以Ctrl+C中断，下次运行会继续

## 故障排除

如果遇到问题：

1. **网络连接**: 检查代理设置是否正确
2. **API配置**: 确认API密钥有读取权限
3. **重试失败**: 使用 `--retry` 参数重试失败的交易对
4. **检查状态**: 使用 `--status` 查看当前数据状态