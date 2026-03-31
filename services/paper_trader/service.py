from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from packages.db import ResearchPersistence
from packages.config import Settings
from packages.core_types.schemas import PaperTradeDecision, PaperTradingStatus, RiskSettings
from services.backtester.strategies import StrategyContext, build_strategy_registry
from services.feature_engine.service import FeatureEngineService
from services.state import InMemoryState


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
        self._strategy_name = "combined_cvd_gap"
        self._blotter = [
            PaperTradeDecision(
                ts=datetime(2026, 3, 31, 11, 59, 40, tzinfo=timezone.utc),
                market_id=UUID("6fd5b43f-b7c7-4f63-bf57-3a91e89e8c30"),
                action="submit_order",
                side="buy_yes",
                price=0.54,
                size=250,
                status="simulated_fill",
                reason="Seeded dry-run example decision",
            )
        ]
        self._state.paper_decisions.extend(self._blotter)

    def blotter(self) -> list[PaperTradeDecision]:
        return self._state.paper_decisions or self._blotter

    def status(self) -> PaperTradingStatus:
        active_market_ids = [market.id for market in self._state.markets.values()]
        realized = sum(
            (decision.price - 0.5) * decision.size
            for decision in self.blotter()
            if decision.status == "simulated_fill"
        )
        positions: dict[str, float] = {}
        for decision in self.blotter():
            if decision.side == "buy_yes":
                positions[str(decision.market_id)] = positions.get(str(decision.market_id), 0.0) + decision.size
            elif decision.side == "buy_no":
                positions[str(decision.market_id)] = positions.get(str(decision.market_id), 0.0) - decision.size
        return PaperTradingStatus(
            strategy_name=self._strategy_name,
            dry_run_only=not self._settings.live_execution_enabled,
            active_market_ids=active_market_ids,
            open_positions=positions,
            unrealized_pnl=0.0,
            realized_pnl=realized,
        )

    def run_once(self, market_id: str) -> PaperTradeDecision:
        snapshot = self._feature_engine.compute_snapshot(market_id)
        strategy = self._strategy_registry[self._strategy_name]
        midpoint = (
            (snapshot.best_bid + snapshot.best_ask) / 2
            if snapshot.best_bid is not None and snapshot.best_ask is not None
            else 0.5
        )
        decision = strategy.decide(StrategyContext(market_price=midpoint, feature_snapshot=snapshot))
        paper_decision = PaperTradeDecision(
            ts=snapshot.ts,
            market_id=snapshot.market_id,
            action="strategy_eval",
            side=decision.decision,
            price=midpoint,
            size=100.0 if decision.decision not in {"hold", "no_trade"} else 0.0,
            status="simulated_fill" if decision.decision not in {"hold", "no_trade"} else "no_action",
            reason=decision.reason,
        )
        self._state.paper_decisions.append(paper_decision)
        if self._persistence is not None:
            self._persistence.save_paper_decision(paper_decision, is_dry_run=True)
        return paper_decision

    def risk_settings(self) -> RiskSettings:
        return RiskSettings(
            live_execution_enabled=self._settings.live_execution_enabled,
            dry_run_only=not self._settings.live_execution_enabled,
            max_market_exposure_usd=self._settings.max_market_exposure_usd,
            global_kill_switch=True,
        )
