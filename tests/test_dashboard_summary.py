from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from packages.config import Settings
from packages.core_types.schemas import BacktestMetric, ClosedMarketBatchReport, ClosedMarketEvaluationRecord, FeatureAvailability
from services.backtester.service import BacktesterService
from services.state import InMemoryState


class _DummyFeatureEngine:
    def compute_snapshot(self, market_id: str):  # pragma: no cover - helper only
        raise NotImplementedError


def test_dashboard_research_slices_include_bucket_metrics() -> None:
    now = datetime.now(timezone.utc)
    report = ClosedMarketBatchReport(
        run_id="dashboard-report",
        strategy_name="combined_cvd_gap",
        mode="bars_plus_hyperliquid",
        asset_filter="BTC",
        timeframe_filter="crypto_5m",
        limit=10,
        created_at=now,
        total_markets_evaluated=4,
        metrics=[
            BacktestMetric(label="accuracy", value=0.625),
            BacktestMetric(label="average_confidence", value=0.73),
            BacktestMetric(label="simple_contract_score", value=2.0),
        ],
        coverage={"bars_only": 1, "bars_plus_trades": 2, "bars_plus_trades_plus_orderbook": 1},
        records=[
            ClosedMarketEvaluationRecord(
                market_id=UUID("00000000-0000-0000-0000-000000000001"),
                market_slug="btc-updown-5m-1",
                asset="BTC",
                timeframe="crypto_5m",
                market_open_time=now,
                market_close_time=now.replace(hour=10),
                strike_price=0.5,
                actual_resolution="yes",
                actual_resolution_source="polymarket",
                historical_window_start=now,
                historical_window_end=now,
                enrichment_availability=FeatureAvailability(bars_available=True, trades_available=True, orderbook_available=True),
                feature_snapshot_summary={},
                final_decision="buy_yes",
                final_confidence=0.82,
                final_signal_value=0.4,
                correctness=True,
                notes=[],
            ),
            ClosedMarketEvaluationRecord(
                market_id=UUID("00000000-0000-0000-0000-000000000002"),
                market_slug="btc-updown-5m-2",
                asset="BTC",
                timeframe="crypto_5m",
                market_open_time=now,
                market_close_time=now.replace(hour=11),
                strike_price=0.5,
                actual_resolution="no",
                actual_resolution_source="polymarket",
                historical_window_start=now,
                historical_window_end=now,
                enrichment_availability=FeatureAvailability(bars_available=True, trades_available=True, orderbook_available=True),
                feature_snapshot_summary={},
                final_decision="buy_yes",
                final_confidence=0.74,
                final_signal_value=0.2,
                correctness=False,
                notes=[],
            ),
        ],
    )
    state = InMemoryState()
    state.closed_market_batch_reports.append(report)
    service = BacktesterService(
        settings=Settings(),
        state=state,
        feature_engine=_DummyFeatureEngine(),
        polymarket_client=object(),
        external_ingestor=object(),
    )

    slices = service.dashboard_research_slices(asset="BTC")

    assert len(slices) == 1
    slice_ = slices[0]
    assert slice_.timeframe == "crypto_5m"
    assert slice_.sample_size == 4
    assert slice_.confidence_buckets
    assert slice_.hour_buckets
    assert slice_.verdict in {"Strong edge", "Building edge", "Mixed edge", "No edge"}
