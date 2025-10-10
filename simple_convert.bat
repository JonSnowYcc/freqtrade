@echo off
REM 简单高效的币安数据转换
chcp 65001 >nul 2>&1

echo ========================================
echo 简单高效的币安数据转换
echo ========================================
echo.

REM 设置Python环境变量
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1

echo 使用简单方法处理数据，避免CSV解析问题
echo.

REM 运行简单转换脚本
python simple_binance_converter.py --input "yccai/binance_data_downloader/data/futures/um/daily/klines" --output "user_data/data/futures" --pair BTCUSDT --timeframe 1m --workers 4

echo.
echo 转换完成! 按任意键退出...
pause >nul
