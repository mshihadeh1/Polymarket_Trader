from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from packages.core_types import PolymarketMarketMetadata

_SHORT_HORIZON_SLUG = re.compile(
    r"^(?P<asset>btc|eth|sol)-updown-(?P<duration>\d+)m-(?P<epoch>\d+)$",
    re.IGNORECASE,
)
_ASSET_PATTERN = re.compile(r"\b(BTC|ETH|SOL)\b", re.IGNORECASE)


@dataclass(frozen=True)
class ShortHorizonMarketFamily:
    market_family: str | None
    asset: str | None
    event_slug: str | None
    event_epoch: int | None
    duration_minutes: int | None
    price_to_beat: float | None


def normalize_short_horizon_market(
    metadata: PolymarketMarketMetadata,
    raw_market: dict[str, Any] | None = None,
) -> PolymarketMarketMetadata:
    parsed = parse_short_horizon_market(metadata.slug or "", metadata.question or "", raw_market=raw_market)
    updates = {
        "market_family": parsed.market_family,
        "event_slug": parsed.event_slug or metadata.slug,
        "event_epoch": parsed.event_epoch,
        "duration_minutes": parsed.duration_minutes,
        "price_to_beat": parsed.price_to_beat if parsed.price_to_beat is not None else metadata.price_to_beat,
    }
    if parsed.market_family is not None:
        updates["market_family"] = parsed.market_family
    return metadata.model_copy(update=updates)


def parse_short_horizon_market(
    slug: str,
    question: str,
    *,
    raw_market: dict[str, Any] | None = None,
) -> ShortHorizonMarketFamily:
    raw_market = raw_market or {}
    candidate_slug = slug or str(raw_market.get("slug") or "")
    candidate_question = question or str(raw_market.get("question") or "")
    parsed = _SHORT_HORIZON_SLUG.match(candidate_slug.strip().lower())
    asset = _asset_from_text(candidate_slug, candidate_question)
    duration_minutes = None
    event_epoch = None
    if parsed:
        asset = parsed.group("asset").upper()
        duration_minutes = int(parsed.group("duration"))
        event_epoch = int(parsed.group("epoch"))
    elif "15m" in candidate_slug.lower() or "15 minute" in candidate_question.lower():
        duration_minutes = 15
    elif "5m" in candidate_slug.lower() or "5 minute" in candidate_question.lower():
        duration_minutes = 5

    market_family = None
    if asset is not None and duration_minutes in {5, 15}:
        market_family = f"{asset.lower()}_updown_{duration_minutes}m"

    price_to_beat = _coerce_float(raw_market.get("price_to_beat"))
    if price_to_beat is None:
        price_to_beat = _coerce_float(raw_market.get("open_reference_price"))
    if price_to_beat is None:
        price_to_beat = _extract_price_to_beat(candidate_question or candidate_slug)

    return ShortHorizonMarketFamily(
        market_family=market_family,
        asset=asset,
        event_slug=candidate_slug or None,
        event_epoch=event_epoch,
        duration_minutes=duration_minutes,
        price_to_beat=price_to_beat,
    )


def _asset_from_text(*texts: str) -> str | None:
    for text in texts:
        match = _ASSET_PATTERN.search(text or "")
        if match:
            return match.group(1).upper()
    return None


def _extract_price_to_beat(text: str) -> float | None:
    cleaned = text.replace(",", "")
    for token in cleaned.split():
        try:
            value = float(token)
            if value > 1:
                return value
        except ValueError:
            continue
    return None


def _coerce_float(value: object) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None
