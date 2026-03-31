from __future__ import annotations

import logging

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from packages.core_types.schemas import BacktestMetric, BacktestReport, FeatureSnapshot, PaperTradeDecision
from packages.db.models import BacktestRunRecord, FeatureSnapshotRecord, PaperDecisionRecord

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
