from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from packages.clients.market_data_provider.base import HistoricalMarketDataProvider
from packages.core_types import OHLCVBar, ExternalOrderBookSnapshot, ExternalTrade, ProviderCapabilities, SymbolMapping
from packages.utils.time import parse_dt


class BinanceHistoricalProvider(HistoricalMarketDataProvider):
    def __init__(
        self,
        base_url: str,
        symbol_map: dict[str, str],
        use_mock: bool = True,
        seed_path: Path | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._symbol_map = symbol_map
        self._use_mock = use_mock
        self._seed_path = seed_path
        self._client = client or httpx.Client(timeout=20.0)

    @property
    def provider_name(self) -> str:
        return "binance"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            has_ohlcv=True,
            has_trades=True,
            has_l2=False,
            has_snapshots=self._use_mock,
        )

    def map_symbol(self, internal_symbol: str) -> SymbolMapping:
        provider_symbol = self._symbol_map.get(internal_symbol.upper(), f"{internal_symbol.upper()}USDT")
        return SymbolMapping(
            internal_symbol=internal_symbol.upper(),
            provider_symbol=provider_symbol,
            provider_name=self.provider_name,
        )

    def get_ohlcv(
        self,
        internal_symbol: str,
        start: datetime,
        end: datetime,
        interval: str,
    ) -> tuple[list[dict[str, Any]], list[OHLCVBar]]:
        raw_rows = self._load_mock_symbol(internal_symbol).get("bars", []) if self._use_mock else self._fetch_klines(internal_symbol, start, end, interval)
        bars = [
            OHLCVBar(
                ts=parse_dt(row["ts"]),
                symbol=internal_symbol.upper(),
                provider=self.provider_name,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
                interval=interval,
            )
            for row in raw_rows
            if start <= parse_dt(row["ts"]) <= end
        ]
        return raw_rows, bars

    def get_trades(
        self,
        internal_symbol: str,
        start: datetime,
        end: datetime,
    ) -> tuple[list[dict[str, Any]], list[ExternalTrade]]:
        raw_rows = self._load_mock_symbol(internal_symbol).get("trades", []) if self._use_mock else self._fetch_agg_trades(internal_symbol, start, end)
        trades = [
            ExternalTrade(
                ts=parse_dt(row["ts"]),
                venue=self.provider_name,
                sequence=row.get("sequence"),
                symbol=internal_symbol.upper(),
                price=float(row["price"]),
                size=float(row["size"]),
                side=row["side"],
                aggressor_side=row.get("aggressor_side"),
            )
            for row in raw_rows
            if start <= parse_dt(row["ts"]) <= end
        ]
        return raw_rows, trades

    def get_orderbook_snapshots(
        self,
        internal_symbol: str,
        start: datetime,
        end: datetime,
    ) -> tuple[list[dict[str, Any]], list[ExternalOrderBookSnapshot]]:
        raw_rows = self._load_mock_symbol(internal_symbol).get("orderbook_snapshots", []) if self._use_mock else []
        snapshots = [
            ExternalOrderBookSnapshot(
                ts=parse_dt(row["ts"]),
                venue=self.provider_name,
                sequence=row.get("sequence"),
                symbol=internal_symbol.upper(),
                best_bid=float(row["best_bid"]),
                best_ask=float(row["best_ask"]),
                bid_size=float(row["bid_size"]),
                ask_size=float(row["ask_size"]),
                mid_price=float(row["mid_price"]),
                depth=row.get("depth", {}),
            )
            for row in raw_rows
            if start <= parse_dt(row["ts"]) <= end
        ]
        return raw_rows, snapshots

    def _load_mock_symbol(self, internal_symbol: str) -> dict[str, Any]:
        if self._seed_path is None:
            raise RuntimeError("Mock Binance provider requires a seed path")
        payload = json.loads(self._seed_path.read_text(encoding="utf-8"))
        return payload[internal_symbol.upper()]

    def _fetch_klines(self, internal_symbol: str, start: datetime, end: datetime, interval: str) -> list[dict[str, Any]]:
        mapping = self.map_symbol(internal_symbol)
        response = self._client.get(
            f"{self._base_url}/api/v3/klines",
            params={
                "symbol": mapping.provider_symbol,
                "interval": interval,
                "startTime": int(start.timestamp() * 1000),
                "endTime": int(end.timestamp() * 1000),
                "limit": 1000,
            },
        )
        response.raise_for_status()
        return [
            {
                "ts": datetime.utcfromtimestamp(row[0] / 1000).isoformat() + "Z",
                "open": row[1],
                "high": row[2],
                "low": row[3],
                "close": row[4],
                "volume": row[5],
            }
            for row in response.json()
        ]

    def _fetch_agg_trades(self, internal_symbol: str, start: datetime, end: datetime) -> list[dict[str, Any]]:
        mapping = self.map_symbol(internal_symbol)
        response = self._client.get(
            f"{self._base_url}/api/v3/aggTrades",
            params={
                "symbol": mapping.provider_symbol,
                "startTime": int(start.timestamp() * 1000),
                "endTime": int(end.timestamp() * 1000),
                "limit": 1000,
            },
        )
        response.raise_for_status()
        return [
            {
                "ts": datetime.utcfromtimestamp(row["T"] / 1000).isoformat() + "Z",
                "sequence": row["a"],
                "price": row["p"],
                "size": row["q"],
                "side": "sell" if row["m"] else "buy",
                "aggressor_side": "sell" if row["m"] else "buy",
            }
            for row in response.json()
        ]
