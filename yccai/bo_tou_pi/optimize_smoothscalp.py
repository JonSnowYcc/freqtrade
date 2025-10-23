#!/usr/bin/env python3
"""
SmoothScalp策略超参数优化脚本
用于优化SmoothScalp策略的所有超参数
"""

import subprocess
import sys
import os
from datetime import datetime, timedelta

def run_hyperopt():
    """运行超参数优化"""
    
    print("=" * 60)
    print("SmoothScalp 策略超参数优化")
    print("=" * 60)
    
    # 检查配置文件是否存在
    config_file = "hyperopt_config_smoothscalp.json"
    if not os.path.exists(config_file):
        print(f"错误: 配置文件 {config_file} 不存在")
        return False
    
    # 优化参数
    epochs = 1000  # 优化轮数
    jobs = 4       # 并行任务数
    min_trades = 50  # 最小交易数量
    spaces = "buy sell roi protection"  # 优化空间
    
    # 构建命令
    cmd = [
        "freqtrade", "hyperopt",
        "--config", config_file,
        "--strategy", "SmoothScalp",
        "--epochs", str(epochs),
        "--jobs", str(jobs),
        "--min-trades", str(min_trades),
        "--spaces", spaces,
        "--timerange", "20240101-20241201",  # 优化时间范围
        "--hyperopt-loss", "SharpeHyperOptLoss",  # 使用夏普比率作为优化目标
        "--print-all"
    ]
    
    print(f"开始优化，参数:")
    print(f"  - 优化轮数: {epochs}")
    print(f"  - 并行任务: {jobs}")
    print(f"  - 最小交易数: {min_trades}")
    print(f"  - 优化空间: {spaces}")
    print(f"  - 时间范围: 2024年1月-12月")
    print(f"  - 优化目标: 夏普比率")
    print()
    
    try:
        # 运行优化
        result = subprocess.run(cmd, check=True, capture_output=False)
        print("\n优化完成!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"优化失败: {e}")
        return False
    except KeyboardInterrupt:
        print("\n优化被用户中断")
        return False

def run_quick_optimization():
    """运行快速优化（用于测试）"""
    
    print("=" * 60)
    print("SmoothScalp 快速优化测试")
    print("=" * 60)
    
    config_file = "hyperopt_config_smoothscalp.json"
    
    # 快速优化参数
    epochs = 50
    jobs = 2
    min_trades = 20
    
    cmd = [
        "freqtrade", "hyperopt",
        "--config", config_file,
        "--strategy", "SmoothScalp",
        "--epochs", str(epochs),
        "--jobs", str(jobs),
        "--min-trades", str(min_trades),
        "--spaces", "buy",
        "--timerange", "20241201-20241215",  # 较短的时间范围
        "--hyperopt-loss", "SharpeHyperOptLoss",
        "--print-all"
    ]
    
    print(f"快速优化参数:")
    print(f"  - 优化轮数: {epochs}")
    print(f"  - 并行任务: {jobs}")
    print(f"  - 最小交易数: {min_trades}")
    print(f"  - 优化空间: buy")
    print(f"  - 时间范围: 2024年12月1-15日")
    print()
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        print("\n快速优化完成!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"快速优化失败: {e}")
        return False
    except KeyboardInterrupt:
        print("\n快速优化被用户中断")
        return False

def show_optimization_results():
    """显示优化结果"""
    
    print("=" * 60)
    print("查看优化结果")
    print("=" * 60)
    
    cmd = [
        "freqtrade", "hyperopt-show",
        "--config", "hyperopt_config_smoothscalp.json",
        "--print-json"
    ]
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("优化结果:")
        print(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"获取结果失败: {e}")

def main():
    """主函数"""
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "quick":
            run_quick_optimization()
        elif command == "results":
            show_optimization_results()
        elif command == "full":
            run_hyperopt()
        else:
            print("未知命令。可用命令: quick, full, results")
    else:
        print("SmoothScalp 超参数优化工具")
        print()
        print("使用方法:")
        print("  python optimize_smoothscalp.py quick   - 快速优化测试")
        print("  python optimize_smoothscalp.py full     - 完整优化")
        print("  python optimize_smoothscalp.py results - 查看结果")
        print()
        
        choice = input("请选择操作 (quick/full/results): ").lower()
        
        if choice == "quick":
            run_quick_optimization()
        elif choice == "full":
            run_hyperopt()
        elif choice == "results":
            show_optimization_results()
        else:
            print("无效选择")

if __name__ == "__main__":
    main()
