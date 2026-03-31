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
