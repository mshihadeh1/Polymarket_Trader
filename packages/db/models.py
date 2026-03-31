from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.schema import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class FeatureSnapshotRecord(Base):
    __tablename__ = "feature_snapshots_cache"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    market_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, nullable=False)


class BacktestRunRecord(Base):
    __tablename__ = "backtest_runs_cache"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    market_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    strategy_name: Mapped[str] = mapped_column(String, nullable=False)
    trade_count: Mapped[int] = mapped_column(default=0, nullable=False)
    metrics: Mapped[list] = mapped_column(JSON, nullable=False)
    decisions: Mapped[list] = mapped_column(JSON, nullable=False)
    notes: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, nullable=False)


class PaperDecisionRecord(Base):
    __tablename__ = "paper_decisions_cache"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    market_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    action: Mapped[str] = mapped_column(String, nullable=False)
    side: Mapped[str] = mapped_column(String, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    size: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str | None] = mapped_column(String)
    is_dry_run: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, nullable=False)
