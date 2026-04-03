from __future__ import annotations

import logging
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from statistics import fmean, pstdev

from packages.clients.market_data_provider import HistoricalMarketDataProvider
from packages.config import Settings
from packages.core_types import (
    BacktestMetric,
    FeatureAvailability,
    OHLCVBar,
    PolymarketMarketMetadata,
    SyntheticBatchReport,
    SyntheticEvaluationRecord,
    SyntheticFeatureSnapshot,
    SyntheticMarketSample,
)
from packages.db import ResearchPersistence
from services.backtester.synthetic_strategies import (
    SyntheticBaseStrategy,
    SyntheticStrategyContext,
    build_synthetic_strategy_registry,
)
from services.market_catalog.classifier import classify_polymarket_market
from services.state import InMemoryState

logger = logging.getLogger(__name__)

_SUPPORTED_TIMEFRAMES = {"crypto_5m": 5, "crypto_15m": 15}


class SyntheticResearchService:
    def __init__(
        self,
        settings: Settings,
        state: InMemoryState,
        historical_provider: HistoricalMarketDataProvider,
        polymarket_client,
        persistence: ResearchPersistence | None = None,
        strategy_registry: dict[str, SyntheticBaseStrategy] | None = None,
    ) -> None:
        self._settings = settings
        self._state = state
        self._historical_provider = historical_provider
        self._polymarket_client = polymarket_client
        self._persistence = persistence
        self._strategy_registry = strategy_registry or build_synthetic_strategy_registry()

    def list_strategies(self) -> list[dict]:
        return [strategy.descriptor.model_dump(mode="json") for strategy in self._strategy_registry.values()]

    def list_samples(
        self,
        asset: str | None = None,
        timeframe: str | None = None,
        limit: int = 100,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[SyntheticMarketSample]:
        samples = self._filtered_samples(asset=asset, timeframe=timeframe, start=start, end=end, limit=limit)
        if not samples:
            samples = self.build_synthetic_dataset(asset=asset, timeframe=timeframe, start=start, end=end)
        return samples[:limit]

    def list_reports(self, source: str | None = None) -> list[SyntheticBatchReport]:
        reports = list(self._state.synthetic_batch_reports)
        if self._persistence is not None and self._persistence.enabled:
            persisted = self._persistence.list_synthetic_batch_reports()
            merged = {report.run_id: report for report in reports}
            for report in persisted:
                if source is None or report.source == source:
                    merged.setdefault(report.run_id, report)
            reports = list(merged.values())
        if source is not None:
            reports = [report for report in reports if report.source == source]
        return sorted(reports, key=lambda report: report.created_at or datetime.min.replace(tzinfo=UTC), reverse=True)

    def build_synthetic_dataset(
        self,
        *,
        asset: str | None = None,
        timeframe: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[SyntheticMarketSample]:
        if not self._historical_provider.capabilities().has_ohlcv:
            return []
        end = end or datetime.now(tz=UTC)
        start = start or (end - timedelta(days=14))
        assets = [asset.upper()] if asset else [symbol.strip().upper() for symbol in self._settings.default_underlyings.split(",") if symbol.strip()]
        timeframe_items = [(timeframe, _SUPPORTED_TIMEFRAMES[timeframe])] if timeframe in _SUPPORTED_TIMEFRAMES else list(_SUPPORTED_TIMEFRAMES.items())

        samples: list[SyntheticMarketSample] = []
        for symbol in assets:
            bars = self._load_symbol_bars(symbol, start=start, end=end)
            if len(bars) < 2:
                continue
            for market_type, window_minutes in timeframe_items:
                samples.extend(self._generate_windows(symbol, market_type, window_minutes, bars))

        samples.sort(key=lambda sample: sample.market_close_time, reverse=True)
        for sample in samples:
            self._state.synthetic_market_samples.setdefault(sample.sample_id, sample)
            if self._persistence is not None:
                self._persistence.save_synthetic_market_sample(sample)
        logger.info(
            "Synthetic dataset built asset=%s timeframe=%s samples=%s",
            asset or "all",
            timeframe or "all",
            len(samples),
        )
        return samples

    def compute_feature_snapshots_for_sample(self, sample: SyntheticMarketSample) -> list[SyntheticFeatureSnapshot]:
        history = self._load_symbol_bars(sample.asset)
        if not history:
            return []
        checkpoint_offsets = [0, 1, 2, 3]
        features: list[SyntheticFeatureSnapshot] = []
        for checkpoint in checkpoint_offsets:
            decision_time = sample.market_open_time + timedelta(minutes=checkpoint)
            if decision_time > sample.market_close_time:
                continue
            snapshot = self._build_feature_snapshot(
                sample=sample,
                bars=history,
                decision_time=decision_time,
                checkpoint_minutes=checkpoint,
            )
            if snapshot is None:
                continue
            features.append(snapshot)
            self._state.synthetic_feature_snapshots.setdefault(sample.sample_id, [])
            cached = self._state.synthetic_feature_snapshots[sample.sample_id]
            if not cached or cached[-1].decision_time != snapshot.decision_time:
                cached.append(snapshot)
            if self._persistence is not None:
                self._persistence.save_synthetic_feature_snapshot(snapshot)
        return features

    def run_synthetic_batch(
        self,
        *,
        asset: str | None = None,
        timeframe: str | None = None,
        strategy_name: str = "synthetic_momentum",
        decision_time: str = "open",
        limit: int = 200,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> SyntheticBatchReport:
        strategy = self._strategy_registry[strategy_name]
        end = end or datetime.now(tz=UTC)
        start = start or (end - timedelta(days=14))
        if not self._state.synthetic_market_samples:
            self.build_synthetic_dataset(asset=asset, timeframe=timeframe, start=start, end=end)
        samples = self._filtered_samples(asset=asset, timeframe=timeframe, start=start, end=end, limit=limit)
        if not samples:
            raise ValueError("No synthetic samples available")

        records: list[SyntheticEvaluationRecord] = []
        coverage = defaultdict(int)
        for sample in samples:
            feature = self._feature_for_sample(sample, decision_time)
            if feature is None:
                continue
            availability = self._feature_availability(sample, feature)
            decision = strategy.decide(SyntheticStrategyContext(feature_snapshot=feature))
            correctness = None
            if decision.decision in {"buy_yes"}:
                correctness = sample.actual_resolution == "yes"
            elif decision.decision in {"buy_no"}:
                correctness = sample.actual_resolution == "no"
            if availability.bars_available and not availability.trades_available:
                coverage["bars_only"] += 1
            if availability.trades_available:
                coverage["bars_plus_trades"] += 1
            if availability.orderbook_available:
                coverage["bars_plus_trades_plus_orderbook"] += 1
            records.append(
                SyntheticEvaluationRecord(
                    sample_id=sample.sample_id,
                    market_id=sample.market_id,
                    source=sample.source,
                    asset=sample.asset,
                    timeframe=sample.timeframe,
                    market_open_time=sample.market_open_time,
                    market_close_time=sample.market_close_time,
                    decision_time=feature.decision_time,
                    price_to_beat=sample.price_to_beat,
                    close_price=sample.close_price,
                    actual_resolution=sample.actual_resolution,
                    actual_resolution_source=sample.source_provider,
                    strategy_name=strategy_name,
                    signal_value=decision.signal_value,
                    confidence=decision.confidence,
                    decision=decision.decision,
                    correctness=correctness,
                    contract_score=1.0 if correctness is True else -1.0 if correctness is False else 0.0,
                    feature_snapshot_summary=feature.feature_summary,
                    notes=[f"decision_time={decision_time}", *sample.notes],
                )
            )

        report = self._build_report(
            records=records,
            strategy_name=strategy_name,
            source="synthetic",
            asset=asset,
            timeframe=timeframe,
            decision_time=decision_time,
            limit=limit,
            coverage=dict(coverage),
        )
        self._persist_report(report)
        return report

    def run_real_validation_batch(
        self,
        *,
        asset: str | None = "BTC",
        timeframe: str | None = None,
        strategy_name: str = "synthetic_momentum",
        limit: int = 50,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> SyntheticBatchReport:
        strategy = self._strategy_registry[strategy_name]
        end = end or datetime.now(tz=UTC)
        start = start or (end - timedelta(days=14))
        candidates = self._discover_closed_markets(asset=asset, timeframe=timeframe, limit=limit * 3, start=start, end=end)
        samples: list[SyntheticMarketSample] = []
        for raw_market, metadata, market_type, underlying in candidates[:limit]:
            if metadata.start_date is None or metadata.end_date is None or underlying is None:
                continue
            sample = self._build_real_validation_sample(
                raw_market=raw_market,
                metadata=metadata,
                asset=underlying,
                timeframe=market_type,
            )
            if sample is not None:
                samples.append(sample)

        records: list[SyntheticEvaluationRecord] = []
        coverage = defaultdict(int)
        for sample in samples:
            feature = self._feature_for_sample(sample, "open")
            if feature is None:
                continue
            availability = self._feature_availability(sample, feature)
            decision = strategy.decide(SyntheticStrategyContext(feature_snapshot=feature))
            correctness = None
            if decision.decision in {"buy_yes"}:
                correctness = sample.actual_resolution == "yes"
            elif decision.decision in {"buy_no"}:
                correctness = sample.actual_resolution == "no"
            if availability.bars_available and not availability.trades_available:
                coverage["bars_only"] += 1
            if availability.trades_available:
                coverage["bars_plus_trades"] += 1
            if availability.orderbook_available:
                coverage["bars_plus_trades_plus_orderbook"] += 1
            records.append(
                SyntheticEvaluationRecord(
                    sample_id=sample.sample_id,
                    market_id=sample.market_id,
                    source="real_validation",
                    asset=sample.asset,
                    timeframe=sample.timeframe,
                    market_open_time=sample.market_open_time,
                    market_close_time=sample.market_close_time,
                    decision_time=feature.decision_time,
                    price_to_beat=sample.price_to_beat,
                    close_price=sample.close_price,
                    actual_resolution=sample.actual_resolution,
                    actual_resolution_source=sample.source_provider,
                    strategy_name=strategy_name,
                    signal_value=decision.signal_value,
                    confidence=decision.confidence,
                    decision=decision.decision,
                    correctness=correctness,
                    contract_score=1.0 if correctness is True else -1.0 if correctness is False else 0.0,
                    feature_snapshot_summary=feature.feature_summary,
                    notes=[*sample.notes, "Real Polymarket validation run"],
                )
            )

        report = self._build_report(
            records=records,
            strategy_name=strategy_name,
            source="real_validation",
            asset=asset,
            timeframe=timeframe,
            decision_time="open",
            limit=limit,
            coverage=dict(coverage),
        )
        self._persist_report(report)
        return report

    def _persist_report(self, report: SyntheticBatchReport) -> None:
        self._state.synthetic_batch_reports.insert(0, report)
        if self._persistence is not None:
            self._persistence.save_synthetic_batch_report(report)

    def _build_report(
        self,
        *,
        records: list[SyntheticEvaluationRecord],
        strategy_name: str,
        source: str,
        asset: str | None,
        timeframe: str | None,
        decision_time: str,
        limit: int,
        coverage: dict[str, int],
    ) -> SyntheticBatchReport:
        total = len(records)
        hits = sum(1 for record in records if record.correctness is True)
        contract_score = sum(record.contract_score for record in records)
        avg_confidence = _avg(record.confidence for record in records)
        avg_signal = _avg(abs(record.signal_value) for record in records)
        trade_frequency = _ratio(sum(1 for record in records if record.decision != "hold"), total)
        report = SyntheticBatchReport(
            run_id=f"{source}:{strategy_name}:{timeframe or 'all'}:{asset or 'all'}:{int(datetime.now(tz=UTC).timestamp())}",
            strategy_name=strategy_name,
            source=source,
            asset_filter=asset,
            timeframe_filter=timeframe,
            decision_time=decision_time,
            limit=limit,
            created_at=datetime.now(tz=UTC),
            total_samples=total,
            metrics=[
                BacktestMetric(label="hit_rate", value=_ratio(hits, total)),
                BacktestMetric(label="edge_over_50", value=(_ratio(hits, total) - 0.5) if total else 0.0),
                BacktestMetric(label="contract_score", value=contract_score),
                BacktestMetric(label="sample_size", value=float(total)),
                BacktestMetric(label="trade_frequency", value=trade_frequency),
                BacktestMetric(label="average_confidence", value=avg_confidence),
                BacktestMetric(label="average_signal", value=avg_signal),
                BacktestMetric(label="hit_rate_high_confidence", value=_bucket_hit_rate(records, "high")),
                BacktestMetric(label="hit_rate_medium_confidence", value=_bucket_hit_rate(records, "medium")),
                BacktestMetric(label="hit_rate_low_confidence", value=_bucket_hit_rate(records, "low")),
            ],
            coverage=coverage,
            records=records,
        )
        return report

    def _feature_for_sample(self, sample: SyntheticMarketSample, decision_time: str) -> SyntheticFeatureSnapshot | None:
        features = self._state.synthetic_feature_snapshots.get(sample.sample_id, [])
        if features:
            if decision_time == "open":
                for feature in features:
                    if feature.checkpoint_minutes == 0:
                        return feature
            if decision_time.endswith("m"):
                try:
                    checkpoint = int(decision_time.rstrip("m"))
                except ValueError:
                    checkpoint = 0
                for feature in features:
                    if feature.checkpoint_minutes == checkpoint:
                        return feature
        history = self._load_symbol_bars(
            sample.asset,
            start=sample.market_open_time - timedelta(days=30),
            end=sample.market_close_time,
        )
        if not history:
            return None
        checkpoint = 0
        if decision_time.endswith("m"):
            try:
                checkpoint = int(decision_time.rstrip("m"))
            except ValueError:
                checkpoint = 0
        feature = self._build_feature_snapshot(
            sample=sample,
            bars=history,
            decision_time=sample.market_open_time + timedelta(minutes=checkpoint),
            checkpoint_minutes=checkpoint,
        )
        if feature is None:
            return None
        self._state.synthetic_feature_snapshots.setdefault(sample.sample_id, []).append(feature)
        if self._persistence is not None:
            self._persistence.save_synthetic_feature_snapshot(feature)
        return feature

    def _feature_availability(self, sample: SyntheticMarketSample, feature: SyntheticFeatureSnapshot) -> FeatureAvailability:
        notes = [
            "Synthetic features computed from local 1-minute bars.",
            f"Decision checkpoint: +{feature.checkpoint_minutes}m",
        ]
        return FeatureAvailability(
            bars_available=True,
            trades_available=False,
            orderbook_available=False,
            enriched_with_hyperliquid=False,
            notes=notes,
        )

    def _generate_windows(
        self,
        symbol: str,
        market_type: str,
        window_minutes: int,
        bars: list[OHLCVBar],
    ) -> list[SyntheticMarketSample]:
        samples: list[SyntheticMarketSample] = []
        if window_minutes <= 0:
            return samples
        usable = len(bars) - (len(bars) % window_minutes)
        if usable <= 0:
            return samples
        for window_index, start in enumerate(range(0, usable, window_minutes)):
            chunk = bars[start:start + window_minutes]
            if len(chunk) != window_minutes:
                continue
            open_bar = chunk[0]
            close_bar = chunk[-1]
            sample_id = f"synthetic:{symbol}:{market_type}:{int(open_bar.ts.timestamp())}"
            price_to_beat = float(open_bar.open)
            close_price = float(close_bar.close)
            actual_resolution = "yes" if close_price > price_to_beat else "no"
            sample = SyntheticMarketSample(
                sample_id=sample_id,
                source="synthetic",
                asset=symbol,
                timeframe=market_type,
                market_open_time=open_bar.ts,
                market_close_time=close_bar.ts,
                decision_time=open_bar.ts,
                decision_horizon_minutes=window_minutes,
                price_to_beat=price_to_beat,
                close_price=close_price,
                actual_resolution=actual_resolution,
                source_provider=self._historical_provider.provider_name,
                window_index=window_index,
                notes=["Generated from aligned 1-minute CSV history."],
            )
            samples.append(sample)
        return samples

    def _build_feature_snapshot(
        self,
        *,
        sample: SyntheticMarketSample,
        bars: list[OHLCVBar],
        decision_time: datetime,
        checkpoint_minutes: int,
    ) -> SyntheticFeatureSnapshot | None:
        relevant = [bar for bar in bars if bar.ts < decision_time]
        if not relevant:
            return None
        current = relevant[-1]
        current_price = float(current.close)
        closes = [float(bar.close) for bar in relevant]
        volumes = [float(bar.volume) for bar in relevant]
        if len(closes) < 2:
            closes = [float(current.open), float(current.close)]
            volumes = [float(current.volume), float(current.volume)]

        prior_return_1m = _return_from_closes(closes, 1)
        prior_return_3m = _return_from_closes(closes, 3)
        prior_return_5m = _return_from_closes(closes, 5)
        prior_return_15m = _return_from_closes(closes, 15)
        realized_vol_5m = _realized_volatility(closes, 5)
        realized_vol_15m = _realized_volatility(closes, 15)
        realized_vol_30m = _realized_volatility(closes, 30)
        rolling_window = closes[-15:] if len(closes) >= 15 else closes
        rolling_mean_price = fmean(rolling_window) if rolling_window else None
        local_range_position = _range_position(relevant[-15:] if len(relevant) >= 15 else relevant, current_price)
        distance_from_vwap = ((current_price - rolling_mean_price) / rolling_mean_price) if rolling_mean_price else None
        acceleration = None
        if prior_return_1m is not None and prior_return_3m is not None:
            acceleration = prior_return_1m - (prior_return_3m / 3.0)
        trend_regime = _trend_regime(prior_return_5m, prior_return_15m, realized_vol_15m)
        time_of_day_bucket = _time_of_day_bucket(decision_time)

        # === CVD Proxy Generation (for synthetic backtesting) ===
        # In production, this comes from Hyperliquid via external_ingestor
        # Here we create a PROXY with realistic noise to simulate real CVD data
        external_cvd = 0.0
        external_trade_imbalance = 0.0
        
        if len(closes) >= 5 and len(volumes) >= 5:
            import random
            random.seed(hash(str(decision_time)) % (2**32))  # Deterministic but noisy
            
            # CVD proxy: cumulative sum of signed volume based on price direction
            cvd_window = min(20, len(closes))
            cvd_values = []
            for i in range(1, cvd_window):
                price_change = closes[i] - closes[i-1]
                volume = volumes[i]
                # Positive CVD if price up, negative if down
                cvd_values.append(volume if price_change > 0 else -volume)
            
            # Normalize CVD to [-1, 1] range
            total_cvd = sum(cvd_values[-10:])  # Last 10 periods
            max_volume = sum(abs(v) for v in cvd_values[-10:]) or 1.0
            base_cvd = total_cvd / max_volume
            
            # Add realistic noise (CVD is NOT perfectly correlated with price)
            # In real markets, CVD can diverge from price due to:
            # - Hidden liquidity
            # - Market maker positioning
            # - Cross-venue arbitrage
            noise = random.gauss(0, 0.3)  # 30% noise
            external_cvd = max(-1.0, min(1.0, base_cvd * 0.7 + noise))
            
            # Trade imbalance: recent buy vs sell pressure with noise
            recent_cvd = sum(cvd_values[-5:])  # Last 5 periods
            base_imbalance = recent_cvd / max_volume
            noise_imb = random.gauss(0, 0.25)  # 25% noise
            external_trade_imbalance = max(-1.0, min(1.0, base_imbalance * 0.6 + noise_imb))

        snapshot = SyntheticFeatureSnapshot(
            sample_id=sample.sample_id,
            market_id=sample.market_id,
            source=sample.source,
            asset=sample.asset,
            timeframe=sample.timeframe,
            market_open_time=sample.market_open_time,
            market_close_time=sample.market_close_time,
            decision_time=decision_time,
            checkpoint_minutes=checkpoint_minutes,
            current_price=current_price,
            rolling_mean_price=rolling_mean_price,
            prior_return_1m=prior_return_1m,
            prior_return_3m=prior_return_3m,
            prior_return_5m=prior_return_5m,
            prior_return_15m=prior_return_15m,
            realized_vol_5m=realized_vol_5m,
            realized_vol_15m=realized_vol_15m,
            realized_vol_30m=realized_vol_30m,
            distance_from_vwap=distance_from_vwap,
            local_range_position=local_range_position,
            acceleration=acceleration,
            trend_regime=trend_regime,
            time_of_day_bucket=time_of_day_bucket,
            # CVD fields (synthetic proxy)
            external_cvd=external_cvd,
            external_trade_imbalance=external_trade_imbalance,
            feature_summary={
                "prior_return_1m": prior_return_1m,
                "prior_return_3m": prior_return_3m,
                "prior_return_5m": prior_return_5m,
                "prior_return_15m": prior_return_15m,
                "realized_vol_5m": realized_vol_5m,
                "realized_vol_15m": realized_vol_15m,
                "realized_vol_30m": realized_vol_30m,
                "distance_from_vwap": distance_from_vwap,
                "local_range_position": local_range_position,
                "acceleration": acceleration,
                "trend_regime": trend_regime,
                "time_of_day_bucket": time_of_day_bucket,
                "external_cvd": external_cvd,
                "external_trade_imbalance": external_trade_imbalance,
            },
        )
        return snapshot

    def _discover_closed_markets(
        self,
        *,
        asset: str | None,
        timeframe: str | None,
        limit: int,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[tuple[dict, PolymarketMarketMetadata, str, str | None]]:
        # Real closed-market validation uses the same classifier and normalized metadata flow as the venue ingestion path.
        raw_markets, normalized = self._poll_closed_markets(limit=max(limit, 100))
        discovered: list[tuple[dict, PolymarketMarketMetadata, str, str | None]] = []
        for raw_market, metadata in zip(raw_markets, normalized, strict=False):
            market_type, underlying = classify_polymarket_market(metadata)
            if market_type not in _SUPPORTED_TIMEFRAMES:
                continue
            if asset is not None and (underlying or "").upper() != asset.upper():
                continue
            if timeframe is not None and market_type != timeframe:
                continue
            if start is not None and metadata.end_date is not None and metadata.end_date < start:
                continue
            if end is not None and metadata.start_date is not None and metadata.start_date > end:
                continue
            discovered.append((raw_market, metadata, market_type, underlying))
        discovered.sort(key=lambda item: item[1].end_date or datetime.min.replace(tzinfo=UTC), reverse=True)
        return discovered[:limit]

    def _poll_closed_markets(self, *, limit: int) -> tuple[list[dict], list[PolymarketMarketMetadata]]:
        # The real client is authoritative; this service only normalizes and scores the closed markets it finds.
        if hasattr(self._polymarket_client, "discover_markets"):
            try:
                return _sync_await(self._polymarket_client.discover_markets(closed=True, limit=limit))
            except RuntimeError:
                raise
            except Exception:
                logger.exception("Failed to discover closed Polymarket markets for real validation")
        return [], []

    def _build_real_validation_sample(
        self,
        *,
        raw_market: dict,
        metadata: PolymarketMarketMetadata,
        asset: str,
        timeframe: str,
    ) -> SyntheticMarketSample | None:
        market_open = metadata.start_date
        market_close = metadata.end_date
        if market_open is None or market_close is None:
            return None
        strike_price = metadata.price_to_beat or _extract_strike(raw_market, metadata)
        if strike_price is None:
            return None
        bars = self._load_symbol_bars(asset, start=market_open - timedelta(days=30), end=market_close)
        if not bars:
            return None
        close_bar = next((bar for bar in reversed(bars) if bar.ts <= market_close), None)
        if close_bar is None:
            return None
        actual_resolution, resolution_source = _resolve_actual_resolution(metadata, raw_market, strike_price, bars, market_close)
        sample_id = f"validation:{metadata.market_id}"
        sample = SyntheticMarketSample(
            sample_id=sample_id,
            market_id=metadata.market_id,
            source="real_validation",
            asset=asset,
            timeframe=timeframe,
            market_open_time=market_open,
            market_close_time=market_close,
            decision_time=market_open,
            decision_horizon_minutes=_SUPPORTED_TIMEFRAMES[timeframe],
            price_to_beat=strike_price,
            close_price=float(close_bar.close),
            actual_resolution=actual_resolution,
            source_provider=resolution_source,
            notes=[f"Real Polymarket closed-market validation using the synthetic feature pipeline ({resolution_source})."],
        )
        self._state.synthetic_market_samples.setdefault(sample.sample_id, sample)
        if self._persistence is not None:
            self._persistence.save_synthetic_market_sample(sample)
        return sample

    def _filtered_samples(
        self,
        *,
        asset: str | None,
        timeframe: str | None,
        start: datetime | None,
        end: datetime | None,
        limit: int,
    ) -> list[SyntheticMarketSample]:
        samples = list(self._state.synthetic_market_samples.values())
        if asset is not None:
            samples = [sample for sample in samples if sample.asset.upper() == asset.upper()]
        if timeframe is not None:
            samples = [sample for sample in samples if sample.timeframe == timeframe]
        if start is not None:
            samples = [sample for sample in samples if sample.market_close_time >= start]
        if end is not None:
            samples = [sample for sample in samples if sample.market_open_time <= end]
        samples.sort(key=lambda sample: sample.market_close_time, reverse=True)
        return samples[:limit]

    def _load_symbol_bars(self, symbol: str, *, start: datetime | None = None, end: datetime | None = None) -> list[OHLCVBar]:
        normalized = symbol.upper()
        report = self._state.external_dataset_validation.get(normalized)
        start = start or (report.first_timestamp if report and report.first_timestamp else datetime(2020, 1, 1, tzinfo=UTC))
        end = end or (report.last_timestamp if report and report.last_timestamp else datetime.now(tz=UTC))
        _, bars = self._historical_provider.fetch_bars(normalized, start, end, "1m")
        bars.sort(key=lambda bar: bar.ts)
        return bars


def _return_from_closes(closes: list[float], lookback: int) -> float | None:
    if len(closes) <= lookback:
        return None
    prev = closes[-lookback - 1]
    current = closes[-1]
    if prev == 0:
        return None
    return (current - prev) / prev


def _realized_volatility(closes: list[float], lookback: int) -> float | None:
    if len(closes) <= lookback:
        return None
    window = closes[-(lookback + 1):]
    returns = []
    for previous, current in zip(window, window[1:], strict=False):
        if previous:
            returns.append((current - previous) / previous)
    if len(returns) < 2:
        return None
    return pstdev(returns)


def _range_position(bars: list[OHLCVBar], current_price: float) -> float | None:
    highs = [bar.high for bar in bars]
    lows = [bar.low for bar in bars]
    if not highs or not lows:
        return None
    high = max(highs)
    low = min(lows)
    if high == low:
        return 0.5
    return max(0.0, min(1.0, (current_price - low) / (high - low)))


def _trend_regime(ret_5m: float | None, ret_15m: float | None, vol_15m: float | None) -> str:
    if ret_15m is None:
        return "unknown"
    if ret_15m > 0.004 and (ret_5m or 0.0) > 0 and (vol_15m or 0.0) < 0.02:
        return "strong_uptrend"
    if ret_15m > 0.001:
        return "uptrend"
    if ret_15m < -0.004 and (ret_5m or 0.0) < 0 and (vol_15m or 0.0) < 0.02:
        return "strong_downtrend"
    if ret_15m < -0.001:
        return "downtrend"
    return "sideways"


def _time_of_day_bucket(ts: datetime) -> str:
    hour = ts.astimezone(UTC).hour
    if 0 <= hour < 6:
        return "overnight"
    if 6 <= hour < 11:
        return "morning"
    if 11 <= hour < 15:
        return "midday"
    if 15 <= hour < 20:
        return "afternoon"
    return "evening"


def _bucket_label(confidence: float) -> str:
    if confidence >= 0.7:
        return "high"
    if confidence >= 0.55:
        return "medium"
    return "low"


def _bucket_hit_rate(records: list[SyntheticEvaluationRecord], bucket: str) -> float:
    subset = [record for record in records if _bucket_label(record.confidence) == bucket and record.correctness is not None]
    if not subset:
        return 0.0
    return sum(1 for record in subset if record.correctness) / len(subset)


def _avg(values) -> float:
    values = [value for value in values if value is not None]
    return fmean(values) if values else 0.0


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _extract_strike(raw_market: dict, metadata: PolymarketMarketMetadata) -> float | None:
    for key in ("price_to_beat", "strike", "threshold"):
        value = raw_market.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                pass
    if metadata.price_to_beat is not None:
        return metadata.price_to_beat
    return None


def _resolve_actual_resolution(
    metadata: PolymarketMarketMetadata,
    raw_market: dict,
    strike_price: float,
    bars: list[OHLCVBar],
    market_close: datetime,
) -> tuple[str, str]:
    if metadata.resolved_outcome in {"yes", "no"}:
        return metadata.resolved_outcome, "polymarket:resolved_outcome"
    winner = raw_market.get("winner") or raw_market.get("outcome")
    if isinstance(winner, str) and winner.lower() in {"yes", "no"}:
        return winner.lower(), "polymarket:raw_market"
    closing_bar = next((bar for bar in reversed(bars) if bar.ts <= market_close), None)
    if closing_bar is None:
        return "unknown", "unresolved"
    return ("yes" if closing_bar.close > strike_price else "no"), "derived_from_external_close"


def _sync_await(result):
    if hasattr(result, "__await__"):
        import asyncio

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(result)
        raise RuntimeError("Synthetic closed-market discovery cannot run inside an active event loop synchronously")
    return result
