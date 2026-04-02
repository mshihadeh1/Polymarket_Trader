from __future__ import annotations

from bisect import bisect_left, bisect_right
import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid5

from packages.config import Settings
from packages.db import ResearchPersistence
from packages.core_types.schemas import (
    BacktestMetric,
    BacktestReport,
    BacktestTrade,
    ClosedMarketBatchReport,
    ClosedMarketEvaluationRecord,
    EquityPoint,
    FeatureAvailability,
    MarketDetail,
    OHLCVBar,
    PolymarketMarketMetadata,
)
from services.backtester.strategies import BaseStrategy, StrategyContext, build_strategy_registry
from services.feature_engine.service import FeatureEngineService
from services.market_catalog.classifier import classify_polymarket_market
from services.state import InMemoryState
from packages.utils.time import parse_dt


class BacktesterService:
    def __init__(
        self,
        settings: Settings,
        state: InMemoryState,
        feature_engine: FeatureEngineService,
        polymarket_client,
        external_ingestor,
        persistence: ResearchPersistence | None = None,
        strategy_registry: dict[str, BaseStrategy] | None = None,
    ) -> None:
        self._settings = settings
        self._state = state
        self._feature_engine = feature_engine
        self._polymarket_client = polymarket_client
        self._external_ingestor = external_ingestor
        self._persistence = persistence
        self._strategy_registry = strategy_registry or build_strategy_registry()
        self._synthetic_bar_cache: dict[str, list[dict[str, float | datetime]]] = {}
        self._synthetic_bar_timestamps: dict[str, list[datetime]] = {}

    def list_strategies(self):
        return [strategy.descriptor for strategy in self._strategy_registry.values()]

    def list_reports(self) -> list[BacktestReport]:
        reports = list(self._state.backtest_reports)
        if self._persistence is not None and self._persistence.enabled:
            persisted = self._persistence.list_backtest_reports()
            merged = {report.run_id: report for report in reports}
            for report in persisted:
                merged.setdefault(report.run_id, report)
            reports = list(merged.values())
        return sorted(reports, key=_report_sort_key, reverse=True)

    def list_closed_market_batch_reports(self) -> list[ClosedMarketBatchReport]:
        reports = list(self._state.closed_market_batch_reports)
        if self._persistence is not None and self._persistence.enabled:
            persisted = self._persistence.list_closed_market_batch_reports()
            merged = {report.run_id: report for report in reports}
            for report in persisted:
                merged.setdefault(report.run_id, report)
            reports = list(merged.values())
        return sorted(reports, key=_report_sort_key, reverse=True)

    async def _closed_market_candidates(self, *, limit: int) -> list[tuple[dict, PolymarketMarketMetadata]]:
        closed_markets = [
            market
            for market in self._state.markets.values()
            if market.market_type in {"crypto_5m", "crypto_15m"} and (market.status == "closed" or market.resolved_outcome != "unknown")
        ]
        if closed_markets:
            candidates = []
            for market in closed_markets[:limit]:
                raw_market = {
                    "id": str(market.id),
                    "slug": market.slug,
                    "price_to_beat": market.price_to_beat,
                    "open_reference_price": market.open_reference_price,
                    "resolved_outcome": market.resolved_outcome,
                    "resolution_price": market.resolution_price,
                }
                metadata = PolymarketMarketMetadata(
                    market_id=str(market.id),
                    condition_id="",
                    slug=market.slug,
                    question=market.title,
                    category=market.category,
                    market_family=market.market_family,
                    event_slug=market.event_slug,
                    event_epoch=market.event_epoch,
                    duration_minutes=market.duration_minutes,
                    active=market.status == "active",
                    closed=market.status == "closed",
                    accepting_orders=market.status == "active",
                    enable_order_book=True,
                    start_date=market.opens_at,
                    end_date=market.closes_at,
                    resolution_source=None,
                    description=None,
                    price_to_beat=market.price_to_beat,
                    resolved_outcome=market.resolved_outcome,
                    resolution_price=market.resolution_price,
                    outcomes=[token.outcome for token in market.tokens],
                    outcome_prices=[],
                    token_ids=[token.token_id for token in market.tokens],
                    best_bid=None,
                    best_ask=None,
                    last_trade_price=None,
                    raw_tags=market.tags,
                )
                candidates.append((raw_market, metadata))
            return candidates
        raw_markets, normalized = await self._polymarket_client.discover_markets(closed=True, limit=limit)
        return list(zip(raw_markets, normalized, strict=False))

    def run_baseline(self, market_id: str, strategy_name: str = "no_trade_baseline") -> BacktestReport:
        market = self._state.markets.get(market_id)
        if market is None:
            raise KeyError(f"Unknown market_id={market_id}")
        bars = self._state.external_bars.get(market_id, [])
        if not bars:
            raise ValueError(f"No external bar history loaded for market_id={market_id}")
        return self._run_sequential_market_backtest(
            market_id=market_id,
            market=self._state.market_details[market_id],
            bars=bars,
            polymarket_trades=self._state.polymarket_trades.get(market_id, []),
            external_trades=self._state.external_trades.get(market_id, []),
            polymarket_orderbooks=self._state.polymarket_orderbooks.get(market_id, []),
            external_orderbooks=self._state.external_orderbooks.get(market_id, []),
            strategy_name=strategy_name,
            persist=True,
        )

    async def list_eligible_closed_markets(
        self,
        *,
        asset: str | None = None,
        timeframe: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        eligible = []
        for raw_market, metadata in await self._closed_market_candidates(limit=max(limit * 3, 100)):
            market_type, underlying = classify_polymarket_market(metadata)
            if market_type not in {"crypto_5m", "crypto_15m"}:
                continue
            if asset is not None and (underlying or "").upper() != asset.upper():
                continue
            if timeframe is not None and market_type != timeframe:
                continue
            if metadata.start_date is None or metadata.end_date is None:
                continue
            eligible.append(
                {
                    "market_id": str(raw_market.get("id", metadata.market_id)),
                    "slug": metadata.slug or metadata.market_id,
                    "title": metadata.question or metadata.slug or metadata.market_id,
                    "asset": underlying,
                    "timeframe": market_type,
                    "market_open_time": metadata.start_date,
                    "market_close_time": metadata.end_date,
                    "strike_price": _extract_strike(raw_market, metadata),
                    "resolution_source": metadata.resolution_source,
                }
            )
        eligible.sort(key=lambda item: item["market_close_time"], reverse=True)
        return eligible[:limit]

    async def run_closed_market_comparison(
        self,
        *,
        asset: str | None = None,
        timeframe: str | None = None,
        limit: int = 20,
        strategy_name: str = "combined_cvd_gap",
    ) -> dict[str, ClosedMarketBatchReport]:
        bars_only = await self.run_closed_market_batch(
            asset=asset,
            timeframe=timeframe,
            limit=limit,
            strategy_name=strategy_name,
            include_hyperliquid_enrichment=False,
        )
        enriched = await self.run_closed_market_batch(
            asset=asset,
            timeframe=timeframe,
            limit=limit,
            strategy_name=strategy_name,
            include_hyperliquid_enrichment=True,
        )
        return {
            "bars_only": bars_only,
            "bars_plus_hyperliquid": enriched,
        }

    async def run_closed_market_batch(
        self,
        *,
        asset: str | None = None,
        timeframe: str | None = None,
        limit: int = 20,
        strategy_name: str = "combined_cvd_gap",
        include_hyperliquid_enrichment: bool,
    ) -> ClosedMarketBatchReport:
        strategy = self._strategy_registry[strategy_name]
        records: list[ClosedMarketEvaluationRecord] = []
        coverage = {
            "bars_only": 0,
            "bars_plus_trades": 0,
            "bars_plus_trades_plus_orderbook": 0,
        }
        for raw_market, metadata in await self._closed_market_candidates(limit=max(limit * 3, 100)):
            market_type, underlying = classify_polymarket_market(metadata)
            if market_type not in {"crypto_5m", "crypto_15m"}:
                continue
            if asset is not None and (underlying or "").upper() != asset.upper():
                continue
            if timeframe is not None and market_type != timeframe:
                continue
            if metadata.start_date is None or metadata.end_date is None or underlying is None:
                continue
            record = self._evaluate_closed_market(
                raw_market=raw_market,
                metadata=metadata,
                asset=underlying,
                timeframe=market_type,
                strategy=strategy,
                include_hyperliquid_enrichment=include_hyperliquid_enrichment,
            )
            if record is None:
                continue
            records.append(record)
            if record.enrichment_availability.bars_available and not record.enrichment_availability.trades_available:
                coverage["bars_only"] += 1
            elif record.enrichment_availability.trades_available and not record.enrichment_availability.orderbook_available:
                coverage["bars_plus_trades"] += 1
            elif record.enrichment_availability.orderbook_available:
                coverage["bars_plus_trades_plus_orderbook"] += 1
            if len(records) >= limit:
                break

        accuracy = _ratio(sum(1 for record in records if record.correctness is True), len(records))
        avg_confidence = _average(record.final_confidence for record in records)
        simple_score = sum(1.0 if record.correctness is True else -1.0 if record.correctness is False else 0.0 for record in records)
        report = ClosedMarketBatchReport(
            run_id=f"{strategy_name}:{timeframe or 'all'}:{asset or 'all'}:{'enriched' if include_hyperliquid_enrichment else 'bars'}:{int(datetime.now(timezone.utc).timestamp())}",
            strategy_name=strategy_name,
            mode="bars_plus_hyperliquid" if include_hyperliquid_enrichment else "bars_only",
            asset_filter=asset,
            timeframe_filter=timeframe,
            limit=limit,
            created_at=datetime.now(timezone.utc),
            total_markets_evaluated=len(records),
            metrics=[
                BacktestMetric(label="accuracy", value=accuracy),
                BacktestMetric(label="average_confidence", value=avg_confidence),
                BacktestMetric(label="simple_contract_score", value=simple_score),
                BacktestMetric(label="accuracy_crypto_5m", value=_accuracy_for(records, timeframe="crypto_5m")),
                BacktestMetric(label="accuracy_crypto_15m", value=_accuracy_for(records, timeframe="crypto_15m")),
                BacktestMetric(label=f"accuracy_{(asset or 'all').lower()}", value=_accuracy_for(records, asset=asset)),
            ],
            coverage=coverage,
            records=records,
        )
        self._state.closed_market_batch_reports.insert(0, report)
        if self._persistence is not None and self._persistence.enabled:
            self._persistence.save_closed_market_batch_report(report)
        return report

    async def _discover_short_horizon_closed_markets(
        self,
        *,
        asset: str | None,
        timeframe: str | None,
        limit: int,
    ) -> list[tuple[dict, PolymarketMarketMetadata, str, str | None]]:
        raw_markets, normalized = await self._polymarket_client.discover_markets(closed=True, limit=max(limit * 3, 100))
        discovered: list[tuple[dict, PolymarketMarketMetadata, str, str | None]] = []
        for raw_market, metadata in zip(raw_markets, normalized, strict=False):
            market_type, underlying = classify_polymarket_market(metadata)
            if market_type not in {"crypto_5m", "crypto_15m"}:
                continue
            if asset is not None and (underlying or "").upper() != asset.upper():
                continue
            if timeframe is not None and market_type != timeframe:
                continue
            discovered.append((raw_market, metadata, market_type, underlying))
        if discovered:
            discovered.sort(key=lambda item: item[1].end_date or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
            return discovered[:limit]
        synthetic = self._build_synthetic_closed_markets(asset=asset, timeframe=timeframe, limit=limit)
        return synthetic[:limit]

    def _build_synthetic_closed_markets(
        self,
        *,
        asset: str | None,
        timeframe: str | None,
        limit: int,
    ) -> list[tuple[dict, PolymarketMarketMetadata, str, str | None]]:
        assets = [asset.upper()] if asset else ["BTC", "ETH", "SOL"]
        timeframe_minutes = []
        if timeframe in {None, "crypto_5m"}:
            timeframe_minutes.append(("crypto_5m", 5))
        if timeframe in {None, "crypto_15m"}:
            timeframe_minutes.append(("crypto_15m", 15))

        synthetic: list[tuple[dict, PolymarketMarketMetadata, str, str | None]] = []
        for symbol in assets:
            bars = self._load_symbol_bars(symbol)
            if not bars:
                continue
            for market_type, minutes in timeframe_minutes:
                synthetic.extend(
                    _build_synthetic_markets_from_bars(
                        bars=bars,
                        asset=symbol,
                        market_type=market_type,
                        window_minutes=minutes,
                        limit=limit,
                    )
                )
        synthetic.sort(key=lambda item: item[1].end_date or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        return synthetic[:limit]

    def _load_symbol_bars(self, symbol: str) -> list[dict[str, float | datetime]]:
        normalized = symbol.upper()
        if normalized in self._synthetic_bar_cache:
            return self._synthetic_bar_cache[normalized]
        path_map = {
            key.upper(): value
            for key, value in json.loads(self._settings.csv_provider_paths).items()
            if isinstance(value, str) and value.strip()
        }
        explicit_paths = {
            "BTC": self._settings.csv_btc_path,
            "ETH": self._settings.csv_eth_path,
            "SOL": self._settings.csv_sol_path,
        }
        for key, value in explicit_paths.items():
            if isinstance(value, str) and value.strip():
                path_map[key] = value

        path_value = path_map.get(normalized)
        if not path_value:
            return []
        path = Path(path_value)
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[2] / path
        if not path.exists():
            return []

        rows: list[dict[str, float | datetime]] = []
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                parsed_ts = parse_dt(str(row.get("datetime") or row.get("timestamp") or row.get("ts") or row.get("date") or "").replace(" ", "T"))
                if parsed_ts is None:
                    continue
                rows.append(
                    {
                        "ts": parsed_ts,
                        "open": float(row["open"]),
                        "close": float(row["close"]),
                    }
                )
        rows.sort(key=lambda item: item["ts"])
        self._synthetic_bar_cache[normalized] = rows
        self._synthetic_bar_timestamps[normalized] = [item["ts"] for item in rows if isinstance(item["ts"], datetime)]
        return rows

    def build_live_feature_view(self, market_id: str) -> dict:
        market = self._state.market_details.get(market_id)
        if market is None:
            raise KeyError(f"Unknown market_id={market_id}")
        snapshot = self._feature_engine.compute_snapshot(market_id)
        return {
            "market_id": market.id,
            "market_type": market.market_type,
            "asset": market.underlying,
            "status": market.status,
            "snapshot": snapshot,
            "availability": self._state.external_feature_availability.get(market_id, {}),
            "notes": self._state.external_feature_availability.get(market_id, {}).get("notes", []),
        }

    def _evaluate_closed_market(
        self,
        *,
        raw_market: dict,
        metadata,
        asset: str,
        timeframe: str,
        strategy: BaseStrategy,
        include_hyperliquid_enrichment: bool,
    ) -> ClosedMarketEvaluationRecord | None:
        strike_price = _extract_strike(raw_market, metadata)
        market_detail = _build_market_detail(raw_market, metadata, asset=asset, timeframe=timeframe, strike_price=strike_price)
        window_start = metadata.start_date - timedelta(minutes=max(self._feature_engine._windows, default=15))
        window_end = metadata.end_date
        if metadata.resolution_source == "synthetic_from_csv_close":
            assembled = self._assemble_synthetic_window(asset, start=window_start, end=window_end)
        else:
            assembled = self._external_ingestor.assemble_window(
                asset,
                start=window_start,
                end=window_end,
                include_recent_enrichment=include_hyperliquid_enrichment,
                include_current_orderbook=False,
            )
        bars = assembled["bars"]
        if not bars:
            return None

        decision_timeline = []
        for bar in [bar for bar in bars if metadata.start_date <= bar.ts <= metadata.end_date]:
            snapshot = self._feature_engine.compute_snapshot_from_series(
                market_id=str(market_detail.id),
                market=market_detail,
                external_bars_all=bars,
                polymarket_trades_all=[],
                external_trades_all=assembled["trades"],
                orderbooks_all=[],
                external_orderbooks_all=assembled["orderbooks"],
                as_of=bar.ts,
                persist=False,
            )
            market_price = self._mark_price(snapshot, bar.close)
            decision = strategy.decide(StrategyContext(market_price=market_price, feature_snapshot=snapshot))
            decision_timeline.append((bar.ts, snapshot, decision))

        if not decision_timeline:
            return None
        final_ts, final_snapshot, final_decision = decision_timeline[-1]
        actual_resolution, resolution_source, resolution_price = _resolve_actual_outcome(metadata, raw_market, strike_price, bars, metadata.end_date)
        correctness = None
        if final_decision.decision in {"buy_yes", "passive_yes"}:
            correctness = actual_resolution == "yes"
        elif final_decision.decision in {"buy_no", "passive_no"}:
            correctness = actual_resolution == "no"

        notes = list(assembled["availability"].notes)
        if resolution_price is not None and strike_price is not None:
            notes.append(f"Derived closing reference={resolution_price:.4f} vs strike={strike_price:.4f}")

        return ClosedMarketEvaluationRecord(
            market_id=market_detail.id,
            market_slug=market_detail.slug,
            asset=asset,
            timeframe=timeframe,
            market_open_time=metadata.start_date,
            market_close_time=metadata.end_date,
            strike_price=strike_price,
            actual_resolution=actual_resolution,
            actual_resolution_source=resolution_source,
            historical_window_start=window_start,
            historical_window_end=window_end,
            enrichment_availability=assembled["availability"],
            feature_snapshot_summary={
                "fair_value_gap": final_snapshot.fair_value_gap,
                "external_return_since_open": final_snapshot.external_return_since_open,
                "external_cvd": final_snapshot.external_cvd,
                "external_trade_imbalance": final_snapshot.external_trade_imbalance,
                "time_to_close_seconds": final_snapshot.time_to_close_seconds,
            },
            final_decision=final_decision.decision,
            final_confidence=final_decision.confidence,
            final_signal_value=final_decision.signal_value,
            correctness=correctness,
            notes=notes,
        )

    def _assemble_synthetic_window(self, symbol: str, *, start: datetime, end: datetime) -> dict:
        rows = self._load_symbol_bars(symbol)
        timestamps = self._synthetic_bar_timestamps.get(symbol.upper(), [])
        if timestamps:
            start_index = bisect_left(timestamps, start)
            end_index = bisect_right(timestamps, end)
            window_rows = rows[start_index:end_index]
        else:
            window_rows = [row for row in rows if start <= row["ts"] <= end]
        bars = [
            OHLCVBar(
                ts=row["ts"],
                symbol=symbol,
                provider="csv_synthetic",
                open=float(row["open"]),
                high=max(float(row["open"]), float(row["close"])),
                low=min(float(row["open"]), float(row["close"])),
                close=float(row["close"]),
                volume=0.0,
                interval="1m",
            )
            for row in window_rows
        ]
        return {
            "bars": bars,
            "trades": [],
            "orderbooks": [],
            "raw_payloads": {"bars": []},
            "availability": FeatureAvailability(
                bars_available=bool(bars),
                trades_available=False,
                orderbook_available=False,
                enriched_with_hyperliquid=False,
                notes=["Synthetic evaluation window sourced from local CSV history."],
            ),
        }

    def _run_sequential_market_backtest(
        self,
        *,
        market_id: str,
        market: MarketDetail,
        bars,
        polymarket_trades,
        external_trades,
        polymarket_orderbooks,
        external_orderbooks,
        strategy_name: str,
        persist: bool,
    ) -> BacktestReport:
        strategy = self._strategy_registry[strategy_name]
        position = 0.0
        entry_price: float | None = None
        realized_pnl = 0.0
        trades: list[BacktestTrade] = []
        equity_curve: list[EquityPoint] = []
        decisions = []
        peak_equity = 0.0
        max_drawdown = 0.0

        size = self._settings.backtest_position_size
        fee_rate = self._settings.backtest_fee_bps / 10_000
        slippage_rate = self._settings.backtest_slippage_bps / 10_000

        for bar in bars:
            snapshot = self._feature_engine.compute_snapshot_from_series(
                market_id=market_id,
                market=market,
                external_bars_all=bars,
                polymarket_trades_all=polymarket_trades,
                external_trades_all=external_trades,
                orderbooks_all=polymarket_orderbooks,
                external_orderbooks_all=external_orderbooks,
                as_of=bar.ts,
                persist=False,
            )
            mark_price = self._mark_price(snapshot, bar.close)
            decision = strategy.decide(StrategyContext(market_price=mark_price, feature_snapshot=snapshot))
            decisions.append(decision)
            target_position = self._target_position(decision.decision, current_position=position)
            if target_position != position:
                realized_pnl, entry_price = self._rebalance_position(
                    market_id=market.id,
                    ts=bar.ts,
                    position=position,
                    target_position=target_position,
                    mark_price=mark_price,
                    entry_price=entry_price,
                    realized_pnl=realized_pnl,
                    size=size,
                    fee_rate=fee_rate,
                    slippage_rate=slippage_rate,
                    reason=decision.reason,
                    trades=trades,
                )
                position = target_position
            unrealized = 0.0
            if position != 0.0 and entry_price is not None:
                unrealized = (mark_price - entry_price) * size * position
            equity = realized_pnl + unrealized
            peak_equity = max(peak_equity, equity)
            max_drawdown = min(max_drawdown, equity - peak_equity)
            equity_curve.append(EquityPoint(ts=bar.ts, equity=equity, realized_pnl=realized_pnl, unrealized_pnl=unrealized, position=position))

        if position != 0.0 and entry_price is not None:
            final_bar = bars[-1]
            final_snapshot = self._feature_engine.compute_snapshot_from_series(
                market_id=market_id,
                market=market,
                external_bars_all=bars,
                polymarket_trades_all=polymarket_trades,
                external_trades_all=external_trades,
                orderbooks_all=polymarket_orderbooks,
                external_orderbooks_all=external_orderbooks,
                as_of=final_bar.ts,
                persist=False,
            )
            final_price = self._mark_price(final_snapshot, final_bar.close)
            realized_pnl, entry_price = self._close_position(
                market_id=market.id,
                ts=final_bar.ts,
                position=position,
                mark_price=final_price,
                entry_price=entry_price,
                realized_pnl=realized_pnl,
                size=size,
                fee_rate=fee_rate,
                slippage_rate=slippage_rate,
                reason="Forced close at end of historical replay",
                trades=trades,
            )
            if equity_curve:
                equity_curve[-1] = EquityPoint(ts=final_bar.ts, equity=realized_pnl, realized_pnl=realized_pnl, unrealized_pnl=0.0, position=0.0)

        gross_pnl = sum(trade.gross_pnl for trade in trades)
        net_pnl = sum(trade.net_pnl for trade in trades)
        total_cost = sum(trade.cost for trade in trades)
        trade_count = len(trades)
        winning_trades = sum(1 for trade in trades if trade.net_pnl > 0)
        expectancy = net_pnl / trade_count if trade_count else 0.0
        avg_edge = sum((decision.reasoning_fields.get("fair_value_gap") or 0.0) for decision in decisions) / len(decisions) if decisions else 0.0

        report = BacktestReport(
            run_id=f"{strategy_name}:{market_id}:{int(datetime.now(timezone.utc).timestamp())}",
            strategy_name=strategy_name,
            market_id=market.id,
            metrics=[
                BacktestMetric(label="gross_pnl", value=gross_pnl),
                BacktestMetric(label="net_pnl", value=net_pnl),
                BacktestMetric(label="hit_rate", value=(winning_trades / trade_count) if trade_count else 0.0),
                BacktestMetric(label="avg_edge_at_entry", value=avg_edge),
                BacktestMetric(label="expectancy_per_trade", value=expectancy),
                BacktestMetric(label="drawdown", value=max_drawdown),
                BacktestMetric(label="total_explicit_cost", value=total_cost),
                BacktestMetric(label="bar_count", value=float(len(bars))),
            ],
            created_at=datetime.now(timezone.utc),
            trade_count=trade_count,
            decisions=decisions[-250:],
            trades=trades,
            equity_curve=equity_curve,
            notes=[
                "Sequential 1-minute replay over normalized external bars.",
                "Execution uses explicit simple costs and dry-run mark-price approximations when Polymarket history is unavailable.",
            ],
        )
        self._state.backtest_reports.insert(0, report)
        if persist and self._persistence is not None:
            self._persistence.save_backtest_report(report)
        return report

    def _mark_price(self, snapshot, fallback_close: float) -> float:
        if snapshot.best_bid is not None and snapshot.best_ask is not None:
            return (snapshot.best_bid + snapshot.best_ask) / 2
        if snapshot.fair_value_estimate is not None:
            return snapshot.fair_value_estimate
        return min(max(0.5 + (snapshot.external_return_since_open or 0.0) * 4, 0.01), 0.99) if fallback_close else 0.5

    def _target_position(self, decision: str, current_position: float) -> float:
        if decision in {"buy_yes", "passive_yes"}:
            return 1.0
        if decision in {"buy_no", "passive_no"}:
            return -1.0
        return current_position

    def _rebalance_position(self, market_id, ts, position, target_position, mark_price, entry_price, realized_pnl, size, fee_rate, slippage_rate, reason, trades):
        updated_realized = realized_pnl
        updated_entry = entry_price
        if position != 0.0 and entry_price is not None:
            updated_realized, updated_entry = self._close_position(market_id, ts, position, mark_price, entry_price, updated_realized, size, fee_rate, slippage_rate, reason, trades)
        if target_position != 0.0:
            cost = mark_price * size * (fee_rate + slippage_rate)
            trades.append(BacktestTrade(ts=ts, market_id=market_id, action="open_long" if target_position > 0 else "open_short", side="buy_yes" if target_position > 0 else "buy_no", price=mark_price, size=size, gross_pnl=0.0, net_pnl=-cost, cost=cost, reason=reason))
            updated_realized -= cost
            updated_entry = mark_price
        return updated_realized, updated_entry

    def _close_position(self, market_id, ts, position, mark_price, entry_price, realized_pnl, size, fee_rate, slippage_rate, reason, trades):
        gross_pnl = (mark_price - entry_price) * size * position
        cost = mark_price * size * (fee_rate + slippage_rate)
        net_pnl = gross_pnl - cost
        trades.append(BacktestTrade(ts=ts, market_id=market_id, action="close_long" if position > 0 else "close_short", side="buy_yes" if position > 0 else "buy_no", price=mark_price, size=size, gross_pnl=gross_pnl, net_pnl=net_pnl, cost=cost, reason=reason))
        return realized_pnl + net_pnl, None


def _extract_strike(raw_market: dict, metadata) -> float | None:
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


def _report_sort_key(report: BacktestReport | ClosedMarketBatchReport) -> datetime:
    created_at = report.created_at
    if created_at is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if created_at.tzinfo is None:
        return created_at.replace(tzinfo=timezone.utc)
    return created_at


def _build_market_detail(raw_market: dict, metadata, *, asset: str, timeframe: str, strike_price: float | None) -> MarketDetail:
    market_uuid = UUID(metadata.market_id) if _is_uuid(metadata.market_id) else uuid5(NAMESPACE_URL, f"polymarket:{metadata.market_id}")
    return MarketDetail(
        id=market_uuid,
        slug=metadata.slug or metadata.market_id,
        title=metadata.question or metadata.slug or metadata.market_id,
        category=metadata.category or "crypto",
        market_type=timeframe,
        underlying=asset,
        status="closed",
        opens_at=metadata.start_date,
        closes_at=metadata.end_date,
        resolves_at=metadata.end_date,
        price_to_beat=strike_price,
        open_reference_price=_extract_open_reference(raw_market, metadata),
        source="real" if raw_market else "mock",
    )


def _extract_open_reference(raw_market: dict, metadata) -> float | None:
    for key in ("open_reference_price", "referencePrice", "openPrice"):
        value = raw_market.get(key)
        try:
            return None if value is None else float(value)
        except (TypeError, ValueError):
            continue
    return metadata.last_trade_price


def _resolve_actual_outcome(metadata, raw_market: dict, strike_price: float | None, bars, market_close: datetime):
    if getattr(metadata, "resolved_outcome", "unknown") in {"yes", "no"}:
        return metadata.resolved_outcome, "polymarket:resolved_outcome", getattr(metadata, "resolution_price", None)
    for key, winner in (("winner", raw_market.get("winner")), ("outcome", raw_market.get("outcome"))):
        if isinstance(winner, str):
            lowered = winner.lower()
            if lowered in {"yes", "no"}:
                return lowered, f"polymarket:{key}", None
    closing_bar = next((bar for bar in reversed(bars) if bar.ts <= market_close), None)
    if closing_bar is not None and strike_price is not None:
        return ("yes" if closing_bar.close > strike_price else "no"), "derived_from_external_close", closing_bar.close
    return "unknown", None, None


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _average(values) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def _accuracy_for(records: list[ClosedMarketEvaluationRecord], *, timeframe: str | None = None, asset: str | None = None) -> float:
    filtered = [
        record
        for record in records
        if (timeframe is None or record.timeframe == timeframe)
        and (asset is None or record.asset == asset)
        and record.correctness is not None
    ]
    return _ratio(sum(1 for record in filtered if record.correctness), len(filtered))


def _is_uuid(value: str) -> bool:
    try:
        UUID(value)
        return True
    except ValueError:
        return False


def _build_synthetic_markets_from_bars(
    *,
    bars: list[dict[str, float | datetime]],
    asset: str,
    market_type: str,
    window_minutes: int,
    limit: int,
) -> list[tuple[dict, PolymarketMarketMetadata, str, str | None]]:
    synthetic: list[tuple[dict, PolymarketMarketMetadata, str, str | None]] = []
    usable = len(bars) - (len(bars) % window_minutes)
    if usable <= 0:
        return synthetic

    windows = bars[:usable]
    for index in range(0, usable, window_minutes):
        chunk = windows[index:index + window_minutes]
        if len(chunk) != window_minutes:
            continue
        open_ts = chunk[0]["ts"]
        close_ts = chunk[-1]["ts"]
        if not isinstance(open_ts, datetime) or not isinstance(close_ts, datetime):
            continue
        open_price = float(chunk[0]["open"])
        close_price = float(chunk[-1]["close"])
        close_label = (close_ts + timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M UTC")
        duration_label = "5m" if window_minutes == 5 else "15m"
        slug = f"synthetic-{asset.lower()}-{duration_label}-close-above-{open_price:.2f}-{int(close_ts.timestamp())}"
        question = f"Will {asset} {duration_label} candle close above {open_price:.2f} at {close_label}?"
        raw_market = {
            "id": f"synthetic:{asset}:{market_type}:{int(close_ts.timestamp())}",
            "slug": slug,
            "question": question,
            "price_to_beat": open_price,
            "winner": "yes" if close_price > open_price else "no",
            "status": "closed",
            "resolutionSource": "synthetic_from_csv_close",
        }
        metadata = PolymarketMarketMetadata(
            market_id=str(raw_market["id"]),
            condition_id=str(raw_market["id"]),
            slug=slug,
            question=question,
            category="crypto",
            active=False,
            closed=True,
            accepting_orders=False,
            enable_order_book=False,
            start_date=open_ts,
            end_date=close_ts,
            resolution_source="synthetic_from_csv_close",
            description=f"Synthetic short-horizon {asset} window generated from local 1m dataset.",
            outcomes=["YES", "NO"],
            outcome_prices=[],
            token_ids=[],
            best_bid=None,
            best_ask=None,
            last_trade_price=None,
            raw_tags=[market_type, asset.lower(), "synthetic"],
        )
        synthetic.append((raw_market, metadata, market_type, asset))

    synthetic.sort(key=lambda item: item[1].end_date or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return synthetic[:limit]
