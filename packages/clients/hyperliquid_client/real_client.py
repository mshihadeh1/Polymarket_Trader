from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from packages.core_types import OHLCVBar, ExternalOrderBookSnapshot, ExternalTrade


class RealHyperliquidClient:
    def __init__(
        self,
        info_url: str,
        trade_limit: int = 500,
        client: httpx.Client | None = None,
    ) -> None:
        self._info_url = info_url
        self._trade_limit = trade_limit
        self._client = client or httpx.Client(timeout=20.0)

    @property
    def client_name(self) -> str:
        return "real_hyperliquid_recent"

    def fetch_recent_trades(
        self,
        coin: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> tuple[list[dict[str, Any]], list[ExternalTrade], list[str]]:
        response = self._client.post(self._info_url, json={"type": "recentTrades", "coin": coin.upper()})
        response.raise_for_status()
        raw_rows = response.json()
        if not isinstance(raw_rows, list):
            return [], [], ["Hyperliquid recentTrades response was not a list"]
        notes: list[str] = []
        trades = []
        for row in raw_rows[: self._trade_limit]:
            ts = _parse_ms(row.get("time") or row.get("timestamp"))
            if ts is None:
                continue
            if start and ts < start:
                continue
            if end and ts > end:
                continue
            side_value = str(row.get("side") or row.get("dir") or "").lower()
            side = "buy" if "buy" in side_value or side_value == "b" else "sell"
            price = _as_float(row.get("px") or row.get("price"))
            size = _as_float(row.get("sz") or row.get("size"))
            if price is None or size is None:
                continue
            trades.append(
                ExternalTrade(
                    ts=ts,
                    venue="hyperliquid",
                    sequence=_as_int(row.get("tid") or row.get("hash")),
                    symbol=coin.upper(),
                    price=price,
                    size=size,
                    side=side,
                    aggressor_side=side,
                )
            )
        trades.sort(key=lambda item: item.ts)
        if not trades:
            notes.append("No Hyperliquid recent trades available in the requested time range")
        return raw_rows, trades, notes

    def fetch_recent_candles(
        self,
        coin: str,
        start: datetime,
        end: datetime,
        interval: str = "1m",
    ) -> tuple[list[dict[str, Any]], list[OHLCVBar], list[str]]:
        response = self._client.post(
            self._info_url,
            json={
                "type": "candleSnapshot",
                "req": {
                    "coin": coin.upper(),
                    "interval": interval,
                    "startTime": int(start.timestamp() * 1000),
                    "endTime": int(end.timestamp() * 1000),
                },
            },
        )
        response.raise_for_status()
        raw_rows = response.json()
        if not isinstance(raw_rows, list):
            return [], [], ["Hyperliquid candleSnapshot response was not a list"]
        bars = []
        for row in raw_rows:
            ts = _parse_ms(row.get("t") or row.get("time") or row.get("timestamp"))
            if ts is None:
                continue
            bars.append(
                OHLCVBar(
                    ts=ts,
                    symbol=coin.upper(),
                    provider="hyperliquid",
                    open=_as_float(row.get("o") or row.get("open")) or 0.0,
                    high=_as_float(row.get("h") or row.get("high")) or 0.0,
                    low=_as_float(row.get("l") or row.get("low")) or 0.0,
                    close=_as_float(row.get("c") or row.get("close")) or 0.0,
                    volume=_as_float(row.get("v") or row.get("volume")) or 0.0,
                    interval=interval,
                )
            )
        bars.sort(key=lambda item: item.ts)
        notes = [] if bars else ["No Hyperliquid recent candles available for the requested range"]
        return raw_rows, bars, notes

    def fetch_l2_book(self, coin: str) -> tuple[dict[str, Any] | list[Any], ExternalOrderBookSnapshot | None, list[str]]:
        response = self._client.post(self._info_url, json={"type": "l2Book", "coin": coin.upper()})
        response.raise_for_status()
        raw_payload = response.json()
        if not isinstance(raw_payload, dict):
            return raw_payload, None, ["Hyperliquid l2Book response was not an object"]
        levels = raw_payload.get("levels") or []
        if not isinstance(levels, list) or len(levels) < 2:
            return raw_payload, None, ["Hyperliquid l2Book response did not include both sides"]
        bids = [_normalize_level(level) for level in levels[0] if _normalize_level(level) is not None]
        asks = [_normalize_level(level) for level in levels[1] if _normalize_level(level) is not None]
        bids = [level for level in bids if level is not None]
        asks = [level for level in asks if level is not None]
        if not bids or not asks:
            return raw_payload, None, ["Hyperliquid l2Book response had no usable top-of-book levels"]
        ts = _parse_ms(raw_payload.get("time")) or datetime.now(timezone.utc)
        best_bid, bid_size = bids[0]
        best_ask, ask_size = asks[0]
        return raw_payload, ExternalOrderBookSnapshot(
            ts=ts,
            venue="hyperliquid",
            sequence=_as_int(raw_payload.get("time")),
            symbol=coin.upper(),
            best_bid=best_bid,
            best_ask=best_ask,
            bid_size=bid_size,
            ask_size=ask_size,
            mid_price=(best_bid + best_ask) / 2,
            depth={"bids": bids[:20], "asks": asks[:20]},
        ), []

    def close(self) -> None:
        self._client.close()


def _parse_ms(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        if isinstance(value, str) and not value.isdigit():
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_level(level: Any) -> tuple[float, float] | None:
    if isinstance(level, dict):
        price = _as_float(level.get("px") or level.get("price"))
        size = _as_float(level.get("sz") or level.get("size"))
    elif isinstance(level, list) and len(level) >= 2:
        price = _as_float(level[0])
        size = _as_float(level[1])
    else:
        return None
    if price is None or size is None:
        return None
    return (price, size)
