from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from packages.db import ResearchPersistence
from packages.config import Settings
from packages.core_types.schemas import PaperPosition, PaperSignalSnapshot, PaperTradeDecision, PaperTradingStatus, RiskSettings
from services.backtester.strategies import StrategyContext, build_strategy_registry
from services.feature_engine.service import FeatureEngineService
from services.state import InMemoryState

logger = logging.getLogger(__name__)


class PaperTraderService:
    def __init__(
        self,
        settings: Settings,
        state: InMemoryState,
        feature_engine: FeatureEngineService,
        persistence: ResearchPersistence | None = None,
    ) -> None:
        self._settings = settings
        self._state = state
        self._feature_engine = feature_engine
        self._persistence = persistence
        self._strategy_registry = build_strategy_registry()
        self._strategy_name = settings.paper_trading_strategy
        self._loop_task: asyncio.Task | None = None
        self._last_decision: PaperTradeDecision | None = None
        self._latest_signals: dict[str, PaperSignalSnapshot] = {}
        self._positions: dict[str, PaperPosition] = {}
        self._realized_pnl = 0.0
        self._signal_count = 0
        self._simulated_fill_count = 0
        self._cycle_count = 0
        self._last_update_at: datetime | None = None
        self._loop_error: str | None = None
        self._paper_blotter_hydrated = False

    def reset_state(self) -> None:
        self._last_decision = None
        self._latest_signals.clear()
        self._positions.clear()
        self._realized_pnl = 0.0
        self._signal_count = 0
        self._simulated_fill_count = 0
        self._cycle_count = 0
        self._last_update_at = None
        self._loop_error = None
        self._paper_blotter_hydrated = False

    def blotter(self) -> list[PaperTradeDecision]:
        self._hydrate_blotter_from_persistence()
        return self._state.paper_decisions

    def status(self) -> PaperTradingStatus:
        selected_market_ids = [UUID(market_id) for market_id in self._selected_market_ids()]
        unrealized_pnl = sum(position.unrealized_pnl for position in self._positions.values())
        open_positions = {market_id: position.size if position.side == "buy_yes" else -position.size for market_id, position in self._positions.items()}
        return PaperTradingStatus(
            strategy_name=self._strategy_name,
            dry_run_only=not self._settings.live_execution_enabled,
            active_market_ids=[market.id for market in self._state.markets.values()],
            selected_market_ids=selected_market_ids,
            signal_count=self._signal_count,
            simulated_fill_count=self._simulated_fill_count,
            fill_rate=(self._simulated_fill_count / self._signal_count) if self._signal_count else 0.0,
            open_positions=open_positions,
            position_details=list(self._positions.values()),
            latest_signals=sorted(self._latest_signals.values(), key=lambda item: item.ts, reverse=True),
            last_decision=self._last_decision,
            loop_running=self._loop_task is not None and not self._loop_task.done(),
            last_update_at=self._last_update_at,
            cycle_count=self._cycle_count,
            loop_error=self._loop_error,
            unrealized_pnl=unrealized_pnl,
            realized_pnl=self._realized_pnl,
        )

    def run_once(self, market_id: str) -> PaperTradeDecision:
        return self._evaluate_market(market_id)

    async def start_loop(self) -> None:
        if not self._settings.paper_trading_loop_enabled:
            logger.info("Paper trading loop disabled by config")
            return
        if self._loop_task is not None and not self._loop_task.done():
            return
        logger.info("Starting paper trading loop with strategy=%s interval=%ss", self._strategy_name, self._settings.paper_trading_loop_seconds)
        self._loop_task = asyncio.create_task(self._run_loop(), name="paper-trading-loop")

    async def stop_loop(self) -> None:
        if self._loop_task is None:
            return
        self._loop_task.cancel()
        try:
            await self._loop_task
        except asyncio.CancelledError:
            logger.info("Stopped paper trading loop")
        self._loop_task = None

    async def _run_loop(self) -> None:
        while True:
            try:
                self.run_cycle()
                self._loop_error = None
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._loop_error = str(exc)
                logger.exception("Paper trading loop cycle failed")
            await asyncio.sleep(max(self._settings.paper_trading_loop_seconds, 5))

    def run_cycle(self) -> list[PaperTradeDecision]:
        decisions: list[PaperTradeDecision] = []
        for market_id in self._selected_market_ids():
            decisions.append(self._evaluate_market(market_id))
        self._cycle_count += 1
        self._last_update_at = datetime.now(timezone.utc)
        return decisions

    def _selected_market_ids(self) -> list[str]:
        allowed_underlyings = {
            value.strip().upper()
            for value in self._settings.paper_trading_underlyings.split(",")
            if value.strip()
        }
        allowed_market_types = {
            value.strip()
            for value in self._settings.paper_trading_market_types.split(",")
            if value.strip()
        }
        selected: dict[tuple[str, str], tuple[str, object]] = {}
        for market_id, market in self._state.markets.items():
            if market.status != "active":
                continue
            underlying = (market.underlying or "").upper()
            if allowed_underlyings and underlying not in allowed_underlyings:
                continue
            if allowed_market_types and market.market_type not in allowed_market_types:
                continue
            key = (underlying, market.market_type)
            current = selected.get(key)
            closes_at = market.closes_at or datetime.max.replace(tzinfo=timezone.utc)
            if current is None or (current[1].closes_at or datetime.max.replace(tzinfo=timezone.utc)) > closes_at:
                selected[key] = (market_id, market)
        return [market_id for market_id, _ in selected.values()]

    def _evaluate_market(self, market_id: str) -> PaperTradeDecision:
        snapshot = self._feature_engine.compute_snapshot(market_id)
        strategy = self._strategy_registry[self._strategy_name]
        midpoint = (
            (snapshot.best_bid + snapshot.best_ask) / 2
            if snapshot.best_bid is not None and snapshot.best_ask is not None
            else snapshot.fair_value_estimate or 0.5
        )
        decision = strategy.decide(StrategyContext(market_price=midpoint, feature_snapshot=snapshot))
        self._latest_signals[market_id] = PaperSignalSnapshot(
            market_id=snapshot.market_id,
            ts=snapshot.ts,
            signal_value=decision.signal_value,
            decision=decision.decision,
            confidence=decision.confidence,
            fair_value_gap=snapshot.fair_value_gap,
            midpoint=midpoint,
        )
        self._signal_count += 1
        paper_decision = PaperTradeDecision(
            ts=snapshot.ts,
            market_id=snapshot.market_id,
            action="loop_eval",
            side=decision.decision,
            price=midpoint,
            size=100.0 if decision.decision not in {"hold", "no_trade"} else 0.0,
            status="simulated_fill" if decision.decision not in {"hold", "no_trade"} else "no_action",
            reason=decision.reason,
            signal_value=decision.signal_value,
            confidence=decision.confidence,
        )
        self._apply_decision(paper_decision)
        if paper_decision.status == "simulated_fill":
            self._simulated_fill_count += 1
        self._state.paper_decisions.append(paper_decision)
        self._last_decision = paper_decision
        if self._persistence is not None:
            self._persistence.save_paper_decision(paper_decision, is_dry_run=True)
        return paper_decision

    def _hydrate_blotter_from_persistence(self) -> None:
        if self._paper_blotter_hydrated:
            return
        self._paper_blotter_hydrated = True
        if self._persistence is None or not self._persistence.enabled:
            return
        persisted = self._persistence.list_paper_decisions()
        if not persisted:
            return
        existing = {
            (
                str(decision.market_id),
                decision.ts,
                decision.action,
                decision.side,
                decision.price,
                decision.size,
                decision.status,
            )
            for decision in self._state.paper_decisions
        }
        for decision in persisted:
            key = (
                str(decision.market_id),
                decision.ts,
                decision.action,
                decision.side,
                decision.price,
                decision.size,
                decision.status,
            )
            if key in existing:
                continue
            self._state.paper_decisions.append(decision)

    def _apply_decision(self, decision: PaperTradeDecision) -> None:
        market_key = str(decision.market_id)
        current_position = self._positions.get(market_key)
        if current_position is not None:
            current_position.mark_price = decision.price
            direction = 1.0 if current_position.side == "buy_yes" else -1.0
            current_position.unrealized_pnl = (decision.price - current_position.avg_price) * current_position.size * direction

        if decision.status != "simulated_fill":
            return

        target_side = None
        if decision.side in {"buy_yes", "passive_yes"}:
            target_side = "buy_yes"
        elif decision.side in {"buy_no", "passive_no"}:
            target_side = "buy_no"
        if target_side is None or decision.size <= 0:
            return

        if current_position is not None and current_position.side != target_side:
            self._realized_pnl += current_position.unrealized_pnl
            del self._positions[market_key]
            current_position = None

        if current_position is None:
            self._positions[market_key] = PaperPosition(
                market_id=decision.market_id,
                side=target_side,
                size=decision.size,
                avg_price=decision.price,
                mark_price=decision.price,
                unrealized_pnl=0.0,
                opened_at=decision.ts,
            )
        else:
            blended_notional = (current_position.avg_price * current_position.size) + (decision.price * decision.size)
            current_position.size += decision.size
            current_position.avg_price = blended_notional / current_position.size
            current_position.mark_price = decision.price
            current_position.unrealized_pnl = (
                (decision.price - current_position.avg_price)
                * current_position.size
                * (1.0 if current_position.side == "buy_yes" else -1.0)
            )

    def risk_settings(self) -> RiskSettings:
        return RiskSettings(
            live_execution_enabled=self._settings.live_execution_enabled,
            dry_run_only=not self._settings.live_execution_enabled,
            max_market_exposure_usd=self._settings.max_market_exposure_usd,
            global_kill_switch=True,
        )
