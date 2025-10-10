@echo off
REM 高速币安数据转换
chcp 65001 >nul 2>&1

echo ========================================
echo 高速币安数据转换为Freqtrade格式
echo ========================================
echo.

REM 设置Python环境变量
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1

echo 使用多进程并行转换，速度提升10倍以上！
echo.

REM 运行高速转换脚本
python fast_binance_converter.py --input "yccai/binance_data_downloader/data/futures/um/daily/klines" --output "user_data/data/futures" --workers 8

echo.
echo 转换完成! 按任意键退出...
pause >nul
