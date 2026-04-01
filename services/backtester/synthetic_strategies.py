from __future__ import annotations

from dataclasses import dataclass

from packages.core_types import StrategyDecision, StrategyDescriptor, SyntheticFeatureSnapshot


@dataclass(frozen=True)
class SyntheticStrategyContext:
    feature_snapshot: SyntheticFeatureSnapshot


class SyntheticBaseStrategy:
    descriptor: StrategyDescriptor

    def decide(self, context: SyntheticStrategyContext) -> StrategyDecision:
        raise NotImplementedError


class SyntheticMomentumStrategy(SyntheticBaseStrategy):
    descriptor = StrategyDescriptor(
        name="synthetic_momentum",
        family="synthetic_momentum",
        description="Follow short-horizon momentum when recent returns and trend regime agree.",
        configurable_fields=["min_signal"],
    )

    def decide(self, context: SyntheticStrategyContext) -> StrategyDecision:
        feature = context.feature_snapshot
        signal = (
            (feature.prior_return_1m or 0.0) * 3.0
            + (feature.prior_return_3m or 0.0) * 2.0
            + (feature.acceleration or 0.0) * 4.0
        )
        decision = _decision_from_signal(signal, threshold=0.0015)
        return StrategyDecision(
            signal_value=signal,
            decision=decision,
            confidence=min(abs(signal) * 12.0, 0.98),
            reason="Momentum continuation on prior short-horizon returns",
            reasoning_fields={
                "prior_return_1m": feature.prior_return_1m,
                "prior_return_3m": feature.prior_return_3m,
                "acceleration": feature.acceleration,
                "trend_regime": feature.trend_regime,
            },
        )


class SyntheticMeanReversionStrategy(SyntheticBaseStrategy):
    descriptor = StrategyDescriptor(
        name="synthetic_mean_reversion",
        family="synthetic_mean_reversion",
        description="Fade moves away from the rolling mean when the range position is extreme.",
        configurable_fields=["min_signal"],
    )

    def decide(self, context: SyntheticStrategyContext) -> StrategyDecision:
        feature = context.feature_snapshot
        distance = feature.distance_from_vwap or 0.0
        range_position = feature.local_range_position or 0.5
        signal = -(distance * 2.0) + ((0.5 - range_position) * 1.5)
        decision = _decision_from_signal(signal, threshold=0.001)
        return StrategyDecision(
            signal_value=signal,
            decision=decision,
            confidence=min(abs(signal) * 15.0, 0.96),
            reason="Mean reversion against rolling mean / VWAP proxy",
            reasoning_fields={
                "distance_from_vwap": feature.distance_from_vwap,
                "local_range_position": feature.local_range_position,
                "rolling_mean_price": feature.rolling_mean_price,
            },
        )


class SyntheticVolatilityBreakoutStrategy(SyntheticBaseStrategy):
    descriptor = StrategyDescriptor(
        name="synthetic_volatility_breakout",
        family="synthetic_volatility",
        description="Trade directional breakouts when short-term volatility expands.",
        configurable_fields=["min_signal"],
    )

    def decide(self, context: SyntheticStrategyContext) -> StrategyDecision:
        feature = context.feature_snapshot
        vol = (feature.realized_vol_5m or 0.0) + (feature.realized_vol_15m or 0.0)
        momentum = (feature.prior_return_1m or 0.0) + (feature.prior_return_3m or 0.0)
        signal = vol * momentum * 10.0
        decision = _decision_from_signal(signal, threshold=0.0015)
        return StrategyDecision(
            signal_value=signal,
            decision=decision,
            confidence=min(abs(signal) * 20.0, 0.94),
            reason="Volatility breakout using volatility expansion and momentum alignment",
            reasoning_fields={
                "realized_vol_5m": feature.realized_vol_5m,
                "realized_vol_15m": feature.realized_vol_15m,
                "prior_return_1m": feature.prior_return_1m,
                "prior_return_3m": feature.prior_return_3m,
            },
        )


class SyntheticRegimeFilterStrategy(SyntheticBaseStrategy):
    descriptor = StrategyDescriptor(
        name="synthetic_regime_filter",
        family="synthetic_regime",
        description="Only trade when the recent regime is directional; otherwise hold.",
        configurable_fields=["min_signal"],
    )

    def decide(self, context: SyntheticStrategyContext) -> StrategyDecision:
        feature = context.feature_snapshot
        regime = (feature.trend_regime or "unknown").lower()
        momentum = (feature.prior_return_1m or 0.0) + (feature.prior_return_5m or 0.0)
        if regime in {"uptrend", "strong_uptrend"}:
            signal = momentum
        elif regime in {"downtrend", "strong_downtrend"}:
            signal = -momentum
        else:
            signal = 0.0
        decision = _decision_from_signal(signal, threshold=0.0015)
        if regime == "sideways":
            decision = "hold"
        return StrategyDecision(
            signal_value=signal,
            decision=decision,
            confidence=min(abs(signal) * 14.0, 0.9),
            reason="Regime filter that stays flat in sideways regimes",
            reasoning_fields={
                "trend_regime": feature.trend_regime,
                "prior_return_1m": feature.prior_return_1m,
                "prior_return_5m": feature.prior_return_5m,
            },
        )


def build_synthetic_strategy_registry() -> dict[str, SyntheticBaseStrategy]:
    strategies: list[SyntheticBaseStrategy] = [
        SyntheticMomentumStrategy(),
        SyntheticMeanReversionStrategy(),
        SyntheticVolatilityBreakoutStrategy(),
        SyntheticRegimeFilterStrategy(),
    ]
    return {strategy.descriptor.name: strategy for strategy in strategies}


def _decision_from_signal(signal: float, *, threshold: float) -> str:
    if signal > threshold:
        return "buy_yes"
    if signal < -threshold:
        return "buy_no"
    return "hold"
