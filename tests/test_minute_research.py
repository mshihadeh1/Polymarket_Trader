from __future__ import annotations

import csv
from datetime import UTC, datetime, timedelta
from pathlib import Path

from packages.clients.market_data_provider import build_historical_market_data_provider
from packages.config import Settings
from packages.core_types import PolymarketMarketMetadata
from services.backtester.minute_research import MinuteResearchService
from services.feature_engine.market_window import MarketWindowService
from services.state import InMemoryState


def _write_csv(path: Path, start: datetime, closes: list[float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["timestamp", "open", "high", "low", "close", "volume"])
        for index, close in enumerate(closes):
            ts = start + timedelta(minutes=index)
            open_price = close - 0.5
            writer.writerow([ts.isoformat(), open_price, close + 0.25, open_price - 0.25, close, 1000 + index])


def _build_service(csv_path: Path, polymarket_client) -> MinuteResearchService:
    settings = Settings(
        external_historical_provider="csv",
        csv_provider_paths=f'{{"BTC":"{csv_path.as_posix()}"}}',
        csv_btc_path=csv_path.as_posix(),
        csv_eth_path=csv_path.as_posix(),
        csv_sol_path=csv_path.as_posix(),
        use_mock_polymarket_client=True,
        enable_db_persistence=False,
    )
    state = InMemoryState()
    provider = build_historical_market_data_provider(settings, root=Path.cwd())
    return MinuteResearchService(
        settings=settings,
        state=state,
        historical_provider=provider,
        polymarket_client=polymarket_client,
        market_window=MarketWindowService(state),
        persistence=None,
    )


def test_minute_dataset_builds_point_in_time_features() -> None:
    csv_path = Path("tests/_scratch/minute_btc.csv")
    start = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    closes = [100 + index for index in range(70)]
    closes[60] = 1000.0
    _write_csv(csv_path, start, closes)
    service = _build_service(csv_path, polymarket_client=_FakePolymarketClient())

    rows = service.build_minute_dataset(asset="BTC", start=start, end=start + timedelta(minutes=69), refresh=True)

    assert len(rows) > 0
    row = next(item for item in rows if item.decision_time == start + timedelta(minutes=30))
    feature = service._feature_for_row(row)
    assert feature is not None
    assert feature.current_price == row.reference_price
    assert feature.ret_1m is not None
    expected_previous = closes[29]
    expected_current = closes[30]
    assert feature.ret_1m == (expected_current - expected_previous) / expected_previous
    expected_mean = sum(closes[16:31]) / len(closes[16:31])
    assert feature.distance_from_mean == (expected_current - expected_mean) / expected_mean


def test_minute_batches_score_5m_and_15m_separately() -> None:
    csv_path = Path("tests/_scratch/minute_btc_batches.csv")
    start = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    closes = [100 + (index * 0.75) for index in range(80)]
    _write_csv(csv_path, start, closes)
    service = _build_service(csv_path, polymarket_client=_FakePolymarketClient())
    service.build_minute_dataset(asset="BTC", start=start, end=start + timedelta(minutes=79), refresh=True)

    report_5m = service.run_batch(asset="BTC", timeframe="crypto_5m", strategy_name="minute_momentum", limit=25, refresh=False)
    report_15m = service.run_batch(asset="BTC", timeframe="crypto_15m", strategy_name="minute_mean_reversion", limit=25, refresh=False)

    assert report_5m.timeframe_filter == "crypto_5m"
    assert report_15m.timeframe_filter == "crypto_15m"
    assert report_5m.total_rows > 0
    assert report_15m.total_rows > 0
    assert report_5m.metrics[0].label == "hit_rate"
    assert report_15m.metrics[0].label == "hit_rate"


def test_real_validation_uses_polymarket_resolution() -> None:
    csv_path = Path("tests/_scratch/minute_btc_validation.csv")
    start = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    closes = [100 + index for index in range(90)]
    _write_csv(csv_path, start, closes)
    metadata = PolymarketMarketMetadata(
        market_id="btc-market-1",
        condition_id="condition-1",
        slug="btc-updown-5m-1775039700",
        question="Bitcoin Up or Down - Example",
        category="crypto",
        market_family="btc_updown_5m",
        event_slug="btc-updown-5m-1775039700",
        event_epoch=1775039700,
        duration_minutes=5,
        active=False,
        closed=True,
        accepting_orders=False,
        enable_order_book=False,
        start_date=start + timedelta(minutes=30),
        end_date=start + timedelta(minutes=35),
        resolution_source="polymarket",
        description="Closed BTC short-horizon market.",
        price_to_beat=130.0,
        resolved_outcome="yes",
        resolution_price=135.0,
        outcomes=["YES", "NO"],
        outcome_prices=[0.0, 0.0],
        token_ids=["yes-token", "no-token"],
        best_bid=None,
        best_ask=None,
        last_trade_price=None,
        raw_tags=["crypto_5m"],
    )
    service = _build_service(
        csv_path,
        polymarket_client=_FakePolymarketClient(
            raw_markets=[{"id": "btc-market-1", "slug": metadata.slug, "price_to_beat": 130.0, "winner": "yes"}],
            normalized_markets=[metadata],
        ),
    )
    report = service.run_real_validation_batch(asset="BTC", timeframe="crypto_5m", strategy_name="minute_momentum", limit=1, refresh=True)

    assert report.source == "real_validation"
    assert report.total_rows > 0
    assert report.records[0].correctness is True


class _FakePolymarketClient:
    def __init__(self, raw_markets: list[dict] | None = None, normalized_markets: list[PolymarketMarketMetadata] | None = None) -> None:
        self._raw_markets = raw_markets or []
        self._normalized_markets = normalized_markets or []
        self.is_mock = True

    async def discover_markets(self, closed: bool | None = None, limit: int | None = None, **_: object):
        return self._raw_markets[: limit or len(self._raw_markets)], self._normalized_markets[: limit or len(self._normalized_markets)]
