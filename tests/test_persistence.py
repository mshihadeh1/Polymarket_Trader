from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from packages.config import Settings
from packages.core_types.schemas import (
    BacktestMetric,
    ClosedMarketBatchReport,
    ClosedMarketEvaluationRecord,
    FeatureAvailability,
    PaperTradeDecision,
)
from packages.db import ResearchPersistence, create_session_factory
from services.backtester.service import BacktesterService
from services.paper_trader.service import PaperTraderService
from services.state import InMemoryState


class _DummyFeatureEngine:
    def compute_snapshot(self, market_id: str):  # pragma: no cover - helper only
        raise NotImplementedError


def _persistence(base_path: Path) -> ResearchPersistence:
    settings = Settings(
        ENABLE_DB_PERSISTENCE=True,
        DATABASE_URL="sqlite:///:memory:",
        SQLITE_FALLBACK_PATH=str(base_path / "polymarket_trader.sqlite"),
    )
    return ResearchPersistence(create_session_factory(settings))


def test_closed_market_batch_reports_round_trip_via_persistence() -> None:
    persistence = _persistence(Path.cwd())
    now = datetime.now(timezone.utc)
    report = ClosedMarketBatchReport(
        run_id="closed-batch-1",
        strategy_name="combined_cvd_gap",
        mode="bars_only",
        asset_filter="BTC",
        timeframe_filter="crypto_5m",
        limit=10,
        created_at=now,
        total_markets_evaluated=1,
        metrics=[BacktestMetric(label="accuracy", value=0.75)],
        coverage={"bars_only": 1},
        records=[
                ClosedMarketEvaluationRecord(
                    market_id=uuid4(),
                market_slug="btc-updown-5m-1",
                asset="BTC",
                timeframe="crypto_5m",
                market_open_time=now,
                market_close_time=now,
                strike_price=0.5,
                actual_resolution="yes",
                actual_resolution_source="polymarket",
                historical_window_start=now,
                historical_window_end=now,
                enrichment_availability=FeatureAvailability(bars_available=True),
                feature_snapshot_summary={"fair_value_gap": 0.1},
                final_decision="buy_yes",
                final_confidence=0.8,
                final_signal_value=0.7,
                correctness=True,
                notes=["persisted"],
            )
        ],
    )

    persistence.save_closed_market_batch_report(report)
    loaded = persistence.list_closed_market_batch_reports()

    assert len(loaded) == 1
    assert loaded[0].run_id == report.run_id
    assert loaded[0].records[0].market_slug == "btc-updown-5m-1"


def test_backtester_merges_persisted_and_in_memory_closed_reports() -> None:
    persistence = _persistence(Path.cwd())
    now = datetime.now(timezone.utc)
    persisted = ClosedMarketBatchReport(
        run_id="persisted-report",
        strategy_name="combined_cvd_gap",
        mode="bars_plus_hyperliquid",
        asset_filter="BTC",
        timeframe_filter="crypto_15m",
        limit=10,
        created_at=now,
        total_markets_evaluated=1,
        metrics=[],
        coverage={},
        records=[],
    )
    in_memory = ClosedMarketBatchReport(
        run_id="memory-report",
        strategy_name="combined_cvd_gap",
        mode="bars_only",
        asset_filter="BTC",
        timeframe_filter="crypto_5m",
        limit=10,
        created_at=now + timedelta(microseconds=1),
        total_markets_evaluated=1,
        metrics=[],
        coverage={},
        records=[],
    )
    persistence.save_closed_market_batch_report(persisted)
    state = InMemoryState()
    state.closed_market_batch_reports.append(in_memory)

    service = BacktesterService(
        settings=Settings(),
        state=state,
        feature_engine=_DummyFeatureEngine(),
        polymarket_client=object(),
        external_ingestor=object(),
        persistence=persistence,
    )

    reports = service.list_closed_market_batch_reports()
    assert {report.run_id for report in reports} == {"memory-report", "persisted-report"}


def test_paper_trader_blotter_hydrates_from_persistence() -> None:
    persistence = _persistence(Path.cwd())
    decision = PaperTradeDecision(
        ts=datetime.now(timezone.utc),
        market_id=uuid4(),
        action="loop_eval",
        side="buy_yes",
        price=0.52,
        size=100.0,
        status="simulated_fill",
        reason="hydration-check",
        signal_value=0.8,
        confidence=0.9,
    )
    persistence.save_paper_decision(decision, is_dry_run=True)

    service = PaperTraderService(
        settings=Settings(),
        state=InMemoryState(),
        feature_engine=_DummyFeatureEngine(),
        persistence=persistence,
    )

    blotter = service.blotter()
    assert len(blotter) == 1
    assert blotter[0].reason == "hydration-check"
