from packages.config import Settings
from polymarket_trader.bootstrap import build_container


def test_external_ingestor_populates_normalized_state_and_raw_payloads() -> None:
    container = build_container(Settings())
    market_id = "6fd5b43f-b7c7-4f63-bf57-3a91e89e8c30"
    assert container.state.external_bars[market_id]
    assert container.state.external_trades[market_id]
    assert container.state.external_orderbooks[market_id]
    assert container.state.external_raw_payloads[market_id]["bars"]
    assert container.market_catalog.get_market(market_id).external_provider == "binance"
