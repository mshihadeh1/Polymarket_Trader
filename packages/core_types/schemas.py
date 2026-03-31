from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class MarketToken(BaseModel):
    id: UUID
    token_id: str
    outcome: str


class MarketRule(BaseModel):
    rule_type: str
    source: str | None = None
    text: str
    normalized: dict[str, Any] = Field(default_factory=dict)


class MarketSummary(BaseModel):
    id: UUID
    event_id: UUID | None = None
    slug: str
    title: str
    category: str
    market_type: str
    underlying: str | None = None
    status: str
    opens_at: datetime | None = None
    closes_at: datetime | None = None
    resolves_at: datetime | None = None
    price_to_beat: float | None = None
    open_reference_price: float | None = None
    tags: list[str] = Field(default_factory=list)
    tokens: list[MarketToken] = Field(default_factory=list)


class OrderBookSnapshot(BaseModel):
    ts: datetime
    venue: Literal["polymarket", "hyperliquid"]
    sequence: int | None = None
    best_bid: float
    best_ask: float
    bid_size: float
    ask_size: float
    mid_price: float | None = None
    depth: dict[str, list[list[float]]] = Field(default_factory=dict)


class Trade(BaseModel):
    ts: datetime
    venue: Literal["polymarket", "hyperliquid"]
    sequence: int | None = None
    price: float
    size: float
    side: Literal["buy", "sell"]
    aggressor_side: Literal["buy", "sell"] | None = None


class ExternalContext(BaseModel):
    symbol: str
    open_price: float | None = None
    current_price: float | None = None
    return_since_open: float | None = None
    time_to_close_seconds: float | None = None


class FeatureSnapshot(BaseModel):
    market_id: UUID
    ts: datetime
    polymarket_cvd: float
    polymarket_rolling_cvd: dict[str, float] = Field(default_factory=dict)
    hyperliquid_cvd: float
    hyperliquid_rolling_cvd: dict[str, float] = Field(default_factory=dict)
    polymarket_trade_imbalance: float
    hyperliquid_trade_imbalance: float
    best_bid: float | None = None
    best_ask: float | None = None
    spread: float | None = None
    top_of_book_imbalance: float | None = None
    fair_value_estimate: float | None = None
    fair_value_gap: float | None = None
    distance_to_threshold: float | None = None
    time_to_close_seconds: float | None = None
    external_return_since_open: float | None = None


class MarketDetail(MarketSummary):
    rules: list[MarketRule] = Field(default_factory=list)
    latest_polymarket_orderbook: OrderBookSnapshot | None = None
    latest_hyperliquid_orderbook: OrderBookSnapshot | None = None
    recent_polymarket_trades: list[Trade] = Field(default_factory=list)
    recent_hyperliquid_trades: list[Trade] = Field(default_factory=list)
    external_context: ExternalContext | None = None

    @property
    def latest_orderbook(self) -> OrderBookSnapshot | None:
        return self.latest_polymarket_orderbook


class ReplayEvent(BaseModel):
    ts: datetime
    venue: str
    event_type: Literal["orderbook", "trade", "raw"]
    payload: dict[str, Any]


class ReplayResponse(BaseModel):
    market_id: UUID
    market_slug: str
    events: list[ReplayEvent]


class StrategyDescriptor(BaseModel):
    name: str
    family: str
    description: str
    configurable_fields: list[str]


class BacktestMetric(BaseModel):
    label: str
    value: float


class BacktestReport(BaseModel):
    run_id: str
    strategy_name: str
    market_id: UUID
    metrics: list[BacktestMetric]
    notes: list[str] = Field(default_factory=list)


class PaperTradeDecision(BaseModel):
    ts: datetime
    market_id: UUID
    action: str
    side: str
    price: float
    size: float
    status: str
    reason: str | None = None


class RiskSettings(BaseModel):
    live_execution_enabled: bool
    dry_run_only: bool
    max_market_exposure_usd: float
    global_kill_switch: bool
