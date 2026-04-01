from __future__ import annotations

from datetime import datetime

from packages.core_types.schemas import ExternalContext, HistoricalBar, MarketDetail, OrderBookSnapshot
from packages.utils.time import seconds_until
from services.state import InMemoryState


class MarketWindowService:
    def __init__(self, state: InMemoryState) -> None:
        self._state = state

    def get_external_context(self, market_id: str, as_of: datetime | None = None):
        market = self._state.market_details.get(market_id)
        if market is None:
            raise KeyError(f"Unknown market_id={market_id}")
        return self.get_external_context_for_series(
            market=market,
            external_bars=self._state.external_bars.get(market_id, []),
            external_orderbooks=self._state.external_orderbooks.get(market_id, []),
            as_of=as_of,
        )

    def get_external_context_for_series(
        self,
        market: MarketDetail,
        external_bars: list[HistoricalBar],
        external_orderbooks: list[OrderBookSnapshot],
        as_of: datetime | None = None,
    ) -> ExternalContext:
        external_bars = [
            bar
            for bar in external_bars
            if as_of is None or bar.ts <= as_of
        ]
        external_orderbooks = [
            book
            for book in external_orderbooks
            if as_of is None or book.ts <= as_of
        ]
        current = external_orderbooks[-1].ts if external_orderbooks else external_bars[-1].ts if external_bars else market.opens_at
        open_price = market.open_reference_price or (external_bars[0].open if external_bars else None)
        current_price = (
            external_orderbooks[-1].mid_price
            if external_orderbooks
            else external_bars[-1].close if external_bars else open_price
        )
        ret = None
        if open_price and current_price:
            ret = (current_price - open_price) / open_price
        return ExternalContext(
            symbol=market.underlying or "UNKNOWN",
            provider=market.external_provider,
            open_price=open_price,
            current_price=current_price,
            return_since_open=ret,
            time_to_close_seconds=seconds_until(market.closes_at, current),
        )
