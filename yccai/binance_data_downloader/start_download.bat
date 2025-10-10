@echo off
REM 强制设置控制台代码页为UTF-8
chcp 65001 >nul 2>&1
REM 设置控制台字体为支持中文的字体
mode con codepage select=65001 >nul 2>&1

echo ========================================
echo 币安数据下载程序（S3 API增强版）
echo ========================================
echo 功能特点：
echo - 超快速增量下载（几秒钟完成扫描）
echo - S3 API直接获取文件列表
echo - 智能检测缺失文件并自动补齐
echo - 支持所有数据类型和间隔
echo 按 Ctrl+C 可以安全退出程序
echo.
echo 使用示例：
echo   start_download.bat                    # 下载所有数据
echo   start_download.bat --dry-run          # 预览模式
echo   start_download.bat -s BTCUSDT         # 下载指定币种
echo   start_download.bat -d klines -i 1m    # 下载指定数据类型和间隔
echo.

REM 设置Python环境变量确保UTF-8编码
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1
set PYTHONLEGACYWINDOWSSTDIO=utf-8
set PYTHONUTF8=1
set LANG=zh_CN.UTF-8
set LC_ALL=zh_CN.UTF-8

REM 设置Windows控制台环境变量
set CONSOLE_CODEPAGE=65001
set CONSOLE_FONT=Consolas

REM 使用进程管理器启动Python程序
python process_manager.py download_all_um_futures.py %*

REM 如果程序正常退出，显示消息
if %ERRORLEVEL% EQU 0 (
    echo.
    echo 程序正常退出
) else (
    echo.
    echo 程序异常退出，错误代码: %ERRORLEVEL%
)

pause
