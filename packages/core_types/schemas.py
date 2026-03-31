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
    external_provider: str | None = None
    source: str | None = None
    tags: list[str] = Field(default_factory=list)
    tokens: list[MarketToken] = Field(default_factory=list)


class ProviderCapabilities(BaseModel):
    has_ohlcv: bool = False
    has_trades: bool = False
    has_l2: bool = False
    has_snapshots: bool = False

    @property
    def ohlcv(self) -> bool:
        return self.has_ohlcv

    @property
    def trades(self) -> bool:
        return self.has_trades

    @property
    def l2(self) -> bool:
        return self.has_l2

    @property
    def snapshots(self) -> bool:
        return self.has_snapshots


class SymbolMapping(BaseModel):
    internal_symbol: str
    provider_symbol: str
    provider_name: str


class OHLCVBar(BaseModel):
    ts: datetime
    symbol: str
    provider: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    interval: str


class ExternalOrderBookSnapshot(BaseModel):
    ts: datetime
    venue: str
    sequence: int | None = None
    symbol: str | None = None
    best_bid: float
    best_ask: float
    bid_size: float
    ask_size: float
    mid_price: float | None = None
    depth: dict[str, list[list[float]]] = Field(default_factory=dict)


class ExternalTrade(BaseModel):
    ts: datetime
    venue: str
    sequence: int | None = None
    symbol: str | None = None
    price: float
    size: float
    side: Literal["buy", "sell"]
    aggressor_side: Literal["buy", "sell"] | None = None


HistoricalBar = OHLCVBar
OrderBookSnapshot = ExternalOrderBookSnapshot
Trade = ExternalTrade


class ExternalContext(BaseModel):
    symbol: str
    provider: str | None = None
    open_price: float | None = None
    current_price: float | None = None
    return_since_open: float | None = None
    time_to_close_seconds: float | None = None


class RawPolymarketEvent(BaseModel):
    event_type: str
    asset_id: str
    market: str
    timestamp: datetime
    sequence: str | None = None
    payload: dict[str, Any]


class PolymarketMarketMetadata(BaseModel):
    market_id: str
    condition_id: str
    slug: str | None = None
    question: str | None = None
    category: str | None = None
    active: bool = False
    closed: bool = False
    accepting_orders: bool = False
    enable_order_book: bool = False
    start_date: datetime | None = None
    end_date: datetime | None = None
    resolution_source: str | None = None
    description: str | None = None
    outcomes: list[str] = Field(default_factory=list)
    outcome_prices: list[float] = Field(default_factory=list)
    token_ids: list[str] = Field(default_factory=list)
    best_bid: float | None = None
    best_ask: float | None = None
    last_trade_price: float | None = None
    raw_tags: list[str] = Field(default_factory=list)


class PolymarketTrade(BaseModel):
    market_id: str
    asset_id: str
    ts: datetime
    sequence: str | None = None
    price: float
    size: float
    side: Literal["buy", "sell"]
    fee_rate_bps: float | None = None


class PolymarketTopOfBook(BaseModel):
    market_id: str
    asset_id: str
    ts: datetime
    sequence: str | None = None
    best_bid: float
    best_ask: float
    spread: float | None = None


class PolymarketOrderBookUpdate(BaseModel):
    market_id: str
    asset_id: str
    ts: datetime
    sequence: str | None = None
    best_bid: float | None = None
    best_ask: float | None = None
    bids: list[list[float]] = Field(default_factory=list)
    asks: list[list[float]] = Field(default_factory=list)


class FeatureSnapshot(BaseModel):
    market_id: UUID
    ts: datetime
    polymarket_cvd: float
    polymarket_rolling_cvd: dict[str, float] = Field(default_factory=dict)
    external_cvd: float
    external_rolling_cvd: dict[str, float] = Field(default_factory=dict)
    polymarket_trade_imbalance: float
    external_trade_imbalance: float
    best_bid: float | None = None
    best_ask: float | None = None
    spread: float | None = None
    top_of_book_imbalance: float | None = None
    fair_value_estimate: float | None = None
    fair_value_gap: float | None = None
    distance_to_threshold: float | None = None
    time_to_close_seconds: float | None = None
    external_return_since_open: float | None = None
    lead_lag_gap: float | None = None
    venue_divergence: float | None = None

    @property
    def hyperliquid_cvd(self) -> float:
        return self.external_cvd

    @property
    def hyperliquid_rolling_cvd(self) -> dict[str, float]:
        return self.external_rolling_cvd

    @property
    def hyperliquid_trade_imbalance(self) -> float:
        return self.external_trade_imbalance


class MarketDetail(MarketSummary):
    rules: list[MarketRule] = Field(default_factory=list)
    latest_polymarket_orderbook: OrderBookSnapshot | None = None
    latest_external_orderbook: OrderBookSnapshot | None = None
    recent_polymarket_trades: list[Trade] = Field(default_factory=list)
    recent_external_trades: list[Trade] = Field(default_factory=list)
    external_context: ExternalContext | None = None

    @property
    def latest_orderbook(self) -> OrderBookSnapshot | None:
        return self.latest_polymarket_orderbook

    @property
    def latest_hyperliquid_orderbook(self) -> OrderBookSnapshot | None:
        return self.latest_external_orderbook

    @property
    def recent_hyperliquid_trades(self) -> list[Trade]:
        return self.recent_external_trades


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


class StrategyDecision(BaseModel):
    signal_value: float
    decision: Literal["buy_yes", "buy_no", "passive_yes", "passive_no", "hold", "no_trade"]
    confidence: float
    reason: str
    reasoning_fields: dict[str, float | str | None] = Field(default_factory=dict)


class BacktestMetric(BaseModel):
    label: str
    value: float


class BacktestReport(BaseModel):
    run_id: str
    strategy_name: str
    market_id: UUID
    metrics: list[BacktestMetric]
    created_at: datetime | None = None
    trade_count: int = 0
    decisions: list[StrategyDecision] = Field(default_factory=list)
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


class PaperTradingStatus(BaseModel):
    strategy_name: str
    dry_run_only: bool
    active_market_ids: list[UUID]
    open_positions: dict[str, float] = Field(default_factory=dict)
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0


class RiskSettings(BaseModel):
    live_execution_enabled: bool
    dry_run_only: bool
    max_market_exposure_usd: float
    global_kill_switch: bool
