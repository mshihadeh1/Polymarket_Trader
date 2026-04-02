from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class PolymarketExecutionAdapter:
    host: str
    chain_id: int = 137
    private_key: str | None = None
    funder: str | None = None
    signature_type: int = 1
    _client: Any | None = field(default=None, init=False, repr=False, compare=False)
    _sdk_import_error: str | None = field(default=None, init=False, repr=False, compare=False)

    @property
    def adapter_name(self) -> str:
        return "py_clob_client"

    @property
    def can_trade(self) -> bool:
        return bool(self.private_key and self.funder)

    @property
    def ready(self) -> bool:
        return self._load_client_class() is not None

    def get_client(self) -> Any:
        if self._client is not None:
            return self._client
        client_cls = self._load_client_class()
        if client_cls is None:
            raise RuntimeError(self._sdk_import_error or "py-clob-client is not installed")

        attempts: list[tuple[tuple[Any, ...], dict[str, Any]]] = [
            ((self.host,), {}),
            (
                (self.host,),
                {
                    "key": self.private_key,
                    "chain_id": self.chain_id,
                    "signature_type": self.signature_type,
                    "funder": self.funder,
                },
            ),
            (
                (self.host, self.private_key, self.chain_id, self.signature_type, self.funder),
                {},
            ),
        ]
        last_error: Exception | None = None
        for args, kwargs in attempts:
            try:
                self._client = client_cls(*args, **kwargs)
                break
            except TypeError as exc:
                last_error = exc
                continue
        if self._client is None:
            raise RuntimeError(f"Unable to initialize Polymarket CLOB client: {last_error}")

        if self.can_trade and hasattr(self._client, "set_api_creds") and hasattr(self._client, "create_or_derive_api_creds"):
            try:
                creds = self._client.create_or_derive_api_creds()
                self._client.set_api_creds(creds)
            except Exception as exc:  # pragma: no cover - SDK/network dependent
                logger.warning("Failed to initialize Polymarket API credentials: %s", exc)
                if not self.can_trade:
                    raise
        return self._client

    def get_market(self, token_id: str) -> Any:
        return self.get_client().get_market(token_id)

    def get_order_book(self, token_id: str) -> Any:
        return self.get_client().get_order_book(token_id)

    def get_orders(self, params: Any | None = None) -> Any:
        client = self.get_client()
        if params is None:
            params = self._build_open_order_params()
        return client.get_orders(params)

    def get_trades(self) -> Any:
        return self.get_client().get_trades()

    def get_balance_allowance(self) -> Any:
        client = self.get_client()
        if hasattr(client, "get_balance_allowance"):
            return client.get_balance_allowance()
        raise AttributeError("Underlying Polymarket client does not expose get_balance_allowance")

    def create_limit_order(self, *, token_id: str, price: float, size: float, order_side: str, order_type: str = "GTC") -> Any:
        client, order_args_type, order_type_enum, side_enum = self._load_order_types()
        side = side_enum.BUY if order_side.upper() == "BUY" else side_enum.SELL
        order_args = order_args_type(token_id=token_id, price=price, size=size, side=side)
        signed = client.create_order(order_args)
        order_type_value = getattr(order_type_enum, order_type, order_type)
        return client.post_order(signed, order_type_value)

    def create_market_order(self, *, token_id: str, amount: float, order_side: str, order_type: str = "FOK") -> Any:
        client, _, order_type_enum, side_enum = self._load_order_types()
        market_order_args = self._load_market_order_args(token_id=token_id, amount=amount, side=side_enum.BUY if order_side.upper() == "BUY" else side_enum.SELL, order_type=getattr(order_type_enum, order_type, order_type))
        signed = client.create_market_order(market_order_args)
        return client.post_order(signed, getattr(order_type_enum, order_type, order_type))

    def cancel(self, order_id: str) -> Any:
        return self.get_client().cancel(order_id)

    def cancel_all(self) -> Any:
        return self.get_client().cancel_all()

    def _load_client_class(self) -> Any | None:
        if self._sdk_import_error is not None:
            return None
        try:
            from py_clob_client.client import ClobClient  # type: ignore
        except Exception as exc:  # pragma: no cover - import availability depends on environment
            self._sdk_import_error = str(exc)
            return None
        return ClobClient

    def _load_order_types(self) -> tuple[Any, Any, Any, Any]:
        client = self.get_client()
        try:
            from py_clob_client.clob_types import OrderArgs, OrderType  # type: ignore
            from py_clob_client.order_builder.constants import BUY, SELL  # type: ignore
        except Exception as exc:  # pragma: no cover - import availability depends on environment
            raise RuntimeError(f"Unable to import py-clob-client order types: {exc}") from exc
        side_enum = type("Side", (), {"BUY": BUY, "SELL": SELL})
        return client, OrderArgs, OrderType, side_enum

    def _load_market_order_args(self, *, token_id: str, amount: float, side: Any, order_type: Any) -> Any:
        try:
            from py_clob_client.clob_types import MarketOrderArgs  # type: ignore
        except Exception as exc:  # pragma: no cover - import availability depends on environment
            raise RuntimeError(f"Unable to import py-clob-client market order types: {exc}") from exc
        return MarketOrderArgs(token_id=token_id, amount=amount, side=side, order_type=order_type)

    def _build_open_order_params(self) -> Any:
        try:
            from py_clob_client.clob_types import OpenOrderParams  # type: ignore
        except Exception as exc:  # pragma: no cover - import availability depends on environment
            raise RuntimeError(f"Unable to import py-clob-client open order params: {exc}") from exc
        return OpenOrderParams()
