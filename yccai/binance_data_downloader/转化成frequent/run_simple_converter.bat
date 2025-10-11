@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8

echo ========================================
echo 简化的增量转换器
echo ========================================
echo.

cd /d "%~dp0"
python simple_incremental_converter.py

echo.
echo 按任意键退出...
pause >nul

