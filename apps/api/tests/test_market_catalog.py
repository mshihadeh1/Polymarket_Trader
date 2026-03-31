from polymarket_trader.bootstrap import build_container
from polymarket_trader.core.config import Settings


def test_list_markets_filters_by_type() -> None:
    container = build_container(Settings())
    markets = container.market_catalog.list_markets(market_type="crypto_5m")
    assert len(markets) == 1
    assert markets[0].market_type == "crypto_5m"


def test_market_detail_contains_latest_orderbook() -> None:
    container = build_container(Settings())
    market_id = "6fd5b43f-b7c7-4f63-bf57-3a91e89e8c30"
    detail = container.market_catalog.get_market(market_id)
    assert detail.latest_orderbook is not None
    assert detail.latest_orderbook.best_bid == 0.54
