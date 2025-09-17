@echo off
REM OKX数据下载器启动脚本 (Windows)
REM 使用方法: 双击运行此文件

echo ========================================
echo OKX数据下载器
echo ========================================
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误: 未找到Python，请先安装Python
    pause
    exit /b 1
)

REM 检查是否在正确的目录
if not exist "okx_data_downloader.py" (
    echo 错误: 请在yccai/okx_data_downloader目录下运行此脚本
    pause
    exit /b 1
)

echo 选择操作模式:
echo 1. 增量下载 (推荐)
echo 2. 强制更新所有数据
echo 3. 检查数据完整性
echo 4. 生成数据报告
echo 5. 退出
echo.

set /p choice=请输入选择 (1-5): 

if "%choice%"=="1" (
    echo 开始增量下载...
    python okx_data_downloader.py
) else if "%choice%"=="2" (
    echo 开始强制更新所有数据...
    python okx_data_downloader.py --force
) else if "%choice%"=="3" (
    echo 开始检查数据完整性...
    python okx_data_downloader.py --check
) else if "%choice%"=="4" (
    echo 开始生成数据报告...
    python okx_data_downloader.py --report
) else if "%choice%"=="5" (
    echo 退出程序
    exit /b 0
) else (
    echo 无效选择，请重新运行脚本
)

echo.
echo 操作完成！
echo 按任意键退出...
pause >nul
