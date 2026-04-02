from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Awaitable, Callable
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
        market_refresh_callback: Callable[[], Awaitable[int]] | None = None,
        persistence: ResearchPersistence | None = None,
    ) -> None:
        self._settings = settings
        self._state = state
        self._feature_engine = feature_engine
        self._market_refresh_callback = market_refresh_callback
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
        self._blocked_signal_count = 0
        self._market_refresh_count = 0
        self._last_market_refresh_at: datetime | None = None
        self._last_market_refresh_error: str | None = None
        self._cycle_count = 0
        self._last_update_at: datetime | None = None
        self._loop_error: str | None = None
        self._paper_blotter_hydrated = False
        self._executed_market_windows: set[str] = set()

    def reset_state(self) -> None:
        self._last_decision = None
        self._latest_signals.clear()
        self._positions.clear()
        self._realized_pnl = 0.0
        self._signal_count = 0
        self._simulated_fill_count = 0
        self._blocked_signal_count = 0
        self._market_refresh_count = 0
        self._last_market_refresh_at = None
        self._last_market_refresh_error = None
        self._cycle_count = 0
        self._last_update_at = None
        self._loop_error = None
        self._paper_blotter_hydrated = False
        self._executed_market_windows.clear()

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
            blocked_signal_count=self._blocked_signal_count,
            market_refresh_count=self._market_refresh_count,
            last_market_refresh_at=self._last_market_refresh_at,
            last_market_refresh_error=self._last_market_refresh_error,
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
                await self._maybe_refresh_markets()
                self.run_cycle()
                self._loop_error = None
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._loop_error = str(exc)
                logger.exception("Paper trading loop cycle failed")
            await asyncio.sleep(max(self._settings.paper_trading_loop_seconds, 5))

    def run_cycle(self) -> list[PaperTradeDecision]:
        self._settle_expired_positions()
        decisions: list[PaperTradeDecision] = []
        for market_id in self._selected_market_ids():
            decisions.append(self._evaluate_market(market_id))
        self._cycle_count += 1
        self._last_update_at = datetime.now(timezone.utc)
        return decisions

    async def refresh_markets(self) -> int:
        if not self._settings.paper_trading_market_refresh_enabled or self._market_refresh_callback is None:
            return 0
        try:
            count = await self._market_refresh_callback()
        except Exception as exc:
            self._last_market_refresh_error = str(exc)
            logger.exception("Paper market refresh failed")
            return 0
        self._market_refresh_count += 1
        self._last_market_refresh_at = datetime.now(timezone.utc)
        self._last_market_refresh_error = None
        return count

    def _selected_market_ids(self) -> list[str]:
        selected = self._select_market_ids(enforce_time_guard=True)
        if selected:
            return selected
        if self._settings.paper_trading_market_refresh_enabled and self._market_refresh_callback is not None:
            return selected
        return self._select_market_ids(enforce_time_guard=False)

    def _select_market_ids(self, *, enforce_time_guard: bool) -> list[str]:
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
        now = datetime.now(timezone.utc)
        for market_id, market in self._state.markets.items():
            if market.status != "active":
                continue
            if enforce_time_guard and market.closes_at is not None and market.closes_at <= now:
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
        market = self._state.market_details[market_id]
        snapshot = self._feature_engine.compute_snapshot(market_id)
        strategy = self._strategy_registry[self._strategy_name]
        midpoint = (
            (snapshot.best_bid + snapshot.best_ask) / 2
            if snapshot.best_bid is not None and snapshot.best_ask is not None
            else snapshot.fair_value_estimate or 0.5
        )
        decision = strategy.decide(StrategyContext(market_price=midpoint, feature_snapshot=snapshot))
        market_window_id = _market_window_id(market_id, market.closes_at)
        blocked_reason = self._paper_block_reason(decision, snapshot, market_window_id=market_window_id)
        executed = blocked_reason is None and decision.decision not in {"hold", "no_trade"}
        execution_price = _execution_price(decision.decision, midpoint, snapshot.spread)
        self._latest_signals[market_id] = PaperSignalSnapshot(
            market_id=snapshot.market_id,
            ts=snapshot.ts,
            signal_value=decision.signal_value,
            decision=decision.decision,
            confidence=decision.confidence,
            reason=decision.reason,
            fair_value_gap=snapshot.fair_value_gap,
            midpoint=midpoint,
            execution_price=execution_price,
            market_window_id=market_window_id,
            flow_alignment_score=snapshot.flow_alignment_score,
            external_flow_signal=snapshot.external_flow_signal,
            polymarket_flow_signal=snapshot.polymarket_flow_signal,
            spread_bps=snapshot.spread_bps,
            distance_to_threshold_bps=snapshot.distance_to_threshold_bps,
            time_to_close_seconds=snapshot.time_to_close_seconds,
            executed=executed,
            blocked_reason=blocked_reason,
        )
        self._signal_count += 1
        if blocked_reason is not None:
            self._blocked_signal_count += 1
        reason = decision.reason if blocked_reason is None else f"{decision.reason} | blocked: {blocked_reason}"
        paper_decision = PaperTradeDecision(
            ts=snapshot.ts,
            market_id=snapshot.market_id,
            action="loop_eval",
            side=decision.decision,
            price=execution_price if executed else midpoint,
            size=100.0 if executed else 0.0,
            status="simulated_fill" if executed else "no_action",
            reason=reason,
            signal_value=decision.signal_value,
            confidence=decision.confidence,
        )
        self._apply_decision(paper_decision)
        if paper_decision.status == "simulated_fill":
            self._simulated_fill_count += 1
            self._executed_market_windows.add(market_window_id)
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

    def _paper_block_reason(self, decision, snapshot, *, market_window_id: str) -> str | None:
        if decision.decision in {"hold", "no_trade"}:
            return None
        if decision.confidence < self._settings.paper_trading_min_confidence:
            return f"confidence_below_threshold({self._settings.paper_trading_min_confidence:.2f})"
        if (
            self._settings.paper_trading_single_fill_per_window
            and market_window_id in self._executed_market_windows
        ):
            return "single_fill_per_window_guard"
        if snapshot.spread_bps is not None and snapshot.spread_bps > 300:
            return "spread_guard"
        return None

    async def _maybe_refresh_markets(self) -> None:
        if not self._settings.paper_trading_market_refresh_enabled or self._market_refresh_callback is None:
            return
        if self._settings.paper_trading_market_refresh_cycles <= 0:
            return
        if self._cycle_count > 0 and self._cycle_count % self._settings.paper_trading_market_refresh_cycles != 0:
            return
        await self.refresh_markets()

    def _settle_expired_positions(self) -> None:
        now = datetime.now(timezone.utc)
        for market_key, position in list(self._positions.items()):
            market = self._state.market_details.get(market_key)
            if market is None or market.closes_at is None or market.closes_at > now:
                continue
            settlement_price, settlement_reason = self._resolve_settlement_price(market_key, market)
            realized = (settlement_price - position.avg_price) * position.size * (
                1.0 if position.side == "buy_yes" else -1.0
            )
            self._realized_pnl += realized
            market.status = "closed"
            summary = self._state.markets.get(market_key)
            if summary is not None:
                summary.status = "closed"
            settlement_decision = PaperTradeDecision(
                ts=now,
                market_id=position.market_id,
                action="auto_settle",
                side=position.side,
                price=settlement_price,
                size=position.size,
                status="settled",
                reason=settlement_reason,
                signal_value=None,
                confidence=None,
            )
            self._state.paper_decisions.append(settlement_decision)
            if self._persistence is not None:
                self._persistence.save_paper_decision(settlement_decision, is_dry_run=True)
            del self._positions[market_key]

    def _resolve_settlement_price(self, market_id: str, market) -> tuple[float, str]:
        try:
            snapshot = self._feature_engine.compute_snapshot(market_id, as_of=market.closes_at)
        except KeyError:
            snapshot = None
        if snapshot is not None and snapshot.distance_to_threshold is not None:
            settlement_price = 1.0 if snapshot.distance_to_threshold > 0 else 0.0
            return settlement_price, "Auto-settled from external close versus strike"
        position = self._positions.get(market_id)
        fallback = position.mark_price if position is not None else 0.5
        return fallback, "Auto-settled from last available mark"


def _market_window_id(market_id: str, closes_at: datetime | None) -> str:
    if closes_at is None:
        return market_id
    return f"{market_id}:{closes_at.isoformat()}"


def _execution_price(decision: str, midpoint: float, spread: float | None) -> float:
    half_spread = (spread or 0.0) / 2.0
    if decision in {"buy_yes", "passive_no"}:
        return _clamp_probability(midpoint + half_spread)
    if decision in {"buy_no", "passive_yes"}:
        return _clamp_probability(midpoint - half_spread)
    return _clamp_probability(midpoint)


def _clamp_probability(value: float) -> float:
    return max(0.01, min(0.99, value))
