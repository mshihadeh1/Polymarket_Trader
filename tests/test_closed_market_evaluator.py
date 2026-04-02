import asyncio
from datetime import datetime, timezone

from packages.config import Settings
from packages.core_types import PolymarketMarketMetadata
from polymarket_trader.bootstrap import build_container


def test_closed_market_batch_evaluator_compares_bars_only_and_enriched_without_lookahead() -> None:
    container = build_container(Settings())

    raw_market = {
        "id": "closed-btc-5m-1",
        "slug": "btc-closed-5m-1",
        "price_to_beat": 84500.0,
        "open_reference_price": 84440.0,
    }
    metadata = PolymarketMarketMetadata(
        market_id="closed-btc-5m-1",
        condition_id="cond-1",
        slug="btc-closed-5m-1",
        question="Will BTC 5m candle close above 84,500 at 12:00 UTC?",
        category="crypto",
        active=False,
        closed=True,
        start_date=datetime(2026, 3, 31, 11, 55, 0, tzinfo=timezone.utc),
        end_date=datetime(2026, 3, 31, 12, 0, 0, tzinfo=timezone.utc),
        resolution_source="derived",
    )

    async def _discover_markets(*, closed=None, active=None, limit=None):
        return [raw_market], [metadata]

    container.backtester._polymarket_client.discover_markets = _discover_markets

    class _FutureOnlyRecentClient:
        def fetch_recent_trades(self, symbol, start=None, end=None):
            from packages.core_types import ExternalTrade

            return [], [
                ExternalTrade(
                    ts=datetime(2026, 3, 31, 12, 5, 0, tzinfo=timezone.utc),
                    venue="hyperliquid",
                    symbol=symbol,
                    price=85000.0,
                    size=1.0,
                    side="buy",
                    aggressor_side="buy",
                )
            ], []

        def fetch_recent_candles(self, symbol, start, end, interval="1m"):
            return [], [], []

        def fetch_l2_book(self, symbol):
            return {}, None, []

    container.backtester._external_ingestor._recent_client = _FutureOnlyRecentClient()

    bars_only = asyncio.run(
        container.backtester.run_closed_market_batch(
            asset="BTC",
            timeframe="crypto_5m",
            limit=5,
            strategy_name="combined_cvd_gap",
            include_hyperliquid_enrichment=False,
        )
    )
    enriched = asyncio.run(
        container.backtester.run_closed_market_batch(
            asset="BTC",
            timeframe="crypto_5m",
            limit=5,
            strategy_name="combined_cvd_gap",
            include_hyperliquid_enrichment=True,
        )
    )

    assert bars_only.total_markets_evaluated == 1
    assert enriched.total_markets_evaluated == 1
    assert bars_only.records[0].historical_window_end == metadata.end_date
    assert bars_only.records[0].actual_resolution in {"yes", "no"}
    assert bars_only.records[0].enrichment_availability.trades_available is True
    assert enriched.records[0].feature_snapshot_summary["external_cvd"] == bars_only.records[0].feature_snapshot_summary["external_cvd"]


def test_closed_market_resolution_prefers_polymarket_truth() -> None:
    container = build_container(Settings())

    raw_market = {
        "id": "closed-btc-5m-2",
        "slug": "btc-updown-5m-1775039400",
        "price_to_beat": 84500.0,
        "open_reference_price": 84440.0,
        "resolved_outcome": "no",
        "resolution_price": 84250.0,
    }
    metadata = PolymarketMarketMetadata(
        market_id="closed-btc-5m-2",
        condition_id="cond-2",
        slug="btc-updown-5m-1775039400",
        question="Will BTC 5m candle close above 84,500 at 11:55 UTC?",
        category="crypto",
        active=False,
        closed=True,
        start_date=datetime(2026, 3, 31, 11, 50, 0, tzinfo=timezone.utc),
        end_date=datetime(2026, 3, 31, 11, 55, 0, tzinfo=timezone.utc),
        resolution_source="polymarket",
        resolved_outcome="no",
        resolution_price=84250.0,
    )

    async def _discover_markets(*, closed=None, active=None, limit=None):
        return [raw_market], [metadata]

    container.backtester._polymarket_client.discover_markets = _discover_markets

    result = asyncio.run(
        container.backtester.run_closed_market_batch(
            asset="BTC",
            timeframe="crypto_5m",
            limit=1,
            strategy_name="combined_cvd_gap",
            include_hyperliquid_enrichment=False,
        )
    )

    assert result.records[0].actual_resolution == "no"
    assert result.records[0].actual_resolution_source == "polymarket:resolved_outcome"


def test_flow_alignment_evaluation_uses_recommended_strategy_defaults() -> None:
    container = build_container(Settings())
    result = asyncio.run(
        container.backtester.run_flow_alignment_evaluation(
            asset="BTC",
            timeframe="crypto_5m",
            limit=2,
            include_hyperliquid_enrichment=True,
        )
    )
    assert result.strategy_name == "flow_alignment_5m"
    assert result.timeframe_filter == "crypto_5m"
