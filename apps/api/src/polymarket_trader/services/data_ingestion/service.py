from __future__ import annotations

from datetime import datetime
from uuid import UUID

from polymarket_trader.domain.schemas import (
    MarketDetailSchema,
    MarketSchema,
    OrderBookSnapshotSchema,
    TokenSchema,
    TradeSchema,
)
from polymarket_trader.services.state import InMemoryState


class DataIngestionService:
    def __init__(self, state: InMemoryState) -> None:
        self._state = state

    def bootstrap_from_payload(self, payload: dict) -> int:
        market_count = 0
        for item in payload.get("markets", []):
            market = MarketSchema(
                id=UUID(item["id"]),
                slug=item["slug"],
                title=item["title"],
                category=item["category"],
                market_type=item["market_type"],
                resolution_source=item.get("resolution_source"),
                rules_text=item.get("rules_text"),
                status=item["status"],
                opens_at=_parse_dt(item.get("opens_at")),
                closes_at=_parse_dt(item.get("closes_at")),
                resolves_at=_parse_dt(item.get("resolves_at")),
                tags=item.get("tags", []),
                tokens=[
                    TokenSchema(
                        id=UUID(token["id"]),
                        token_id=token["token_id"],
                        outcome=token["outcome"],
                    )
                    for token in item.get("tokens", [])
                ],
            )
            orderbooks = [
                OrderBookSnapshotSchema(
                    ts=_parse_dt(snapshot["ts"]),
                    best_bid=snapshot["best_bid"],
                    best_ask=snapshot["best_ask"],
                    bid_size=snapshot["bid_size"],
                    ask_size=snapshot["ask_size"],
                    depth=snapshot.get("depth", {}),
                )
                for snapshot in item.get("orderbook", [])
            ]
            trades = [
                TradeSchema(
                    ts=_parse_dt(trade["ts"]),
                    price=trade["price"],
                    size=trade["size"],
                    side=trade["side"],
                    aggressor_side=trade.get("aggressor_side"),
                )
                for trade in item.get("trades", [])
            ]
            detail = MarketDetailSchema(
                **market.model_dump(),
                latest_orderbook=orderbooks[-1] if orderbooks else None,
                recent_trades=trades[-10:],
            )
            market_key = str(market.id)
            self._state.markets[market_key] = market
            self._state.market_details[market_key] = detail
            self._state.orderbooks[market_key] = orderbooks
            self._state.trades[market_key] = trades
            market_count += 1
        return market_count


def _parse_dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
