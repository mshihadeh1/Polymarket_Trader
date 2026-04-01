from __future__ import annotations

import logging
from bisect import bisect_right
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from statistics import fmean, pstdev

from packages.clients.market_data_provider import HistoricalMarketDataProvider
from packages.config import Settings
from packages.core_types import (
    BacktestMetric,
    FeatureAvailability,
    MinuteBatchReport,
    MinuteEvaluationRecord,
    MinuteFeatureSnapshot,
    MinuteResearchRow,
    PolymarketMarketMetadata,
)
from packages.db import ResearchPersistence
from services.backtester.minute_strategies import (
    MinuteBaseStrategy,
    MinuteStrategyContext,
    build_minute_strategy_registry,
)
from services.feature_engine.market_window import MarketWindowService
from services.market_catalog.classifier import classify_polymarket_market
from services.market_catalog.short_horizon import normalize_short_horizon_market
from services.state import InMemoryState

logger = logging.getLogger(__name__)

_SUPPORTED_TIMEFRAMES = {"crypto_5m": 5, "crypto_15m": 15}


class MinuteResearchService:
    def __init__(
        self,
        settings: Settings,
        state: InMemoryState,
        historical_provider: HistoricalMarketDataProvider,
        polymarket_client,
        market_window: MarketWindowService,
        persistence: ResearchPersistence | None = None,
        strategy_registry: dict[str, MinuteBaseStrategy] | None = None,
    ) -> None:
        self._settings = settings
        self._state = state
        self._historical_provider = historical_provider
        self._polymarket_client = polymarket_client
        self._market_window = market_window
        self._persistence = persistence
        self._strategy_registry = strategy_registry or build_minute_strategy_registry()
        self._bar_cache: dict[str, list] = {}
        self._feature_cache: dict[str, MinuteFeatureSnapshot] = {}

    def list_strategies(self) -> list[dict]:
        return [strategy.descriptor.model_dump(mode="json") for strategy in self._strategy_registry.values()]

    def list_rows(
        self,
        *,
        asset: str | None = None,
        limit: int = 200,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[MinuteResearchRow]:
        rows = self._load_rows()
        rows = self._filter_rows(rows, asset=asset, start=start, end=end)
        return rows[:limit]

    def list_reports(self, source: str | None = None, timeframe: str | None = None) -> list[MinuteBatchReport]:
        reports = list(self._state.minute_batch_reports)
        if self._persistence is not None and self._persistence.enabled:
            persisted = self._persistence.list_minute_batch_reports()
            merged = {report.run_id: report for report in reports}
            for report in persisted:
                merged.setdefault(report.run_id, report)
            reports = list(merged.values())
        if source is not None:
            reports = [report for report in reports if report.source == source]
        if timeframe is not None:
            reports = [report for report in reports if report.timeframe_filter == timeframe]
        return sorted(reports, key=lambda report: report.created_at or datetime.min.replace(tzinfo=UTC), reverse=True)

    def build_minute_dataset(
        self,
        *,
        asset: str | None = "BTC",
        start: datetime | None = None,
        end: datetime | None = None,
        refresh: bool = False,
    ) -> list[MinuteResearchRow]:
        if not self._historical_provider.capabilities().has_ohlcv:
            return []
        assets = [asset.upper()] if asset else [symbol.strip().upper() for symbol in self._settings.default_underlyings.split(",") if symbol.strip()]
        end = end or datetime.now(tz=UTC)
        start = start or (end - timedelta(days=14))
        rows: list[MinuteResearchRow] = []
        for symbol in assets:
            bars = self._load_symbol_bars(symbol, start=start, end=end, refresh=refresh)
            if len(bars) < 45:
                continue
            rows.extend(self._build_rows_for_symbol(symbol, bars))
        rows.sort(key=lambda row: row.decision_time)
        for row in rows:
            if refresh or row.row_id not in self._state.minute_research_rows:
                self._state.minute_research_rows[row.row_id] = row
                if self._persistence is not None:
                    self._persistence.save_minute_research_row(row)
            feature = self._build_feature_snapshot_for_row(row)
            if feature is not None:
                self._cache_feature_snapshot(feature)
        logger.info("Minute research dataset built asset=%s rows=%s provider=%s", asset or "all", len(rows), self._historical_provider.provider_name)
        return rows

    def run_batch(
        self,
        *,
        asset: str | None = "BTC",
        timeframe: str = "crypto_5m",
        strategy_name: str = "minute_momentum",
        limit: int = 500,
        start: datetime | None = None,
        end: datetime | None = None,
        refresh: bool = False,
    ) -> MinuteBatchReport:
        strategy = self._strategy_registry[strategy_name]
        horizon_minutes = _SUPPORTED_TIMEFRAMES.get(timeframe)
        if horizon_minutes is None:
            raise ValueError(f"Unsupported timeframe={timeframe}")
        rows = self._ensure_rows(asset=asset, start=start, end=end, refresh=refresh)
        rows = self._filter_rows(rows, asset=asset, start=start, end=end)[:limit]
        if not rows:
            raise ValueError("No minute research rows available")
        records: list[MinuteEvaluationRecord] = []
        coverage = defaultdict(int)
        for row in rows:
            feature = self._feature_for_row(row)
            if feature is None:
                continue
            decision = strategy.decide(MinuteStrategyContext(feature_snapshot=feature))
            label_up, future_return, close_price = self._label_for_row(row, horizon_minutes)
            correctness = None
            if decision.decision == "higher":
                correctness = label_up is True
            elif decision.decision == "lower":
                correctness = label_up is False
            coverage["rows_with_features"] += 1
            coverage["bars_only"] += 1
            records.append(
                MinuteEvaluationRecord(
                    row_id=row.row_id,
                    asset=row.asset,
                    source=row.source,
                    decision_time=row.decision_time,
                    horizon_minutes=horizon_minutes,
                    strategy_name=strategy_name,
                    decision=decision.decision,
                    confidence=decision.confidence,
                    signal_value=decision.signal_value,
                    actual_label_up=label_up,
                    correctness=correctness,
                    future_return=future_return,
                    reference_price=row.reference_price,
                    close_price=close_price,
                    feature_snapshot_summary=feature.feature_summary,
                    notes=[*row.notes, f"horizon={horizon_minutes}m"],
                )
            )
        report = self._build_report(
            records=records,
            strategy_name=strategy_name,
            source="synthetic",
            asset=asset,
            timeframe=timeframe,
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
        strategy_name: str = "minute_momentum",
        limit: int = 50,
        start: datetime | None = None,
        end: datetime | None = None,
        refresh: bool = False,
    ) -> MinuteBatchReport:
        strategy = self._strategy_registry[strategy_name]
        rows = self._build_real_validation_rows(asset=asset, timeframe=timeframe, limit=limit, start=start, end=end, refresh=refresh)
        if not rows:
            raise ValueError("No closed Polymarket markets available for validation")
        records: list[MinuteEvaluationRecord] = []
        coverage = defaultdict(int)
        for row in rows:
            feature = self._feature_for_row(row)
            if feature is None:
                continue
            decision = strategy.decide(MinuteStrategyContext(feature_snapshot=feature))
            horizon_minutes = 5 if row.row_id.endswith(":5m") else 15
            label_up, future_return, close_price = self._label_for_row(row, horizon_minutes)
            correctness = None
            if decision.decision == "higher":
                correctness = label_up is True
            elif decision.decision == "lower":
                correctness = label_up is False
            coverage["rows_with_features"] += 1
            coverage["bars_only"] += 1
            records.append(
                MinuteEvaluationRecord(
                    row_id=row.row_id,
                    asset=row.asset,
                    source="real_validation",
                    decision_time=row.decision_time,
                    horizon_minutes=horizon_minutes,
                    strategy_name=strategy_name,
                    decision=decision.decision,
                    confidence=decision.confidence,
                    signal_value=decision.signal_value,
                    actual_label_up=label_up,
                    correctness=correctness,
                    future_return=future_return,
                    reference_price=row.reference_price,
                    close_price=close_price,
                    feature_snapshot_summary=feature.feature_summary,
                    notes=[*row.notes, "Real Polymarket validation run"],
                )
            )
        report = self._build_report(
            records=records,
            strategy_name=strategy_name,
            source="real_validation",
            asset=asset,
            timeframe=timeframe,
            limit=limit,
            coverage=dict(coverage),
        )
        self._persist_report(report)
        return report

    def list_validation_results(self, timeframe: str | None = None) -> list[MinuteBatchReport]:
        return self.list_reports(source="real_validation", timeframe=timeframe)

    def list_synthetic_results(self, timeframe: str | None = None) -> list[MinuteBatchReport]:
        return self.list_reports(source="synthetic", timeframe=timeframe)

    def build_live_feature_view(self, asset: str = "BTC") -> dict:
        rows = self.list_rows(asset=asset, limit=1)
        if not rows:
            self.build_minute_dataset(asset=asset)
            rows = self.list_rows(asset=asset, limit=1)
        row = rows[0] if rows else None
        if row is None:
            raise KeyError(f"Unknown minute research asset={asset}")
        feature = self._feature_for_row(row)
        if feature is None:
            raise KeyError(f"No feature snapshot available for asset={asset}")
        availability = FeatureAvailability(
            bars_available=True,
            trades_available=False,
            orderbook_available=False,
            enriched_with_hyperliquid=False,
            notes=[
                "Minute-level research view computed from local 1-minute bars.",
                "Hyperliquid enrichment remains optional and is not required for the first milestone.",
            ],
        )
        return {
            "asset": asset,
            "decision_time": row.decision_time,
            "row": row,
            "snapshot": feature,
            "availability": availability,
            "notes": availability.notes,
        }

    def _persist_report(self, report: MinuteBatchReport) -> None:
        self._state.minute_batch_reports.insert(0, report)
        if self._persistence is not None:
            self._persistence.save_minute_batch_report(report)

    def _build_report(
        self,
        *,
        records: list[MinuteEvaluationRecord],
        strategy_name: str,
        source: str,
        asset: str | None,
        timeframe: str | None,
        limit: int,
        coverage: dict[str, int],
    ) -> MinuteBatchReport:
        total = len(records)
        hits = sum(1 for record in records if record.correctness is True)
        avg_confidence = _avg(record.confidence for record in records)
        avg_signal = _avg(abs(record.signal_value) for record in records)
        trade_frequency = _ratio(sum(1 for record in records if record.decision != "hold"), total)
        contract_score = sum(1.0 if record.correctness is True else -1.0 if record.correctness is False else 0.0 for record in records)
        return MinuteBatchReport(
            run_id=f"{source}:{strategy_name}:{timeframe or 'all'}:{asset or 'all'}:{int(datetime.now(tz=UTC).timestamp())}",
            strategy_name=strategy_name,
            source=source,
            asset_filter=asset,
            timeframe_filter=timeframe,
            limit=limit,
            created_at=datetime.now(tz=UTC),
            total_rows=total,
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

    def _ensure_rows(
        self,
        *,
        asset: str | None,
        start: datetime | None,
        end: datetime | None,
        refresh: bool,
    ) -> list[MinuteResearchRow]:
        rows = self._load_rows()
        rows = self._filter_rows(rows, asset=asset, start=start, end=end)
        if rows and not refresh:
            return rows
        return self.build_minute_dataset(asset=asset, start=start, end=end, refresh=refresh)

    def _load_rows(self) -> list[MinuteResearchRow]:
        if self._state.minute_research_rows:
            return sorted(self._state.minute_research_rows.values(), key=lambda row: row.decision_time)
        if self._persistence is not None and self._persistence.enabled:
            rows = self._persistence.list_minute_research_rows()
            for row in rows:
                self._state.minute_research_rows.setdefault(row.row_id, row)
            return rows
        return []

    def _filter_rows(
        self,
        rows: list[MinuteResearchRow],
        *,
        asset: str | None,
        start: datetime | None,
        end: datetime | None,
    ) -> list[MinuteResearchRow]:
        filtered = list(rows)
        if asset is not None:
            filtered = [row for row in filtered if row.asset.upper() == asset.upper()]
        if start is not None:
            filtered = [row for row in filtered if row.decision_time >= start]
        if end is not None:
            filtered = [row for row in filtered if row.decision_time <= end]
        return sorted(filtered, key=lambda row: row.decision_time)

    def _load_symbol_bars(
        self,
        symbol: str,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        refresh: bool = False,
    ):
        normalized = symbol.upper()
        if normalized in self._bar_cache and not refresh:
            return self._bar_cache[normalized]
        report = self._state.external_dataset_validation.get(normalized)
        if start is None and report and report.first_timestamp is not None:
            start = report.first_timestamp
        if end is None and report and report.last_timestamp is not None:
            end = report.last_timestamp
        start = start or datetime(2020, 1, 1, tzinfo=UTC)
        end = end or datetime.now(tz=UTC)
        _, bars = self._historical_provider.fetch_bars(normalized, start, end, "1m")
        bars.sort(key=lambda bar: bar.ts)
        self._bar_cache[normalized] = bars
        return bars

    def _build_rows_for_symbol(self, symbol: str, bars) -> list[MinuteResearchRow]:
        rows: list[MinuteResearchRow] = []
        if len(bars) < 45:
            return rows
        for index in range(30, len(bars) - 15):
            row = self._build_row_for_bar(symbol=symbol, bars=bars, index=index)
            if row is not None:
                rows.append(row)
        return rows

    def _build_row_for_bar(self, *, symbol: str, bars, index: int) -> MinuteResearchRow | None:
        current_bar = bars[index]
        future_5m = bars[index + 5]
        future_15m = bars[index + 15]
        reference_price = float(current_bar.close)
        close_5m = float(future_5m.close)
        close_15m = float(future_15m.close)
        row_id = f"minute:{symbol}:{int(current_bar.ts.timestamp())}"
        return MinuteResearchRow(
            row_id=row_id,
            asset=symbol,
            source="synthetic",
            decision_time=current_bar.ts,
            reference_price=reference_price,
            close_5m=close_5m,
            close_15m=close_15m,
            label_up_5m=close_5m > reference_price,
            label_up_15m=close_15m > reference_price,
            future_return_5m=_future_return(reference_price, close_5m),
            future_return_15m=_future_return(reference_price, close_15m),
            source_provider=self._historical_provider.provider_name,
            notes=["Generated from minute-aligned historical bars."],
        )

    def _feature_for_row(self, row: MinuteResearchRow) -> MinuteFeatureSnapshot | None:
        cached = self._feature_cache.get(row.row_id)
        if cached is not None:
            return cached
        bars = self._load_symbol_bars(row.asset, end=row.decision_time)
        feature = self._build_feature_snapshot_for_row(row, bars=bars)
        if feature is not None:
            self._cache_feature_snapshot(feature)
        return feature

    def _build_feature_snapshot_for_row(self, row: MinuteResearchRow, bars=None) -> MinuteFeatureSnapshot | None:
        if bars is None:
            bars = self._load_symbol_bars(row.asset, end=row.decision_time)
        relevant = [bar for bar in bars if bar.ts <= row.decision_time]
        if not relevant:
            return None
        current = relevant[-1]
        closes = [float(bar.close) for bar in relevant]
        current_price = float(current.close)
        ret_1m = _return_from_closes(closes, 1)
        ret_3m = _return_from_closes(closes, 3)
        ret_5m = _return_from_closes(closes, 5)
        ret_15m = _return_from_closes(closes, 15)
        ret_30m = _return_from_closes(closes, 30)
        vol_5m = _realized_volatility(closes, 5)
        vol_15m = _realized_volatility(closes, 15)
        vol_30m = _realized_volatility(closes, 30)
        window = closes[-15:] if len(closes) >= 15 else closes
        mean_price = fmean(window) if window else None
        recent_prices = closes[-30:] if len(closes) >= 30 else closes
        recent_high = max(recent_prices) if recent_prices else None
        recent_low = min(recent_prices) if recent_prices else None
        distance_from_mean = ((current_price - mean_price) / mean_price) if mean_price else None
        distance_from_recent_high = ((current_price - recent_high) / recent_high) if recent_high else None
        distance_from_recent_low = ((current_price - recent_low) / recent_low) if recent_low else None
        range_percentile = _range_position(recent_high, recent_low, current_price)
        slope_5m = _slope(closes, 5)
        slope_15m = _slope(closes, 15)
        acceleration = None
        if slope_5m is not None and slope_15m is not None:
            acceleration = slope_5m - (slope_15m / 3.0)
        regime = _trend_regime(ret_5m, ret_15m, vol_15m)
        session_bucket = _session_bucket(row.decision_time)
        return MinuteFeatureSnapshot(
            row_id=row.row_id,
            asset=row.asset,
            source=row.source,
            decision_time=row.decision_time,
            current_price=current_price,
            ret_1m=ret_1m,
            ret_3m=ret_3m,
            ret_5m=ret_5m,
            ret_15m=ret_15m,
            ret_30m=ret_30m,
            vol_5m=vol_5m,
            vol_15m=vol_15m,
            vol_30m=vol_30m,
            distance_from_mean=distance_from_mean,
            distance_from_recent_high=distance_from_recent_high,
            distance_from_recent_low=distance_from_recent_low,
            range_percentile=range_percentile,
            slope_5m=slope_5m,
            slope_15m=slope_15m,
            acceleration=acceleration,
            regime=regime,
            session_bucket=session_bucket,
            feature_summary={
                "ret_1m": ret_1m,
                "ret_3m": ret_3m,
                "ret_5m": ret_5m,
                "ret_15m": ret_15m,
                "ret_30m": ret_30m,
                "vol_5m": vol_5m,
                "vol_15m": vol_15m,
                "vol_30m": vol_30m,
                "distance_from_mean": distance_from_mean,
                "range_percentile": range_percentile,
                "acceleration": acceleration,
                "regime": regime,
                "session_bucket": session_bucket,
            },
        )

    def _cache_feature_snapshot(self, snapshot: MinuteFeatureSnapshot) -> None:
        self._feature_cache[snapshot.row_id] = snapshot
        self._state.minute_feature_snapshots.setdefault(snapshot.row_id, [])
        cached = self._state.minute_feature_snapshots[snapshot.row_id]
        if not cached or cached[-1].decision_time != snapshot.decision_time:
            cached.append(snapshot)
        if self._persistence is not None:
            self._persistence.save_minute_feature_snapshot(snapshot)

    def _label_for_row(self, row: MinuteResearchRow, horizon_minutes: int) -> tuple[bool, float, float]:
        if horizon_minutes == 5:
            return row.label_up_5m, row.future_return_5m, row.close_5m
        if horizon_minutes == 15:
            return row.label_up_15m, row.future_return_15m, row.close_15m
        raise ValueError(f"Unsupported horizon_minutes={horizon_minutes}")

    def _build_real_validation_rows(
        self,
        *,
        asset: str | None,
        timeframe: str | None,
        limit: int,
        start: datetime | None,
        end: datetime | None,
        refresh: bool,
    ) -> list[MinuteResearchRow]:
        candidates = self._discover_closed_markets(asset=asset, timeframe=timeframe, limit=limit * 3, start=start, end=end)
        rows: list[MinuteResearchRow] = []
        for raw_market, metadata, market_type, underlying in candidates[:limit]:
            if metadata.start_date is None or metadata.end_date is None or underlying is None:
                continue
            rows.extend(
                self._build_validation_rows_for_market(
                    raw_market=raw_market,
                    metadata=metadata,
                    asset=underlying,
                    timeframe=market_type,
                    refresh=refresh,
                )
            )
        return rows

    def _build_validation_rows_for_market(
        self,
        *,
        raw_market: dict,
        metadata: PolymarketMarketMetadata,
        asset: str,
        timeframe: str,
        refresh: bool,
    ) -> list[MinuteResearchRow]:
        market_open = metadata.start_date
        market_close = metadata.end_date
        if market_open is None or market_close is None:
            return []
        bars = self._load_symbol_bars(asset, start=market_open - timedelta(minutes=60), end=market_close, refresh=refresh)
        if len(bars) < 30:
            return []
        open_bar = _bar_at_or_before(bars, market_open)
        if open_bar is None:
            return []
        actual_resolution, resolution_source = _resolve_actual_resolution(metadata, raw_market, bars, market_close)
        rows: list[MinuteResearchRow] = []
        for horizon_minutes in (5, 15):
            future_5 = _bar_at_or_before(bars, market_open + timedelta(minutes=5))
            future_15 = _bar_at_or_before(bars, market_open + timedelta(minutes=15))
            future_bar = future_5 if horizon_minutes == 5 else future_15
            if future_bar is None:
                continue
            row_id = f"validation:{metadata.market_id}:{horizon_minutes}m"
            row = MinuteResearchRow(
                row_id=row_id,
                asset=asset,
                source="real_validation",
                decision_time=open_bar.ts,
                reference_price=float(open_bar.close),
                close_5m=float(future_5.close) if future_5 is not None else float(future_bar.close),
                close_15m=float(future_15.close) if future_15 is not None else float(future_bar.close),
                label_up_5m=actual_resolution == "yes",
                label_up_15m=actual_resolution == "yes",
                future_return_5m=_future_return(float(open_bar.close), float(future_5.close)) if future_5 is not None else _future_return(float(open_bar.close), float(future_bar.close)),
                future_return_15m=_future_return(float(open_bar.close), float(future_15.close)) if future_15 is not None else _future_return(float(open_bar.close), float(future_bar.close)),
                source_provider=resolution_source,
                market_id=metadata.market_id,
                notes=[
                    f"Real Polymarket validation for {metadata.slug or metadata.market_id}",
                    f"resolution_source={resolution_source}",
                    f"timeframe={timeframe}",
                    f"horizon={horizon_minutes}m",
                ],
            )
            rows.append(row)
            self._state.minute_research_rows.setdefault(row.row_id, row)
            if self._persistence is not None:
                self._persistence.save_minute_research_row(row)
            feature = self._build_feature_snapshot_for_row(row, bars=bars)
            if feature is not None:
                self._cache_feature_snapshot(feature)
        return rows

    def _discover_closed_markets(
        self,
        *,
        asset: str | None,
        timeframe: str | None,
        limit: int,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[tuple[dict, PolymarketMarketMetadata, str, str | None]]:
        raw_markets, normalized = self._poll_closed_markets(limit=max(limit, 100))
        discovered: list[tuple[dict, PolymarketMarketMetadata, str, str | None]] = []
        for raw_market, metadata in zip(raw_markets, normalized, strict=False):
            normalized_metadata = normalize_short_horizon_market(metadata, raw_market=raw_market)
            market_type, underlying = classify_polymarket_market(normalized_metadata)
            if market_type not in _SUPPORTED_TIMEFRAMES:
                continue
            if asset is not None and (underlying or "").upper() != asset.upper():
                continue
            if timeframe is not None and market_type != timeframe:
                continue
            if start is not None and normalized_metadata.end_date is not None and normalized_metadata.end_date < start:
                continue
            if end is not None and normalized_metadata.start_date is not None and normalized_metadata.start_date > end:
                continue
            discovered.append((raw_market, normalized_metadata, market_type, underlying))
        discovered.sort(key=lambda item: item[1].end_date or datetime.min.replace(tzinfo=UTC), reverse=True)
        return discovered[:limit]

    def _poll_closed_markets(self, *, limit: int) -> tuple[list[dict], list[PolymarketMarketMetadata]]:
        if hasattr(self._polymarket_client, "discover_markets"):
            try:
                return _sync_await(self._polymarket_client.discover_markets(closed=True, limit=limit))
            except RuntimeError:
                raise
            except Exception:
                logger.exception("Failed to discover closed Polymarket markets for minute validation")
        return [], []


def _future_return(reference: float, future: float) -> float:
    if reference == 0:
        return 0.0
    return (future - reference) / reference


def _return_from_closes(closes: list[float], lookback: int) -> float | None:
    if len(closes) <= lookback:
        return None
    previous = closes[-lookback - 1]
    current = closes[-1]
    if previous == 0:
        return None
    return (current - previous) / previous


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


def _slope(closes: list[float], lookback: int) -> float | None:
    if len(closes) <= lookback:
        return None
    start = closes[-lookback - 1]
    end = closes[-1]
    return (end - start) / lookback if lookback else None


def _range_position(recent_high: float | None, recent_low: float | None, current_price: float) -> float | None:
    if recent_high is None or recent_low is None:
        return None
    if recent_high == recent_low:
        return 0.5
    return max(0.0, min(1.0, (current_price - recent_low) / (recent_high - recent_low)))


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
    return "choppy"


def _session_bucket(ts: datetime) -> str:
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


def _bucket_hit_rate(records: list[MinuteEvaluationRecord], bucket: str) -> float:
    subset = [record for record in records if _bucket_label(record.confidence) == bucket and record.correctness is not None]
    if not subset:
        return 0.0
    return sum(1 for record in subset if record.correctness) / len(subset)


def _avg(values) -> float:
    values = [value for value in values if value is not None]
    return fmean(values) if values else 0.0


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _bar_at_or_before(bars, as_of: datetime):
    timestamps = [bar.ts for bar in bars]
    index = bisect_right(timestamps, as_of) - 1
    if index < 0:
        return None
    return bars[index]


def _resolve_actual_resolution(
    metadata: PolymarketMarketMetadata,
    raw_market: dict,
    bars,
    market_close: datetime,
) -> tuple[str, str]:
    if metadata.resolved_outcome in {"yes", "no"}:
        return metadata.resolved_outcome, "polymarket:resolved_outcome"
    winner = raw_market.get("winner") or raw_market.get("outcome")
    if isinstance(winner, str) and winner.lower() in {"yes", "no"}:
        return winner.lower(), "polymarket:raw_market"
    closing_bar = _bar_at_or_before(bars, market_close)
    if closing_bar is None:
        return "unknown", "unresolved"
    strike = metadata.price_to_beat or _extract_strike(raw_market, metadata)
    if strike is None:
        return "unknown", "unresolved"
    return ("yes" if closing_bar.close > strike else "no"), "derived_from_external_close"


def _extract_strike(raw_market: dict, metadata: PolymarketMarketMetadata) -> float | None:
    for key in ("price_to_beat", "strike", "threshold"):
        value = raw_market.get(key)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                pass
    text = " ".join(filter(None, [metadata.question or "", metadata.slug or "", metadata.description or ""]))
    cleaned = text.replace(",", "")
    for token in cleaned.split():
        try:
            value = float(token)
            if value > 1:
                return value
        except ValueError:
            continue
    return None


def _sync_await(result):
    if hasattr(result, "__await__"):
        import asyncio

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(result)
        raise RuntimeError("Minute research discovery cannot run inside an active event loop synchronously")
    return result
