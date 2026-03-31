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

## Current build status

- Phase 1: implemented as a mostly mock-first vertical slice, with a real Polymarket discovery path now available behind config and a partially working real websocket ingestion path
- Phase 2: partially implemented with market-window alignment, local and external CVD features, and a baseline fair-value model
- Phase 3: partially implemented with a strategy registry, stored backtest reports, and cost-aware baseline backtest scaffolding
- Phase 4: partially implemented with paper-trading status and blotter plus execution and rules-engine scaffolds

The remaining work is still explicit in code and docs: persistent historical ingestion into the full Timescale schema, richer queue and latency simulation, and a real live-paper loop.

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

See [infrastructure/env/.env.example](C:/Users/Mahdi/Documents/Polymarket_Trader/infrastructure/env/.env.example) for supported variables. Live execution is disabled by default. Polymarket connectivity and external historical market data are isolated behind adapters so mock clients and pluggable providers can be used in development and tests.

The initial free historical provider is Binance, but downstream services consume only normalized internal bars, trades, and order book snapshots. Provider selection is configuration-driven so future sources such as Tardis, Parquet, or custom datasets do not require replay or strategy rewrites.

## External Market Data Providers

The external historical market data path now uses a provider interface in [packages/clients/market_data_provider/base.py](C:/Users/Mahdi/Documents/Polymarket_Trader/packages/clients/market_data_provider/base.py).

- Provider interface: `HistoricalMarketDataProvider`
- Normalized internal models: `OHLCVBar`, `ExternalTrade`, `ExternalOrderBookSnapshot`, `ProviderCapabilities`
- Provider selection: `EXTERNAL_HISTORICAL_PROVIDER=binance`
- Symbol mapping: `EXTERNAL_PROVIDER_SYMBOL_MAP={"BTC":"BTCUSDT","ETH":"ETHUSDT"}`

Current provider support:
- `binance`: implemented for historical 1-minute OHLCV, with trades and snapshots available as provider methods
- `tardis`: placeholder scaffold
- `parquet`: placeholder scaffold

The application stores both raw provider payloads and normalized records in the in-memory runtime state. Downstream modules consume only normalized internal models.

## Real Polymarket Ingestion

The repo now supports a narrow real Polymarket path behind config while preserving the mock path for fallback.

Config:

```bash
USE_MOCK_POLYMARKET_CLIENT=false
POLYMARKET_API_BASE_URL=https://gamma-api.polymarket.com
POLYMARKET_WS_URL=wss://ws-subscriptions-clob.polymarket.com/ws/market
```

Current real Polymarket status:
- real discovery from Gamma works and populates market state
- real markets are classified into short-horizon crypto buckets and exposed through the existing market endpoints
- the websocket path connects and receives real market events
- raw websocket payloads are stored before normalization
- normalized Polymarket order-book and trade records are only partially working in real mode today

Known limitations / TODOs:
- the websocket adapter currently handles only a narrow set of market-channel events: `last_trade_price`, `price_change`, `best_bid_ask`, and `book`
- the real websocket path is not yet end-to-end reliable: during a live validation run on March 31, 2026 it received real events and then failed on an unexpected `book` payload shape in top-of-book normalization
- some Polymarket feed fields are normalized defensively because public docs are not exhaustive for every event variant
- this slice focuses on live ingestion and in-memory/runtime persistence, not full Timescale historical persistence yet

Optional local persistence for feature snapshots, backtest reports, and paper decisions can be enabled with:

```bash
ENABLE_DB_PERSISTENCE=true
SQLITE_FALLBACK_PATH=data/polymarket_trader.db
```

That persistence layer is a local development helper, not a claim that the full Timescale ingestion path is already finished.

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
- `GET /api/v1/backtests`
- `GET /api/v1/backtests/{run_id}`
- `GET /api/v1/paper-trading/blotter`
- `GET /api/v1/paper-trading/status`
- `POST /api/v1/paper-trading/run/{market_id}`
- `GET /api/v1/risk/settings`
- `GET /api/v1/execution/status`
- `GET /api/v1/system/health`

## Web pages

- `/`: active market dashboard
- `/markets/[marketId]`: market detail with local and external context plus feature panel
- `/replay`: historical replay viewer
- `/backtests`: backtest results and strategy list
- `/paper-trading`: paper blotter and strategy status

## Testing

```bash
python -m pytest apps/api/tests tests
```

## Notes

- Hyperliquid remains mock-first in the current app bootstrap.
- Polymarket is no longer code-only mock-first: real discovery works behind config, but the live websocket ingestion path still needs hardening before it can be called end-to-end working.
- Live order routing is not implemented and all execution paths remain dry-run only.
- Weather and other market types are reflected in the schema and interfaces, but their specialized models and rule parsing land in later phases.
- The current backtester is a Phase 1 scaffold that exposes result shapes and feature hooks without claiming full queue-position realism yet.
