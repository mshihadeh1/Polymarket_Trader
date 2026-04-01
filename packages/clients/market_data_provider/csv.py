from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any

from packages.clients.market_data_provider.base import HistoricalMarketDataProvider
from packages.core_types import OHLCVBar, ExternalOrderBookSnapshot, ExternalTrade, ProviderCapabilities, SymbolMapping
from packages.utils.time import parse_dt


class CsvHistoricalProvider(HistoricalMarketDataProvider):
    def __init__(self, path_map: dict[str, str], symbol_map: dict[str, str], root: Path) -> None:
        self._path_map = {key.upper(): value for key, value in path_map.items()}
        self._symbol_map = {key.upper(): value for key, value in symbol_map.items()}
        self._root = root

    @property
    def provider_name(self) -> str:
        return "csv"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(has_ohlcv=True, has_trades=False, has_l2=False, has_snapshots=False)

    def map_symbol(self, internal_symbol: str) -> SymbolMapping:
        normalized = internal_symbol.upper()
        return SymbolMapping(
            internal_symbol=normalized,
            provider_symbol=self._symbol_map.get(normalized, normalized),
            provider_name=self.provider_name,
        )

    def get_ohlcv(
        self,
        internal_symbol: str,
        start: datetime,
        end: datetime,
        interval: str,
    ) -> tuple[list[dict[str, Any]], list[OHLCVBar]]:
        if interval != "1m":
            raise ValueError("CsvHistoricalProvider currently supports only 1m bars")
        rows = self._read_symbol_rows(internal_symbol)
        filtered_rows = [row for row in rows if start <= _parse_timestamp(row) <= end]
        bars = [
            OHLCVBar(
                ts=_parse_timestamp(row),
                symbol=internal_symbol.upper(),
                provider=self.provider_name,
                open=_coerce_float(row, "open"),
                high=_coerce_float(row, "high"),
                low=_coerce_float(row, "low"),
                close=_coerce_float(row, "close"),
                volume=_coerce_float(row, "volume", default=0.0),
                interval=interval,
            )
            for row in filtered_rows
        ]
        return filtered_rows, bars

    def get_trades(
        self,
        internal_symbol: str,
        start: datetime,
        end: datetime,
    ) -> tuple[list[dict[str, Any]], list[ExternalTrade]]:
        return [], []

    def get_orderbook_snapshots(
        self,
        internal_symbol: str,
        start: datetime,
        end: datetime,
    ) -> tuple[list[dict[str, Any]], list[ExternalOrderBookSnapshot]]:
        return [], []

    def _read_symbol_rows(self, internal_symbol: str) -> list[dict[str, Any]]:
        normalized = internal_symbol.upper()
        path_value = self._path_map.get(normalized)
        if path_value is None:
            raise KeyError(f"No CSV dataset configured for symbol={normalized}")
        path = Path(path_value)
        if not path.is_absolute():
            path = self._root / path
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            return [dict(row) for row in reader]


def _parse_timestamp(row: dict[str, Any]) -> datetime:
    for key in ("ts", "timestamp", "datetime", "date"):
        value = row.get(key)
        if value:
            return parse_dt(str(value))
    raise ValueError("CSV row is missing a timestamp column")


def _coerce_float(row: dict[str, Any], key: str, default: float | None = None) -> float:
    value = row.get(key)
    if value in (None, ""):
        if default is not None:
            return default
        raise ValueError(f"CSV row is missing required column {key}")
    return float(value)
