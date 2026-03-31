# Polymarket Trader

Production-minded research and trading platform scaffold for Polymarket, starting with 5-minute and 15-minute crypto markets and designed to expand to weather and other event markets.

## Phase 1 scope

- Monorepo scaffold
- Historical store schema and migrations
- Market catalog ingestion
- Mockable trade and order book ingestion
- FastAPI backend for market browsing and replay
- Next.js dashboard and replay UI
- Docker Compose local stack
- Seed data and sample tests

## Monorepo layout

- `apps/api`: FastAPI backend and API composition root
- `apps/web`: Next.js research dashboard
- `services/market_catalog`: market metadata and filtering
- `services/polymarket_ingestor`: Polymarket metadata, book, trade, and raw-event ingestion
- `services/hyperliquid_ingestor`: Hyperliquid trade and book ingestion
- `services/feature_engine`: market-window alignment and feature computation
- `services/fair_value_models`: interpretable baseline fair-value models
- `services/backtester`: replay/backtest scaffolding
- `services/paper_trader`: paper-trading state and risk-facing status
- `services/execution_engine`: dry-run-only execution scaffold
- `services/rules_engine`: resolution rule normalization scaffold
- `packages/core_types`: shared typed schemas
- `packages/config`: environment-based settings
- `packages/utils`: reusable time and feature utilities
- `packages/clients`: exchange/client adapters with mock implementations
- `infrastructure/docker-compose.yml`: local stack entrypoint
- `infrastructure/env/.env.example`: environment template
- `infrastructure/migrations`: SQL schema migrations
- `data/seed`: mock seed payloads for Polymarket and Hyperliquid
- `tests`: cross-service research tests

## Quick start

1. Copy `.env.example` to `.env`.
2. Copy `infrastructure/env/.env.example` to `.env` if you want a root env file as well.
3. Start the stack:

```bash
docker compose -f infrastructure/docker-compose.yml up --build
```

3. Backend API:
   - `http://localhost:8000/docs`
4. Frontend:
   - `http://localhost:3000`

## Local development

### API

```bash
cd apps/api
pip install -e .[dev]
uvicorn polymarket_trader.main:app --reload --port 8000
```

### Web

```bash
cd apps/web
npm install
npm run dev
```

## Environment

See [infrastructure/env/.env.example](C:/Users/Mahdi/Documents/Polymarket_Trader/infrastructure/env/.env.example) for supported variables. Live execution is disabled by default. Polymarket and Hyperliquid connectivity are isolated behind adapters so mock clients can be used in development and tests.

## Phase 1 API endpoints

- `GET /healthz`
- `GET /api/v1/markets`
- `GET /api/v1/markets/{market_id}`
- `GET /api/v1/markets/{market_id}/orderbook`
- `GET /api/v1/markets/{market_id}/trades`
- `GET /api/v1/markets/{market_id}/features`
- `GET /api/v1/replay/{market_id}`
- `POST /api/v1/ingestion/bootstrap`
- `GET /api/v1/strategies`
- `POST /api/v1/backtests/{market_id}`
- `GET /api/v1/paper-trading/blotter`
- `GET /api/v1/risk/settings`
- `GET /api/v1/execution/status`
- `GET /api/v1/system/health`

## Testing

```bash
python -m pytest apps/api/tests tests
```

## Notes

- The current Polymarket and Hyperliquid integration paths are intentionally mock-first.
- Live order routing is not implemented and all execution paths remain dry-run only.
- Weather and other market types are reflected in the schema and interfaces, but their specialized models and rule parsing land in later phases.
- The current backtester is a Phase 1 scaffold that exposes result shapes and feature hooks without claiming full queue-position realism yet.
