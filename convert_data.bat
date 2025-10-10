@echo off
REM 币安数据转换为Freqtrade格式
chcp 65001 >nul 2>&1

echo ========================================
echo 币安数据转换为Freqtrade格式
echo ========================================
echo.

REM 设置Python环境变量
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1

echo 开始转换数据...
echo.

REM 运行转换脚本
python convert_data_example.py

echo.
echo 转换完成! 按任意键退出...
pause >nul
