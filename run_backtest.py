#!/usr/bin/env python3
"""
Run CSV backtest for Polymarket Trader.

Usage:
    python3 run_backtest.py [ASSET] [TIMEFRAME] [LIMIT]
    
Examples:
    python3 run_backtest.py BTC crypto_5m 10
    python3 run_backtest.py ETH crypto_15m 20
"""

import sys
import os

# Add project root to path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT_DIR, "apps", "api", "src"))
sys.path.insert(0, ROOT_DIR)

# Set environment variables for CSV backtest mode
os.environ.setdefault("EXTERNAL_HISTORICAL_PROVIDER", "csv")
os.environ.setdefault("USE_MOCK_EXTERNAL_PROVIDER", "false")
os.environ.setdefault("USE_MOCK_POLYMARKET", "true")
os.environ.setdefault("USE_MOCK_POLYMARKET_CLIENT", "true")
os.environ.setdefault("PAPER_TRADING_LOOP_ENABLED", "false")
os.environ.setdefault("ENABLE_DB_PERSISTENCE", "false")
os.environ.setdefault("MOCK_STARTUP_DEMO_ENABLED", "false")

from packages.config import Settings
from polymarket_trader.bootstrap import build_container
import asyncio


async def run_backtest(asset: str = "BTC", timeframe: str = "crypto_5m", limit: int = 10):
    """Run CSV backtest for closed markets."""
    print(f"Starting CSV backtest...")
    print(f"  Asset: {asset}")
    print(f"  Timeframe: {timeframe}")
    print(f"  Limit: {limit}")
    print()
    
    settings = Settings()
    print(f"External historical provider: {settings.external_historical_provider}")
    print(f"CSV BTC path: {settings.csv_btc_path}")
    print(f"CSV ETH path: {settings.csv_eth_path}")
    print()
    
    # Build container (this will validate CSV datasets)
    print("Building container and validating datasets...")
    container = build_container(settings, bootstrap_on_build=False)
    
    # Check CSV validation reports
    if container.state.external_dataset_validation:
        print("\nCSV Dataset Validation Reports:")
        for symbol, report in container.state.external_dataset_validation.items():
            print(f"  {symbol}:")
            print(f"    Rows: {report.row_count}")
            print(f"    First timestamp: {report.first_timestamp}")
            print(f"    Last timestamp: {report.last_timestamp}")
            print(f"    Duplicates: {report.duplicate_count}")
            print(f"    Schema issues: {report.schema_issues}")
    print()
    
    # Get eligible closed markets
    print("Finding eligible closed markets...")
    eligible = await container.backtester.list_eligible_closed_markets(
        asset=asset,
        timeframe=timeframe,
        limit=limit,
    )
    print(f"Found {len(eligible)} eligible closed markets:")
    for market in eligible[:5]:
        print(f"  - {market['slug']} ({market['market_open_time']} to {market['market_close_time']})")
    if len(eligible) > 5:
        print(f"  ... and {len(eligible) - 5} more")
    print()
    
    # Run baseline closed-market batch without Hyperliquid enrichment (bars_only)
    print("Running bars_only backtest (without Hyperliquid enrichment)...")
    bars_only_report = await container.backtester.run_closed_market_batch(
        asset=asset,
        timeframe=timeframe,
        limit=limit,
        strategy_name="combined_cvd_gap",
        include_hyperliquid_enrichment=False,
    )
    print(f"\nBars-only results:")
    print(f"  Total markets evaluated: {bars_only_report.total_markets_evaluated}")
    for metric in bars_only_report.metrics:
        print(f"  {metric.label}: {metric.value:.4f}" if isinstance(metric.value, float) else f"  {metric.label}: {metric.value}")
    print()
    
    # Run enriched closed-market batch with Hyperliquid enrichment
    print("Running bars_plus_hyperliquid backtest (with Hyperliquid enrichment)...")
    enriched_report = await container.backtester.run_closed_market_batch(
        asset=asset,
        timeframe=timeframe,
        limit=limit,
        strategy_name="combined_cvd_gap",
        include_hyperliquid_enrichment=True,
    )
    print(f"\nBars+Hyperliquid results:")
    print(f"  Total markets evaluated: {enriched_report.total_markets_evaluated}")
    for metric in enriched_report.metrics:
        print(f"  {metric.label}: {metric.value:.4f}" if isinstance(metric.value, float) else f"  {metric.label}: {metric.value}")
    print()
    
    # Comparison summary
    print("=" * 60)
    print("COMPARISON SUMMARY")
    print("=" * 60)
    bars_only_accuracy = next((m.value for m in bars_only_report.metrics if m.label == "accuracy"), 0)
    enriched_accuracy = next((m.value for m in enriched_report.metrics if m.label == "accuracy"), 0)
    print(f"Bars-only accuracy:              {bars_only_accuracy:.4f}")
    print(f"Bars+Hyperliquid accuracy:       {enriched_accuracy:.4f}")
    improvement = enriched_accuracy - bars_only_accuracy
    print(f"Improvement:                     {improvement:+.4f}")
    print()
    
    return {
        "bars_only": bars_only_report,
        "enriched": enriched_report,
    }


if __name__ == "__main__":
    asset = sys.argv[1] if len(sys.argv) > 1 else "BTC"
    timeframe = sys.argv[2] if len(sys.argv) > 2 else "crypto_5m"
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 10
    
    results = asyncio.run(run_backtest(asset, timeframe, limit))
