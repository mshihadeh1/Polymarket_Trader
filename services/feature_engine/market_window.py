from __future__ import annotations

from packages.core_types.schemas import ExternalContext
from packages.utils.time import seconds_until
from services.state import InMemoryState


class MarketWindowService:
    def __init__(self, state: InMemoryState) -> None:
        self._state = state

    def get_external_context(self, market_id: str):
        market = self._state.market_details.get(market_id)
        if market is None:
            raise KeyError(f"Unknown market_id={market_id}")
        hyper_orderbooks = self._state.hyperliquid_orderbooks.get(market_id, [])
        current = hyper_orderbooks[-1].ts if hyper_orderbooks else market.opens_at
        open_price = market.open_reference_price
        current_price = hyper_orderbooks[-1].mid_price if hyper_orderbooks else open_price
        ret = None
        if open_price and current_price:
            ret = (current_price - open_price) / open_price
        return ExternalContext(
            symbol=market.underlying or "UNKNOWN",
            open_price=open_price,
            current_price=current_price,
            return_since_open=ret,
            time_to_close_seconds=seconds_until(market.closes_at, current),
        )
