#!/bin/bash
# OKX数据下载器启动脚本 (Linux/macOS)
# 使用方法: chmod +x run_downloader.sh && ./run_downloader.sh

echo "========================================"
echo "OKX数据下载器"
echo "========================================"
echo

# 检查Python是否安装
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到Python3，请先安装Python3"
    exit 1
fi

# 检查是否在正确的目录
if [ ! -f "okx_data_downloader.py" ]; then
    echo "错误: 请在yccai/okx_data_downloader目录下运行此脚本"
    exit 1
fi

echo "选择操作模式:"
echo "1. 增量下载 (推荐)"
echo "2. 强制更新所有数据"
echo "3. 检查数据完整性"
echo "4. 生成数据报告"
echo "5. 退出"
echo

read -p "请输入选择 (1-5): " choice

case $choice in
    1)
        echo "开始增量下载..."
        python3 okx_data_downloader.py
        ;;
    2)
        echo "开始强制更新所有数据..."
        python3 okx_data_downloader.py --force
        ;;
    3)
        echo "开始检查数据完整性..."
        python3 okx_data_downloader.py --check
        ;;
    4)
        echo "开始生成数据报告..."
        python3 okx_data_downloader.py --report
        ;;
    5)
        echo "退出程序"
        exit 0
        ;;
    *)
        echo "无效选择，请重新运行脚本"
        exit 1
        ;;
esac

echo
echo "操作完成！"
