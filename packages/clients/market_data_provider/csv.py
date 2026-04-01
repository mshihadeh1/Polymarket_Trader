from __future__ import annotations

import csv
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from packages.clients.market_data_provider.base import HistoricalMarketDataProvider
from packages.core_types import (
    DatasetValidationReport,
    OHLCVBar,
    ExternalOrderBookSnapshot,
    ExternalTrade,
    ProviderCapabilities,
    SymbolMapping,
)
from packages.utils.time import parse_dt

_REQUIRED_PRICE_COLUMNS = {"open", "high", "low", "close", "volume"}
_TIMESTAMP_COLUMNS = ("timestamp", "datetime", "ts", "date")


class CsvHistoricalProvider(HistoricalMarketDataProvider):
    def __init__(self, path_map: dict[str, str], symbol_map: dict[str, str], root: Path) -> None:
        self._path_map = {key.upper(): value for key, value in path_map.items()}
        self._symbol_map = {key.upper(): value for key, value in symbol_map.items()}
        self._root = root
        self._row_cache: dict[str, list[dict[str, Any]]] = {}
        self._validation_cache: dict[str, DatasetValidationReport] = {}

    @property
    def provider_name(self) -> str:
        return "csv"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(has_ohlcv=True, has_trades=False, has_l2=False, has_snapshots=False)

    def map_symbol(self, internal_symbol: str) -> SymbolMapping:
        normalized = internal_symbol.upper()
        return SymbolMapping(
            internal_symbol=normalized,
            provider_symbol=self._symbol_map.get(normalized, normalized),
            provider_name=self.provider_name,
        )

    def get_ohlcv(
        self,
        internal_symbol: str,
        start: datetime,
        end: datetime,
        interval: str,
    ) -> tuple[list[dict[str, Any]], list[OHLCVBar]]:
        if interval != "1m":
            raise ValueError("CsvHistoricalProvider currently supports only 1m bars")
        rows = self._read_symbol_rows(internal_symbol)
        filtered_rows = [row for row in rows if start <= row["_parsed_ts"] <= end]
        bars = [
            OHLCVBar(
                ts=row["_parsed_ts"],
                symbol=internal_symbol.upper(),
                provider=self.provider_name,
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row.get("volume", 0.0) or 0.0),
                interval=interval,
            )
            for row in filtered_rows
        ]
        raw_rows = [{key: value for key, value in row.items() if key != "_parsed_ts"} for row in filtered_rows]
        return raw_rows, bars

    def get_trades(
        self,
        internal_symbol: str,
        start: datetime,
        end: datetime,
    ) -> tuple[list[dict[str, Any]], list[ExternalTrade]]:
        return [], []

    def get_orderbook_snapshots(
        self,
        internal_symbol: str,
        start: datetime,
        end: datetime,
    ) -> tuple[list[dict[str, Any]], list[ExternalOrderBookSnapshot]]:
        return [], []

    def validate_datasets(self) -> list[DatasetValidationReport]:
        reports = []
        for symbol in sorted(self._path_map):
            reports.append(self.validate_symbol(symbol))
        return reports

    def validate_symbol(self, internal_symbol: str) -> DatasetValidationReport:
        normalized = internal_symbol.upper()
        if normalized in self._validation_cache:
            return self._validation_cache[normalized]
        try:
            path = self._resolve_path(normalized)
        except FileNotFoundError as exc:
            report = DatasetValidationReport(
                symbol=normalized,
                provider=self.provider_name,
                path=str(self._root / self._path_map.get(normalized, "")),
                schema_issues=[str(exc)],
            )
            self._validation_cache[normalized] = report
            return report
        schema_issues: list[str] = []
        duplicate_count = 0
        first_ts: datetime | None = None
        last_ts: datetime | None = None
        row_count = 0
        seen_timestamps: set[datetime] = set()
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = {field for field in (reader.fieldnames or []) if field}
            if not any(column in fieldnames for column in _TIMESTAMP_COLUMNS):
                schema_issues.append("Missing timestamp column. Expected one of: timestamp, datetime, ts, date")
            missing_columns = sorted(column for column in _REQUIRED_PRICE_COLUMNS if column not in fieldnames)
            if missing_columns:
                schema_issues.append(f"Missing required columns: {', '.join(missing_columns)}")
            for row in reader:
                row_count += 1
                try:
                    ts = _parse_timestamp(row)
                except Exception as exc:
                    schema_issues.append(f"Timestamp parse error on row {row_count}: {exc}")
                    continue
                if first_ts is None or ts < first_ts:
                    first_ts = ts
                if last_ts is None or ts > last_ts:
                    last_ts = ts
                if ts in seen_timestamps:
                    duplicate_count += 1
                else:
                    seen_timestamps.add(ts)
        report = DatasetValidationReport(
            symbol=normalized,
            provider=self.provider_name,
            path=str(path),
            row_count=row_count,
            first_timestamp=first_ts,
            last_timestamp=last_ts,
            duplicate_count=duplicate_count,
            schema_issues=_dedupe(schema_issues),
        )
        self._validation_cache[normalized] = report
        return report

    def _read_symbol_rows(self, internal_symbol: str) -> list[dict[str, Any]]:
        normalized = internal_symbol.upper()
        if normalized in self._row_cache:
            return self._row_cache[normalized]

        path = self._resolve_path(normalized)
        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = {field for field in (reader.fieldnames or []) if field}
            _validate_columns(fieldnames, normalized)
            for index, row in enumerate(reader, start=1):
                parsed_ts = _parse_timestamp(row)
                normalized_row = dict(row)
                normalized_row["_parsed_ts"] = parsed_ts
                rows.append(normalized_row)
        rows.sort(key=lambda row: row["_parsed_ts"])
        self._row_cache[normalized] = rows
        return rows

    def _resolve_path(self, internal_symbol: str) -> Path:
        normalized = internal_symbol.upper()
        path_value = self._path_map.get(normalized)
        if path_value is None:
            raise KeyError(f"No CSV dataset configured for symbol={normalized}")
        path = Path(path_value)
        if not path.is_absolute():
            path = self._root / path
        if not path.exists():
            raise FileNotFoundError(f"CSV dataset for symbol={normalized} not found at {path}")
        return path


def _parse_timestamp(row: dict[str, Any]) -> datetime:
    for key in _TIMESTAMP_COLUMNS:
        value = row.get(key)
        if value:
            parsed = parse_dt(str(value).replace(" ", "T"))
            if parsed is not None:
                return parsed
    raise ValueError("row is missing a parseable timestamp")


def _validate_columns(fieldnames: Iterable[str], symbol: str) -> None:
    columns = set(fieldnames)
    if not any(column in columns for column in _TIMESTAMP_COLUMNS):
        raise ValueError(f"CSV dataset for {symbol} is missing a timestamp column")
    missing_columns = sorted(column for column in _REQUIRED_PRICE_COLUMNS if column not in columns)
    if missing_columns:
        raise ValueError(f"CSV dataset for {symbol} is missing required columns: {', '.join(missing_columns)}")


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
