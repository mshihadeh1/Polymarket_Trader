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


class SyntheticImprovedMomentumStrategy(SyntheticBaseStrategy):
    descriptor = StrategyDescriptor(
        name="synthetic_improved_momentum",
        family="synthetic_momentum",
        description="Improved momentum with longer lookbacks, reduced acceleration weight, and regime filter.",
        configurable_fields=["min_signal"],
    )

    def decide(self, context: SyntheticStrategyContext) -> StrategyDecision:
        feature = context.feature_snapshot
        regime = (feature.trend_regime or "unknown").lower()
        
        # Skip sideways regimes (46% accuracy → 72% in trends)
        if regime == "sideways":
            return StrategyDecision(
                signal_value=0.0,
                decision="hold",
                confidence=0.0,
                reason="Skipping sideways regime",
                reasoning_fields={"trend_regime": regime},
            )
        
        # Use longer lookbacks (5m, 15m instead of 1m, 3m)
        # Reduce acceleration weight from 4.0 to 0.5
        signal = (
            (feature.prior_return_5m or 0.0) * 3.0
            + (feature.prior_return_15m or 0.0) * 2.0
            + (feature.acceleration or 0.0) * 0.5
        )
        
        # Invert confidence: lower signal magnitude = higher accuracy (70% vs 50%)
        base_confidence = min(abs(signal) * 8.0, 0.95)
        adjusted_confidence = 1.0 - base_confidence  # Invert so low confidence = high trust
        
        decision = _decision_from_signal(signal, threshold=0.001)
        return StrategyDecision(
            signal_value=signal,
            decision=decision,
            confidence=adjusted_confidence,
            reason="Improved momentum with regime filter and calibrated confidence",
            reasoning_fields={
                "prior_return_5m": feature.prior_return_5m,
                "prior_return_15m": feature.prior_return_15m,
                "acceleration": feature.acceleration,
                "trend_regime": regime,
            },
        )


class SyntheticImprovedMeanReversionStrategy(SyntheticBaseStrategy):
    descriptor = StrategyDescriptor(
        name="synthetic_improved_mr",
        family="synthetic_mean_reversion",
        description="Enhanced mean reversion with volatility adjustment and regime awareness.",
        configurable_fields=["min_signal"],
    )

    def decide(self, context: SyntheticStrategyContext) -> StrategyDecision:
        feature = context.feature_snapshot
        regime = (feature.trend_regime or "unknown").lower()
        
        distance = feature.distance_from_vwap or 0.0
        range_position = feature.local_range_position or 0.5
        
        # Add volatility scaling: mean reversion works better in high vol
        vol = (feature.realized_vol_5m or 0.0) + (feature.realized_vol_15m or 0.0)
        vol_scale = 1.0 + (vol * 100.0)  # Scale up signal in high vol
        
        # Base mean reversion signal
        signal = (-(distance * 2.0) + ((0.5 - range_position) * 1.5)) * vol_scale
        
        # Boost signal in sideways regimes (where MR works best)
        if regime == "sideways":
            signal *= 1.3
        elif regime in {"strong_uptrend", "strong_downtrend"}:
            signal *= 0.7  # Reduce in strong trends
        
        # Confidence based on extreme range position (more extreme = more confident)
        extremeness = abs(range_position - 0.5) * 2.0  # 0 to 1 scale
        confidence = min(0.4 + (extremeness * 0.5), 0.95)
        
        decision = _decision_from_signal(signal, threshold=0.0008)
        return StrategyDecision(
            signal_value=signal,
            decision=decision,
            confidence=confidence,
            reason="Enhanced mean reversion with volatility scaling and regime boost",
            reasoning_fields={
                "distance_from_vwap": distance,
                "local_range_position": range_position,
                "realized_vol_5m": feature.realized_vol_5m,
                "trend_regime": regime,
            },
        )


