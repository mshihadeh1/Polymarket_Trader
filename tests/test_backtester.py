from packages.config import Settings
from polymarket_trader.bootstrap import build_container


def test_backtester_replays_bars_and_returns_equity_curve() -> None:
    container = build_container(Settings())
    report = container.backtester.run_baseline("6fd5b43f-b7c7-4f63-bf57-3a91e89e8c30", strategy_name="combined_cvd_gap")
    metric_labels = {metric.label for metric in report.metrics}
    assert "net_pnl" in metric_labels
    assert "hit_rate" in metric_labels
    assert "bar_count" in metric_labels
    assert report.equity_curve
    assert report.trade_count == len(report.trades)
