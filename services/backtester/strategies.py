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


class FlowAlignment5mStrategy(BaseStrategy):
    descriptor = StrategyDescriptor(
        name="flow_alignment_5m",
        family="cross_venue",
        description="Trades 5-minute-style flow alignment when fair value and venue flow agree near the strike.",
        configurable_fields=["min_alignment", "max_spread_bps", "max_distance_to_threshold_bps"],
    )

    def decide(self, context: StrategyContext) -> StrategyDecision:
        snapshot = context.feature_snapshot
        alignment = snapshot.flow_alignment_score or 0.0
        spread_bps = snapshot.spread_bps
        distance_bps = abs(snapshot.distance_to_threshold_bps) if snapshot.distance_to_threshold_bps is not None else None
        time_to_close = snapshot.time_to_close_seconds

        if time_to_close is not None and time_to_close > 390:
            return self._hold(alignment, "Waiting for the final 5-minute decision window", snapshot)
        if spread_bps is not None and spread_bps > 300:
            return self._hold(alignment, "Spread too wide for short-horizon flow entry", snapshot)
        if distance_bps is not None and distance_bps > 60:
            return self._hold(alignment, "Underlying is too far from the strike for the flow setup", snapshot)
        if (
            snapshot.external_flow_signal is not None
            and snapshot.polymarket_flow_signal is not None
            and snapshot.external_flow_signal * snapshot.polymarket_flow_signal < -0.12
        ):
            return self._hold(alignment, "External and Polymarket flow disagree materially", snapshot)
        if abs(alignment) < 0.32:
            return self._hold(alignment, "Flow alignment is too weak", snapshot)

        decision = "buy_yes" if alignment > 0 else "buy_no"
        confidence = min(0.55 + abs(alignment) * 0.35, 0.97)
        return StrategyDecision(
            signal_value=alignment,
            decision=decision,
            confidence=confidence,
            reason="Short-horizon flow, fair-value gap, and strike proximity are aligned",
            reasoning_fields=_flow_reasoning_fields(snapshot, alignment),
        )

    def _hold(self, alignment: float, reason: str, snapshot: FeatureSnapshot) -> StrategyDecision:
        return StrategyDecision(
            signal_value=alignment,
            decision="hold",
            confidence=min(abs(alignment), 0.9),
            reason=reason,
            reasoning_fields=_flow_reasoning_fields(snapshot, alignment),
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
        FlowAlignment5mStrategy(),
        PassiveQuoteStrategy(),
    ]
    return {strategy.descriptor.name: strategy for strategy in strategies}


def _flow_reasoning_fields(snapshot: FeatureSnapshot, alignment: float) -> dict[str, float | str | None]:
    return {
        "flow_alignment_score": alignment,
        "external_flow_signal": snapshot.external_flow_signal,
        "polymarket_flow_signal": snapshot.polymarket_flow_signal,
        "fair_value_gap": snapshot.fair_value_gap,
        "spread_bps": snapshot.spread_bps,
        "distance_to_threshold_bps": snapshot.distance_to_threshold_bps,
        "time_to_close_seconds": snapshot.time_to_close_seconds,
    }
