from __future__ import annotations

from packages.clients.hyperliquid_client import MockHyperliquidClient
from packages.core_types.schemas import OrderBookSnapshot, Trade
from packages.utils.time import parse_dt
from services.state import InMemoryState


class HyperliquidIngestorService:
    def __init__(self, state: InMemoryState, client: MockHyperliquidClient) -> None:
        self._state = state
        self._client = client

    def bootstrap(self) -> int:
        payload = self._client.fetch_seed()
        count = 0
        for item in payload.get("markets", []):
            market_id = item["market_id"]
            orderbooks = [
                OrderBookSnapshot(
                    ts=parse_dt(snapshot["ts"]),
                    venue="hyperliquid",
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
                    venue="hyperliquid",
                    sequence=trade.get("sequence"),
                    price=trade["price"],
                    size=trade["size"],
                    side=trade["side"],
                    aggressor_side=trade.get("aggressor_side"),
                )
                for trade in item.get("trades", [])
            ]
            self._state.hyperliquid_orderbooks[market_id] = orderbooks
            self._state.hyperliquid_trades[market_id] = trades
            self._state.hyperliquid_raw_events[market_id] = item.get("raw_events", [])
            market = self._state.market_details.get(market_id)
            if market is not None:
                market.latest_hyperliquid_orderbook = orderbooks[-1] if orderbooks else None
                market.recent_hyperliquid_trades = trades[-20:]
            count += 1
        return count
