from __future__ import annotations

from dataclasses import dataclass

from packages.core_types import MinuteFeatureSnapshot, StrategyDecision, StrategyDescriptor


@dataclass(frozen=True)
class MinuteStrategyContext:
    feature_snapshot: MinuteFeatureSnapshot


class MinuteBaseStrategy:
    descriptor: StrategyDescriptor

    def decide(self, context: MinuteStrategyContext) -> StrategyDecision:
        raise NotImplementedError


class MinuteMomentumStrategy(MinuteBaseStrategy):
    descriptor = StrategyDescriptor(
        name="minute_momentum",
        family="minute_momentum",
        description="Follow short-horizon momentum using recent returns and acceleration.",
        configurable_fields=["threshold"],
    )

    def decide(self, context: MinuteStrategyContext) -> StrategyDecision:
        feature = context.feature_snapshot
        signal = (
            (feature.ret_1m or 0.0) * 3.0
            + (feature.ret_3m or 0.0) * 2.0
            + (feature.acceleration or 0.0) * 4.0
            + _trend_bonus(feature.regime)
        )
        decision = _decision_from_signal(signal, threshold=0.0012)
        return StrategyDecision(
            signal_value=signal,
            decision=decision,
            confidence=min(abs(signal) * 12.0, 0.98),
            reason="Momentum continuation on point-in-time minute features",
            reasoning_fields={
                "ret_1m": feature.ret_1m,
                "ret_3m": feature.ret_3m,
                "acceleration": feature.acceleration,
                "regime": feature.regime,
            },
        )


class MinuteMeanReversionStrategy(MinuteBaseStrategy):
    descriptor = StrategyDescriptor(
        name="minute_mean_reversion",
        family="minute_mean_reversion",
        description="Fade moves away from the rolling mean when price is stretched.",
        configurable_fields=["threshold"],
    )

    def decide(self, context: MinuteStrategyContext) -> StrategyDecision:
        feature = context.feature_snapshot
        signal = 0.0
        if feature.distance_from_mean is not None:
            signal -= feature.distance_from_mean * 2.5
        if feature.range_percentile is not None:
            signal += (0.5 - feature.range_percentile) * 1.8
        decision = _decision_from_signal(signal, threshold=0.001)
        return StrategyDecision(
            signal_value=signal,
            decision=decision,
            confidence=min(abs(signal) * 14.0, 0.96),
            reason="Mean reversion against rolling mean and recent range",
            reasoning_fields={
                "distance_from_mean": feature.distance_from_mean,
                "range_percentile": feature.range_percentile,
                "regime": feature.regime,
            },
        )


class MinuteBreakoutStrategy(MinuteBaseStrategy):
    descriptor = StrategyDescriptor(
        name="minute_breakout",
        family="minute_breakout",
        description="Trade directional breakouts when volatility expands.",
        configurable_fields=["threshold"],
    )

    def decide(self, context: MinuteStrategyContext) -> StrategyDecision:
        feature = context.feature_snapshot
        volatility = (feature.vol_5m or 0.0) + (feature.vol_15m or 0.0)
        momentum = (feature.ret_1m or 0.0) + (feature.ret_3m or 0.0) + (feature.ret_5m or 0.0)
        signal = volatility * momentum * 12.0
        if feature.regime in {"choppy", "unknown"} and abs(signal) < 0.001:
            decision = "hold"
        else:
            decision = _decision_from_signal(signal, threshold=0.0012)
        return StrategyDecision(
            signal_value=signal,
            decision=decision,
            confidence=min(abs(signal) * 18.0, 0.94),
            reason="Volatility breakout on minute-level trend expansion",
            reasoning_fields={
                "vol_5m": feature.vol_5m,
                "vol_15m": feature.vol_15m,
                "ret_1m": feature.ret_1m,
                "ret_3m": feature.ret_3m,
                "ret_5m": feature.ret_5m,
            },
        )


class MinuteRegimeFilterStrategy(MinuteBaseStrategy):
    descriptor = StrategyDescriptor(
        name="minute_regime_filter",
        family="minute_regime_filter",
        description="Only act when the minute regime is directional enough.",
        configurable_fields=["threshold"],
    )

    def decide(self, context: MinuteStrategyContext) -> StrategyDecision:
        feature = context.feature_snapshot
        regime = (feature.regime or "unknown").lower()
        if regime in {"uptrend", "strong_uptrend"}:
            signal = (feature.ret_1m or 0.0) + (feature.ret_5m or 0.0)
        elif regime in {"downtrend", "strong_downtrend"}:
            signal = -((feature.ret_1m or 0.0) + (feature.ret_5m or 0.0))
        else:
            signal = 0.0
        decision = _decision_from_signal(signal, threshold=0.0012)
        if regime in {"sideways", "choppy", "unknown"}:
            decision = "hold"
        return StrategyDecision(
            signal_value=signal,
            decision=decision,
            confidence=min(abs(signal) * 14.0, 0.9),
            reason="Regime filter for directional minutes only",
            reasoning_fields={
                "regime": feature.regime,
                "ret_1m": feature.ret_1m,
                "ret_5m": feature.ret_5m,
            },
        )


def build_minute_strategy_registry() -> dict[str, MinuteBaseStrategy]:
    strategies: list[MinuteBaseStrategy] = [
        MinuteMomentumStrategy(),
        MinuteMeanReversionStrategy(),
        MinuteBreakoutStrategy(),
        MinuteRegimeFilterStrategy(),
    ]
    return {strategy.descriptor.name: strategy for strategy in strategies}


def _decision_from_signal(signal: float, *, threshold: float) -> str:
    if signal > threshold:
        return "higher"
    if signal < -threshold:
        return "lower"
    return "hold"


def _trend_bonus(regime: str) -> float:
    normalized = (regime or "").lower()
    if normalized in {"strong_uptrend", "uptrend"}:
        return 0.001
    if normalized in {"strong_downtrend", "downtrend"}:
        return -0.001
    return 0.0
