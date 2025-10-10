import subprocess
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import sys


def run_month(pair: str, exchange: str, timeframe: str, start_date: datetime, end_date: datetime) -> int:
    tr_start = start_date.strftime("%Y%m%d")
    tr_end = end_date.strftime("%Y%m%d")
    cmd = [
        sys.executable,
        "-m",
        "freqtrade",
        "download-data",
        "--exchange",
        exchange,
        "--pairs",
        pair,
        "--timeframe",
        timeframe,
        "--timerange",
        f"{tr_start}-{tr_end}",
    ]
    print(f"==== 下载区间: {tr_start}-{tr_end} ====")
    return subprocess.call(cmd)


def main():
    pair = "BTC/USDT"
    exchange = "okx"
    timeframe = "1m"
    start = datetime(2024, 1, 1)
    today = datetime.now()

    current = start
    while current.date() < today.date():
        next_month = current + relativedelta(months=1)
        month_end = next_month - timedelta(days=1)
        if month_end.date() > today.date():
            month_end = today
        rc = run_month(pair, exchange, timeframe, current, month_end)
        if rc != 0:
            print(f"区间失败: {current:%Y%m%d}-{month_end:%Y%m%d}")
            sys.exit(rc)
        current = next_month


if __name__ == "__main__":
    main()