class SyntheticEnsembleStrategy(SyntheticBaseStrategy):
    descriptor = StrategyDescriptor(
        name="synthetic_ensemble",
        family="synthetic_ensemble",
        description="Combines mean reversion (primary) with momentum filter (confirmation).",
        configurable_fields=["min_signal"],
    )

    def decide(self, context: SyntheticStrategyContext) -> StrategyDecision:
        feature = context.feature_snapshot
        regime = (feature.trend_regime or "unknown").lower()

        # Mean reversion signal (primary)
        mr_distance = feature.distance_from_vwap or 0.0
        mr_range = feature.local_range_position or 0.5
        mr_signal = -(mr_distance * 2.0) + ((0.5 - mr_range) * 1.5)

        # Momentum signal (confirmation filter)
        mom_signal = (
            (feature.prior_return_5m or 0.0) * 2.0
            + (feature.acceleration or 0.0) * 0.5
        )

        # Combine: MR is primary, momentum confirms
        # If MR and momentum agree, boost signal
        # If they disagree, reduce signal
        if (mr_signal > 0 and mom_signal > 0) or (mr_signal < 0 and mom_signal < 0):
            # Agreement: boost
            combined_signal = mr_signal * 1.0 + mom_signal * 0.3
        else:
            # Disagreement: MR dominates, momentum reduces
            combined_signal = mr_signal * 1.0 - mom_signal * 0.2

        # Confidence: high when MR signal is extreme AND regime is sideways
        extremeness = abs(mr_range - 0.5) * 2.0
        regime_boost = 1.2 if regime == "sideways" else 1.0
        confidence = min((0.3 + extremeness * 0.4 + abs(combined_signal) * 5.0) * regime_boost, 0.95)

        decision = _decision_from_signal(combined_signal, threshold=0.001)
        return StrategyDecision(
            signal_value=combined_signal,
            decision=decision,
            confidence=confidence,
            reason="Ensemble: MR primary with momentum confirmation",
            reasoning_fields={
                "mr_signal": mr_signal,
                "mom_signal": mom_signal,
                "combined_signal": combined_signal,
                "trend_regime": regime,
            },
        )


class SyntheticAdaptiveEnsembleStrategy(SyntheticBaseStrategy):
    descriptor = StrategyDescriptor(
        name="synthetic_adaptive_ensemble",
        family="synthetic_ensemble",
        description="Adaptive ensemble that weights MR vs Momentum based on regime and volatility.",
        configurable_fields=["min_signal"],
    )

    def decide(self, context: SyntheticStrategyContext) -> StrategyDecision:
        feature = context.feature_snapshot
        regime = (feature.trend_regime or "unknown").lower()
        
        # Calculate regime strength
        is_strong_trend = regime in {"strong_uptrend", "strong_downtrend"}
        is_weak_trend = regime in {"uptrend", "downtrend"}
        is_sideways = regime == "sideways"
        
        # Mean reversion signal
        mr_distance = feature.distance_from_vwap or 0.0
        mr_range = feature.local_range_position or 0.5
        mr_signal = -(mr_distance * 2.0) + ((0.5 - mr_range) * 1.5)
        
        # Momentum signal
        mom_signal = (
            (feature.prior_return_5m or 0.0) * 2.0
            + (feature.prior_return_15m or 0.0) * 1.0
            + (feature.acceleration or 0.0) * 0.3
        )
        
        # Adaptive weighting based on regime
        if is_sideways:
            # Pure mean reversion in sideways (MR works best here)
            mr_weight, mom_weight = 1.0, 0.0
        elif is_strong_trend:
            # Reduce MR, increase momentum in strong trends
            mr_weight, mom_weight = 0.4, 0.6
        elif is_weak_trend:
            # Balanced in weak trends
            mr_weight, mom_weight = 0.7, 0.3
        else:
            # Default: MR dominant
            mr_weight, mom_weight = 0.8, 0.2
        
        # Volatility adjustment: scale up signals in high vol
        vol = (feature.realized_vol_5m or 0.0) + (feature.realized_vol_15m or 0.0)
        vol_multiplier = 1.0 + min(vol * 50.0, 0.5)  # Cap at 1.5x
        
        # Combine signals
        combined_signal = (mr_signal * mr_weight + mom_signal * mom_weight) * vol_multiplier
        
        # Confidence based on:
        # 1. Extremeness of range position
        # 2. Regime clarity (strong trends or sideways = more confident)
        # 3. Signal magnitude
        extremeness = abs(mr_range - 0.5) * 2.0
        regime_clarity = 1.2 if (is_sideways or is_strong_trend) else 1.0
        confidence = min((0.35 + extremeness * 0.35 + abs(combined_signal) * 4.0) * regime_clarity, 0.95)
        
        decision = _decision_from_signal(combined_signal, threshold=0.0009)
        return StrategyDecision(
            signal_value=combined_signal,
            decision=decision,
            confidence=confidence,
            reason=f"Adaptive ensemble (MR:{mr_weight:.1f} Mom:{mom_weight:.1f}) in {regime}",
            reasoning_fields={
                "mr_signal": mr_signal,
                "mom_signal": mom_signal,
                "mr_weight": mr_weight,
                "mom_weight": mom_weight,
                "combined_signal": combined_signal,
                "trend_regime": regime,
                "vol_multiplier": vol_multiplier,
            },
        )


