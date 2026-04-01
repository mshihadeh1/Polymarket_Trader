from __future__ import annotations

import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from packages.core_types.schemas import (
    BacktestMetric,
    BacktestReport,
    FeatureSnapshot,
    MarketSummary,
    PaperTradeDecision,
    SyntheticBatchReport,
    SyntheticEvaluationRecord,
    SyntheticFeatureSnapshot,
    SyntheticMarketSample,
    PolymarketTopOfBook,
    PolymarketTrade,
    RawPolymarketEvent,
)
from packages.db.models import (
    BacktestRunRecord,
    FeatureSnapshotRecord,
    PaperDecisionRecord,
    PolymarketBookRecord,
    PolymarketMarketRecord,
    PolymarketRawEventRecord,
    PolymarketTradeRecord,
    SyntheticBatchReportRecord,
    SyntheticFeatureSnapshotRecord,
    SyntheticMarketSampleRecord,
)

logger = logging.getLogger(__name__)


class ResearchPersistence:
    def __init__(self, session_factory: sessionmaker | None) -> None:
        self._session_factory = session_factory

    @property
    def enabled(self) -> bool:
        return self._session_factory is not None

    def save_feature_snapshot(self, snapshot: FeatureSnapshot) -> None:
        if not self._session_factory:
            return
        record = FeatureSnapshotRecord(
            market_id=str(snapshot.market_id),
            ts=snapshot.ts,
            payload=snapshot.model_dump(mode="json"),
        )
        self._write(record)

    def save_backtest_report(self, report: BacktestReport) -> None:
        if not self._session_factory:
            return
        record = BacktestRunRecord(
            id=report.run_id,
            market_id=str(report.market_id),
            strategy_name=report.strategy_name,
            trade_count=report.trade_count,
            metrics=[metric.model_dump(mode="json") for metric in report.metrics],
            decisions=[decision.model_dump(mode="json") for decision in report.decisions],
            notes=report.notes,
        )
        self._write(record, merge=True)

    def save_synthetic_market_sample(self, sample: SyntheticMarketSample) -> None:
        if not self._session_factory:
            return
        record = SyntheticMarketSampleRecord(
            id=sample.sample_id,
            market_id=sample.market_id,
            source=sample.source,
            asset=sample.asset,
            timeframe=sample.timeframe,
            market_open_time=sample.market_open_time,
            market_close_time=sample.market_close_time,
            decision_time=sample.decision_time,
            source_provider=sample.source_provider,
            payload=sample.model_dump(mode="json"),
        )
        self._write(record, merge=True)

    def save_synthetic_feature_snapshot(self, snapshot: SyntheticFeatureSnapshot) -> None:
        if not self._session_factory:
            return
        record = SyntheticFeatureSnapshotRecord(
            id=f"{snapshot.sample_id}:{snapshot.decision_time.isoformat()}",
            sample_id=snapshot.sample_id,
            market_id=snapshot.market_id,
            decision_time=snapshot.decision_time,
            payload=snapshot.model_dump(mode="json"),
        )
        self._write(record, merge=True)

    def save_synthetic_batch_report(self, report: SyntheticBatchReport) -> None:
        if not self._session_factory:
            return
        record = SyntheticBatchReportRecord(
            id=report.run_id,
            strategy_name=report.strategy_name,
            source=report.source,
            asset_filter=report.asset_filter,
            timeframe_filter=report.timeframe_filter,
            decision_time=report.decision_time,
            total_samples=report.total_samples,
            metrics=[metric.model_dump(mode="json") for metric in report.metrics],
            coverage=report.coverage,
            records=[record.model_dump(mode="json") for record in report.records],
        )
        self._write(record, merge=True)

    def save_paper_decision(self, decision: PaperTradeDecision, is_dry_run: bool = True) -> None:
        if not self._session_factory:
            return
        record = PaperDecisionRecord(
            market_id=str(decision.market_id),
            ts=decision.ts,
            action=decision.action,
            side=decision.side,
            price=decision.price,
            size=decision.size,
            status=decision.status,
            reason=decision.reason,
            is_dry_run=is_dry_run,
        )
        self._write(record)

    def list_backtest_reports(self) -> list[BacktestReport]:
        if not self._session_factory:
            return []
        with self._session_factory() as session:
            rows = session.query(BacktestRunRecord).order_by(BacktestRunRecord.created_at.desc()).all()
        return [
            BacktestReport(
                run_id=row.id,
                strategy_name=row.strategy_name,
                market_id=row.market_id,
                metrics=[BacktestMetric(**metric) for metric in row.metrics],
                trade_count=row.trade_count,
                decisions=row.decisions,
                notes=row.notes,
                created_at=row.created_at,
            )
            for row in rows
        ]

    def list_synthetic_batch_reports(self) -> list[SyntheticBatchReport]:
        if not self._session_factory:
            return []
        with self._session_factory() as session:
            rows = session.query(SyntheticBatchReportRecord).order_by(SyntheticBatchReportRecord.created_at.desc()).all()
        return [
            SyntheticBatchReport(
                run_id=row.id,
                strategy_name=row.strategy_name,
                source=row.source,
                asset_filter=row.asset_filter,
                timeframe_filter=row.timeframe_filter,
                decision_time=row.decision_time,
                total_samples=row.total_samples,
                metrics=[BacktestMetric(**metric) for metric in row.metrics],
                coverage=row.coverage,
                records=[SyntheticEvaluationRecord(**record) for record in row.records],
                created_at=row.created_at,
            )
            for row in rows
        ]

    def save_market_summary(self, market: MarketSummary) -> None:
        if not self._session_factory:
            return
        record = PolymarketMarketRecord(
            id=str(market.id),
            slug=market.slug,
            event_slug=market.event_slug,
            event_epoch=market.event_epoch,
            duration_minutes=market.duration_minutes,
            market_type=market.market_type,
            underlying=market.underlying,
            market_family=market.market_family,
            source=market.source or "unknown",
            price_to_beat=market.price_to_beat,
            resolved_outcome=market.resolved_outcome,
            resolution_price=market.resolution_price,
            payload=market.model_dump(mode="json"),
        )
        self._write(record, merge=True)

    def save_polymarket_trade(self, trade: PolymarketTrade) -> None:
        if not self._session_factory:
            return
        key = trade.sequence or f"{trade.market_id}:{trade.asset_id}:{trade.ts.isoformat()}:{trade.price}:{trade.size}"
        record = PolymarketTradeRecord(
            id=key,
            market_id=trade.market_id,
            asset_id=trade.asset_id,
            ts=trade.ts,
            payload=trade.model_dump(mode="json"),
        )
        self._write(record, merge=True)

    def save_polymarket_top_of_book(self, top: PolymarketTopOfBook) -> None:
        if not self._session_factory:
            return
        key = top.sequence or f"{top.market_id}:{top.asset_id}:{top.ts.isoformat()}"
        record = PolymarketBookRecord(
            id=key,
            market_id=top.market_id,
            asset_id=top.asset_id,
            ts=top.ts,
            payload=top.model_dump(mode="json"),
        )
        self._write(record, merge=True)

    def save_polymarket_raw_event(self, event: RawPolymarketEvent, market_id: str) -> None:
        if not self._session_factory:
            return
        key = event.sequence or f"{market_id}:{event.asset_id}:{event.timestamp.isoformat()}:{event.event_type}"
        record = PolymarketRawEventRecord(
            id=key,
            market_id=market_id,
            asset_id=event.asset_id,
            event_type=event.event_type,
            ts=event.timestamp,
            payload=event.model_dump(mode="json"),
        )
        self._write(record, merge=True)

    def _write(self, record: object, merge: bool = False) -> None:
        try:
            with self._session_factory() as session:
                if merge:
                    session.merge(record)
                else:
                    session.add(record)
                session.commit()
        except SQLAlchemyError:
            logger.exception("Failed to persist record")
