from __future__ import annotations

from datetime import datetime, timezone

from packages.config import Settings
from packages.db import ResearchPersistence
from packages.core_types.schemas import BacktestMetric, BacktestReport, BacktestTrade, EquityPoint
from services.feature_engine.service import FeatureEngineService
from services.state import InMemoryState
from services.backtester.strategies import BaseStrategy, StrategyContext, build_strategy_registry


class BacktesterService:
    def __init__(
        self,
        settings: Settings,
        state: InMemoryState,
        feature_engine: FeatureEngineService,
        persistence: ResearchPersistence | None = None,
        strategy_registry: dict[str, BaseStrategy] | None = None,
    ) -> None:
        self._settings = settings
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
        bars = self._state.external_bars.get(market_id, [])
        if not bars:
            raise ValueError(f"No external bar history loaded for market_id={market_id}")
        strategy = self._strategy_registry[strategy_name]

        position = 0.0
        entry_price: float | None = None
        realized_pnl = 0.0
        trades: list[BacktestTrade] = []
        equity_curve: list[EquityPoint] = []
        decisions = []
        peak_equity = 0.0
        max_drawdown = 0.0

        size = self._settings.backtest_position_size
        fee_rate = self._settings.backtest_fee_bps / 10_000
        slippage_rate = self._settings.backtest_slippage_bps / 10_000

        for bar in bars:
            snapshot = self._feature_engine.compute_snapshot(market_id, as_of=bar.ts)
            mark_price = self._mark_price(snapshot, bar.close)
            decision = strategy.decide(StrategyContext(market_price=mark_price, feature_snapshot=snapshot))
            decisions.append(decision)

            target_position = self._target_position(decision.decision, current_position=position)
            if target_position != position:
                realized_pnl, entry_price = self._rebalance_position(
                    market_id=market.id,
                    ts=bar.ts,
                    position=position,
                    target_position=target_position,
                    mark_price=mark_price,
                    entry_price=entry_price,
                    realized_pnl=realized_pnl,
                    size=size,
                    fee_rate=fee_rate,
                    slippage_rate=slippage_rate,
                    reason=decision.reason,
                    trades=trades,
                )
                position = target_position

            unrealized = 0.0
            if position != 0.0 and entry_price is not None:
                unrealized = (mark_price - entry_price) * size * position
            equity = realized_pnl + unrealized
            peak_equity = max(peak_equity, equity)
            max_drawdown = min(max_drawdown, equity - peak_equity)
            equity_curve.append(
                EquityPoint(
                    ts=bar.ts,
                    equity=equity,
                    realized_pnl=realized_pnl,
                    unrealized_pnl=unrealized,
                    position=position,
                )
            )

        if position != 0.0 and entry_price is not None:
            final_bar = bars[-1]
            final_snapshot = self._feature_engine.compute_snapshot(market_id, as_of=final_bar.ts)
            final_price = self._mark_price(final_snapshot, final_bar.close)
            realized_pnl, entry_price = self._close_position(
                market_id=market.id,
                ts=final_bar.ts,
                position=position,
                mark_price=final_price,
                entry_price=entry_price,
                realized_pnl=realized_pnl,
                size=size,
                fee_rate=fee_rate,
                slippage_rate=slippage_rate,
                reason="Forced close at end of historical replay",
                trades=trades,
            )
            position = 0.0
            if equity_curve:
                equity_curve[-1] = EquityPoint(
                    ts=final_bar.ts,
                    equity=realized_pnl,
                    realized_pnl=realized_pnl,
                    unrealized_pnl=0.0,
                    position=0.0,
                )

        gross_pnl = sum(trade.gross_pnl for trade in trades)
        net_pnl = sum(trade.net_pnl for trade in trades)
        total_cost = sum(trade.cost for trade in trades)
        trade_count = len(trades)
        winning_trades = sum(1 for trade in trades if trade.net_pnl > 0)
        expectancy = net_pnl / trade_count if trade_count else 0.0
        avg_edge = (
            sum((decision.reasoning_fields.get("fair_value_gap") or 0.0) for decision in decisions) / len(decisions)
            if decisions else 0.0
        )

        report = BacktestReport(
            run_id=f"{strategy_name}:{market_id}:{int(datetime.now(timezone.utc).timestamp())}",
            strategy_name=strategy_name,
            market_id=market.id,
            metrics=[
                BacktestMetric(label="gross_pnl", value=gross_pnl),
                BacktestMetric(label="net_pnl", value=net_pnl),
                BacktestMetric(label="hit_rate", value=(winning_trades / trade_count) if trade_count else 0.0),
                BacktestMetric(label="avg_edge_at_entry", value=avg_edge),
                BacktestMetric(label="expectancy_per_trade", value=expectancy),
                BacktestMetric(label="drawdown", value=max_drawdown),
                BacktestMetric(label="total_explicit_cost", value=total_cost),
                BacktestMetric(label="bar_count", value=float(len(bars))),
            ],
            created_at=datetime.now(timezone.utc),
            trade_count=trade_count,
            decisions=decisions[-250:],
            trades=trades,
            equity_curve=equity_curve,
            notes=[
                "Sequential 1-minute replay over normalized external bars.",
                "Execution uses explicit simple costs and dry-run mark-price approximations when Polymarket history is unavailable.",
            ],
        )
        self._state.backtest_reports.insert(0, report)
        if self._persistence is not None:
            self._persistence.save_backtest_report(report)
        return report

    def _mark_price(self, snapshot, fallback_close: float) -> float:
        if snapshot.best_bid is not None and snapshot.best_ask is not None:
            return (snapshot.best_bid + snapshot.best_ask) / 2
        if snapshot.fair_value_estimate is not None:
            return snapshot.fair_value_estimate
        return min(max(0.5 + (snapshot.external_return_since_open or 0.0) * 4, 0.01), 0.99) if fallback_close else 0.5

    def _target_position(self, decision: str, current_position: float) -> float:
        if decision in {"buy_yes", "passive_yes"}:
            return 1.0
        if decision in {"buy_no", "passive_no"}:
            return -1.0
        return current_position

    def _rebalance_position(
        self,
        market_id,
        ts,
        position,
        target_position,
        mark_price,
        entry_price,
        realized_pnl,
        size,
        fee_rate,
        slippage_rate,
        reason,
        trades,
    ):
        updated_realized = realized_pnl
        updated_entry = entry_price
        if position != 0.0 and entry_price is not None:
            updated_realized, updated_entry = self._close_position(
                market_id=market_id,
                ts=ts,
                position=position,
                mark_price=mark_price,
                entry_price=entry_price,
                realized_pnl=updated_realized,
                size=size,
                fee_rate=fee_rate,
                slippage_rate=slippage_rate,
                reason=reason,
                trades=trades,
            )
        if target_position != 0.0:
            cost = mark_price * size * (fee_rate + slippage_rate)
            trades.append(
                BacktestTrade(
                    ts=ts,
                    market_id=market_id,
                    action="open_long" if target_position > 0 else "open_short",
                    side="buy_yes" if target_position > 0 else "buy_no",
                    price=mark_price,
                    size=size,
                    gross_pnl=0.0,
                    net_pnl=-cost,
                    cost=cost,
                    reason=reason,
                )
            )
            updated_realized -= cost
            updated_entry = mark_price
        return updated_realized, updated_entry

    def _close_position(
        self,
        market_id,
        ts,
        position,
        mark_price,
        entry_price,
        realized_pnl,
        size,
        fee_rate,
        slippage_rate,
        reason,
        trades,
    ):
        gross_pnl = (mark_price - entry_price) * size * position
        cost = mark_price * size * (fee_rate + slippage_rate)
        net_pnl = gross_pnl - cost
        trades.append(
            BacktestTrade(
                ts=ts,
                market_id=market_id,
                action="close_long" if position > 0 else "close_short",
                side="buy_yes" if position > 0 else "buy_no",
                price=mark_price,
                size=size,
                gross_pnl=gross_pnl,
                net_pnl=net_pnl,
                cost=cost,
                reason=reason,
            )
        )
        return realized_pnl + net_pnl, None
