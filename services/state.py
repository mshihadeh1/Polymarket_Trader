from __future__ import annotations

from dataclasses import dataclass, field

from packages.core_types.schemas import FeatureSnapshot, MarketDetail, MarketSummary, OrderBookSnapshot, Trade


@dataclass
class InMemoryState:
    markets: dict[str, MarketSummary] = field(default_factory=dict)
    market_details: dict[str, MarketDetail] = field(default_factory=dict)
    polymarket_orderbooks: dict[str, list[OrderBookSnapshot]] = field(default_factory=dict)
    polymarket_trades: dict[str, list[Trade]] = field(default_factory=dict)
    polymarket_raw_events: dict[str, list[dict]] = field(default_factory=dict)
    hyperliquid_orderbooks: dict[str, list[OrderBookSnapshot]] = field(default_factory=dict)
    hyperliquid_trades: dict[str, list[Trade]] = field(default_factory=dict)
    hyperliquid_raw_events: dict[str, list[dict]] = field(default_factory=dict)
    feature_snapshots: dict[str, list[FeatureSnapshot]] = field(default_factory=dict)
