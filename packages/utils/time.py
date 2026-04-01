from __future__ import annotations

from datetime import datetime, timezone


def parse_dt(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def seconds_until(target: datetime | None, current: datetime) -> float | None:
    if target is None:
        return None
    return max((target - current).total_seconds(), 0.0)
