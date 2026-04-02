from datetime import datetime, timezone

from packages.config import Settings
from polymarket_trader.bootstrap import build_container


def test_feature_engine_is_point_in_time_correct() -> None:
    container = build_container(Settings())
    snapshot = container.feature_engine.compute_snapshot(
        "6fd5b43f-b7c7-4f63-bf57-3a91e89e8c30",
        as_of=datetime(2026, 3, 31, 11, 59, 0, tzinfo=timezone.utc),
    )
    assert snapshot.polymarket_cvd == 750
    assert snapshot.external_cvd < 1.0


def test_feature_engine_does_not_duplicate_same_timestamp_snapshot() -> None:
    container = build_container(Settings())
    market_id = "6fd5b43f-b7c7-4f63-bf57-3a91e89e8c30"
    before = len(container.feature_engine.list_snapshots(market_id))
    container.feature_engine.compute_snapshot(market_id)
    after = len(container.feature_engine.list_snapshots(market_id))
    assert after == before


def test_feature_engine_exposes_short_horizon_flow_features() -> None:
    container = build_container(Settings())
    snapshot = container.feature_engine.compute_snapshot(
        "6fd5b43f-b7c7-4f63-bf57-3a91e89e8c30",
        as_of=datetime(2026, 3, 31, 11, 59, 0, tzinfo=timezone.utc),
    )
    assert snapshot.polymarket_rolling_trade_imbalance
    assert snapshot.external_rolling_trade_imbalance
    assert snapshot.polymarket_flow_signal is not None
    assert snapshot.external_flow_signal is not None
    assert snapshot.flow_alignment_score is not None
    assert -1.0 <= snapshot.flow_alignment_score <= 1.0
    assert snapshot.spread_bps is not None
    assert snapshot.distance_to_threshold_bps is not None
