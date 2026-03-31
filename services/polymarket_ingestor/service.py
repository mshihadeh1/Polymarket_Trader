from __future__ import annotations

from uuid import UUID

from packages.clients.polymarket_client import MockPolymarketClient
from packages.core_types.schemas import (
    ExternalContext,
    MarketDetail,
    MarketRule,
    MarketSummary,
    MarketToken,
    OrderBookSnapshot,
    Trade,
)
from packages.utils.time import parse_dt
from services.state import InMemoryState


class PolymarketIngestorService:
    def __init__(self, state: InMemoryState, client: MockPolymarketClient) -> None:
        self._state = state
        self._client = client

    def bootstrap(self) -> int:
        payload = self._client.fetch_seed()
        count = 0
        for item in payload.get("markets", []):
            summary = MarketSummary(
                id=UUID(item["id"]),
                event_id=UUID(item["event_id"]),
                slug=item["slug"],
                title=item["title"],
                category=item["category"],
                market_type=item["market_type"],
                underlying=item.get("underlying"),
                status=item["status"],
                opens_at=parse_dt(item.get("opens_at")),
                closes_at=parse_dt(item.get("closes_at")),
                resolves_at=parse_dt(item.get("resolves_at")),
                price_to_beat=item.get("price_to_beat"),
                open_reference_price=item.get("open_reference_price"),
                tags=item.get("tags", []),
                tokens=[
                    MarketToken(
                        id=UUID(token["id"]),
                        token_id=token["token_id"],
                        outcome=token["outcome"],
                    )
                    for token in item.get("tokens", [])
                ],
            )
            market_id = str(summary.id)
            orderbooks = [
                OrderBookSnapshot(
                    ts=parse_dt(snapshot["ts"]),
                    venue="polymarket",
                    sequence=snapshot.get("sequence"),
                    best_bid=snapshot["best_bid"],
                    best_ask=snapshot["best_ask"],
                    bid_size=snapshot["bid_size"],
                    ask_size=snapshot["ask_size"],
                    mid_price=snapshot.get("mid_price"),
                    depth=snapshot.get("depth", {}),
                )
                for snapshot in item.get("orderbook", [])
            ]
            trades = [
                Trade(
                    ts=parse_dt(trade["ts"]),
                    venue="polymarket",
                    sequence=trade.get("sequence"),
                    price=trade["price"],
                    size=trade["size"],
                    side=trade["side"],
                    aggressor_side=trade.get("aggressor_side"),
                )
                for trade in item.get("trades", [])
            ]
            raw_events = item.get("raw_events", [])
            detail = MarketDetail(
                **summary.model_dump(),
                rules=[
                    MarketRule(
                        rule_type="resolution",
                        source=item.get("resolution_source"),
                        text=item.get("rules_text", ""),
                        normalized={
                            "source": item.get("resolution_source"),
                            "contains_threshold": item.get("price_to_beat") is not None,
                        },
                    )
                ],
                latest_polymarket_orderbook=orderbooks[-1] if orderbooks else None,
                recent_polymarket_trades=trades[-20:],
                external_context=ExternalContext(symbol=summary.underlying or "UNKNOWN"),
            )
            self._state.markets[market_id] = summary
            self._state.market_details[market_id] = detail
            self._state.polymarket_orderbooks[market_id] = orderbooks
            self._state.polymarket_trades[market_id] = trades
            self._state.polymarket_raw_events[market_id] = raw_events
            count += 1
        return count
