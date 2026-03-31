from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class MarketRecord(Base):
    __tablename__ = "markets"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    market_type: Mapped[str] = mapped_column(String, nullable=False)
    resolution_source: Mapped[str | None] = mapped_column(String)
    rules_text: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, nullable=False)
    opens_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolves_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OrderBookSnapshotRecord(Base):
    __tablename__ = "orderbook_snapshots"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    best_bid: Mapped[float] = mapped_column(Float, nullable=False)
    best_ask: Mapped[float] = mapped_column(Float, nullable=False)
    bid_size: Mapped[float] = mapped_column(Float, nullable=False)
    ask_size: Mapped[float] = mapped_column(Float, nullable=False)
    depth_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class TradeRecord(Base):
    __tablename__ = "trades"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    size: Mapped[float] = mapped_column(Float, nullable=False)
    side: Mapped[str] = mapped_column(String, nullable=False)
    aggressor_side: Mapped[str | None] = mapped_column(String)


class FillRecord(Base):
    __tablename__ = "fills"

    id: Mapped[str] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    market_id: Mapped[str] = mapped_column(ForeignKey("markets.id"), nullable=False)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    side: Mapped[str] = mapped_column(String, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    size: Mapped[float] = mapped_column(Float, nullable=False)
    fee: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    is_hypothetical: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
