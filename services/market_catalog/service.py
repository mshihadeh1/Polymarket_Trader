from __future__ import annotations

from packages.core_types.schemas import MarketDetail, MarketSummary
from services.state import InMemoryState


class MarketCatalogService:
    def __init__(self, state: InMemoryState) -> None:
        self._state = state

    def list_markets(
        self,
        market_type: str | None = None,
        category: str | None = None,
        short_horizon_only: bool = False,
    ) -> list[MarketSummary]:
        allowed_types = {"crypto_5m", "crypto_15m"} if short_horizon_only else None
        markets = self._state.markets.values()
        filtered = [
            market
            for market in markets
            if (market_type is None or market.market_type == market_type)
            and (category is None or market.category == category)
            and (allowed_types is None or market.market_type in allowed_types)
        ]
        return sorted(filtered, key=lambda market: market.closes_at or market.opens_at)

    def get_market(self, market_id: str) -> MarketDetail:
        market = self._state.market_details.get(market_id)
        if market is None:
            raise KeyError(f"Unknown market_id={market_id}")
        return market
