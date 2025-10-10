from __future__ import annotations

from typing import Any
import json
import os

import numpy as np
import pandas as pd

from freqtrade.strategy import (
    IStrategy,
    IntParameter,
    DecimalParameter,
    CategoricalParameter,
)
from freqtrade.persistence import Trade


class Always50GridLeverageStrategy(IStrategy):
    """
    无限网格 + 50/50 再平衡（长多为主）+ 杠杆（期货/杠杆账户）

    设计要点：
    - 通过 `grid_distance` 控制买卖触发的价格偏离幅度（可超参优化）
    - 通过 `leverage_opt` 为非现货模式返回杠杆倍数（可超参优化）
    - 使用简单的价格锚（EMA）作为再平衡参考，向下偏离买入、向上偏离卖出
    - 使用固定 `stoploss`，可通过超参优化 `stoploss_opt` 进行调整

    说明：
    - Freqtrade 的组合层面 50/50 精准再平衡需钱包级信息与多资产配比控制。
      在策略层面，我们用“价格相对锚点偏离”的网格式再平衡近似实现：
        * 当 close 相对锚点下跌超过 grid_distance -> 产生买入信号
        * 当 close 相对锚点上涨超过 grid_distance -> 产生卖出（退出）信号
    - 杠杆仅在非现货模式有效（FUTURES/MARGIN）。
    """

    # 基本参数
    can_short = False
    timeframe = "5m"
    startup_candle_count = 100

    # 允许加仓（网格分批）
    position_adjustment_enable = True

    # 进出场订单类型
    order_types = {
        "entry": "limit",
        "exit": "limit",
        "emergency_exit": "market",
        "force_exit": "market",
        "stoploss": "market",
        "stoploss_on_exchange": False,
    }

    order_time_in_force = {
        "entry": "gtc",
        "exit": "gtc",
    }

    # 可优化参数
    # 注意：以 buy_ 前缀命名，便于 Freqtrade 将其纳入 'buy' 空间进行超参优化
    buy_grid_distance = DecimalParameter(0.01, 0.10, default=0.01, decimals=3, optimize=True)
    buy_ema_period = IntParameter(20, 200, default=50, optimize=True)
    buy_leverage_opt = CategoricalParameter([1.0, 2.0, 3.0, 4.0], default=2.0, optimize=True)
    buy_stoploss_opt = DecimalParameter(-0.30, -0.02, default=-0.12, decimals=3, optimize=True)

    # 固定止损由可优化参数驱动
    stoploss = -0.12

    minimal_roi = {
        "0": 0.10,
    }

    # 超参结果文件：与本策略同目录、固定文件名
    _PARAMS_FILENAME = "always50_grid_leverage_strategy.params.json"

    def __init__(self, config: dict) -> None:
        super().__init__(config)
        # 启动时自动从同目录下加载最佳参数（若存在）
        try:
            self._load_optimized_params()
        except Exception:
            # 加载失败则忽略，沿用默认/当前参数
            pass

    # 读取并应用同目录下的超参优化结果
    def _load_optimized_params(self) -> None:
        strategy_dir = os.path.dirname(os.path.abspath(__file__))
        params_path = os.path.join(strategy_dir, self._PARAMS_FILENAME)
        if not os.path.isfile(params_path):
            return

        with open(params_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 若是 freqtrade 导出的完整结构，取其中 params.buy / params.stoploss / params.roi
        if isinstance(data, dict) and "params" in data:
            params_dict = data.get("params", {}) or {}
            buy_dict = params_dict.get("buy", {}) or {}
            # 将 buy_* 平铺到 data，兼容 _get_value 逻辑
            data.update(buy_dict)
            # roi/stoploss 同步到实例（若存在）
            roi_dict = params_dict.get("roi", {}) or {}
            if roi_dict:
                try:
                    # 将键转为 str 以和 freqtrade 兼容
                    self.minimal_roi = {str(k): float(v) for k, v in roi_dict.items()}
                except Exception:
                    pass
            stoploss_dict = params_dict.get("stoploss", {}) or {}
            if "stoploss" in stoploss_dict:
                try:
                    self.stoploss = float(stoploss_dict["stoploss"])  # noqa: PLW2901
                except Exception:
                    pass

        # 读取并安全设置参数值（裁剪到定义区间内）
        def _get_value(keys: list[str], default: float | int) -> float | int:
            for k in keys:
                if k in data:
                    val = data[k]
                    return float(val) if isinstance(default, float) else int(val)
            val = default
            return float(val) if isinstance(default, float) else int(val)

        # grid_distance -> buy_grid_distance（兼容旧键名）
        if hasattr(self.buy_grid_distance, "low") and hasattr(self.buy_grid_distance, "high"):
            gd = float(_get_value(["buy_grid_distance", "grid_distance"], float(self.buy_grid_distance.value)))
            gd = float(min(max(gd, float(self.buy_grid_distance.low)), float(self.buy_grid_distance.high)))
            self.buy_grid_distance.value = gd

        # ema_period -> buy_ema_period（兼容旧键名）
        if hasattr(self.buy_ema_period, "low") and hasattr(self.buy_ema_period, "high"):
            ep = int(_get_value(["buy_ema_period", "ema_period"], int(self.buy_ema_period.value)))
            ep = int(min(max(ep, int(self.buy_ema_period.low)), int(self.buy_ema_period.high)))
            self.buy_ema_period.value = ep

        # leverage_opt -> buy_leverage_opt（离散集合内取最近合法值，兼容旧键名）
        try:
            cand = list(self.buy_leverage_opt.options)  # type: ignore[attr-defined]
        except Exception:
            cand = [float(self.buy_leverage_opt)]  # 回退
        lv = float(_get_value(["buy_leverage_opt", "leverage_opt"], float(self.buy_leverage_opt.value)))
        # 按数值与候选集最接近取值
        if cand:
            closest = min(cand, key=lambda x: abs(float(x) - lv))
            self.buy_leverage_opt.value = float(closest)

        # stoploss_opt -> buy_stoploss_opt（负值区间，兼容旧键名）
        if hasattr(self.buy_stoploss_opt, "low") and hasattr(self.buy_stoploss_opt, "high"):
            sl = float(_get_value(["buy_stoploss_opt", "stoploss_opt"], float(self.buy_stoploss_opt.value)))
            sl = float(min(max(sl, float(self.buy_stoploss_opt.low)), float(self.buy_stoploss_opt.high)))
            self.buy_stoploss_opt.value = sl
            # 若使用引擎默认 stoploss，也同步一次，避免图表等引用
            try:
                self.stoploss = sl  # noqa: PLW2901 (覆盖类属性用于实例)
            except Exception:
                pass

    def leverage(
        self,
        pair: str,
        current_time: pd.Timestamp,
        current_rate: float,
        proposed_leverage: float,
        max_leverage: float,
        side: str,
        entry_tag: str | None,
        **kwargs: Any,
    ) -> float:
        # 返回不超过交易所允许的杠杆
        lev = float(self.buy_leverage_opt.value) if hasattr(self.buy_leverage_opt, "value") else float(self.buy_leverage_opt)
        return float(min(max(1.0, lev), max_leverage))

    def custom_stoploss(
        self,
        pair: str,
        trade: Trade,
        current_time: pd.Timestamp,
        current_rate: float,
        current_profit: float,
        **kwargs: Any,
    ) -> float:
        # 使用可优化的固定止损
        return float(self.buy_stoploss_opt.value)

    def custom_stake_amount(
        self,
        pair: str,
        current_time: pd.Timestamp,
        current_rate: float,
        proposed_stake: float,
        min_stake: float,
        max_stake: float,
        leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs: Any,
    ) -> float:
        # 简单网格动态仓位：偏离越大，下单越大（线性放大），受 max_stake 限制
        # 偏离使用最近指标的 ema 与 close 差异估算
        df = self.dp.get_pair_dataframe(pair, self.timeframe)
        if df is None or len(df) == 0 or "grid_anchor" not in df.columns:
            return float(np.clip(proposed_stake, min_stake, max_stake))

        anchor = float(df.iloc[-1]["grid_anchor"]) or current_rate
        deviation = abs(current_rate - anchor) / max(anchor, 1e-12)
        scale = 1.0 + (deviation / max(self.buy_grid_distance.value, 1e-6))
        sized = proposed_stake * min(scale, 3.0)  # 上限放大 3x，避免过度出价
        return float(np.clip(sized, min_stake, max_stake))

    def informative_pairs(self):
        return []

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        # 价格锚：EMA（使用 pandas 计算，避免 talib 依赖）
        period = int(self.buy_ema_period.value)
        dataframe["grid_anchor"] = (
            dataframe["close"].ewm(span=period, adjust=False).mean()
        )

        # 波动衡量：ATR（简单 rolling 版）
        prev_close = dataframe["close"].shift(1)
        tr1 = dataframe["high"] - dataframe["low"]
        tr2 = (dataframe["high"] - prev_close).abs()
        tr3 = (dataframe["low"] - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr_period = max(14, period // 5)
        dataframe["atr"] = tr.rolling(window=atr_period, min_periods=1).mean()

        # 偏离比（正向为上涨超锚，负向为下跌超锚）
        dataframe["deviation"] = (dataframe["close"] - dataframe["grid_anchor"]) / dataframe["grid_anchor"]

        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        df = dataframe
        dist = float(self.buy_grid_distance.value)

        # 下穿偏离阈值 -> 买入
        buy_cond = (
            (df["grid_anchor"].notnull())
            & (df["deviation"] <= -dist)
        )

        df.loc[buy_cond, ["enter_long", "enter_tag"]] = (1, "grid_long_entry")

        return df

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        df = dataframe
        dist = float(self.buy_grid_distance.value)

        # 上穿偏离阈值 -> 卖出（部分或全部）
        sell_cond = (
            (df["grid_anchor"].notnull())
            & (df["deviation"] >= dist)
        )

        df.loc[sell_cond, ["exit_long", "exit_tag"]] = (1, "grid_long_exit")

        return df

    plot_config = {
        "main_plot": {
            "grid_anchor": {"color": "orange"},
        },
        "subplots": {
            "deviation": {
                "deviation": {"color": "blue"},
            },
            "atr": {
                "atr": {"color": "purple"},
            },
        },
    }


