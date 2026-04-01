from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from packages.core_types.schemas import PolymarketMarketMetadata, RawPolymarketEvent


class PolymarketClient(ABC):
    @property
    @abstractmethod
    def client_name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def is_mock(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def discover_markets(
        self,
        *,
        closed: bool | None = None,
        active: bool | None = None,
        limit: int | None = None,
    ) -> tuple[list[dict[str, Any]], list[PolymarketMarketMetadata]]:
        raise NotImplementedError

    @abstractmethod
    async def discover_active_markets(self) -> tuple[list[dict[str, Any]], list[PolymarketMarketMetadata]]:
        raise NotImplementedError

    async def fetch_market_by_identifier(self, identifier: str) -> tuple[dict[str, Any], PolymarketMarketMetadata] | None:
        markets = await self.discover_markets(limit=500)
        raw_markets, normalized_markets = markets
        normalized_identifier = identifier.lower()
        for raw_market, metadata in zip(raw_markets, normalized_markets, strict=False):
            if metadata.market_id.lower() == normalized_identifier:
                return raw_market, metadata
            if (metadata.slug or "").lower() == normalized_identifier:
                return raw_market, metadata
        return None

    @abstractmethod
    async def stream_market_events(
        self,
        asset_ids: list[str],
        on_event: Callable[[RawPolymarketEvent], None],
    ) -> None:
        raise NotImplementedError
