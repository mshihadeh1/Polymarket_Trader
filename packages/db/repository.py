from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from packages.core_types.schemas import (
    BacktestMetric,
    BacktestReport,
    ExecutionFillRecord,
    ExecutionOrderRecord,
    ClosedMarketBatchReport,
    ClosedMarketEvaluationRecord,
    FeatureSnapshot,
    MarketSummary,
    MinuteBatchReport,
    MinuteEvaluationRecord,
    MinuteFeatureSnapshot,
    MinuteResearchRow,
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
    ClosedMarketBatchReportRecord,
    ExecutionFillRecord as ExecutionFillRecordModel,
    ExecutionOrderRecord as ExecutionOrderRecordModel,
    FeatureSnapshotRecord,
    MinuteBatchReportRecord,
    MinuteFeatureSnapshotRecord,
    MinuteResearchRowRecord,
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

    def save_minute_research_row(self, row: MinuteResearchRow) -> None:
        if not self._session_factory:
            return
        record = MinuteResearchRowRecord(
            id=row.row_id,
            asset=row.asset,
            source=row.source,
            decision_time=row.decision_time,
            horizon_minutes=15,
            reference_price=row.reference_price,
            close_5m=row.close_5m,
            close_15m=row.close_15m,
            label_up_5m=row.label_up_5m,
            label_up_15m=row.label_up_15m,
            future_return_5m=row.future_return_5m,
            future_return_15m=row.future_return_15m,
            source_provider=row.source_provider,
            market_id=row.market_id,
            payload=row.model_dump(mode="json"),
        )
        self._write(record, merge=True)

    def save_minute_feature_snapshot(self, snapshot: MinuteFeatureSnapshot) -> None:
        if not self._session_factory:
            return
        record = MinuteFeatureSnapshotRecord(
            id=f"{snapshot.row_id}:{snapshot.decision_time.isoformat()}",
            row_id=snapshot.row_id,
            asset=snapshot.asset,
            source=snapshot.source,
            decision_time=snapshot.decision_time,
            payload=snapshot.model_dump(mode="json"),
        )
        self._write(record, merge=True)

    def save_minute_batch_report(self, report: MinuteBatchReport) -> None:
        if not self._session_factory:
            return
        record = MinuteBatchReportRecord(
            id=report.run_id,
            strategy_name=report.strategy_name,
            source=report.source,
            asset_filter=report.asset_filter,
            timeframe_filter=report.timeframe_filter,
            total_rows=report.total_rows,
            metrics=[metric.model_dump(mode="json") for metric in report.metrics],
            coverage=report.coverage,
            records=[record.model_dump(mode="json") for record in report.records],
        )
        self._write(record, merge=True)

    def save_closed_market_batch_report(self, report: ClosedMarketBatchReport) -> None:
        if not self._session_factory:
            return
        record = ClosedMarketBatchReportRecord(
            id=report.run_id,
            strategy_name=report.strategy_name,
            mode=report.mode,
            asset_filter=report.asset_filter,
            timeframe_filter=report.timeframe_filter,
            limit=report.limit,
            total_markets_evaluated=report.total_markets_evaluated,
            metrics=[metric.model_dump(mode="json") for metric in report.metrics],
            coverage=report.coverage,
            records=[record.model_dump(mode="json") for record in report.records],
        )
        self._write(record, merge=True)

    def list_minute_research_rows(self) -> list[MinuteResearchRow]:
        if not self._session_factory:
            return []
        with self._session_factory() as session:
            rows = session.query(MinuteResearchRowRecord).order_by(MinuteResearchRowRecord.decision_time.asc()).all()
        return [MinuteResearchRow(**row.payload) for row in rows]

    def list_closed_market_batch_reports(self) -> list[ClosedMarketBatchReport]:
        if not self._session_factory:
            return []
        with self._session_factory() as session:
            rows = session.query(ClosedMarketBatchReportRecord).order_by(ClosedMarketBatchReportRecord.created_at.desc()).all()
        return [
            ClosedMarketBatchReport(
                run_id=row.id,
                strategy_name=row.strategy_name,
                mode=row.mode,  # type: ignore[arg-type]
                asset_filter=row.asset_filter,
                timeframe_filter=row.timeframe_filter,
                limit=row.limit,
                created_at=row.created_at,
                total_markets_evaluated=row.total_markets_evaluated,
                metrics=[BacktestMetric(**metric) for metric in row.metrics],
                coverage=row.coverage,
                records=[ClosedMarketEvaluationRecord(**record) for record in row.records],
            )
            for row in rows
        ]

    def list_minute_feature_snapshots(self, row_id: str | None = None) -> list[MinuteFeatureSnapshot]:
        if not self._session_factory:
            return []
        with self._session_factory() as session:
            query = session.query(MinuteFeatureSnapshotRecord)
            if row_id is not None:
                query = query.filter(MinuteFeatureSnapshotRecord.row_id == row_id)
            rows = query.order_by(MinuteFeatureSnapshotRecord.decision_time.asc()).all()
        return [MinuteFeatureSnapshot(**row.payload) for row in rows]

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
            id=f"{decision.market_id}:{decision.ts.isoformat()}:{decision.action}:{decision.side}:{decision.price}:{decision.size}:{decision.status}",
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
        self._write(record, merge=True)

    def list_paper_decisions(self) -> list[PaperTradeDecision]:
        if not self._session_factory:
            return []
        with self._session_factory() as session:
            rows = session.query(PaperDecisionRecord).order_by(PaperDecisionRecord.ts.asc()).all()
        return [
            PaperTradeDecision(
                ts=row.ts,
                market_id=UUID(row.market_id),
                action=row.action,
                side=row.side,
                price=row.price,
                size=row.size,
                status=row.status,
                reason=row.reason,
                signal_value=None,
                confidence=None,
            )
            for row in rows
        ]

    def save_execution_order(self, order: ExecutionOrderRecord) -> None:
        if not self._session_factory:
            return
        record = ExecutionOrderRecordModel(
            id=order.order_id,
            intent_id=order.intent_id,
            strategy_name=order.strategy_name,
            market_id=str(order.market_id),
            token_id=order.token_id,
            market_side=order.market_side,
            order_side=order.order_side,
            price=order.price,
            size=order.size,
            order_type=order.order_type,
            post_only=order.post_only,
            dry_run=order.dry_run,
            status=order.status,
            exchange_order_id=order.exchange_order_id,
            request_payload=order.request_payload,
            response_payload=order.response_payload,
            created_at=order.created_at or datetime.now(timezone.utc),
            updated_at=order.updated_at or datetime.now(timezone.utc),
        )
        self._write(record, merge=True)

    def list_execution_orders(self) -> list[ExecutionOrderRecord]:
        if not self._session_factory:
            return []
        with self._session_factory() as session:
            rows = session.query(ExecutionOrderRecordModel).order_by(ExecutionOrderRecordModel.created_at.desc()).all()
        return [
            ExecutionOrderRecord(
                order_id=row.id,
                intent_id=row.intent_id,
                strategy_name=row.strategy_name,
                market_id=UUID(row.market_id),
                token_id=row.token_id,
                market_side=row.market_side,  # type: ignore[arg-type]
                order_side=row.order_side,  # type: ignore[arg-type]
                price=row.price,
                size=row.size,
                order_type=row.order_type,  # type: ignore[arg-type]
                post_only=row.post_only,
                dry_run=row.dry_run,
                status=row.status,
                exchange_order_id=row.exchange_order_id,
                request_payload=row.request_payload,
                response_payload=row.response_payload,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
            for row in rows
        ]

    def save_execution_fill(self, fill: ExecutionFillRecord) -> None:
        if not self._session_factory:
            return
        record = ExecutionFillRecordModel(
            id=fill.fill_id,
            order_id=fill.order_id,
            market_id=str(fill.market_id),
            token_id=fill.token_id,
            ts=fill.ts,
            side=fill.side,
            price=fill.price,
            size=fill.size,
            fee=fill.fee,
            fee_currency=fill.fee_currency,
            status=fill.status,
            dry_run=fill.dry_run,
            source=fill.source,
            payload=fill.payload,
        )
        self._write(record, merge=True)

    def list_execution_fills(self) -> list[ExecutionFillRecord]:
        if not self._session_factory:
            return []
        with self._session_factory() as session:
            rows = session.query(ExecutionFillRecordModel).order_by(ExecutionFillRecordModel.ts.desc()).all()
        return [
            ExecutionFillRecord(
                fill_id=row.id,
                order_id=row.order_id,
                market_id=UUID(row.market_id),
                token_id=row.token_id,
                ts=row.ts,
                side=row.side,  # type: ignore[arg-type]
                price=row.price,
                size=row.size,
                fee=row.fee,
                fee_currency=row.fee_currency,
                status=row.status,
                dry_run=row.dry_run,
                source=row.source,
                payload=row.payload,
            )
            for row in rows
        ]

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

    def list_minute_batch_reports(self) -> list[MinuteBatchReport]:
        if not self._session_factory:
            return []
        with self._session_factory() as session:
            rows = session.query(MinuteBatchReportRecord).order_by(MinuteBatchReportRecord.created_at.desc()).all()
        return [
            MinuteBatchReport(
                run_id=row.id,
                strategy_name=row.strategy_name,
                source=row.source,
                asset_filter=row.asset_filter,
                timeframe_filter=row.timeframe_filter,
                total_rows=row.total_rows,
                metrics=[BacktestMetric(**metric) for metric in row.metrics],
                coverage=row.coverage,
                records=[MinuteEvaluationRecord(**record) for record in row.records],
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
