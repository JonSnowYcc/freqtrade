import subprocess
import sys
from pathlib import Path
import os
import json
import re

# --- Configuration ---
# Path to the strategies directory
STRATEGIES_DIR = Path(__file__).parent / "strategies"
# Path to the configuration file
CONFIG_FILE = Path(__file__).parent / "config.json"
# List of strategies to skip
STRATEGIES_TO_SKIP = [
    "SampleStrategy",
    "InformativeSample",
    "TechnicalExampleStrategy",
    "DoesNothingStrategy",
    # Add any other strategies you want to skip here
]
# Additional hyperopt parameters (optional)
# Example: "--epochs 50 --spaces buy sell --hyperopt-loss ShortTradeDurHyperOptLoss"
DEFAULT_HYPEROPT_PARAMS = "--epochs 100 --spaces buy roi --hyperopt-loss DefaultHyperOptLoss"


def get_hyperopt_params_for_strategy(strategy_name):
    """
    尝试读取与策略同名的 .hyperopt 文件，返回自定义参数，否则返回默认参数。
    """
    hyperopt_file = STRATEGIES_DIR / f"{strategy_name}.hyperopt"
    if hyperopt_file.exists():
        try:
            with open(hyperopt_file, "r", encoding="utf-8") as f:
                params = f.read().strip()
                if params:
                    print(f"使用自定义超参命令: {params}")
                    return params
        except Exception as ex:
            print(f"读取 {hyperopt_file} 失败: {ex}")
    return DEFAULT_HYPEROPT_PARAMS


def extract_best_params_from_hyperopt_output(stdout):
    """
    从超参优化输出中提取最优参数
    """
    best_params = {}
    
    # 提取ROI表
    roi_match = re.search(r'minimal_roi\s*=\s*{([^}]+)}', stdout)
    if roi_match:
        roi_content = roi_match.group(1)
        roi_dict = {}
        for match in re.finditer(r'(\d+):\s*([\d.]+)', roi_content):
            roi_dict[int(match.group(1))] = float(match.group(2))
        best_params['minimal_roi'] = roi_dict
    
    # 提取stoploss
    stoploss_match = re.search(r'stoploss\s*=\s*([-\d.]+)', stdout)
    if stoploss_match:
        best_params['stoploss'] = float(stoploss_match.group(1))
    
    # 提取其他参数
    param_patterns = [
        (r'buy_(\w+)\s*=\s*([-\d.]+)', 'buy'),
        (r'sell_(\w+)\s*=\s*([-\d.]+)', 'sell'),
        (r'(\w+)_period\s*=\s*(\d+)', 'indicators'),
    ]
    
    for pattern, category in param_patterns:
        matches = re.finditer(pattern, stdout)
        for match in matches:
            param_name = match.group(1)
            param_value = match.group(2)
            if category not in best_params:
                best_params[category] = {}
            best_params[category][param_name] = param_value
    
    return best_params


