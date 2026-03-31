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
    async def discover_active_markets(self) -> tuple[list[dict[str, Any]], list[PolymarketMarketMetadata]]:
        raise NotImplementedError

    @abstractmethod
    async def stream_market_events(
        self,
        asset_ids: list[str],
        on_event: Callable[[RawPolymarketEvent], None],
    ) -> None:
        raise NotImplementedError
