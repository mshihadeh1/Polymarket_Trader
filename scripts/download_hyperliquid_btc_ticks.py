#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.utils.time import parse_dt

DEFAULT_BUCKET = "hl-mainnet-node-data"
DEFAULT_PREFIX = "node_fills_by_block"

UTC = timezone.utc

NODE_ARCHIVE_WINDOWS: list[tuple[str, date, date | None]] = [
    ("node_trades", date(2025, 3, 22), date(2025, 5, 25)),
    ("node_fills", date(2025, 5, 25), date(2025, 7, 27)),
    ("node_fills_by_block", date(2025, 7, 27), None),
]


@dataclass(frozen=True)
class ArchiveKey:
    key: str
    source_prefix: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download Hyperliquid BTC market-wide tick data from the public archive and export CSV.",
    )
    parser.add_argument(
        "--start",
        required=True,
        help="Start datetime or date in ISO-8601 format, e.g. 2025-07-27 or 2025-07-27T00:00:00Z",
    )
    parser.add_argument(
        "--end",
        required=True,
        help="End datetime or date in ISO-8601 format, e.g. 2026-04-01 or 2026-04-01T23:59:59Z",
    )
    parser.add_argument(
        "--bucket",
        default=DEFAULT_BUCKET,
        help=f"S3 bucket name. Default: {DEFAULT_BUCKET}",
    )
    parser.add_argument(
        "--prefix",
        default=DEFAULT_PREFIX,
        help=f"Archive prefix to scan. Default: {DEFAULT_PREFIX}. Use 'auto' to span all known trade archive windows.",
    )
    parser.add_argument(
        "--source",
        default="auto",
        choices=["auto", "node_trades", "node_fills", "node_fills_by_block"],
        help="Archive format selector. Default: auto",
    )
    parser.add_argument(
        "--coin",
        default="BTC",
        help="Raw coin to keep. Default: BTC",
    )
    parser.add_argument(
        "--out",
        default="data/hyperliquid/btc_ticks.csv",
        help="Output CSV path. Default: data/hyperliquid/btc_ticks.csv",
    )
    parser.add_argument(
        "--max-keys",
        type=int,
        default=0,
        help="Optional limit on archive objects to process. Useful for quick smoke tests.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    start = _parse_target_datetime(args.start)
    end = _parse_target_datetime(args.end)
    if end < start:
        raise SystemExit("--end must be on or after --start")

    coin = args.coin.upper()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    writer, handle = _open_csv(out_path)
    try:
        row_count = 0
        key_count = 0
        for source_prefix, source_start, source_end in _resolved_sources(args.source, args.prefix, start, end):
            source_window_start = max(start, source_start)
            source_window_end = min(end, source_end) if source_end is not None else end
            for archive_key in iter_archive_keys(
                bucket=args.bucket,
                prefix=source_prefix,
                start=source_window_start,
                end=source_window_end,
            ):
                key_count += 1
                if args.max_keys and key_count > args.max_keys:
                    break
                payload = fetch_object_bytes(args.bucket, archive_key.key)
                records = iter_trade_records(payload)
                for record in records:
                    normalized = normalize_tick_record(record, coin=coin, source_key=archive_key.key)
                    if normalized is None:
                        continue
                    ts = normalized["timestamp"]
                    if ts < start or ts > end:
                        continue
                    writer.writerow(normalized)
                    row_count += 1
            if args.max_keys and key_count > args.max_keys:
                break
        print(f"Wrote {row_count} BTC ticks to {out_path}")
        return 0
    finally:
        handle.close()


def _open_csv(path: Path) -> tuple[csv.DictWriter[str], Any]:
    handle = path.open("w", newline="", encoding="utf-8")
    fieldnames = [
        "timestamp",
        "timestamp_ms",
        "pair",
        "raw_coin",
        "price",
        "size",
        "side",
        "trade_id",
        "user_address",
        "block_number",
        "block_time",
        "local_time",
        "source_key",
        "dir",
        "closedPnl",
        "fee",
        "crossed",
        "builder",
        "builderFee",
        "trade_dir_override",
        "hash",
    ]
    writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    return writer, handle


def _parse_target_datetime(value: str) -> datetime:
    parsed = parse_dt(value)
    if parsed is None:
        raise SystemExit(f"Could not parse datetime value: {value}")
    return parsed.astimezone(UTC)


def iter_archive_keys(bucket: str, prefix: str, start: datetime, end: datetime) -> Iterator[ArchiveKey]:
    seen: set[str] = set()
    for current_date in _iter_dates(start.date(), end.date()):
        for date_prefix in _date_prefixes(prefix, current_date):
            try:
                for key in list_keys(bucket, date_prefix):
                    if key in seen:
                        continue
                    seen.add(key)
                    yield ArchiveKey(key=key, source_prefix=date_prefix)
            except RuntimeError:
                continue


def _iter_dates(start_date: date, end_date: date) -> Iterator[date]:
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def _date_prefixes(prefix: str, current_date: date) -> list[str]:
    date_variants = [current_date.strftime("%Y%m%d"), current_date.strftime("%Y-%m-%d")]
    prefixes: list[str] = []
    for variant in date_variants:
        prefixes.append(f"{prefix}/{variant}/")
        prefixes.append(f"{prefix}/hourly/{variant}/")
    return prefixes


def _resolved_sources(
    source: str,
    prefix: str,
    start: datetime,
    end: datetime,
) -> list[tuple[str, date, date | None]]:
    if source != "auto":
        resolved_prefix = source if prefix == DEFAULT_PREFIX else prefix
        return [(resolved_prefix, date.min, None)]

    resolved: list[tuple[str, date, date | None]] = []
    for archive_prefix, window_start, window_end in NODE_ARCHIVE_WINDOWS:
        if end.date() < window_start:
            continue
        if window_end is not None and start.date() >= window_end:
            continue
        resolved.append((archive_prefix, window_start, window_end))
    return resolved


def list_keys(bucket: str, prefix: str) -> Iterator[str]:
    try:
        import boto3  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("boto3 is required to list Hyperliquid archive keys") from exc

    client = boto3.client("s3")
    paginator = client.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=bucket, Prefix=prefix, RequestPayer="requester")
    found_any = False
    for page in pages:
        for item in page.get("Contents", []):
            key = item.get("Key")
            if not key or key.endswith("/"):
                continue
            found_any = True
            yield key
    if not found_any:
        raise RuntimeError(f"No archive objects found under {bucket}/{prefix}")