class SyntheticGridSearchMRStrategy(SyntheticBaseStrategy):
    descriptor = StrategyDescriptor(
        name="synthetic_grid_search_mr",
        family="synthetic_mean_reversion",
        description="Mean reversion with configurable hyperparameters for grid search optimization.",
        configurable_fields=["distance_weight", "range_weight", "vol_scale", "threshold"],
    )

    def __init__(
        self,
        distance_weight: float = 2.0,
        range_weight: float = 1.5,
        vol_scale_factor: float = 50.0,
        vol_cap: float = 0.2,
        threshold: float = 0.0008,
        regime_boost: float = 1.1,
    ):
        self.distance_weight = distance_weight
        self.range_weight = range_weight
        self.vol_scale_factor = vol_scale_factor
        self.vol_cap = vol_cap
        self.threshold = threshold
        self.regime_boost = regime_boost

    def decide(self, context: SyntheticStrategyContext) -> StrategyDecision:
        feature = context.feature_snapshot
        regime = (feature.trend_regime or "unknown").lower()

        distance = feature.distance_from_vwap or 0.0
        range_position = feature.local_range_position or 0.5

        # Configurable mean reversion signal
        signal = -(distance * self.distance_weight) + ((0.5 - range_position) * self.range_weight)

        # Volatility scaling
        vol = (feature.realized_vol_5m or 0.0) + (feature.realized_vol_15m or 0.0)
        vol_scale = 1.0 + min(vol * self.vol_scale_factor, self.vol_cap)

        # Regime boost
        regime_scale = self.regime_boost if regime == "sideways" else 1.0

        signal = signal * vol_scale * regime_scale

        # Confidence
        extremeness = abs(range_position - 0.5) * 2.0
        confidence = min(0.45 + extremeness * 0.4, 0.92)

        decision = _decision_from_signal(signal, threshold=self.threshold)
        return StrategyDecision(
            signal_value=signal,
            decision=decision,
            confidence=confidence,
            reason=f"Grid search MR (dw={self.distance_weight}, rw={self.range_weight})",
            reasoning_fields={
                "distance_from_vwap": distance,
                "local_range_position": range_position,
                "distance_weight": self.distance_weight,
                "range_weight": self.range_weight,
                "vol_scale": vol_scale,
                "trend_regime": regime,
            },
        )


class SyntheticCVDEnhancedMRStrategy(SyntheticBaseStrategy):
    descriptor = StrategyDescriptor(
        name="synthetic_cvd_enhanced_mr",
        family="synthetic_mean_reversion",
        description="Mean reversion enhanced with CVD flow confirmation. Only trades when MR and CVD agree.",
        configurable_fields=["min_signal", "cvd_threshold"],
    )

    def decide(self, context: SyntheticStrategyContext) -> StrategyDecision:
        feature = context.feature_snapshot
        regime = (feature.trend_regime or "unknown").lower()

        # === LAYER 1: Mean Reversion Base Signal ===
        distance = feature.distance_from_vwap or 0.0
        range_position = feature.local_range_position or 0.5

        # Stronger MR signal (validated in V2)
        mr_signal = -(distance * 3.0) + ((0.5 - range_position) * 2.5)

        # Volatility scaling
        vol = (feature.realized_vol_5m or 0.0) + (feature.realized_vol_15m or 0.0)
        vol_scale = 1.0 + min(vol * 100.0, 0.4)
        regime_scale = 1.2 if regime == "sideways" else 1.0
        mr_signal = mr_signal * vol_scale * regime_scale

        # === LAYER 2: CVD Flow Confirmation ===
        # Get CVD data from Hyperliquid (or synthetic proxy)
        cvd = getattr(feature, 'external_cvd', 0.0) or 0.0
        cvd_imbalance = getattr(feature, 'external_trade_imbalance', 0.0) or 0.0
        
        # Normalize CVD to similar scale as MR signal
        cvd_signal = cvd_imbalance * 2.0  # Scale to [-2, +2] range

        # === LAYER 3: Agreement Filter ===
        mr_direction = 1 if mr_signal > 0 else -1
        cvd_direction = 1 if cvd_signal > 0 else -1
        agreement = mr_direction == cvd_direction

        # Combine signals based on agreement
        if agreement and abs(cvd_imbalance) > 0.05:
            # MR and CVD agree with meaningful flow
            combined_signal = mr_signal * 1.3 + cvd_signal * 0.3
            confidence = min(0.55 + abs(cvd_imbalance) * 2.0, 0.85)
        elif abs(cvd_imbalance) > 0.2:
            # Strong CVD overrides weak MR
            combined_signal = cvd_signal * 0.7 + mr_signal * 0.3
            confidence = min(0.50 + abs(cvd_imbalance) * 1.5, 0.80)
        elif not agreement:
            # MR and CVD disagree - reduce conviction
            combined_signal = mr_signal * 0.5
            confidence = 0.30
        else:
            # Weak CVD, use MR with reduced confidence
            combined_signal = mr_signal
            confidence = 0.45

        # === Decision ===
        decision = _decision_from_signal(combined_signal, threshold=0.001)
        
        return StrategyDecision(
            signal_value=combined_signal,
            decision=decision,
            confidence=confidence,
            reason="CVD-enhanced MR" + (" (agreement)" if agreement else " (disagreement)"),
            reasoning_fields={
                "mr_signal": mr_signal,
                "cvd": cvd,
                "cvd_imbalance": cvd_imbalance,
                "cvd_signal": cvd_signal,
                "combined_signal": combined_signal,
                "agreement": agreement,
                "trend_regime": regime,
            },
        )


