import json
from pathlib import Path
import pandas as pd
from datetime import datetime

def analyze_results():
    """
    分析所有策略的超参优化和回测结果
    """
    strategies_dir = Path(__file__).parent / "strategies"
    
    results = []
    
    # 遍历所有.result.json文件
    for result_file in strategies_dir.glob("*.result.json"):
        try:
            with open(result_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            strategy_name = data.get("strategy_name", result_file.stem)
            hyperopt_results = data.get("超参优化结果", {})
            backtest_results = data.get("回测结果", {})
            
            # 提取关键指标
            result = {
                "策略名称": strategy_name,
                "总收益": backtest_results.get("total_profit", "N/A"),
                "收益率": backtest_results.get("profit_rate", "N/A"),
                "交易次数": backtest_results.get("total_trades", "N/A"),
                "平均收益": backtest_results.get("avg_profit", "N/A"),
                "胜率": backtest_results.get("win_rate", "N/A"),
                "最优ROI": str(hyperopt_results.get("最优参数", {}).get("minimal_roi", "N/A")),
                "最优止损": hyperopt_results.get("最优参数", {}).get("stoploss", "N/A"),
            }
            
            results.append(result)
            
        except Exception as e:
            print(f"解析 {result_file} 失败: {e}")
    
    if not results:
        print("没有找到任何结果文件")
        return
    
    # 创建DataFrame并排序
    df = pd.DataFrame(results)
    
    # 尝试按收益率排序（如果有数值的话）
    try:
        # 提取收益率中的数字部分
        df['收益率数值'] = df['收益率'].str.extract(r'([-\d.]+)').astype(float)
        df = df.sort_values('收益率数值', ascending=False)
        df = df.drop('收益率数值', axis=1)
    except:
        # 如果无法排序，保持原顺序
        pass
    
    # 打印结果
    print("=" * 80)
    print("策略超参优化和回测结果汇总")
    print("=" * 80)
    print(df.to_string(index=False))
    
    # 保存到CSV文件
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_file = Path(__file__).parent / f"strategy_results_{timestamp}.csv"
    df.to_csv(csv_file, index=False, encoding='utf-8-sig')
    print(f"\n结果已保存到: {csv_file}")
    
    # 生成详细报告
    generate_detailed_report(results)
    
    return df


def generate_detailed_report(results):
    """
    生成详细的分析报告
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = Path(__file__).parent / f"detailed_report_{timestamp}.txt"
    
    with open(report_file, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write("策略超参优化和回测详细报告\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 80 + "\n\n")
        
        # 按收益率排序
        def extract_profit_rate(result):
            rate_str = str(result.get("收益率", "0"))
            if rate_str == "N/A":
                return 0
            try:
                # 提取数字部分
                rate_clean = rate_str.replace("%", "").replace("(", "").replace(")", "").split()[0]
                return float(rate_clean)
            except:
                return 0
        
        sorted_results = sorted(results, key=extract_profit_rate, reverse=True)
        
        f.write("策略排名（按收益率排序）:\n")
        f.write("-" * 80 + "\n")
        
        for i, result in enumerate(sorted_results, 1):
            f.write(f"{i}. {result['策略名称']}\n")
            f.write(f"   总收益: {result['总收益']}\n")
            f.write(f"   收益率: {result['收益率']}\n")
            f.write(f"   交易次数: {result['交易次数']}\n")
            f.write(f"   平均收益: {result['平均收益']}\n")
            f.write(f"   胜率: {result['胜率']}\n")
            f.write(f"   最优ROI: {result['最优ROI']}\n")
            f.write(f"   最优止损: {result['最优止损']}\n")
            f.write("\n")
        
        # 统计信息
        f.write("\n统计信息:\n")
        f.write("-" * 80 + "\n")
        f.write(f"总策略数: {len(results)}\n")
        
        # 计算平均指标
        profitable_strategies = [r for r in results if r['收益率'] != 'N/A' and '0' not in str(r['收益率'])]
        f.write(f"盈利策略数: {len(profitable_strategies)}\n")
        
        if profitable_strategies:
            f.write("表现最好的策略:\n")
            best = max(profitable_strategies, key=extract_profit_rate)
            f.write(f"  {best['策略名称']} - {best['收益率']}\n")
    
    print(f"详细报告已保存到: {report_file}")


def show_strategy_details(strategy_name):
    """
    显示特定策略的详细信息
    """
    strategies_dir = Path(__file__).parent / "strategies"
    result_file = strategies_dir / f"{strategy_name}.result.json"
    
    if not result_file.exists():
        print(f"未找到策略 {strategy_name} 的结果文件")
        return
    
    try:
        with open(result_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        print(f"\n策略: {strategy_name}")
        print("=" * 50)
        
        # 显示回测结果
        backtest_results = data.get("回测结果", {})
        print("回测结果:")
        for key, value in backtest_results.items():
            print(f"  {key}: {value}")
        
        # 显示最优参数
        hyperopt_results = data.get("超参优化结果", {})
        best_params = hyperopt_results.get("最优参数", {})
        print("\n最优参数:")
        for key, value in best_params.items():
            print(f"  {key}: {value}")
        
    except Exception as e:
        print(f"读取策略详情失败: {e}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # 如果提供了策略名称，显示该策略的详细信息
        strategy_name = sys.argv[1]
        show_strategy_details(strategy_name)
    else:
        # 否则分析所有结果
        analyze_results() 