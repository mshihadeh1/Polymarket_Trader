from __future__ import annotations

import re

from packages.core_types.schemas import PolymarketMarketMetadata

_BTC_PATTERN = re.compile(r"\bbtc\b|bitcoin", re.IGNORECASE)
_ETH_PATTERN = re.compile(r"\beth\b|ethereum", re.IGNORECASE)
_FIVE_MIN_PATTERN = re.compile(r"(?<!1)\b5m\b|(?<!1)5-minute|(?<!1)5 minute", re.IGNORECASE)
_FIFTEEN_MIN_PATTERN = re.compile(r"\b15m\b|15-minute|15 minute", re.IGNORECASE)


def classify_polymarket_market(metadata: PolymarketMarketMetadata) -> tuple[str, str | None]:
    text = " ".join(filter(None, [metadata.question, metadata.slug or "", metadata.description or ""]))
    underlying = None
    if _BTC_PATTERN.search(text):
        underlying = "BTC"
    elif _ETH_PATTERN.search(text):
        underlying = "ETH"

    if underlying == "BTC" and _FIVE_MIN_PATTERN.search(text):
        return "crypto_5m", underlying
    if underlying == "BTC" and _FIFTEEN_MIN_PATTERN.search(text):
        return "crypto_15m", underlying
    if underlying == "ETH" and _FIVE_MIN_PATTERN.search(text):
        return "crypto_5m", underlying
    if underlying == "ETH" and _FIFTEEN_MIN_PATTERN.search(text):
        return "crypto_15m", underlying
    return "other", underlying
