#!/usr/bin/env sh
set -eu

export USE_MOCK_POLYMARKET=false
export USE_MOCK_POLYMARKET_CLIENT=false
export PAPER_TRADING_LOOP_ENABLED=false

echo "Starting stack for real Polymarket observation mode..."
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

echo "System health:"
curl -fsS http://localhost:8000/api/v1/system/health
echo
echo "Recent markets:"
curl -fsS "http://localhost:8000/api/v1/markets?short_horizon_only=true"
echo
echo "Tail API logs with:"
echo "  docker compose --env-file .env -f infrastructure/docker-compose.yml logs -f api"
echo "Open http://localhost:3000 and use the BTC quick-launch cards to inspect a live market."
