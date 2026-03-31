from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class TokenSchema(BaseModel):
    id: UUID
    token_id: str
    outcome: str


class OrderBookSnapshotSchema(BaseModel):
    ts: datetime
    best_bid: float
    best_ask: float
    bid_size: float
    ask_size: float
    depth: dict[str, list[list[float]]] = Field(default_factory=dict)


class TradeSchema(BaseModel):
    ts: datetime
    price: float
    size: float
    side: Literal["buy", "sell"]
    aggressor_side: Literal["buy", "sell"] | None = None


class MarketSchema(BaseModel):
    id: UUID
    slug: str
    title: str
    category: str
    market_type: str
    resolution_source: str | None = None
    rules_text: str | None = None
    status: str
    opens_at: datetime | None = None
    closes_at: datetime | None = None
    resolves_at: datetime | None = None
    tags: list[str] = Field(default_factory=list)
    tokens: list[TokenSchema] = Field(default_factory=list)


class MarketDetailSchema(MarketSchema):
    latest_orderbook: OrderBookSnapshotSchema | None = None
    recent_trades: list[TradeSchema] = Field(default_factory=list)


class ReplayEventSchema(BaseModel):
    ts: datetime
    event_type: Literal["orderbook", "trade"]
    payload: dict[str, Any]


class ReplayResponseSchema(BaseModel):
    market_id: UUID
    market_slug: str
    events: list[ReplayEventSchema]


class PaperTradeDecisionSchema(BaseModel):
    ts: datetime
    market_id: UUID
    action: str
    side: str
    price: float
    size: float
    status: str


class RiskSettingsSchema(BaseModel):
    live_execution_enabled: bool
    dry_run_only: bool
    max_market_exposure_usd: float
    global_kill_switch: bool
