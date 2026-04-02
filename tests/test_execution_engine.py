from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from packages.config import Settings
from packages.core_types.schemas import ExecutionFillRecord, ExecutionOrderIntent
from packages.db import ResearchPersistence, create_session_factory
from services.execution_engine import ExecutionEngineService
from services.state import InMemoryState


def _persistence(base_path: Path) -> ResearchPersistence:
    settings = Settings(
        ENABLE_DB_PERSISTENCE=True,
        DATABASE_URL="sqlite:///:memory:",
        SQLITE_FALLBACK_PATH=str(base_path / "execution_engine.sqlite"),
    )
    return ResearchPersistence(create_session_factory(settings))


def test_execution_engine_persists_dry_run_orders_and_fills() -> None:
    persistence = _persistence(Path.cwd())
    settings = Settings(LIVE_EXECUTION_ENABLED=False)
    service = ExecutionEngineService(settings=settings, state=InMemoryState(), persistence=persistence)

    intent = ExecutionOrderIntent(
        intent_id="intent-1",
        strategy_name="combined_cvd_gap",
        market_id=uuid4(),
        token_id="token-1",
        market_side="buy_yes",
        order_side="BUY",
        price=0.52,
        size=50.0,
        order_type="GTC",
        post_only=True,
        dry_run=False,
        created_at=datetime.now(timezone.utc),
    )

    order = service.submit_intent(intent)
    assert order.dry_run is True
    assert order.status == "dry_run"
    assert service.status().enabled is False
    assert len(service.list_orders()) == 1
    assert len(persistence.list_execution_orders()) == 1

    fill = ExecutionFillRecord(
        fill_id="fill-1",
        order_id=order.order_id,
        market_id=intent.market_id,
        token_id=intent.token_id,
        ts=datetime.now(timezone.utc),
        side="BUY",
        price=0.51,
        size=50.0,
        fee=0.35,
        fee_currency="USDC",
        status="filled",
        dry_run=True,
        source="paper",
        payload={"source": "unit-test"},
    )
    service.record_fill(fill)
    assert len(service.list_fills()) == 1
    assert len(persistence.list_execution_fills()) == 1