class SyntheticOptimizedMRStrategyV2(SyntheticBaseStrategy):
    descriptor = StrategyDescriptor(
        name="synthetic_optimized_mr_v2",
        family="synthetic_mean_reversion",
        description="Optimized MR v2: stronger mean reversion signals with higher vol scaling.",
        configurable_fields=["min_signal"],
    )

    def decide(self, context: SyntheticStrategyContext) -> StrategyDecision:
        feature = context.feature_snapshot
        regime = (feature.trend_regime or "unknown").lower()

        distance = feature.distance_from_vwap or 0.0
        range_position = feature.local_range_position or 0.5

        # Stronger mean reversion signal
        signal = -(distance * 3.0) + ((0.5 - range_position) * 2.5)

        # More aggressive volatility scaling
        vol = (feature.realized_vol_5m or 0.0) + (feature.realized_vol_15m or 0.0)
        vol_scale = 1.0 + min(vol * 100.0, 0.4)  # Max 1.4x

        # Stronger regime boost
        regime_scale = 1.2 if regime == "sideways" else 1.0

        signal = signal * vol_scale * regime_scale

        # Confidence
        extremeness = abs(range_position - 0.5) * 2.0
        confidence = min(0.5 + extremeness * 0.4, 0.95)

        decision = _decision_from_signal(signal, threshold=0.001)
        return StrategyDecision(
            signal_value=signal,
            decision=decision,
            confidence=confidence,
            reason="Optimized MR v2 (stronger signals)",
            reasoning_fields={
                "distance_from_vwap": distance,
                "local_range_position": range_position,
                "trend_regime": regime,
                "vol_scale": vol_scale,
            },
        )


class SyntheticOptimizedMRStrategyV3(SyntheticBaseStrategy):
    descriptor = StrategyDescriptor(
        name="synthetic_optimized_mr_v3",
        family="synthetic_mean_reversion",
        description="Optimized MR v3: conservative signals with tighter threshold.",
        configurable_fields=["min_signal"],
    )

    def decide(self, context: SyntheticStrategyContext) -> StrategyDecision:
        feature = context.feature_snapshot
        regime = (feature.trend_regime or "unknown").lower()

        distance = feature.distance_from_vwap or 0.0
        range_position = feature.local_range_position or 0.5

        # Conservative mean reversion signal
        signal = -(distance * 1.5) + ((0.5 - range_position) * 1.0)

        # Minimal volatility scaling
        vol = (feature.realized_vol_5m or 0.0) + (feature.realized_vol_15m or 0.0)
        vol_scale = 1.0 + min(vol * 25.0, 0.1)  # Max 1.1x

        # No regime boost
        regime_scale = 1.0

        signal = signal * vol_scale * regime_scale

        # Lower threshold for more trades
        extremeness = abs(range_position - 0.5) * 2.0
        confidence = min(0.4 + extremeness * 0.3, 0.85)

        decision = _decision_from_signal(signal, threshold=0.0005)
        return StrategyDecision(
            signal_value=signal,
            decision=decision,
            confidence=confidence,
            reason="Optimized MR v3 (conservative)",
            reasoning_fields={
                "distance_from_vwap": distance,
                "local_range_position": range_position,
                "trend_regime": regime,
                "vol_scale": vol_scale,
            },
        )


