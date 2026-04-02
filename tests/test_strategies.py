from packages.config import Settings
from polymarket_trader.bootstrap import build_container


def test_combined_strategy_backtest_creates_trade() -> None:
    container = build_container(Settings())
    report = container.backtester.run_baseline(
        "6fd5b43f-b7c7-4f63-bf57-3a91e89e8c30",
        strategy_name="combined_cvd_gap",
    )
    assert report.trade_count >= 1
    assert any(decision.decision in {"buy_yes", "buy_no"} for decision in report.decisions)


def test_flow_alignment_strategy_backtest_creates_trade() -> None:
    container = build_container(Settings())
    report = container.backtester.run_baseline(
        "6fd5b43f-b7c7-4f63-bf57-3a91e89e8c30",
        strategy_name="flow_alignment_5m",
    )
    assert report.trade_count >= 1
    assert any(decision.decision in {"buy_yes", "buy_no"} for decision in report.decisions)


def test_strategy_registry_is_exposed() -> None:
    container = build_container(Settings())
    names = {strategy.name for strategy in container.backtester.list_strategies()}
    assert {"no_trade_baseline", "local_cvd_only", "hyperliquid_cvd_only", "combined_cvd_gap", "flow_alignment_5m"}.issubset(names)
