from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from packages.config import Settings
from packages.core_types.schemas import PaperTradeDecision, RiskSettings


class PaperTraderService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
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

    def blotter(self) -> list[PaperTradeDecision]:
        return self._blotter

    def risk_settings(self) -> RiskSettings:
        return RiskSettings(
            live_execution_enabled=self._settings.live_execution_enabled,
            dry_run_only=not self._settings.live_execution_enabled,
            max_market_exposure_usd=self._settings.max_market_exposure_usd,
            global_kill_switch=True,
        )
