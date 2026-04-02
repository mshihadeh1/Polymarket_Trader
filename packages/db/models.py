from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String
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


class ClosedMarketBatchReportRecord(Base):
    __tablename__ = "closed_market_batch_reports_cache"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    strategy_name: Mapped[str] = mapped_column(String, nullable=False)
    mode: Mapped[str] = mapped_column(String, nullable=False)
    asset_filter: Mapped[str | None] = mapped_column(String)
    timeframe_filter: Mapped[str | None] = mapped_column(String)
    limit: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_markets_evaluated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    metrics: Mapped[list] = mapped_column(JSON, nullable=False)
    coverage: Mapped[dict] = mapped_column(JSON, nullable=False)
    records: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, nullable=False)


class MinuteResearchRowRecord(Base):
    __tablename__ = "minute_research_rows_cache"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    asset: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    decision_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    horizon_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reference_price: Mapped[float] = mapped_column(Float, nullable=False)
    close_5m: Mapped[float] = mapped_column(Float, nullable=False)
    close_15m: Mapped[float] = mapped_column(Float, nullable=False)
    label_up_5m: Mapped[bool] = mapped_column(Boolean, nullable=False)
    label_up_15m: Mapped[bool] = mapped_column(Boolean, nullable=False)
    future_return_5m: Mapped[float] = mapped_column(Float, nullable=False)
    future_return_15m: Mapped[float] = mapped_column(Float, nullable=False)
    source_provider: Mapped[str] = mapped_column(String, nullable=False)
    market_id: Mapped[str | None] = mapped_column(String, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, nullable=False)


class MinuteFeatureSnapshotRecord(Base):
    __tablename__ = "minute_feature_snapshots_cache"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    row_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    asset: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    decision_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, nullable=False)


class MinuteBatchReportRecord(Base):
    __tablename__ = "minute_batch_reports_cache"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    strategy_name: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    asset_filter: Mapped[str | None] = mapped_column(String)
    timeframe_filter: Mapped[str | None] = mapped_column(String)
    total_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    metrics: Mapped[list] = mapped_column(JSON, nullable=False)
    coverage: Mapped[dict] = mapped_column(JSON, nullable=False)
    records: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, nullable=False)


class SyntheticMarketSampleRecord(Base):
    __tablename__ = "synthetic_market_samples_cache"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    market_id: Mapped[str | None] = mapped_column(String, index=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    asset: Mapped[str] = mapped_column(String, nullable=False)
    timeframe: Mapped[str] = mapped_column(String, nullable=False)
    market_open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    market_close_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    decision_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_provider: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, nullable=False)


class SyntheticFeatureSnapshotRecord(Base):
    __tablename__ = "synthetic_feature_snapshots_cache"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    sample_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    market_id: Mapped[str | None] = mapped_column(String, index=True)
    decision_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, nullable=False)


class SyntheticBatchReportRecord(Base):
    __tablename__ = "synthetic_batch_reports_cache"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    strategy_name: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    asset_filter: Mapped[str | None] = mapped_column(String)
    timeframe_filter: Mapped[str | None] = mapped_column(String)
    decision_time: Mapped[str] = mapped_column(String, nullable=False)
    total_samples: Mapped[int] = mapped_column(default=0, nullable=False)
    metrics: Mapped[list] = mapped_column(JSON, nullable=False)
    coverage: Mapped[dict] = mapped_column(JSON, nullable=False)
    records: Mapped[list] = mapped_column(JSON, nullable=False)
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


class PolymarketMarketRecord(Base):
    __tablename__ = "polymarket_market_cache"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    slug: Mapped[str | None] = mapped_column(String)
    event_slug: Mapped[str | None] = mapped_column(String)
    event_epoch: Mapped[int | None] = mapped_column(Integer)
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    market_type: Mapped[str] = mapped_column(String, nullable=False)
    underlying: Mapped[str | None] = mapped_column(String)
    market_family: Mapped[str | None] = mapped_column(String)
    source: Mapped[str] = mapped_column(String, nullable=False)
    price_to_beat: Mapped[float | None] = mapped_column(Float)
    resolved_outcome: Mapped[str] = mapped_column(String, default="unknown", nullable=False)
    resolution_price: Mapped[float | None] = mapped_column(Float)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, nullable=False)


class PolymarketTradeRecord(Base):
    __tablename__ = "polymarket_trade_cache"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    market_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    asset_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, nullable=False)


class PolymarketBookRecord(Base):
    __tablename__ = "polymarket_book_cache"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    market_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    asset_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, nullable=False)


class PolymarketRawEventRecord(Base):
    __tablename__ = "polymarket_raw_event_cache"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    market_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    asset_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utc_now, nullable=False)
