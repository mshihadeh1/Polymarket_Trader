from __future__ import annotations

from packages.core_types.schemas import BacktestMetric, BacktestReport
from packages.utils.cvd import trade_imbalance
from services.feature_engine.service import FeatureEngineService
from services.state import InMemoryState


class BacktesterService:
    def __init__(self, state: InMemoryState, feature_engine: FeatureEngineService) -> None:
        self._state = state
        self._feature_engine = feature_engine

    def run_baseline(self, market_id: str, strategy_name: str = "no_trade_baseline") -> BacktestReport:
        market = self._state.markets.get(market_id)
        if market is None:
            raise KeyError(f"Unknown market_id={market_id}")
        snapshot = self._feature_engine.compute_snapshot(market_id)
        trades = self._state.polymarket_trades.get(market_id, [])
        avg_edge = snapshot.fair_value_gap or 0.0
        expectancy = avg_edge - 0.01
        gross_pnl = 0.0 if strategy_name == "no_trade_baseline" else avg_edge * 100.0
        net_pnl = gross_pnl - 1.5
        hit_rate = 0.0 if strategy_name == "no_trade_baseline" else max(min(0.5 + trade_imbalance(trades) * 0.2, 1.0), 0.0)
        return BacktestReport(
            run_id=f"{strategy_name}:{market_id}",
            strategy_name=strategy_name,
            market_id=market.id,
            metrics=[
                BacktestMetric(label="gross_pnl", value=gross_pnl),
                BacktestMetric(label="net_pnl", value=net_pnl),
                BacktestMetric(label="hit_rate", value=hit_rate),
                BacktestMetric(label="avg_edge_at_entry", value=avg_edge),
                BacktestMetric(label="expectancy_per_trade", value=expectancy),
                BacktestMetric(label="drawdown", value=min(net_pnl, 0.0)),
            ],
            notes=[
                "Phase 1 baseline backtester scaffold; full queue/fill model lands in Phase 3.",
                "Net PnL includes a simple fixed cost placeholder for taker fees/slippage.",
            ],
        )
