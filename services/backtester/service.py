from __future__ import annotations

from datetime import datetime, timezone

from packages.db import ResearchPersistence
from packages.core_types.schemas import BacktestMetric, BacktestReport
from services.feature_engine.service import FeatureEngineService
from services.state import InMemoryState
from services.backtester.strategies import BaseStrategy, StrategyContext, build_strategy_registry


class BacktesterService:
    def __init__(
        self,
        state: InMemoryState,
        feature_engine: FeatureEngineService,
        persistence: ResearchPersistence | None = None,
        strategy_registry: dict[str, BaseStrategy] | None = None,
    ) -> None:
        self._state = state
        self._feature_engine = feature_engine
        self._persistence = persistence
        self._strategy_registry = strategy_registry or build_strategy_registry()

    def list_strategies(self):
        return [strategy.descriptor for strategy in self._strategy_registry.values()]

    def list_reports(self) -> list[BacktestReport]:
        reports = list(self._state.backtest_reports)
        if self._persistence is not None and self._persistence.enabled:
            persisted = self._persistence.list_backtest_reports()
            merged = {report.run_id: report for report in reports}
            for report in persisted:
                merged.setdefault(report.run_id, report)
            reports = list(merged.values())
        return sorted(reports, key=lambda report: report.created_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    def run_baseline(self, market_id: str, strategy_name: str = "no_trade_baseline") -> BacktestReport:
        market = self._state.markets.get(market_id)
        if market is None:
            raise KeyError(f"Unknown market_id={market_id}")
        strategy = self._strategy_registry[strategy_name]
        snapshot = self._feature_engine.compute_snapshot(market_id)
        market_price = snapshot.fair_value_estimate if snapshot.fair_value_estimate is not None else (
            (snapshot.best_bid + snapshot.best_ask) / 2 if snapshot.best_bid is not None and snapshot.best_ask is not None else None
        )
        decision = strategy.decide(StrategyContext(market_price=market_price, feature_snapshot=snapshot))
        avg_edge = snapshot.fair_value_gap or 0.0
        gross_pnl = 0.0
        trade_count = 0
        if decision.decision not in {"hold", "no_trade"}:
            trade_count = 1
            side_multiplier = 1 if decision.decision in {"buy_yes", "passive_yes"} else -1
            gross_pnl = side_multiplier * avg_edge * 1000.0
        spread_cost = (snapshot.spread or 0.0) * 100.0 if trade_count else 0.0
        fee_cost = 1.0 if trade_count else 0.0
        slippage_cost = max(abs(decision.signal_value) * 0.2, 0.25) if trade_count else 0.0
        net_pnl = gross_pnl - spread_cost - fee_cost - slippage_cost
        expectancy = net_pnl / trade_count if trade_count else 0.0
        hit_rate = 1.0 if net_pnl > 0 and trade_count else 0.0
        report = BacktestReport(
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
                BacktestMetric(label="spread_cost", value=spread_cost),
                BacktestMetric(label="fee_cost", value=fee_cost),
                BacktestMetric(label="slippage_cost", value=slippage_cost),
            ],
            created_at=datetime.now(timezone.utc),
            trade_count=trade_count,
            decisions=[decision],
            notes=[
                "Event-driven skeleton using point-in-time feature snapshots and strategy callbacks.",
                "Queue position and latency remain approximate placeholders pending the full execution simulator.",
            ],
        )
        self._state.backtest_reports = [existing for existing in self._state.backtest_reports if existing.run_id != report.run_id]
        self._state.backtest_reports.insert(0, report)
        if self._persistence is not None:
            self._persistence.save_backtest_report(report)
        return report
