from packages.config import Settings
from polymarket_trader.bootstrap import build_container


def test_paper_trader_status_is_dry_run() -> None:
    container = build_container(Settings())
    status = container.paper_trader.status()
    assert status.dry_run_only is True
    assert status.strategy_name == "combined_cvd_gap"


def test_paper_trader_run_once_appends_blotter_entry() -> None:
    container = build_container(Settings())
    before = len(container.paper_trader.blotter())
    container.paper_trader.run_once("6fd5b43f-b7c7-4f63-bf57-3a91e89e8c30")
    after = len(container.paper_trader.blotter())
    assert after == before + 1


def test_paper_trader_cycle_updates_live_status() -> None:
    settings = Settings(PAPER_TRADING_UNDERLYINGS="BTC", PAPER_TRADING_MARKET_TYPES="crypto_5m,crypto_15m")
    container = build_container(settings)
    decisions = container.paper_trader.run_cycle()
    status = container.paper_trader.status()
    assert decisions
    assert status.cycle_count == 1
    assert status.last_update_at is not None
    assert status.selected_market_ids
