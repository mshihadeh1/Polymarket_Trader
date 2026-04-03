#!/usr/bin/env python3
"""
Hyperparameter Grid Search Optimization for BTC Mean Reversion Strategy.

This script systematically tests different parameter combinations to find
the optimal configuration for BTC 5-minute mean reversion trading.

Usage:
    python3 scripts/optimize_btc_strategy.py
"""

import sys
import os
from itertools import product

# Add project paths
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT_DIR, "apps", "api", "src"))
sys.path.insert(0, ROOT_DIR)

os.environ.setdefault("EXTERNAL_HISTORICAL_PROVIDER", "csv")
os.environ.setdefault("USE_MOCK_EXTERNAL_PROVIDER", "false")
os.environ.setdefault("USE_MOCK_POLYMARKET", "true")
os.environ.setdefault("USE_MOCK_POLYMARKET_CLIENT", "true")
os.environ.setdefault("PAPER_TRADING_LOOP_ENABLED", "false")
os.environ.setdefault("ENABLE_DB_PERSISTENCE", "false")

import requests
import json

API_BASE = "http://localhost:8000"

def run_backtest(params: dict, limit: int = 200) -> dict | None:
    """Run a single backtest with given parameters."""
    endpoint = f"{API_BASE}/api/v1/research/synthetic/run"
    payload = {
        "asset": "BTC",
        "timeframe": "crypto_5m",
        "limit": limit,
        "strategy_name": "synthetic_grid_search_mr",
    }
    
    # Add custom parameters
    for key, value in params.items():
        payload[f"param_{key}"] = value
    
    try:
        response = requests.post(endpoint, params=payload, timeout=60)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"  Error {response.status_code}: {response.text[:100]}")
            return None
    except Exception as e:
        print(f"  Exception: {e}")
        return None


def extract_metrics(result: dict) -> dict:
    """Extract key metrics from backtest result."""
    metrics = {m['label']: m['value'] for m in result.get('metrics', [])}
    return {
        'hit_rate': metrics.get('hit_rate', 0),
        'edge': metrics.get('edge_over_50', 0),
        'contract_score': metrics.get('contract_score', 0),
        'trade_frequency': metrics.get('trade_frequency', 0),
        'total_samples': result.get('total_samples', 0),
    }


def print_results_table(results: list):
    """Print formatted results table."""
    print("\n" + "=" * 100)
    print("GRID SEARCH RESULTS (sorted by edge)")
    print("=" * 100)
    print(f"\n{'Rank':<5} {'Distance W':<12} {'Range W':<10} {'Vol Scale':<10} {'Threshold':<10} "
          f"{'Hit Rate':<10} {'Edge':<10} {'Contract':<10} {'Trades':<8} {'Samples':<8}")
    print("-" * 100)
    
    # Sort by edge (descending)
    sorted_results = sorted(results, key=lambda x: x['metrics']['edge'], reverse=True)
    
    for i, r in enumerate(sorted_results[:20], 1):  # Show top 20
        p = r['params']
        m = r['metrics']
        marker = " ★" if i == 1 else ""
        print(f"{i:<5} {p['distance_weight']:<12.1f} {p['range_weight']:<10.1f} "
              f"{p['vol_scale_factor']:<10.1f} {p['threshold']:<10.5f} "
              f"{m['hit_rate']:<9.1%} {m['edge']:<+9.1%}{marker} {m['contract_score']:<9.1f} "
              f"{m['trade_frequency']:<7.0%} {m['total_samples']:<8}")
    
    print("\n" + "=" * 100)
    if sorted_results:
        best = sorted_results[0]
        print(f"BEST CONFIGURATION:")
        print(f"  Distance Weight: {best['params']['distance_weight']}")
        print(f"  Range Weight: {best['params']['range_weight']}")
        print(f"  Vol Scale Factor: {best['params']['vol_scale_factor']}")
        print(f"  Threshold: {best['params']['threshold']}")
        print(f"  Performance: {best['metrics']['hit_rate']:.1%} HR, {best['metrics']['edge']:+.1%} Edge")
    print("=" * 100)


def main():
    print("=" * 100)
    print("BTC MEAN REVERSION HYPERPARAMETER GRID SEARCH")
    print("=" * 100)
    
    # Define parameter grid
    distance_weights = [1.5, 2.0, 2.5, 3.0]
    range_weights = [1.0, 1.5, 2.0, 2.5]
    vol_scale_factors = [25.0, 50.0, 75.0, 100.0]
    thresholds = [0.0005, 0.0008, 0.001, 0.0012]
    
    # Create all combinations
    param_grid = list(product(distance_weights, range_weights, vol_scale_factors, thresholds))
    
    print(f"\nTesting {len(param_grid)} parameter combinations...")
    print(f"Distance weights: {distance_weights}")
    print(f"Range weights: {range_weights}")
    print(f"Vol scale factors: {vol_scale_factors}")
    print(f"Thresholds: {thresholds}")
    print("\nRunning backtests...\n")
    
    results = []
    completed = 0
    
    for dw, rw, vol, thresh in param_grid:
        params = {
            'distance_weight': dw,
            'range_weight': rw,
            'vol_scale_factor': vol,
            'threshold': thresh,
        }
        
        completed += 1
        print(f"[{completed}/{len(param_grid)}] Testing: dw={dw}, rw={rw}, vol={vol}, thresh={thresh}...")
        
        result = run_backtest(params, limit=200)
        if result:
            metrics = extract_metrics(result)
            results.append({
                'params': params,
                'metrics': metrics,
                'result': result,
            })
            print(f"  → HR={metrics['hit_rate']:.1%}, Edge={metrics['edge']:+.1%}, "
                  f"Trades={metrics['trade_frequency']:.0%}")
        else:
            print(f"  → FAILED")
    
    if results:
        print_results_table(results)
        
        # Save best configuration
        best = max(results, key=lambda x: x['metrics']['edge'])
        config_file = os.path.join(ROOT_DIR, "data", "best_btc_config.json")
        os.makedirs(os.path.dirname(config_file), exist_ok=True)
        with open(config_file, 'w') as f:
            json.dump({
                'best_params': best['params'],
                'metrics': best['metrics'],
            }, f, indent=2)
        print(f"\nBest configuration saved to: {config_file}")
    else:
        print("\nNo successful backtests completed!")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
