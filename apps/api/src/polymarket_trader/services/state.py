from __future__ import annotations

from dataclasses import dataclass, field

from polymarket_trader.domain.schemas import (
    MarketDetailSchema,
    MarketSchema,
    OrderBookSnapshotSchema,
    TradeSchema,
)


@dataclass
class InMemoryState:
    markets: dict[str, MarketSchema] = field(default_factory=dict)
    market_details: dict[str, MarketDetailSchema] = field(default_factory=dict)
    orderbooks: dict[str, list[OrderBookSnapshotSchema]] = field(default_factory=dict)
    trades: dict[str, list[TradeSchema]] = field(default_factory=dict)
