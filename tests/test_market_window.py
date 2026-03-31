from packages.config import Settings
from services.feature_engine import MarketWindowService
from polymarket_trader.bootstrap import build_container


def test_market_window_external_context_maps_open_and_current_price() -> None:
    container = build_container(Settings())
    service = MarketWindowService(container.state)
    context = service.get_external_context("6fd5b43f-b7c7-4f63-bf57-3a91e89e8c30")
    assert context.symbol == "BTC"
    assert context.open_price == 84440.0
    assert context.current_price == 84529.0
    assert context.return_since_open is not None and context.return_since_open > 0
