import asyncio
from datetime import datetime, timezone

from packages.config import Settings
from packages.core_types.schemas import PolymarketMarketMetadata, RawPolymarketEvent
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


def test_polymarket_ingestor_hydrates_closed_market_by_identifier() -> None:
    container = build_container(Settings())

    raw_market = {
        "id": "closed-btc-5m-1775039700",
        "slug": "btc-updown-5m-1775039700",
        "price_to_beat": 84500.0,
        "open_reference_price": 84440.0,
        "resolved_outcome": "yes",
        "resolution_price": 84620.0,
    }
    metadata = PolymarketMarketMetadata(
        market_id="closed-btc-5m-1775039700",
        condition_id="cond-closed-btc-5m",
        slug="btc-updown-5m-1775039700",
        question="BTC Up/Down 5m",
        category="crypto",
        market_family="btc_updown_5m",
        event_slug="btc-updown-5m-1775039700",
        event_epoch=1775039700,
        duration_minutes=5,
        active=False,
        closed=True,
        accepting_orders=False,
        enable_order_book=True,
        start_date=datetime(2026, 3, 31, 11, 55, 0, tzinfo=timezone.utc),
        end_date=datetime(2026, 3, 31, 12, 0, 0, tzinfo=timezone.utc),
        resolution_source="polymarket",
        description="BTC closes above the reference",
        price_to_beat=84500.0,
        resolved_outcome="yes",
        resolution_price=84620.0,
        token_ids=["tok_yes", "tok_no"],
    )

    async def _fetch_market_by_identifier(identifier: str):
        assert identifier == "btc-updown-5m-1775039700"
        return raw_market, metadata

    container.polymarket_ingestor._client.fetch_market_by_identifier = _fetch_market_by_identifier  # type: ignore[method-assign]

    before = len(container.state.markets)
    hydrated = asyncio.run(container.polymarket_ingestor.hydrate_closed_markets(["btc-updown-5m-1775039700"]))
    after = len(container.state.markets)

    assert hydrated == 1
    assert after == before + 1
    market = next(m for m in container.state.markets.values() if m.event_slug == "btc-updown-5m-1775039700")
    assert market.event_slug == "btc-updown-5m-1775039700"
    assert market.resolved_outcome == "yes"
