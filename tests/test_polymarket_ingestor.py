from datetime import datetime, timezone

from packages.config import Settings
from packages.core_types.schemas import RawPolymarketEvent
from polymarket_trader.bootstrap import build_container


def test_polymarket_ingestor_dedupes_duplicate_trade_events() -> None:
    container = build_container(Settings())
    market_id = next(iter(container.state.markets))
    asset_id = container.state.markets[market_id].tokens[0].token_id
    event = RawPolymarketEvent(
        event_type="last_trade_price",
        asset_id=asset_id,
        market="cond",
        timestamp=datetime(2026, 3, 31, 11, 59, 0, tzinfo=timezone.utc),
        sequence="dup-1",
        payload={"event_type": "last_trade_price", "asset_id": asset_id, "price": "0.51", "size": "100", "side": "BUY"},
    )
    before = len(container.state.polymarket_trade_events[market_id])
    container.polymarket_ingestor.handle_raw_event(event)
    container.polymarket_ingestor.handle_raw_event(event)
    after = len(container.state.polymarket_trade_events[market_id])
    assert after == before + 1
