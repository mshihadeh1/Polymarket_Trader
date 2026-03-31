from packages.config import Settings
from polymarket_trader.bootstrap import build_container


def test_backtester_returns_net_pnl_metric() -> None:
    container = build_container(Settings())
    report = container.backtester.run_baseline("6fd5b43f-b7c7-4f63-bf57-3a91e89e8c30")
    metric_labels = {metric.label for metric in report.metrics}
    assert "net_pnl" in metric_labels
    assert "hit_rate" in metric_labels
