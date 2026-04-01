from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from packages.core_types import OHLCVBar, ExternalOrderBookSnapshot, ExternalTrade
from packages.utils.time import parse_dt


class MockHyperliquidClient:
    def __init__(self, seed_path: Path) -> None:
        self._seed_path = seed_path

    def fetch_seed(self) -> dict[str, Any]:
        return json.loads(self._seed_path.read_text(encoding="utf-8"))

    def ws_stream_supported(self) -> bool:
        return False

    @property
    def client_name(self) -> str:
        return "mock_hyperliquid_recent"

    def fetch_recent_trades(
        self,
        coin: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> tuple[list[dict[str, Any]], list[ExternalTrade], list[str]]:
        payload = self.fetch_seed().get(coin.upper(), {})
        raw_rows = payload.get("trades", [])
        trades = [
            ExternalTrade(
                ts=parse_dt(row["ts"]),
                venue="hyperliquid",
                sequence=row.get("sequence"),
                symbol=coin.upper(),
                price=float(row["price"]),
                size=float(row["size"]),
                side=row["side"],
                aggressor_side=row.get("aggressor_side"),
            )
            for row in raw_rows
            if (start is None or parse_dt(row["ts"]) >= start)
            and (end is None or parse_dt(row["ts"]) <= end)
        ]
        return raw_rows, trades, ([] if trades else ["No mock Hyperliquid trades available in range"])

    def fetch_recent_candles(
        self,
        coin: str,
        start: datetime,
        end: datetime,
        interval: str = "1m",
    ) -> tuple[list[dict[str, Any]], list[OHLCVBar], list[str]]:
        payload = self.fetch_seed().get(coin.upper(), {})
        raw_rows = payload.get("bars", [])
        bars = [
            OHLCVBar(
                ts=parse_dt(row["ts"]),
                symbol=coin.upper(),
                provider="hyperliquid",
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
        return raw_rows, bars, ([] if bars else ["No mock Hyperliquid candles available in range"])

    def fetch_l2_book(self, coin: str) -> tuple[dict[str, Any] | list[Any], ExternalOrderBookSnapshot | None, list[str]]:
        payload = self.fetch_seed().get(coin.upper(), {})
        raw_rows = payload.get("orderbook_snapshots", [])
        if not raw_rows:
            return {}, None, ["No mock Hyperliquid book available"]
        row = raw_rows[-1]
        snapshot = ExternalOrderBookSnapshot(
            ts=parse_dt(row["ts"]),
            venue="hyperliquid",
            sequence=row.get("sequence"),
            symbol=coin.upper(),
            best_bid=float(row["best_bid"]),
            best_ask=float(row["best_ask"]),
            bid_size=float(row["bid_size"]),
            ask_size=float(row["ask_size"]),
            mid_price=float(row.get("mid_price", 0.0)),
            depth=row.get("depth", {}),
        )
        return row, snapshot, []
