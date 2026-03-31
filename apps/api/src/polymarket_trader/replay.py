from __future__ import annotations

from packages.core_types.schemas import ReplayEvent, ReplayResponse
from packages.utils.time import parse_dt
from services.state import InMemoryState


class ReplayService:
    def __init__(self, state: InMemoryState) -> None:
        self._state = state

    def get_replay(self, market_id: str) -> ReplayResponse:
        market = self._state.markets.get(market_id)
        if market is None:
            raise KeyError(f"Unknown market_id={market_id}")
        events: list[ReplayEvent] = []
        for snapshot in self._state.polymarket_orderbooks.get(market_id, []):
            events.append(
                ReplayEvent(
                    ts=snapshot.ts,
                    venue="polymarket",
                    event_type="orderbook",
                    payload=snapshot.model_dump(mode="json"),
                )
            )
        for trade in self._state.polymarket_trades.get(market_id, []):
            events.append(
                ReplayEvent(
                    ts=trade.ts,
                    venue="polymarket",
                    event_type="trade",
                    payload=trade.model_dump(mode="json"),
                )
            )
        for snapshot in self._state.external_orderbooks.get(market_id, []):
            events.append(
                ReplayEvent(
                    ts=snapshot.ts,
                    venue=snapshot.venue,
                    event_type="orderbook",
                    payload=snapshot.model_dump(mode="json"),
                )
            )
        for trade in self._state.external_trades.get(market_id, []):
            events.append(
                ReplayEvent(
                    ts=trade.ts,
                    venue=trade.venue,
                    event_type="trade",
                    payload=trade.model_dump(mode="json"),
                )
            )
        for raw_event in self._state.polymarket_raw_events.get(market_id, []):
            events.append(
                ReplayEvent(
                    ts=market.opens_at if "ts" not in raw_event else parse_dt(raw_event["ts"]),
                    venue="polymarket",
                    event_type="raw",
                    payload=raw_event,
                )
            )
        events.sort(key=lambda event: event.ts)
        return ReplayResponse(market_id=market.id, market_slug=market.slug, events=events)
