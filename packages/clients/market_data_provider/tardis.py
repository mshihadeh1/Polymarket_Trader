from __future__ import annotations

from datetime import datetime

from packages.clients.market_data_provider.base import HistoricalMarketDataProvider
from packages.core_types import OHLCVBar, ExternalOrderBookSnapshot, ExternalTrade, ProviderCapabilities, SymbolMapping


class TardisHistoricalProvider(HistoricalMarketDataProvider):
    @property
    def provider_name(self) -> str:
        return "tardis"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(has_ohlcv=False, has_trades=True, has_l2=True, has_snapshots=True)

    def map_symbol(self, internal_symbol: str) -> SymbolMapping:
        return SymbolMapping(internal_symbol=internal_symbol, provider_symbol=internal_symbol, provider_name=self.provider_name)

    def get_ohlcv(self, internal_symbol: str, start: datetime, end: datetime, interval: str) -> tuple[list[dict[str, object]], list[OHLCVBar]]:
        raise NotImplementedError("TODO: implement Tardis historical bar synthesis")

    def get_trades(self, internal_symbol: str, start: datetime, end: datetime) -> tuple[list[dict[str, object]], list[ExternalTrade]]:
        raise NotImplementedError("TODO: implement Tardis historical trade loader")

    def get_orderbook_snapshots(self, internal_symbol: str, start: datetime, end: datetime) -> tuple[list[dict[str, object]], list[ExternalOrderBookSnapshot]]:
        raise NotImplementedError("TODO: implement Tardis L2 snapshot loader")
