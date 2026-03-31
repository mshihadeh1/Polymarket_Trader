from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from packages.core_types import OHLCVBar, ExternalOrderBookSnapshot, ExternalTrade, ProviderCapabilities, SymbolMapping


class HistoricalMarketDataProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        raise NotImplementedError

    @abstractmethod
    def map_symbol(self, internal_symbol: str) -> SymbolMapping:
        raise NotImplementedError

    @abstractmethod
    def get_ohlcv(
        self,
        internal_symbol: str,
        start: datetime,
        end: datetime,
        interval: str,
    ) -> tuple[list[dict[str, Any]], list[OHLCVBar]]:
        raise NotImplementedError

    @abstractmethod
    def get_trades(
        self,
        internal_symbol: str,
        start: datetime,
        end: datetime,
    ) -> tuple[list[dict[str, Any]], list[ExternalTrade]]:
        raise NotImplementedError

    @abstractmethod
    def get_orderbook_snapshots(
        self,
        internal_symbol: str,
        start: datetime,
        end: datetime,
    ) -> tuple[list[dict[str, Any]], list[ExternalOrderBookSnapshot]]:
        raise NotImplementedError

    def fetch_bars(
        self,
        internal_symbol: str,
        start: datetime,
        end: datetime,
        interval: str,
    ) -> tuple[list[dict[str, Any]], list[OHLCVBar]]:
        return self.get_ohlcv(internal_symbol, start, end, interval)

    def fetch_trades(
        self,
        internal_symbol: str,
        start: datetime,
        end: datetime,
    ) -> tuple[list[dict[str, Any]], list[ExternalTrade]]:
        return self.get_trades(internal_symbol, start, end)

    def fetch_orderbook_snapshots(
        self,
        internal_symbol: str,
        start: datetime,
        end: datetime,
    ) -> tuple[list[dict[str, Any]], list[ExternalOrderBookSnapshot]]:
        return self.get_orderbook_snapshots(internal_symbol, start, end)
