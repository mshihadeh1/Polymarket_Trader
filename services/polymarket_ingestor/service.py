from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, UUID, uuid5

from packages.clients.polymarket_client import PolymarketClient
from packages.db import ResearchPersistence
from packages.core_types.schemas import (
    ExternalContext,
    MarketDetail,
    MarketRule,
    MarketSummary,
    MarketToken,
    OrderBookSnapshot,
    PolymarketMarketMetadata,
    PolymarketTopOfBook,
    PolymarketTrade,
    RawPolymarketEvent,
    Trade,
)
from packages.utils.time import parse_dt
from services.market_catalog.classifier import classify_polymarket_market
from services.state import InMemoryState

logger = logging.getLogger(__name__)


class PolymarketIngestorService:
    def __init__(
        self,
        state: InMemoryState,
        client: PolymarketClient,
        persistence: ResearchPersistence | None = None,
    ) -> None:
        self._state = state
        self._client = client
        self._persistence = persistence
        self._stream_task: asyncio.Task | None = None
        self._asset_to_market: dict[str, str] = {}
        self._seen_event_keys: set[str] = set()

    @property
    def data_source(self) -> str:
        return "mock" if self._client.is_mock else "real"

    async def bootstrap(self) -> int:
        raw_markets, normalized_markets = await self._client.discover_active_markets()
        count = 0
        selected_asset_ids: list[str] = []
        for raw_market, metadata in zip(raw_markets, normalized_markets, strict=False):
            market_type, underlying = classify_polymarket_market(metadata)
            if market_type not in {"crypto_5m", "crypto_15m"}:
                continue
            summary = self._build_market_summary(
                metadata,
                raw_market=raw_market,
                market_type=market_type,
                underlying=underlying,
            )
            market_id = str(summary.id)
            orderbooks = self._seed_orderbooks(raw_market, underlying)
            trades = self._seed_trades(raw_market, underlying)
            raw_event_payloads = raw_market.get("raw_events", []) if isinstance(raw_market, dict) else []
            detail = MarketDetail(
                **summary.model_dump(),
                rules=[
                    MarketRule(
                        rule_type="resolution",
                        source=metadata.resolution_source,
                        text=metadata.description or "",
                        normalized={"source": metadata.resolution_source},
                    )
                ],
                latest_polymarket_orderbook=orderbooks[-1] if orderbooks else self._initial_orderbook(metadata),
                recent_polymarket_trades=trades[-20:],
                external_context=ExternalContext(symbol=summary.underlying or "UNKNOWN"),
            )
            self._state.markets[market_id] = summary
            self._state.market_details[market_id] = detail
            self._state.polymarket_orderbooks[market_id] = orderbooks
            self._state.polymarket_trades[market_id] = trades
            self._state.polymarket_raw_events[market_id] = raw_event_payloads
            self._state.polymarket_top_of_book.setdefault(market_id, [])
            self._state.polymarket_trade_events.setdefault(market_id, [])
            self._state.polymarket_raw_envelopes.setdefault(market_id, [])
            for token in summary.tokens:
                self._asset_to_market[token.token_id] = market_id
                selected_asset_ids.append(token.token_id)
            if self._persistence is not None:
                self._persistence.save_market_summary(summary)
            count += 1
        logger.info("Polymarket discovery returned %s selected short-horizon markets", count)
        logger.info("Selected Polymarket asset ids: %s", selected_asset_ids)
        return count

    async def start_live_ingestion(self) -> None:
        if self._client.is_mock or not self._asset_to_market:
            return
        if self._stream_task is not None and not self._stream_task.done():
            return
        asset_ids = sorted(self._asset_to_market.keys())
        self._stream_task = asyncio.create_task(
            self._client.stream_market_events(asset_ids, self.handle_raw_event),
            name="polymarket-market-stream",
        )

    async def stop_live_ingestion(self) -> None:
        if self._stream_task is not None:
            self._stream_task.cancel()
            try:
                await self._stream_task
            except asyncio.CancelledError:
                logger.info("Stopped Polymarket market stream")
        close = getattr(self._client, "close", None)
        if callable(close):
            await close()

    def handle_raw_event(self, raw_event: RawPolymarketEvent) -> None:
        market_id = self._asset_to_market.get(raw_event.asset_id)
        if market_id is None:
            return
        event_key = raw_event.sequence or f"{market_id}:{raw_event.asset_id}:{raw_event.timestamp.isoformat()}:{raw_event.event_type}"
        if event_key in self._seen_event_keys:
            logger.debug("Dropped duplicate Polymarket event %s", event_key)
            return
        self._seen_event_keys.add(event_key)
        self._state.polymarket_raw_events.setdefault(market_id, []).append(raw_event.payload)
        self._state.polymarket_raw_envelopes.setdefault(market_id, []).append(raw_event)
        if self._persistence is not None:
            self._persistence.save_polymarket_raw_event(raw_event, market_id=market_id)

        if raw_event.event_type in {"last_trade_price", "price_change"}:
            trade = self._normalize_trade(raw_event, market_id)
            if trade is not None:
                self._state.polymarket_trade_events[market_id].append(trade)
                self._state.polymarket_trades[market_id].append(
                    Trade(
                        ts=trade.ts,
                        venue="polymarket",
                        sequence=None if trade.sequence is None else int(trade.sequence) if trade.sequence.isdigit() else None,
                        symbol=self._state.markets[market_id].underlying,
                        price=trade.price,
                        size=trade.size,
                        side=trade.side,
                        aggressor_side=trade.side,
                    )
                )
                self._state.market_details[market_id].recent_polymarket_trades = self._state.polymarket_trades[market_id][-20:]
                if self._persistence is not None:
                    self._persistence.save_polymarket_trade(trade)

        if raw_event.event_type in {"best_bid_ask", "book"}:
            top = self._normalize_top_of_book(raw_event, market_id)
            if top is not None:
                self._state.polymarket_top_of_book[market_id].append(top)
                snapshot = OrderBookSnapshot(
                    ts=top.ts,
                    venue="polymarket",
                    sequence=None if top.sequence is None else int(top.sequence) if top.sequence.isdigit() else None,
                    symbol=self._state.markets[market_id].underlying,
                    best_bid=top.best_bid,
                    best_ask=top.best_ask,
                    bid_size=0.0,
                    ask_size=0.0,
                    mid_price=(top.best_bid + top.best_ask) / 2,
                    depth={},
                )
                self._state.polymarket_orderbooks[market_id].append(snapshot)
                self._state.market_details[market_id].latest_polymarket_orderbook = snapshot
                if self._persistence is not None:
                    self._persistence.save_polymarket_top_of_book(top)

    def _build_market_summary(
        self,
        metadata: PolymarketMarketMetadata,
        raw_market: dict[str, object],
        market_type: str,
        underlying: str | None,
    ) -> MarketSummary:
        token_ids = metadata.token_ids or [f"{metadata.market_id}:YES", f"{metadata.market_id}:NO"]
        outcomes = metadata.outcomes or ["YES", "NO"]
        tokens = [
            MarketToken(
                id=uuid5(NAMESPACE_URL, f"{metadata.market_id}:{token_id}:{index}"),
                token_id=token_id,
                outcome=outcomes[index] if index < len(outcomes) else f"OUTCOME_{index}",
            )
            for index, token_id in enumerate(token_ids)
        ]
        return MarketSummary(
            id=UUID(metadata.market_id) if _is_uuid(metadata.market_id) else uuid5(NAMESPACE_URL, f"polymarket:{metadata.market_id}"),
            event_id=None,
            slug=metadata.slug or metadata.market_id,
            title=metadata.question or metadata.slug or metadata.market_id,
            category=metadata.category or "crypto",
            market_type=market_type,
            underlying=underlying,
            status="active" if metadata.active else "inactive",
            opens_at=metadata.start_date,
            closes_at=metadata.end_date,
            resolves_at=metadata.end_date,
            price_to_beat=_coerce_float(raw_market.get("price_to_beat")) or _extract_price_to_beat(metadata.question or metadata.slug or ""),
            open_reference_price=_coerce_float(raw_market.get("open_reference_price")),
            external_provider=None,
            source=self.data_source,
            tags=[market_type, underlying.lower() if underlying else "unknown"],
            tokens=tokens,
        )

    def _initial_orderbook(self, metadata: PolymarketMarketMetadata) -> OrderBookSnapshot | None:
        if metadata.best_bid is None or metadata.best_ask is None:
            return None
        return OrderBookSnapshot(
            ts=datetime.now(timezone.utc),
            venue="polymarket",
            sequence=None,
            symbol=None,
            best_bid=metadata.best_bid,
            best_ask=metadata.best_ask,
            bid_size=0.0,
            ask_size=0.0,
            mid_price=(metadata.best_bid + metadata.best_ask) / 2,
            depth={},
        )

    def _normalize_trade(self, raw_event: RawPolymarketEvent, market_id: str) -> PolymarketTrade | None:
        payload = raw_event.payload
        price = _coerce_float(payload.get("price") or payload.get("last_trade_price") or payload.get("p"))
        if price is None:
            return None
        side_value = str(payload.get("side") or payload.get("taker_side") or "BUY").upper()
        side = "buy" if side_value in {"BUY", "BID"} else "sell"
        size = _coerce_float(payload.get("size") or payload.get("amount") or payload.get("q") or 0.0) or 0.0
        return PolymarketTrade(
            market_id=market_id,
            asset_id=raw_event.asset_id,
            ts=raw_event.timestamp,
            sequence=raw_event.sequence,
            price=price,
            size=size,
            side=side,
            fee_rate_bps=_coerce_float(payload.get("fee_rate_bps")),
        )

    def _normalize_top_of_book(self, raw_event: RawPolymarketEvent, market_id: str) -> PolymarketTopOfBook | None:
        payload = raw_event.payload
        best_bid = _coerce_float(payload.get("best_bid") or payload.get("bid") or payload.get("b"))
        best_ask = _coerce_float(payload.get("best_ask") or payload.get("ask") or payload.get("a"))
        if best_bid is None or best_ask is None:
            bids = payload.get("bids", [])
            asks = payload.get("asks", [])
            if bids and asks:
                best_bid = _coerce_float(bids[0][0])
                best_ask = _coerce_float(asks[0][0])
        if best_bid is None or best_ask is None:
            return None
        return PolymarketTopOfBook(
            market_id=market_id,
            asset_id=raw_event.asset_id,
            ts=raw_event.timestamp,
            sequence=raw_event.sequence,
            best_bid=best_bid,
            best_ask=best_ask,
            spread=best_ask - best_bid,
        )

    def _seed_orderbooks(self, raw_market: dict[str, object], underlying: str | None) -> list[OrderBookSnapshot]:
        snapshots = raw_market.get("orderbook", [])
        if not isinstance(snapshots, list):
            return []
        return [
            OrderBookSnapshot(
                ts=parse_dt(snapshot["ts"]),
                venue="polymarket",
                sequence=snapshot.get("sequence"),
                symbol=underlying,
                best_bid=float(snapshot["best_bid"]),
                best_ask=float(snapshot["best_ask"]),
                bid_size=float(snapshot.get("bid_size", 0.0)),
                ask_size=float(snapshot.get("ask_size", 0.0)),
                mid_price=_coerce_float(snapshot.get("mid_price")),
                depth=snapshot.get("depth", {}),
            )
            for snapshot in snapshots
        ]

    def _seed_trades(self, raw_market: dict[str, object], underlying: str | None) -> list[Trade]:
        trades = raw_market.get("trades", [])
        if not isinstance(trades, list):
            return []
        return [
            Trade(
                ts=parse_dt(trade["ts"]),
                venue="polymarket",
                sequence=trade.get("sequence"),
                symbol=underlying,
                price=float(trade["price"]),
                size=float(trade["size"]),
                side=trade["side"],
                aggressor_side=trade.get("aggressor_side"),
            )
            for trade in trades
        ]


def _extract_price_to_beat(text: str) -> float | None:
    cleaned = text.replace(",", "")
    for token in cleaned.split():
        try:
            value = float(token)
            if value > 100:
                return value
        except ValueError:
            continue
    return None


def _coerce_float(value: object) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
        return True
    except ValueError:
        return False
