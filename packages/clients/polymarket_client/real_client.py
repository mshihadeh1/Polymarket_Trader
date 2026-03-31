from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

import httpx
import websockets

from packages.clients.polymarket_client.base import PolymarketClient
from packages.core_types.schemas import PolymarketMarketMetadata, RawPolymarketEvent
from packages.utils.time import parse_dt

logger = logging.getLogger(__name__)


class RealPolymarketClient(PolymarketClient):
    def __init__(
        self,
        api_base_url: str,
        ws_url: str,
        http_client: httpx.AsyncClient | None = None,
        reconnect_delay_seconds: float = 3.0,
    ) -> None:
        self._api_base_url = api_base_url.rstrip("/")
        self._ws_url = ws_url
        self._http_client = http_client or httpx.AsyncClient(timeout=20.0)
        self._reconnect_delay_seconds = reconnect_delay_seconds
        self._stop_event = asyncio.Event()

    @property
    def client_name(self) -> str:
        return "real_polymarket"

    @property
    def is_mock(self) -> bool:
        return False

    async def discover_active_markets(self) -> tuple[list[dict[str, Any]], list[PolymarketMarketMetadata]]:
        raw_markets: list[dict[str, Any]] = []
        normalized: list[PolymarketMarketMetadata] = []
        offset = 0
        limit = 100
        while True:
            response = await self._http_client.get(
                f"{self._api_base_url}/markets",
                params={"closed": "false", "limit": limit, "offset": offset},
            )
            response.raise_for_status()
            page = response.json()
            if not isinstance(page, list) or not page:
                break
            active_page = [item for item in page if item.get("active")]
            raw_markets.extend(active_page)
            normalized.extend(self._normalize_market_payload(item) for item in active_page)
            if len(page) < limit:
                break
            offset += limit
        return raw_markets, normalized

    async def stream_market_events(
        self,
        asset_ids: list[str],
        on_event: Callable[[RawPolymarketEvent], None],
    ) -> None:
        self._stop_event.clear()
        while not self._stop_event.is_set():
            try:
                logger.info("Connecting to Polymarket market websocket for %s assets", len(asset_ids))
                async with websockets.connect(self._ws_url, ping_interval=None) as websocket:
                    await self._subscribe(websocket, asset_ids)
                    await self._event_loop(websocket, on_event)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Polymarket websocket disconnected; reconnecting after delay")
                await asyncio.sleep(self._reconnect_delay_seconds)

    async def close(self) -> None:
        self._stop_event.set()
        await self._http_client.aclose()

    async def _subscribe(self, websocket: Any, asset_ids: list[str]) -> None:
        payload = {
            "type": "market",
            "assets_ids": asset_ids,
            "custom_feature_enabled": True,
        }
        await websocket.send(json.dumps(payload))

    async def _event_loop(
        self,
        websocket: Any,
        on_event: Callable[[RawPolymarketEvent], None],
    ) -> None:
        async for message in websocket:
            if message == "PONG":
                continue
            if message == "PING":
                await websocket.send("PONG")
                continue
            payload = json.loads(message)
            if isinstance(payload, dict):
                # TODO: Expand schema handling if Polymarket adds additional market-channel event envelopes.
                on_event(self._normalize_raw_event(payload))

    def _normalize_market_payload(self, payload: dict[str, Any]) -> PolymarketMarketMetadata:
        token_ids = self._parse_json_list(payload.get("clobTokenIds"))
        outcomes = self._parse_json_list(payload.get("outcomes"))
        outcome_prices = self._parse_json_list(payload.get("outcomePrices"))
        return PolymarketMarketMetadata(
            market_id=str(payload["id"]),
            condition_id=str(payload.get("conditionId", "")),
            slug=payload.get("slug"),
            question=payload.get("question"),
            category=payload.get("category"),
            active=bool(payload.get("active")),
            closed=bool(payload.get("closed")),
            accepting_orders=bool(payload.get("acceptingOrders", payload.get("accepting_orders", False))),
            enable_order_book=bool(payload.get("enableOrderBook")),
            start_date=parse_dt(payload.get("startDate") or payload.get("startDateIso")),
            end_date=parse_dt(payload.get("endDate") or payload.get("endDateIso")),
            resolution_source=payload.get("resolutionSource"),
            description=payload.get("description"),
            outcomes=outcomes,
            outcome_prices=[float(value) for value in outcome_prices if value is not None],
            token_ids=[str(token_id) for token_id in token_ids],
            best_bid=_as_float(payload.get("bestBid")),
            best_ask=_as_float(payload.get("bestAsk")),
            last_trade_price=_as_float(payload.get("lastTradePrice")),
            raw_tags=[tag.get("slug", "") for tag in payload.get("tags", []) if isinstance(tag, dict)],
        )

    def _normalize_raw_event(self, payload: dict[str, Any]) -> RawPolymarketEvent:
        timestamp_ms = payload.get("timestamp")
        ts = (
            datetime.fromtimestamp(int(timestamp_ms) / 1000, tz=timezone.utc)
            if timestamp_ms is not None
            else datetime.now(timezone.utc)
        )
        return RawPolymarketEvent(
            event_type=str(payload.get("event_type", "unknown")),
            asset_id=str(payload.get("asset_id", "")),
            market=str(payload.get("market", "")),
            timestamp=ts,
            sequence=str(payload.get("hash") or payload.get("sequence") or payload.get("timestamp") or ""),
            payload=payload,
        )

    @staticmethod
    def _parse_json_list(value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                return parsed if isinstance(parsed, list) else []
            except json.JSONDecodeError:
                return []
        return []


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
