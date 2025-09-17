# SmoothScalp 超参数优化脚本
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "SmoothScalp 超参数优化" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "请选择优化类型:" -ForegroundColor Yellow
Write-Host "1. 快速测试优化 (50轮, 仅买入参数)" -ForegroundColor Green
Write-Host "2. 买入参数优化 (200轮)" -ForegroundColor Green
Write-Host "3. 卖出参数优化 (200轮)" -ForegroundColor Green
Write-Host "4. 风险控制优化 (200轮)" -ForegroundColor Green
Write-Host "5. 全面优化 (500轮)" -ForegroundColor Green
Write-Host "6. 查看优化结果" -ForegroundColor Green
Write-Host ""

$choice = Read-Host "请输入选择 (1-6)"

switch ($choice) {
    "1" {
        Write-Host "开始快速测试优化..." -ForegroundColor Yellow
        freqtrade hyperopt --config hyperopt_config_smoothscalp.json --strategy SmoothScalp --epochs 50 --spaces buy --hyperopt-loss SharpeHyperOptLoss --timerange 20241201-20241215 --print-all
    }
    "2" {
        Write-Host "开始买入参数优化..." -ForegroundColor Yellow
        freqtrade hyperopt --config hyperopt_config_smoothscalp.json --strategy SmoothScalp --epochs 200 --spaces buy --hyperopt-loss SharpeHyperOptLoss --timerange 20240101-20241201 --print-all
    }
    "3" {
        Write-Host "开始卖出参数优化..." -ForegroundColor Yellow
        freqtrade hyperopt --config hyperopt_config_smoothscalp.json --strategy SmoothScalp --epochs 200 --spaces sell --hyperopt-loss SharpeHyperOptLoss --timerange 20240101-20241201 --print-all
    }
    "4" {
        Write-Host "开始风险控制优化..." -ForegroundColor Yellow
        freqtrade hyperopt --config hyperopt_config_smoothscalp.json --strategy SmoothScalp --epochs 200 --spaces protection --hyperopt-loss SharpeHyperOptLoss --timerange 20240101-20241201 --print-all
    }
    "5" {
        Write-Host "开始全面优化..." -ForegroundColor Yellow
        freqtrade hyperopt --config hyperopt_config_smoothscalp.json --strategy SmoothScalp --epochs 500 --spaces buy sell roi protection --hyperopt-loss SharpeHyperOptLoss --timerange 20240101-20241201 --print-all
    }
    "6" {
        Write-Host "显示优化结果..." -ForegroundColor Yellow
        freqtrade hyperopt-show --config hyperopt_config_smoothscalp.json --print-json
    }
    default {
        Write-Host "无效选择，请重新运行脚本" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "优化完成！" -ForegroundColor Green
Read-Host "按回车键退出"
