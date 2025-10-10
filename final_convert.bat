@echo off
REM 最终版币安数据转换脚本
chcp 65001 >nul 2>&1

echo ========================================
echo 最终版币安数据转换
echo ========================================
echo.

REM 设置Python环境变量
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1

echo 使用修复后的转换脚本处理indexPriceKlines数据
echo 数据路径: yccai/binance_data_downloader/data/futures/um/daily/indexPriceKlines
echo 输出路径: user_data/data/futures
echo.

REM 运行最终转换脚本
python final_binance_converter.py --input "yccai/binance_data_downloader/data/futures/um/daily/indexPriceKlines" --output "user_data/data/futures" --pair BTCUSDT --timeframe 1m --workers 4

echo.
echo 转换完成! 按任意键退出...
pause >nul
