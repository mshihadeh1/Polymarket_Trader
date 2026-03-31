from datetime import timezone

from packages.clients.polymarket_client.real_client import RealPolymarketClient
from packages.core_types.schemas import RawPolymarketEvent


def test_real_client_normalizes_market_payload() -> None:
    client = RealPolymarketClient(
        api_base_url="https://gamma-api.polymarket.com",
        ws_url="wss://ws-subscriptions-clob.polymarket.com/ws/market",
    )
    payload = {
        "id": "100",
        "conditionId": "0xabc",
        "slug": "btc-5m-close-above-100000",
        "question": "Will BTC 5m candle close above 100,000?",
        "category": "crypto",
        "active": True,
        "closed": False,
        "acceptingOrders": True,
        "enableOrderBook": True,
        "startDate": "2026-03-31T11:55:00Z",
        "endDate": "2026-03-31T12:00:00Z",
        "resolutionSource": "Polymarket",
        "description": "Resolves by official BTC close.",
        "outcomes": "[\"YES\",\"NO\"]",
        "clobTokenIds": "[\"tok_yes\",\"tok_no\"]",
        "bestBid": "0.48",
        "bestAsk": "0.50",
        "lastTradePrice": "0.49",
    }
    normalized = client._normalize_market_payload(payload)
    assert normalized.market_id == "100"
    assert normalized.token_ids == ["tok_yes", "tok_no"]
    assert normalized.best_bid == 0.48
    assert normalized.best_ask == 0.50


def test_real_client_normalizes_raw_ws_event() -> None:
    client = RealPolymarketClient(
        api_base_url="https://gamma-api.polymarket.com",
        ws_url="wss://ws-subscriptions-clob.polymarket.com/ws/market",
    )
    raw = client._normalize_raw_event(
        {
            "event_type": "best_bid_ask",
            "asset_id": "tok_yes",
            "market": "0xabc",
            "timestamp": 1774958345000,
            "best_bid": "0.48",
            "best_ask": "0.50",
        }
    )
    assert isinstance(raw, RawPolymarketEvent)
    assert raw.event_type == "best_bid_ask"
    assert raw.asset_id == "tok_yes"
    assert raw.timestamp.tzinfo == timezone.utc
    assert raw.timestamp.year == 2026
