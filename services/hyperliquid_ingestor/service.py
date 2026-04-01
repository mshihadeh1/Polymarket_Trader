from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from packages.clients.market_data_provider import HistoricalMarketDataProvider
from packages.core_types import FeatureAvailability, OHLCVBar, OrderBookSnapshot, Trade
from services.state import InMemoryState

logger = logging.getLogger(__name__)


class HyperliquidIngestorService:
    def __init__(self, state: InMemoryState, provider: HistoricalMarketDataProvider, recent_client: Any | None = None) -> None:
        self._state = state
        self._provider = provider
        self._recent_client = recent_client

    def bootstrap(self) -> int:
        count = 0
        for market_id, market in self._state.market_details.items():
            if market.underlying is None or market.opens_at is None or market.closes_at is None:
                continue
            assembled = self.assemble_window(
                market.underlying,
                start=market.opens_at,
                end=market.closes_at if market.status == "closed" else datetime.now(timezone.utc),
                include_recent_enrichment=True,
                include_current_orderbook=market.status == "active",
            )
            self._state.external_bars[market_id] = assembled["bars"]
            self._state.external_trades[market_id] = assembled["trades"]
            self._state.external_orderbooks[market_id] = assembled["orderbooks"]
            self._state.external_raw_payloads[market_id] = assembled["raw_payloads"]
            self._state.external_feature_availability[market_id] = assembled["availability"].model_dump(mode="json")
            market.external_provider = self._provider.provider_name
            if assembled["orderbooks"]:
                market.latest_external_orderbook = assembled["orderbooks"][-1]
            if assembled["trades"]:
                market.recent_external_trades = assembled["trades"][-20:]
            if market.external_context is not None:
                market.external_context.provider = self._provider.provider_name
            count += 1
        return count

    def assemble_window(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        *,
        include_recent_enrichment: bool,
        include_current_orderbook: bool = False,
    ) -> dict[str, Any]:
        raw_bars, bars = self._provider.get_ohlcv(symbol, start=start, end=end, interval="1m")
        raw_trades, trades = self._provider.get_trades(symbol, start=start, end=end)
        raw_books, snapshots = self._provider.get_orderbook_snapshots(symbol, start=start, end=end)
        notes: list[str] = []

        availability = FeatureAvailability(
            bars_available=bool(bars),
            trades_available=bool(trades),
            orderbook_available=bool(snapshots),
            enriched_with_hyperliquid=False,
            notes=[],
        )

        raw_payloads: dict[str, list[dict]] = {
            "bars": raw_bars,
            "trades": raw_trades,
            "orderbook_snapshots": raw_books,
        }

        if include_recent_enrichment and self._recent_client is not None:
            notes.append("Recent Hyperliquid enrichment requested")
            recent_raw_trades, recent_trades, trade_notes = self._recent_client.fetch_recent_trades(symbol, start=start, end=end)
            recent_trades = [trade for trade in recent_trades if start <= trade.ts <= end]
            raw_payloads["recent_hyperliquid_trades"] = recent_raw_trades
            notes.extend(trade_notes)
            if recent_trades:
                trades = _merge_trades(trades, recent_trades)
                availability.trades_available = True
                availability.enriched_with_hyperliquid = True

            # Candle snapshot is limited to the most recent 5000 candles. Use it only to fill near-term gaps.
            lookback_floor = datetime.now(timezone.utc) - timedelta(minutes=5000)
            if end >= lookback_floor:
                recent_raw_bars, recent_bars, bar_notes = self._recent_client.fetch_recent_candles(symbol, start=max(start, lookback_floor), end=end, interval="1m")
                recent_bars = [bar for bar in recent_bars if start <= bar.ts <= end]
                raw_payloads["recent_hyperliquid_bars"] = recent_raw_bars
                notes.extend(bar_notes)
                if recent_bars:
                    bars = _merge_bars(bars, recent_bars)
                    availability.bars_available = True
                    availability.enriched_with_hyperliquid = True
            else:
                notes.append("Historical window predates Hyperliquid candleSnapshot retention; recent bar enrichment unavailable")

            if include_current_orderbook:
                recent_raw_book, recent_book, book_notes = self._recent_client.fetch_l2_book(symbol)
                raw_payloads["recent_hyperliquid_l2_book"] = [recent_raw_book] if recent_raw_book else []
                notes.extend(book_notes)
                if recent_book is not None:
                    snapshots = _merge_books(snapshots, [recent_book])
                    availability.orderbook_available = True
                    availability.enriched_with_hyperliquid = True
            elif self._recent_client is not None:
                notes.append("Current Hyperliquid orderbook omitted for historical windows to avoid lookahead")

        availability.notes = list(dict.fromkeys(notes))
        return {
            "bars": bars,
            "trades": trades,
            "orderbooks": snapshots,
            "raw_payloads": raw_payloads,
            "availability": availability,
        }

    def raw_payloads(self, market_id: str) -> dict[str, list[dict]]:
        return self._state.external_raw_payloads.get(market_id, {})


def _merge_bars(primary: list[OHLCVBar], secondary: list[OHLCVBar]) -> list[OHLCVBar]:
    merged = {bar.ts: bar for bar in primary}
    for bar in secondary:
        merged[bar.ts] = bar
    return sorted(merged.values(), key=lambda item: item.ts)


def _merge_trades(primary: list[Trade], secondary: list[Trade]) -> list[Trade]:
    merged: dict[tuple[datetime, float, float, str], Trade] = {
        (trade.ts, trade.price, trade.size, trade.side): trade
        for trade in primary
    }
    for trade in secondary:
        merged[(trade.ts, trade.price, trade.size, trade.side)] = trade
    return sorted(merged.values(), key=lambda item: item.ts)


def _merge_books(primary: list[OrderBookSnapshot], secondary: list[OrderBookSnapshot]) -> list[OrderBookSnapshot]:
    merged = {book.ts: book for book in primary}
    for book in secondary:
        merged[book.ts] = book
    return sorted(merged.values(), key=lambda item: item.ts)
