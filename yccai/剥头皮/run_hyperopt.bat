@echo off
echo ========================================
echo SmoothScalp 超参数优化
echo ========================================
echo.

echo 请选择优化类型:
echo 1. 快速测试优化 (50轮, 仅买入参数)
echo 2. 买入参数优化 (200轮)
echo 3. 卖出参数优化 (200轮)
echo 4. 风险控制优化 (200轮)
echo 5. 全面优化 (500轮)
echo 6. 查看优化结果
echo.

set /p choice=请输入选择 (1-6): 

if "%choice%"=="1" (
    echo 开始快速测试优化...
    freqtrade hyperopt --config hyperopt_config_smoothscalp.json --strategy SmoothScalp --epochs 50 --spaces buy --hyperopt-loss SharpeHyperOptLoss --timerange 20241201-20241215 --print-all
) else if "%choice%"=="2" (
    echo 开始买入参数优化...
    freqtrade hyperopt --config hyperopt_config_smoothscalp.json --strategy SmoothScalp --epochs 200 --spaces buy --hyperopt-loss SharpeHyperOptLoss --timerange 20240101-20241201 --print-all
) else if "%choice%"=="3" (
    echo 开始卖出参数优化...
    freqtrade hyperopt --config hyperopt_config_smoothscalp.json --strategy SmoothScalp --epochs 200 --spaces sell --hyperopt-loss SharpeHyperOptLoss --timerange 20240101-20241201 --print-all
) else if "%choice%"=="4" (
    echo 开始风险控制优化...
    freqtrade hyperopt --config hyperopt_config_smoothscalp.json --strategy SmoothScalp --epochs 200 --spaces protection --hyperopt-loss SharpeHyperOptLoss --timerange 20240101-20241201 --print-all
) else if "%choice%"=="5" (
    echo 开始全面优化...
    freqtrade hyperopt --config hyperopt_config_smoothscalp.json --strategy SmoothScalp --epochs 500 --spaces buy sell roi protection --hyperopt-loss SharpeHyperOptLoss --timerange 20240101-20241201 --print-all
) else if "%choice%"=="6" (
    echo 显示优化结果...
    freqtrade hyperopt-show --config hyperopt_config_smoothscalp.json --print-json
) else (
    echo 无效选择，请重新运行脚本
)

echo.
echo 优化完成！按任意键退出...
pause >nul
