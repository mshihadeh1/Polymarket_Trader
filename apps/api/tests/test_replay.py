from polymarket_trader.bootstrap import build_container
from polymarket_trader.core.config import Settings


def test_replay_merges_orderbook_and_trades_in_time_order() -> None:
    container = build_container(Settings())
    replay = container.replay.get_replay("6fd5b43f-b7c7-4f63-bf57-3a91e89e8c30")
    assert replay.events
    timestamps = [event.ts for event in replay.events]
    assert timestamps == sorted(timestamps)
    assert {"orderbook", "trade"}.issubset({event.event_type for event in replay.events})
