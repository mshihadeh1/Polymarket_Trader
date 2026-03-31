from packages.core_types.schemas import PolymarketMarketMetadata
from services.market_catalog.classifier import classify_polymarket_market


def test_classifier_identifies_btc_5m_market() -> None:
    metadata = PolymarketMarketMetadata(
        market_id="123",
        condition_id="abc",
        slug="btc-5m-close-above-100000",
        question="Will BTC 5m candle close above 100,000?",
        category="crypto",
        active=True,
    )
    market_type, underlying = classify_polymarket_market(metadata)
    assert market_type == "crypto_5m"
    assert underlying == "BTC"


def test_classifier_identifies_btc_15m_market() -> None:
    metadata = PolymarketMarketMetadata(
        market_id="456",
        condition_id="def",
        slug="btc-15m-close-above-100000",
        question="Will BTC 15m candle close above 100,000?",
        category="crypto",
        active=True,
    )
    market_type, underlying = classify_polymarket_market(metadata)
    assert market_type == "crypto_15m"
    assert underlying == "BTC"


def test_classifier_marks_non_target_market_as_other() -> None:
    metadata = PolymarketMarketMetadata(
        market_id="789",
        condition_id="ghi",
        slug="will-it-rain-tomorrow",
        question="Will it rain tomorrow?",
        category="weather",
        active=True,
    )
    market_type, underlying = classify_polymarket_market(metadata)
    assert market_type == "other"
    assert underlying is None
