#!/usr/bin/env sh
set -eu

LIMIT="${1:-10}"
ASSET="${2:-BTC}"
TIMEFRAME="${3:-crypto_5m}"

export EXTERNAL_HISTORICAL_PROVIDER=csv
export USE_MOCK_EXTERNAL_PROVIDER=false
export PAPER_TRADING_LOOP_ENABLED=false

echo "Starting stack for CSV baseline backtest..."
docker compose --env-file .env -f infrastructure/docker-compose.yml up -d --build

echo "Waiting for API health..."
attempt=0
until curl -fsS http://localhost:8000/healthz >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 60 ]; then
    echo "API did not become healthy within 120 seconds."
    exit 1
  fi
  sleep 2
done

echo "CSV validation report:"
curl -fsS http://localhost:8000/api/v1/external-provider
echo
echo "Eligible closed markets:"
curl -fsS "http://localhost:8000/api/v1/evaluations/closed-markets?asset=${ASSET}&timeframe=${TIMEFRAME}&limit=${LIMIT}"
echo
echo "Running baseline closed-market batch without Hyperliquid enrichment..."
curl -fsS -X POST "http://localhost:8000/api/v1/evaluations/closed-markets/run?asset=${ASSET}&timeframe=${TIMEFRAME}&limit=${LIMIT}&strategy_name=combined_cvd_gap&include_hyperliquid_enrichment=false"
echo
echo "Open http://localhost:3000/backtests?asset=${ASSET}&timeframe=${TIMEFRAME}&limit=${LIMIT} to inspect the results."