def run_backtest_with_params(strategy_name, best_params):
    """
    使用最优参数执行回测
    """
    print(f"--- 使用最优参数执行回测: {strategy_name} ---")
    
    # 创建临时配置文件
    temp_config = Path(__file__).parent / f"temp_config_{strategy_name}.json"
    
    try:
        # 读取原始配置
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        # 添加最优参数到配置
        if 'minimal_roi' in best_params:
            config['minimal_roi'] = best_params['minimal_roi']
        if 'stoploss' in best_params:
            config['stoploss'] = best_params['stoploss']
        
        # 写入临时配置
        with open(temp_config, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        # 执行回测
        command = [
            sys.executable,
            "-m", "freqtrade",
            "backtesting",
            "--config", str(temp_config),
            "--strategy", strategy_name,
        ]
        
        result = subprocess.run(
            command,
            check=True,
            text=True,
            capture_output=True,
            encoding='utf-8'
        )
        
        # 解析回测结果
        backtest_results = parse_backtest_results(result.stdout)
        
        return backtest_results
        
    except subprocess.CalledProcessError as e:
        print(f"回测执行失败: {e}")
        print("--- Stderr: ---")
        print(e.stderr)
        return None
    finally:
        # 清理临时配置文件
        if temp_config.exists():
            temp_config.unlink()


def parse_backtest_results(stdout):
    """
    解析回测结果
    """
    results = {}
    
    # 提取总收益
    profit_match = re.search(r'Total profit\s+([\-\d\.eE]+)\s+\w+\s*\(([^\)]+)\)', stdout)
    if profit_match:
        results['total_profit'] = profit_match.group(1)
        results['profit_rate'] = profit_match.group(2)
    
    # 提取交易次数
    trades_match = re.search(r'(\d+)\s+trades', stdout)
    if trades_match:
        results['total_trades'] = int(trades_match.group(1))
    
    # 提取平均收益
    avg_profit_match = re.search(r'Avg profit\s+([\-\d\.]+%)', stdout)
    if avg_profit_match:
        results['avg_profit'] = avg_profit_match.group(1)
    
    # 提取胜率
    win_rate_match = re.search(r'Win Rate\s+([\d\.]+%)', stdout)
    if win_rate_match:
        results['win_rate'] = win_rate_match.group(1)
    
    return results


def run_hyperopt_for_all_strategies():
    """
    为所有没有同名.json的策略依次运行hyperopt，然后用最优参数执行回测。
    """
    if not STRATEGIES_DIR.is_dir():
        print(f"Error: Strategies directory not found at {STRATEGIES_DIR}")
        return

    if not CONFIG_FILE.is_file():
        print(f"Error: Config file not found at {CONFIG_FILE}")
        return

    # 获取所有.py策略文件，按文件名排序
    strategy_files = sorted([
        f for f in STRATEGIES_DIR.glob("*.py")
        if f.is_file() and not f.name.startswith("__")
    ], key=lambda x: x.name)

    executed_any = False
    for strategy_file in strategy_files:
        strategy_name = strategy_file.stem
        if strategy_name in STRATEGIES_TO_SKIP or " copy" in strategy_name:
            continue
        
        # 检查是否已有完整的优化结果
        result_json_file = STRATEGIES_DIR / f"{strategy_name}.result.json"
        if result_json_file.exists():
            try:
                with open(result_json_file, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)
                    if "超参优化结果" in existing_data and "回测结果" in existing_data:
                        print(f"跳过已有完整结果的策略: {strategy_name}")
                        continue
            except:
                pass
        
        print(f"--- Starting hyperopt for strategy: {strategy_name} ---")
        
        # 执行超参优化
        command = [
            sys.executable,
            "-m", "freqtrade",
            "hyperopt",
            "--config", str(CONFIG_FILE),
            "--strategy", strategy_name,
        ]
        
        # 获取该策略的超参命令
        hyperopt_params = get_hyperopt_params_for_strategy(strategy_name)
        if hyperopt_params:
            command.extend(hyperopt_params.split())
        
        try:
            result = subprocess.run(
                command,
                check=True,
                text=True,
                capture_output=True,
                encoding='utf-8'
            )
            print(f"Successfully completed hyperopt for {strategy_name}")
            
            # 解析超参优化结果
            stdout = result.stdout
            best_params = extract_best_params_from_hyperopt_output(stdout)
            
            # 使用最优参数执行回测
            backtest_results = run_backtest_with_params(strategy_name, best_params)
            
            # 保存完整结果
            result_data = {
                "strategy_name": strategy_name,
                "超参优化结果": {
                    "最优参数": best_params,
                    "完整输出": stdout
                },
                "回测结果": backtest_results
            }
            
            # 写入结果文件
            with open(result_json_file, "w", encoding="utf-8") as f:
                json.dump(result_data, f, ensure_ascii=False, indent=2)
            
            print(f"完成策略 {strategy_name} 的优化和回测")
            executed_any = True
            
        except subprocess.CalledProcessError as e:
            print(f"An error occurred while running hyperopt for {strategy_name}:")
            print(e)
            print("--- Stderr: ---")
            print(e.stderr)
            print("--- Stdout: ---")
            print(e.stdout)
        except FileNotFoundError:
            print("Error: 'freqtrade' command not found.")
            print("Please make sure you are in the correct virtual environment.")
    
    if executed_any:
        print("所有策略的超参优化和回测已完成。")
    else:
        print("没有需要处理的策略。")


if __name__ == "__main__":
    run_hyperopt_for_all_strategies() 