def fetch_object_bytes(bucket: str, key: str) -> bytes:
    try:
        import boto3  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("boto3 is required to download Hyperliquid archive objects") from exc

    client = boto3.client("s3")
    response = client.get_object(Bucket=bucket, Key=key, RequestPayer="requester")
    return response["Body"].read()


def iter_trade_records(payload: bytes) -> Iterator[dict[str, Any]]:
    raw = _maybe_decompress(payload)
    text = raw.decode("utf-8", errors="replace").strip()
    if not text:
        return

    if text.startswith("{") or text.startswith("["):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        if parsed is not None:
            yield from _walk_trade_like_objects(parsed, context={})
            return

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        yield from _walk_trade_like_objects(parsed, context={})


def _walk_trade_like_objects(value: Any, context: dict[str, Any]) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        next_context = dict(context)
        for key in ("local_time", "block_time", "block_number", "coin", "side", "time", "px", "sz", "hash", "tid", "dir", "closedPnl", "fee", "crossed", "builder", "builderFee", "trade_dir_override"):
            if key in value and key not in next_context:
                next_context[key] = value[key]

        if _looks_like_trade_record(value):
            yield {**next_context, **value}
            return

        if "events" in value and isinstance(value["events"], list):
            for event in value["events"]:
                yield from _walk_trade_like_objects(event, next_context)
            return

        for key in ("fill", "trade", "event", "data"):
            if key in value:
                yield from _walk_trade_like_objects(value[key], next_context)
        return

    if isinstance(value, list):
        if len(value) == 2 and isinstance(value[1], dict):
            user_address = value[0] if isinstance(value[0], str) else context.get("user_address")
            nested_context = dict(context)
            if user_address:
                nested_context.setdefault("user_address", user_address)
            yield from _walk_trade_like_objects(value[1], nested_context)
            return
        for item in value:
            yield from _walk_trade_like_objects(item, context)