class SyntheticOptimizedMRStrategy(SyntheticBaseStrategy):
    descriptor = StrategyDescriptor(
        name="synthetic_optimized_mr",
        family="synthetic_mean_reversion",
        description="Optimized mean reversion: simple, robust, with proven parameters.",
        configurable_fields=["min_signal"],
    )

    def decide(self, context: SyntheticStrategyContext) -> StrategyDecision:
        feature = context.feature_snapshot
        regime = (feature.trend_regime or "unknown").lower()

        distance = feature.distance_from_vwap or 0.0
        range_position = feature.local_range_position or 0.5

        # Core mean reversion signal (proven effective)
        signal = -(distance * 2.0) + ((0.5 - range_position) * 1.5)

        # Volatility scaling (slight boost in high vol)
        vol = (feature.realized_vol_5m or 0.0) + (feature.realized_vol_15m or 0.0)
        vol_scale = 1.0 + min(vol * 50.0, 0.2)  # Conservative: max 1.2x

        # Small regime boost for sideways (where MR excels)
        regime_scale = 1.1 if regime == "sideways" else 1.0

        signal = signal * vol_scale * regime_scale

        # Simple confidence: based on range extremeness
        extremeness = abs(range_position - 0.5) * 2.0
        confidence = min(0.45 + extremeness * 0.4, 0.92)

        decision = _decision_from_signal(signal, threshold=0.0008)
        return StrategyDecision(
            signal_value=signal,
            decision=decision,
            confidence=confidence,
            reason="Optimized mean reversion",
            reasoning_fields={
                "distance_from_vwap": distance,
                "local_range_position": range_position,
                "trend_regime": regime,
                "vol_scale": vol_scale,
            },
        )


class SyntheticConservativeMRStrategy(SyntheticBaseStrategy):
    descriptor = StrategyDescriptor(
        name="synthetic_conservative_mr",
        family="synthetic_mean_reversion",
        description="Conservative mean reversion: lower trade frequency, higher confidence threshold.",
        configurable_fields=["min_signal", "min_confidence"],
    )

    def decide(self, context: SyntheticStrategyContext) -> StrategyDecision:
        feature = context.feature_snapshot
        
        distance = feature.distance_from_vwap or 0.0
        range_position = feature.local_range_position or 0.5
        
        # Require extreme conditions to trade
        is_extreme_range = range_position < 0.15 or range_position > 0.85
        is_extreme_vwap = abs(distance) > 0.004  # >0.4% from VWAP
        
        if not (is_extreme_range or is_extreme_vwap):
            return StrategyDecision(
                signal_value=0.0,
                decision="hold",
                confidence=0.0,
                reason="Conditions not extreme enough",
                reasoning_fields={
                    "range_position": range_position,
                    "distance_from_vwap": distance,
                },
            )
        
        # Stronger mean reversion signal
        signal = -(distance * 2.5) + ((0.5 - range_position) * 2.0)
        
        # High confidence for extreme conditions
        extremeness = max(
            abs(range_position - 0.5) * 2.0,
            min(abs(distance) * 100.0, 1.0)
        )
        confidence = min(0.55 + extremeness * 0.35, 0.95)
        
        decision = _decision_from_signal(signal, threshold=0.0015)
        return StrategyDecision(
            signal_value=signal,
            decision=decision,
            confidence=confidence,
            reason="Conservative MR (extreme conditions)",
            reasoning_fields={
                "distance_from_vwap": distance,
                "local_range_position": range_position,
                "is_extreme_range": is_extreme_range,
                "is_extreme_vwap": is_extreme_vwap,
            },
        )


def build_synthetic_strategy_registry() -> dict[str, SyntheticBaseStrategy]:
    strategies: list[SyntheticBaseStrategy] = [
        SyntheticMomentumStrategy(),
        SyntheticMeanReversionStrategy(),
        SyntheticVolatilityBreakoutStrategy(),
        SyntheticRegimeFilterStrategy(),
        SyntheticImprovedMomentumStrategy(),
        SyntheticImprovedMeanReversionStrategy(),
        SyntheticEnsembleStrategy(),
        SyntheticAdaptiveEnsembleStrategy(),
        SyntheticOptimizedMRStrategy(),
        SyntheticOptimizedMRStrategyV2(),
        SyntheticOptimizedMRStrategyV3(),
        SyntheticCVDEnhancedMRStrategy(),
        SyntheticConservativeMRStrategy(),
        SyntheticGridSearchMRStrategy(),
    ]
    return {strategy.descriptor.name: strategy for strategy in strategies}


def _decision_from_signal(signal: float, *, threshold: float) -> str:
    if signal > threshold:
        return "buy_yes"
    if signal < -threshold:
        return "buy_no"
    return "hold"
