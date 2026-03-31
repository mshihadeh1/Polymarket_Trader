from __future__ import annotations

from dataclasses import dataclass

from packages.core_types.schemas import FeatureSnapshot, StrategyDecision, StrategyDescriptor


@dataclass(frozen=True)
class StrategyContext:
    market_price: float | None
    feature_snapshot: FeatureSnapshot


class BaseStrategy:
    descriptor: StrategyDescriptor

    def decide(self, context: StrategyContext) -> StrategyDecision:
        raise NotImplementedError


class NoTradeStrategy(BaseStrategy):
    descriptor = StrategyDescriptor(
        name="no_trade_baseline",
        family="baseline",
        description="Control strategy that never trades.",
        configurable_fields=[],
    )

    def decide(self, context: StrategyContext) -> StrategyDecision:
        return StrategyDecision(
            signal_value=0.0,
            decision="no_trade",
            confidence=1.0,
            reason="Baseline control run",
        )


class LocalCvdStrategy(BaseStrategy):
    descriptor = StrategyDescriptor(
        name="local_cvd_only",
        family="microstructure",
        description="Trades only when local Polymarket CVD is materially one-sided.",
        configurable_fields=["min_abs_cvd"],
    )

    def decide(self, context: StrategyContext) -> StrategyDecision:
        cvd = context.feature_snapshot.polymarket_cvd
        if cvd > 500:
            decision = "buy_yes"
        elif cvd < -500:
            decision = "buy_no"
        else:
            decision = "hold"
        return StrategyDecision(
            signal_value=cvd,
            decision=decision,
            confidence=min(abs(cvd) / 2000, 0.95),
            reason="Local CVD threshold rule",
            reasoning_fields={"polymarket_cvd": cvd},
        )


class HyperliquidCvdStrategy(BaseStrategy):
    descriptor = StrategyDescriptor(
        name="hyperliquid_cvd_only",
        family="external_microstructure",
        description="Trades only when Hyperliquid CVD strongly favors one side.",
        configurable_fields=["min_abs_cvd"],
    )

    def decide(self, context: StrategyContext) -> StrategyDecision:
        cvd = context.feature_snapshot.external_cvd
        if cvd > 0.5:
            decision = "buy_yes"
        elif cvd < -0.5:
            decision = "buy_no"
        else:
            decision = "hold"
        return StrategyDecision(
            signal_value=cvd,
            decision=decision,
            confidence=min(abs(cvd), 0.95),
            reason="External CVD threshold rule",
            reasoning_fields={"external_cvd": cvd},
        )


class CombinedFlowStrategy(BaseStrategy):
    descriptor = StrategyDescriptor(
        name="combined_cvd_gap",
        family="cross_venue",
        description="Combines local flow, external flow, and fair-value gap.",
        configurable_fields=["min_gap", "min_confidence"],
    )

    def decide(self, context: StrategyContext) -> StrategyDecision:
        snapshot = context.feature_snapshot
        composite = (
            (snapshot.fair_value_gap or 0.0) * 10
            + snapshot.polymarket_trade_imbalance
            + snapshot.external_trade_imbalance
        )
        if composite > 0.2:
            decision = "buy_yes"
        elif composite < -0.2:
            decision = "buy_no"
        else:
            decision = "hold"
        return StrategyDecision(
            signal_value=composite,
            decision=decision,
            confidence=min(abs(composite), 0.99),
            reason="Combined flow and fair-value gap score",
            reasoning_fields={
                "fair_value_gap": snapshot.fair_value_gap,
                "polymarket_imbalance": snapshot.polymarket_trade_imbalance,
                "external_imbalance": snapshot.external_trade_imbalance,
            },
        )


class PassiveQuoteStrategy(BaseStrategy):
    descriptor = StrategyDescriptor(
        name="passive_quote_prototype",
        family="maker",
        description="Prototype passive quoting strategy when fair-value gap and spread justify resting liquidity.",
        configurable_fields=["min_spread", "min_gap"],
    )

    def decide(self, context: StrategyContext) -> StrategyDecision:
        spread = context.feature_snapshot.spread or 0.0
        gap = context.feature_snapshot.fair_value_gap or 0.0
        if spread >= 0.02 and gap > 0:
            decision = "passive_yes"
        elif spread >= 0.02 and gap < 0:
            decision = "passive_no"
        else:
            decision = "hold"
        return StrategyDecision(
            signal_value=gap,
            decision=decision,
            confidence=min(abs(gap) * 8, 0.85),
            reason="Passive quote prototype using spread and fair-value gap",
            reasoning_fields={"spread": spread, "fair_value_gap": gap},
        )


def build_strategy_registry() -> dict[str, BaseStrategy]:
    strategies: list[BaseStrategy] = [
        NoTradeStrategy(),
        LocalCvdStrategy(),
        HyperliquidCvdStrategy(),
        CombinedFlowStrategy(),
        PassiveQuoteStrategy(),
    ]
    return {strategy.descriptor.name: strategy for strategy in strategies}
