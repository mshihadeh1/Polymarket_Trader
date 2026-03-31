from __future__ import annotations

from packages.clients.market_data_provider import HistoricalMarketDataProvider
from services.state import InMemoryState


class HyperliquidIngestorService:
    def __init__(self, state: InMemoryState, provider: HistoricalMarketDataProvider) -> None:
        self._state = state
        self._provider = provider

    def bootstrap(self) -> int:
        count = 0
        for market_id, market in self._state.market_details.items():
            if market.underlying is None or market.opens_at is None or market.closes_at is None:
                continue
            raw_bars, bars = self._provider.get_ohlcv(
                market.underlying,
                start=market.opens_at,
                end=market.closes_at,
                interval="1m",
            )
            raw_trades, trades = self._provider.get_trades(
                market.underlying,
                start=market.opens_at,
                end=market.closes_at,
            )
            raw_books, snapshots = self._provider.get_orderbook_snapshots(
                market.underlying,
                start=market.opens_at,
                end=market.closes_at,
            )
            self._state.external_bars[market_id] = bars
            self._state.external_trades[market_id] = trades
            self._state.external_orderbooks[market_id] = snapshots
            self._state.external_raw_payloads[market_id] = {
                "bars": raw_bars,
                "trades": raw_trades,
                "orderbook_snapshots": raw_books,
            }
            market.external_provider = self._provider.provider_name
            if snapshots:
                market.latest_external_orderbook = snapshots[-1]
            if trades:
                market.recent_external_trades = trades[-20:]
            if market.external_context is not None:
                market.external_context.provider = self._provider.provider_name
            count += 1
        return count

    def raw_payloads(self, market_id: str) -> dict[str, list[dict]]:
        return self._state.external_raw_payloads.get(market_id, {})
