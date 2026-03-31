from datetime import datetime, timezone

from packages.core_types.schemas import Trade
from packages.utils.cvd import cumulative_volume_delta, rolling_cvd, trade_imbalance


def build_trade(second: int, size: float, side: str) -> Trade:
    return Trade(
        ts=datetime(2026, 3, 31, 12, 0, second, tzinfo=timezone.utc),
        venue="polymarket",
        price=0.5,
        size=size,
        side=side,
        aggressor_side=side,
    )


def test_cumulative_volume_delta_uses_signed_aggressor_flow() -> None:
    trades = [build_trade(1, 10, "buy"), build_trade(2, 4, "sell"), build_trade(3, 3, "buy")]
    assert cumulative_volume_delta(trades) == 9


def test_rolling_cvd_respects_time_window() -> None:
    trades = [build_trade(1, 10, "buy"), build_trade(10, 4, "sell"), build_trade(20, 3, "buy")]
    values = rolling_cvd(trades, trades[-1].ts, [5, 30])
    assert values["5s"] == 3
    assert values["30s"] == 9


def test_trade_imbalance_normalizes_volume() -> None:
    trades = [build_trade(1, 6, "buy"), build_trade(2, 4, "sell")]
    assert trade_imbalance(trades) == 0.2
