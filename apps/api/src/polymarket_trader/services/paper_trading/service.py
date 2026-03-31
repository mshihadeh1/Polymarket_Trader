from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from polymarket_trader.domain.schemas import PaperTradeDecisionSchema, RiskSettingsSchema


class PaperTradingService:
    def __init__(self) -> None:
        self._blotter = [
            PaperTradeDecisionSchema(
                ts=datetime(2026, 3, 31, 11, 59, 40, tzinfo=timezone.utc),
                market_id=UUID("6fd5b43f-b7c7-4f63-bf57-3a91e89e8c30"),
                action="submit_order",
                side="buy_yes",
                price=0.54,
                size=250,
                status="simulated_fill",
            )
        ]

    def blotter(self) -> list[PaperTradeDecisionSchema]:
        return self._blotter

    def risk_settings(self, live_execution_enabled: bool) -> RiskSettingsSchema:
        return RiskSettingsSchema(
            live_execution_enabled=live_execution_enabled,
            dry_run_only=not live_execution_enabled,
            max_market_exposure_usd=500.0,
            global_kill_switch=True,
        )
