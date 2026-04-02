from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta

from packages.core_types.schemas import Trade


def _signed_volume(trade: Trade) -> float:
    side = trade.aggressor_side or trade.side
    return trade.size if side == "buy" else -trade.size


def cumulative_volume_delta(trades: Iterable[Trade]) -> float:
    return sum(_signed_volume(trade) for trade in trades)


def rolling_cvd(trades: list[Trade], as_of: datetime, windows_seconds: list[int]) -> dict[str, float]:
    values: dict[str, float] = {}
    for window in windows_seconds:
        start = as_of - timedelta(seconds=window)
        window_trades = [trade for trade in trades if start <= trade.ts <= as_of]
        values[f"{window}s"] = cumulative_volume_delta(window_trades)
    return values


def rolling_trade_imbalance(trades: list[Trade], as_of: datetime, windows_seconds: list[int]) -> dict[str, float]:
    values: dict[str, float] = {}
    for window in windows_seconds:
        start = as_of - timedelta(seconds=window)
        window_trades = [trade for trade in trades if start <= trade.ts <= as_of]
        values[f"{window}s"] = trade_imbalance(window_trades)
    return values


def trade_imbalance(trades: Iterable[Trade]) -> float:
    buy = 0.0
    sell = 0.0
    for trade in trades:
        if (trade.aggressor_side or trade.side) == "buy":
            buy += trade.size
        else:
            sell += trade.size
    total = buy + sell
    if total == 0:
        return 0.0
    return (buy - sell) / total
