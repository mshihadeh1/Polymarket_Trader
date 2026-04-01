from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from packages.clients.polymarket_client.base import PolymarketClient
from packages.core_types.schemas import PolymarketMarketMetadata, RawPolymarketEvent
from packages.utils.time import parse_dt


class MockPolymarketClient(PolymarketClient):
    def __init__(self, seed_path: Path) -> None:
        self._seed_path = seed_path

    @property
    def client_name(self) -> str:
        return "mock_polymarket"

    @property
    def is_mock(self) -> bool:
        return True

    def fetch_seed(self) -> dict[str, Any]:
        return json.loads(self._seed_path.read_text(encoding="utf-8"))

    def ws_stream_supported(self) -> bool:
        return False

    async def discover_markets(
        self,
        *,
        closed: bool | None = None,
        active: bool | None = None,
        limit: int | None = None,
    ) -> tuple[list[dict[str, Any]], list[PolymarketMarketMetadata]]:
        payload = self.fetch_seed()
        markets = payload.get("markets", [])
        filtered = [
            item
            for item in markets
            if (closed is None or (item.get("status") == "closed") == closed)
            and (active is None or (item.get("status") == "active") == active)
        ]
        if limit is not None:
            filtered = filtered[:limit]
        normalized = [
            PolymarketMarketMetadata(
                market_id=item["id"],
                condition_id=str(item.get("condition_id", item.get("event_id", ""))),
                slug=item.get("slug"),
                question=item.get("title"),
                category=item.get("category"),
                active=item.get("status") == "active",
                closed=item.get("status") == "closed",
                accepting_orders=item.get("status") == "active",
                enable_order_book=True,
                start_date=parse_dt(item.get("opens_at")),
                end_date=parse_dt(item.get("closes_at")),
                resolution_source=item.get("resolution_source"),
                description=item.get("rules_text"),
                outcomes=[token["outcome"] for token in item.get("tokens", [])],
                outcome_prices=[],
                token_ids=[token["token_id"] for token in item.get("tokens", [])],
                best_bid=item.get("orderbook", [{}])[-1].get("best_bid") if item.get("orderbook") else None,
                best_ask=item.get("orderbook", [{}])[-1].get("best_ask") if item.get("orderbook") else None,
                last_trade_price=item.get("trades", [{}])[-1].get("price") if item.get("trades") else None,
                raw_tags=item.get("tags", []),
            )
            for item in filtered
        ]
        return filtered, normalized

    async def discover_active_markets(self) -> tuple[list[dict[str, Any]], list[PolymarketMarketMetadata]]:
        return await self.discover_markets(active=True)

    async def stream_market_events(
        self,
        asset_ids: list[str],
        on_event: Callable[[RawPolymarketEvent], None],
    ) -> None:
        return None