def _looks_like_trade_record(value: dict[str, Any]) -> bool:
    return all(key in value for key in ("coin", "px", "sz", "side", "time"))


def normalize_tick_record(record: dict[str, Any], coin: str, source_key: str) -> dict[str, Any] | None:
    raw_coin = str(record.get("coin") or "").upper()
    if raw_coin != coin:
        return None

    ts = _parse_trade_timestamp(record.get("time"))
    if ts is None:
        return None

    price = _as_float(record.get("px"))
    size = _as_float(record.get("sz"))
    if price is None or size is None:
        return None

    side = str(record.get("side") or "").upper()
    pair = _normalize_pair(raw_coin)

    return {
        "timestamp": ts.isoformat().replace("+00:00", "Z"),
        "timestamp_ms": int(ts.timestamp() * 1000),
        "pair": pair,
        "raw_coin": raw_coin,
        "price": price,
        "size": size,
        "side": side,
        "trade_id": _as_int(record.get("tid")),
        "user_address": _extract_user_address(record),
        "block_number": _as_int(record.get("block_number")),
        "block_time": _normalize_timestamp_like(record.get("block_time")),
        "local_time": _normalize_timestamp_like(record.get("local_time")),
        "source_key": source_key,
        "dir": record.get("dir"),
        "closedPnl": record.get("closedPnl"),
        "fee": record.get("fee"),
        "crossed": record.get("crossed"),
        "builder": record.get("builder"),
        "builderFee": record.get("builderFee"),
        "trade_dir_override": record.get("trade_dir_override"),
        "hash": record.get("hash"),
    }


def _normalize_pair(raw_coin: str) -> str:
    if raw_coin.startswith("@"):
        return raw_coin
    return f"{raw_coin}-PERP"


def _extract_user_address(record: dict[str, Any]) -> str | None:
    if isinstance(record.get("user_address"), str):
        return str(record["user_address"])
    if isinstance(record.get("user"), str):
        return str(record["user"])
    if isinstance(record.get("_user"), str):
        return str(record["_user"])
    return None


def _maybe_decompress(payload: bytes) -> bytes:
    if payload.startswith(b"\x1f\x8b"):
        return gzip.decompress(payload)

    if payload.startswith(b"\x04\x22\x4D\x18"):
        try:
            import lz4.frame  # type: ignore[import-not-found]
        except ImportError as exc:
            raise RuntimeError(
                "This archive object is LZ4-compressed. Install lz4 or pre-decompress the file.",
            ) from exc
        return lz4.frame.decompress(payload)

    return payload


def _parse_trade_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value) / 1000.0, tz=UTC)
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.isdigit():
            return datetime.fromtimestamp(int(stripped) / 1000.0, tz=UTC)
        parsed = parse_dt(stripped)
        if parsed is not None:
            return parsed.astimezone(UTC)
    return None


def _normalize_timestamp_like(value: Any) -> str | None:
    ts = _parse_trade_timestamp(value)
    if ts is not None:
        return ts.isoformat().replace("+00:00", "Z")
    if isinstance(value, str):
        parsed = parse_dt(value)
        if parsed is not None:
            return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")
        return value
    return None


def _as_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    raise SystemExit(main())
