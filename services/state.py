from __future__ import annotations

from dataclasses import dataclass, field

from packages.core_types.schemas import (
    BacktestReport,
    FeatureSnapshot,
    HistoricalBar,
    MarketDetail,
    MarketSummary,
    OrderBookSnapshot,
    PaperTradeDecision,
    Trade,
)


@dataclass
class InMemoryState:
    markets: dict[str, MarketSummary] = field(default_factory=dict)
    market_details: dict[str, MarketDetail] = field(default_factory=dict)
    polymarket_orderbooks: dict[str, list[OrderBookSnapshot]] = field(default_factory=dict)
    polymarket_trades: dict[str, list[Trade]] = field(default_factory=dict)
    polymarket_raw_events: dict[str, list[dict]] = field(default_factory=dict)
    external_orderbooks: dict[str, list[OrderBookSnapshot]] = field(default_factory=dict)
    external_trades: dict[str, list[Trade]] = field(default_factory=dict)
    external_bars: dict[str, list[HistoricalBar]] = field(default_factory=dict)
    external_raw_payloads: dict[str, dict[str, list[dict]]] = field(default_factory=dict)
    feature_snapshots: dict[str, list[FeatureSnapshot]] = field(default_factory=dict)
    backtest_reports: list[BacktestReport] = field(default_factory=list)
    paper_decisions: list[PaperTradeDecision] = field(default_factory=list)
