from __future__ import annotations

from polymarket_trader.domain.schemas import OrderBookSnapshotSchema, TradeSchema
from polymarket_trader.services.state import InMemoryState


class HistoricalStoreService:
    def __init__(self, state: InMemoryState) -> None:
        self._state = state

    def get_orderbook(self, market_id: str) -> list[OrderBookSnapshotSchema]:
        return self._state.orderbooks.get(market_id, [])

    def get_trades(self, market_id: str) -> list[TradeSchema]:
        return self._state.trades.get(market_id, [])
