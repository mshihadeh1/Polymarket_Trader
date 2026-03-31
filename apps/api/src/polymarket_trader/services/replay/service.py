from __future__ import annotations

from polymarket_trader.domain.schemas import ReplayEventSchema, ReplayResponseSchema
from polymarket_trader.services.state import InMemoryState


class ReplayService:
    def __init__(self, state: InMemoryState) -> None:
        self._state = state

    def get_replay(self, market_id: str) -> ReplayResponseSchema:
        market = self._state.markets.get(market_id)
        if market is None:
            raise KeyError(f"Unknown market_id={market_id}")
        events: list[ReplayEventSchema] = []
        for snapshot in self._state.orderbooks.get(market_id, []):
            events.append(
                ReplayEventSchema(
                    ts=snapshot.ts,
                    event_type="orderbook",
                    payload=snapshot.model_dump(mode="json"),
                )
            )
        for trade in self._state.trades.get(market_id, []):
            events.append(
                ReplayEventSchema(
                    ts=trade.ts,
                    event_type="trade",
                    payload=trade.model_dump(mode="json"),
                )
            )
        events.sort(key=lambda event: event.ts)
        return ReplayResponseSchema(
            market_id=market.id,
            market_slug=market.slug,
            events=events,
        )
