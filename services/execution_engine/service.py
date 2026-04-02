from __future__ import annotations

import logging
from datetime import datetime, timezone

from packages.clients.polymarket_client import PolymarketExecutionAdapter
from packages.config import Settings
from packages.core_types.schemas import (
    ExecutionFillRecord,
    ExecutionOrderIntent,
    ExecutionOrderRecord,
    ExecutionStatus,
)
from packages.db import ResearchPersistence
from services.state import InMemoryState

logger = logging.getLogger(__name__)

_TERMINAL_ORDER_STATUSES = {"filled", "cancelled", "rejected", "failed", "expired"}


class ExecutionEngineService:
    def __init__(
        self,
        settings: Settings,
        state: InMemoryState,
        persistence: ResearchPersistence | None = None,
        adapter: PolymarketExecutionAdapter | None = None,
    ) -> None:
        self._settings = settings
        self._state = state
        self._persistence = persistence
        self._adapter = adapter or self._build_adapter(settings)
        self._hydrated = False
        self._last_error: str | None = None
        self._last_order_at: datetime | None = None
        self._last_fill_at: datetime | None = None

    @property
    def adapter(self) -> PolymarketExecutionAdapter | None:
        return self._adapter

    def status(self) -> ExecutionStatus:
        self._hydrate_from_persistence()
        orders = self.list_orders()
        fills = self.list_fills()
        enabled = bool(self._settings.live_execution_enabled and self._adapter is not None and self._adapter.can_trade)
        message = "Live routing is disabled by config"
        if self._settings.live_execution_enabled and self._adapter is not None and not self._adapter.can_trade:
            message = "Live routing enabled but Polymarket credentials are incomplete"
        elif enabled:
            message = "Execution adapter ready"
        return ExecutionStatus(
            enabled=enabled,
            dry_run_default=not self._settings.live_execution_enabled,
            live_execution_enabled=self._settings.live_execution_enabled,
            adapter_name=self._adapter.adapter_name if self._adapter is not None else None,
            open_order_count=sum(1 for order in orders if order.status not in _TERMINAL_ORDER_STATUSES and not order.dry_run),
            fill_count=len(fills),
            last_order_at=self._last_order_at,
            last_fill_at=self._last_fill_at,
            last_error=self._last_error,
            message=message,
        )

    def submit_intent(self, intent: ExecutionOrderIntent) -> ExecutionOrderRecord:
        self._hydrate_from_persistence()
        created_at = intent.created_at or datetime.now(timezone.utc)
        order_id = f"order_{intent.intent_id}"
        order_record = ExecutionOrderRecord(
            order_id=order_id,
            intent_id=intent.intent_id,
            strategy_name=intent.strategy_name,
            market_id=intent.market_id,
            token_id=intent.token_id,
            market_side=intent.market_side,
            order_side=intent.order_side,
            price=float(intent.price),
            size=float(intent.size),
            order_type=intent.order_type,
            post_only=bool(intent.post_only),
            dry_run=bool(intent.dry_run or not self._settings.live_execution_enabled or not self._can_route_live()),
            status="dry_run" if intent.dry_run or not self._settings.live_execution_enabled else "submitted",
            exchange_order_id=None,
            request_payload=intent.model_dump(mode="json"),
            response_payload={},
            created_at=created_at,
            updated_at=created_at,
        )

        if order_record.dry_run:
            logger.info(
                "Dry-run execution intent strategy=%s market_id=%s token_id=%s side=%s price=%s size=%s",
                intent.strategy_name,
                intent.market_id,
                intent.token_id,
                intent.order_side,
                intent.price,
                intent.size,
            )
            self._persist_order(order_record)
            return order_record

        if self._adapter is None:
            order_record.status = "failed"
            order_record.response_payload = {"error": "execution adapter unavailable"}
            self._persist_order(order_record)
            return order_record

        try:
            response = self._place_live_order(intent)
            order_record.exchange_order_id = _extract_string(response, "order_id", "id", "uuid")
            order_record.response_payload = _coerce_payload(response)
            order_record.status = _extract_string(response, "status", default="submitted") or "submitted"
            order_record.updated_at = datetime.now(timezone.utc)
            self._persist_order(order_record)
            return order_record
        except Exception as exc:  # pragma: no cover - network / SDK dependent
            logger.exception("Execution submission failed")
            order_record.status = "failed"
            order_record.response_payload = {"error": str(exc)}
            order_record.updated_at = datetime.now(timezone.utc)
            self._last_error = str(exc)
            self._persist_order(order_record)
            return order_record

    def record_fill(self, fill: ExecutionFillRecord) -> None:
        self._hydrate_from_persistence()
        fill = fill.model_copy(update={"created_at": fill.created_at or datetime.now(timezone.utc)})
        self._persist_fill(fill)

    def list_orders(self) -> list[ExecutionOrderRecord]:
        self._hydrate_from_persistence()
        seen: set[str] = set()
        combined: list[ExecutionOrderRecord] = []
        for record in self._state.execution_orders:
            if record.order_id in seen:
                continue
            seen.add(record.order_id)
            combined.append(record)
        return sorted(combined, key=lambda item: item.created_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    def list_fills(self) -> list[ExecutionFillRecord]:
        self._hydrate_from_persistence()
        seen: set[str] = set()
        combined: list[ExecutionFillRecord] = []
        for record in self._state.execution_fills:
            if record.fill_id in seen:
                continue
            seen.add(record.fill_id)
            combined.append(record)
        return sorted(combined, key=lambda item: item.ts, reverse=True)

    def _hydrate_from_persistence(self) -> None:
        if self._hydrated:
            return
        self._hydrated = True
        if self._persistence is None or not self._persistence.enabled:
            return
        for order in self._persistence.list_execution_orders():
            if order.order_id not in {item.order_id for item in self._state.execution_orders}:
                self._state.execution_orders.append(order)
                if order.created_at and (self._last_order_at is None or order.created_at > self._last_order_at):
                    self._last_order_at = order.created_at
        for fill in self._persistence.list_execution_fills():
            if fill.fill_id not in {item.fill_id for item in self._state.execution_fills}:
                self._state.execution_fills.append(fill)
                if self._last_fill_at is None or fill.ts > self._last_fill_at:
                    self._last_fill_at = fill.ts

    def _persist_order(self, order: ExecutionOrderRecord) -> None:
        self._state.execution_orders.append(order)
        if order.created_at and (self._last_order_at is None or order.created_at > self._last_order_at):
            self._last_order_at = order.created_at
        if self._persistence is not None:
            self._persistence.save_execution_order(order)

    def _persist_fill(self, fill: ExecutionFillRecord) -> None:
        self._state.execution_fills.append(fill)
        if self._last_fill_at is None or fill.ts > self._last_fill_at:
            self._last_fill_at = fill.ts
        if self._persistence is not None:
            self._persistence.save_execution_fill(fill)

    def _can_route_live(self) -> bool:
        return bool(self._adapter is not None and self._adapter.ready and self._adapter.can_trade)

    def _place_live_order(self, intent: ExecutionOrderIntent) -> object:
        if self._adapter is None:
            raise RuntimeError("Execution adapter is unavailable")
        if intent.order_type in {"FOK", "IOC"}:
            return self._adapter.create_market_order(
                token_id=intent.token_id,
                amount=float(intent.size),
                order_side=intent.order_side,
                order_type=intent.order_type,
            )
        return self._adapter.create_limit_order(
            token_id=intent.token_id,
            price=float(intent.price),
            size=float(intent.size),
            order_side=intent.order_side,
            order_type=intent.order_type,
        )

    def _build_adapter(self, settings: Settings) -> PolymarketExecutionAdapter | None:
        if not settings.live_execution_enabled and not settings.polymarket_private_key:
            return PolymarketExecutionAdapter(
                host=settings.polymarket_clob_host,
                chain_id=settings.polymarket_chain_id,
                private_key=None,
                funder=None,
                signature_type=settings.polymarket_signature_type,
            )
        return PolymarketExecutionAdapter(
            host=settings.polymarket_clob_host,
            chain_id=settings.polymarket_chain_id,
            private_key=settings.polymarket_private_key,
            funder=settings.polymarket_funder,
            signature_type=settings.polymarket_signature_type,
        )


def _coerce_payload(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        dumped = value.model_dump()  # type: ignore[attr-defined]
        if isinstance(dumped, dict):
            return dumped
    if hasattr(value, "__dict__"):
        return {key: val for key, val in vars(value).items() if not key.startswith("_")}
    return {"value": str(value)}


def _extract_string(value: object, *keys: str, default: str | None = None) -> str | None:
    payload = _coerce_payload(value)
    for key in keys:
        candidate = payload.get(key)
        if candidate is not None and str(candidate).strip():
            return str(candidate)
    return default
