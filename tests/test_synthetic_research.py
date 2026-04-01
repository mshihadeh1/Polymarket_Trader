from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path

from packages.clients.market_data_provider.csv import CsvHistoricalProvider
from packages.config import Settings
from packages.core_types import PolymarketMarketMetadata
from services.backtester.synthetic_research import SyntheticResearchService
from services.state import InMemoryState


def _write_1m_csv(path: Path, start: datetime, rows: int, base_price: float = 100.0) -> None:
    lines = ["timestamp,open,high,low,close,volume"]
    for index in range(rows):
        ts = start + timedelta(minutes=index)
        open_price = base_price + index * 0.5
        close_price = open_price + (0.25 if index % 2 == 0 else -0.1)
        high = max(open_price, close_price) + 0.15
        low = min(open_price, close_price) - 0.15
        lines.append(
            f"{ts.isoformat().replace('+00:00', 'Z')},{open_price:.2f},{high:.2f},{low:.2f},{close_price:.2f},{100 + index}"
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def _build_service() -> tuple[SyntheticResearchService, CsvHistoricalProvider]:
    tmp_path = Path("C:/Users/Mahdi/Documents/Polymarket_Trader/data/test_tmp/synthetic_research")
    tmp_path.mkdir(parents=True, exist_ok=True)
    csv_path = tmp_path / "btc.csv"
    _write_1m_csv(csv_path, datetime(2026, 3, 31, 11, 0, tzinfo=timezone.utc), 40)
    provider = CsvHistoricalProvider(path_map={"BTC": str(csv_path)}, symbol_map={"BTC": "BTCUSDT"}, root=tmp_path)
    state = InMemoryState()
    state.external_dataset_validation["BTC"] = provider.validate_symbol("BTC")
    service = SyntheticResearchService(
        settings=Settings(DEFAULT_UNDERLYINGS="BTC"),
        state=state,
        historical_provider=provider,
        polymarket_client=object(),
        persistence=None,
    )
    return service, provider


def test_synthetic_dataset_builds_point_in_time_samples() -> None:
    service, _ = _build_service()
    samples = service.build_synthetic_dataset(asset="BTC", timeframe="crypto_5m")

    assert samples
    sample = next(
        sample
        for sample in samples
        if sample.timeframe == "crypto_5m"
        and sample.market_open_time == datetime(2026, 3, 31, 11, 5, tzinfo=timezone.utc)
    )
    features = service.compute_feature_snapshots_for_sample(sample)
    open_snapshot = next(feature for feature in features if feature.checkpoint_minutes == 0)

    assert open_snapshot.decision_time == sample.market_open_time
    assert open_snapshot.current_price == 102.25
    assert open_snapshot.prior_return_1m is not None
    assert open_snapshot.feature_summary["trend_regime"] in {"unknown", "uptrend", "strong_uptrend", "sideways"}
    assert sample.actual_resolution in {"yes", "no"}


def test_synthetic_batch_produces_cached_report() -> None:
    service, _ = _build_service()
    report = service.run_synthetic_batch(asset="BTC", timeframe="crypto_5m", strategy_name="synthetic_momentum", limit=10)

    assert report.source == "synthetic"
    assert report.total_samples > 0
    assert report.metrics
    assert service.list_reports(source="synthetic")[0].run_id == report.run_id


def test_real_validation_scores_closed_market_with_same_feature_pipeline() -> None:
    service, _ = _build_service()
    raw_market = {
        "id": "real-btc-5m-1",
        "slug": "btc-updown-5m-1775039700",
        "price_to_beat": 102.0,
        "resolved_outcome": "yes",
    }
    metadata = PolymarketMarketMetadata(
        market_id="real-btc-5m-1",
        condition_id="cond-1",
        slug="btc-updown-5m-1775039700",
        question="Will BTC 5m candle close above 102.00?",
        category="crypto",
        market_family="btc_updown_5m",
        event_slug="btc-updown-5m-1775039700",
        event_epoch=1775039700,
        duration_minutes=5,
        active=False,
        closed=True,
        start_date=datetime(2026, 3, 31, 11, 10, tzinfo=timezone.utc),
        end_date=datetime(2026, 3, 31, 11, 15, tzinfo=timezone.utc),
        resolution_source="polymarket",
        price_to_beat=102.0,
        resolved_outcome="yes",
        resolution_price=103.0,
    )

    class _StubClient:
        async def discover_markets(self, *, closed=None, active=None, limit=None):
            return [raw_market], [metadata]

    service._polymarket_client = _StubClient()

    report = service.run_real_validation_batch(asset="BTC", timeframe="crypto_5m", strategy_name="synthetic_momentum", limit=1)

    assert report.source == "real_validation"
    assert report.total_samples == 1
    assert report.records[0].market_id == "real-btc-5m-1"
    assert report.records[0].actual_resolution == "yes"
