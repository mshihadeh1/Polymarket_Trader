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


def test_polymarket_ingestor_accepts_dict_shaped_book_levels() -> None:
    container = build_container(Settings())
    market_id = next(iter(container.state.markets))
    asset_id = container.state.markets[market_id].tokens[0].token_id
    event = RawPolymarketEvent(
        event_type="book",
        asset_id=asset_id,
        market="cond",
        timestamp=datetime(2026, 3, 31, 12, 1, 0, tzinfo=timezone.utc),
        sequence="book-1",
        payload={
            "event_type": "book",
            "asset_id": asset_id,
            "bids": [{"price": "0.48", "size": "120"}],
            "asks": [{"price": "0.52", "size": "90"}],
        },
    )
    before = len(container.state.polymarket_orderbooks[market_id])
    container.polymarket_ingestor.handle_raw_event(event)
    after = len(container.state.polymarket_orderbooks[market_id])
    assert after == before + 1


def test_polymarket_ingestor_tracks_dropped_book_events_without_raising() -> None:
    container = build_container(Settings())
    market_id = next(iter(container.state.markets))
    asset_id = container.state.markets[market_id].tokens[0].token_id
    event = RawPolymarketEvent(
        event_type="book",
        asset_id=asset_id,
        market="cond",
        timestamp=datetime(2026, 3, 31, 12, 2, 0, tzinfo=timezone.utc),
        sequence="book-2",
        payload={"event_type": "book", "asset_id": asset_id, "bids": [{"size": "120"}], "asks": []},
    )
    before = container.state.polymarket_observation.dropped_event_count
    container.polymarket_ingestor.handle_raw_event(event)
    after = container.state.polymarket_observation.dropped_event_count
    assert after == before + 1
