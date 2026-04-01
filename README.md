# Polymarket Trader

Research-first Polymarket platform for short-horizon crypto markets. The current repo is aimed at observation, replay, baseline backtesting, and dry-run paper workflows. It is not claiming live-trading readiness.

## Getting Started

Fastest path from a fresh clone:

1. Clone the repo:

```bash
git clone https://github.com/mshihadeh1/Polymarket_Trader.git
cd Polymarket_Trader
git switch codex/persistence-timescale
```

2. Copy the root env file:

```bash
cp .env.example .env
```

PowerShell:

```powershell
Copy-Item .env.example .env
```

3. Start the stack:

```bash
docker compose --env-file .env -f infrastructure/docker-compose.yml up --build
```

Or use the helper scripts:

```bash
./scripts/dev-up.sh
```

PowerShell:

```powershell
./scripts/dev-up.ps1
```

4. Open the UI:
- frontend: [http://localhost:3000](http://localhost:3000)
- backend docs: [http://localhost:8000/docs](http://localhost:8000/docs)

5. Verify health:

```bash
./scripts/check-health.sh
```

PowerShell:

```powershell
./scripts/check-health.ps1
```

## First 10 Minutes After Clone

1. Copy `.env.example` to `.env`.
2. Leave the default mock settings alone for the first run.
3. Start Docker Compose with `docker compose --env-file .env -f infrastructure/docker-compose.yml up --build`.
4. Open the dashboard at [http://localhost:3000](http://localhost:3000).
5. Confirm the dashboard shows `mock venue` and a loaded market table.
6. Open [http://localhost:8000/healthz](http://localhost:8000/healthz) and [http://localhost:8000/api/v1/system/health](http://localhost:8000/api/v1/system/health).
7. Open one market detail page from the dashboard.
8. If you want real observation next, flip the Polymarket mock flags in `.env` and restart.
9. If you want backtests on your own data next, switch the external provider to `csv` and point `CSV_PROVIDER_PATHS` to your files.

## Run Modes

### Mock mode

Best for first launch, UI verification, and basic development.

Use:

```bash
USE_MOCK_POLYMARKET=true
USE_MOCK_POLYMARKET_CLIENT=true
EXTERNAL_HISTORICAL_PROVIDER=binance
USE_MOCK_EXTERNAL_PROVIDER=true
PAPER_TRADING_LOOP_ENABLED=false
```

What to expect:
- seeded markets and seeded venue data
- dashboard, replay, backtests, and paper pages all load
- safest mode for a fresh clone

### Real Polymarket observation mode

Best for a 2 to 4 hour venue observation session.

Use:

```bash
USE_MOCK_POLYMARKET=false
USE_MOCK_POLYMARKET_CLIENT=false
POLYMARKET_API_BASE_URL=https://gamma-api.polymarket.com
POLYMARKET_WS_URL=wss://ws-subscriptions-clob.polymarket.com/ws/market
USE_MOCK_EXTERNAL_PROVIDER=true
```

What is real:
- active Polymarket market discovery
- BTC and ETH short-horizon market classification
- live websocket observation with reconnect supervision
- UI status for connection state, last event time, dropped events, and duplicate counts

What is not claimed:
- no live trading
- no trading-grade execution reliability
- websocket normalization is still narrow and defensive

### Historical backtest mode

Best for replaying your own 1-minute datasets.

Use:

```bash
EXTERNAL_HISTORICAL_PROVIDER=csv
USE_MOCK_EXTERNAL_PROVIDER=false
CSV_PROVIDER_PATHS={"BTC":"data/datasets/btc_1m.csv","ETH":"data/datasets/eth_1m.csv","SOL":"data/datasets/sol_1m.csv"}
```

What it does today:
- loads local 1-minute CSV bars into normalized `OHLCVBar` records
- recomputes features bar by bar
- replays sequentially through the current baseline backtester
- outputs trade list, equity curve, net PnL, drawdown, and expectancy

Truthful limitation:
- the backtester is usable for baseline research, but the execution model is still intentionally simple rather than microstructure-realistic

### Live paper mode

Best for a dry-run monitoring loop. This is still partial.

Use:

```bash
USE_MOCK_POLYMARKET=false
USE_MOCK_POLYMARKET_CLIENT=false
PAPER_TRADING_LOOP_ENABLED=true
PAPER_TRADING_LOOP_SECONDS=30
PAPER_TRADING_UNDERLYINGS=BTC
PAPER_TRADING_MARKET_TYPES=crypto_5m,crypto_15m
PAPER_TRADING_STRATEGY=combined_cvd_gap
LIVE_EXECUTION_ENABLED=false
```

What it does today:
- periodically evaluates selected live markets
- appends dry-run decisions continuously
- tracks latest signal, last decision, open positions, realized PnL, unrealized PnL, and loop health

Truthful limitation:
- this is a supervised dry-run loop for observation and research, not a full live-paper execution simulator

## Local Historical Datasets

The repo now supports local 1-minute CSV datasets through the provider layer without changing downstream code.

Expected CSV columns:
- `ts` or `timestamp`
- `open`
- `high`
- `low`
- `close`
- `volume`

Example config:

```bash
EXTERNAL_HISTORICAL_PROVIDER=csv
USE_MOCK_EXTERNAL_PROVIDER=false
CSV_PROVIDER_PATHS={"BTC":"data/datasets/btc_1m.csv","ETH":"data/datasets/eth_1m.csv","SOL":"data/datasets/sol_1m.csv"}
EXTERNAL_PROVIDER_SYMBOL_MAP={"BTC":"BTCUSDT","ETH":"ETHUSDT","SOL":"SOLUSDT"}
```

Downstream modules remain provider-agnostic:
- feature engine reads normalized bars
- market-window service reads normalized bars
- backtester reads normalized bars
- UI reads API output, not provider payloads

## Environment Notes

The main file to copy is [`.env.example`](C:/Users/Mahdi/Documents/Polymarket_Trader/.env.example). Docker Compose now reads the root `.env` directly.

Most important flags:
- `USE_MOCK_POLYMARKET` and `USE_MOCK_POLYMARKET_CLIENT`
  Controls whether the app boots from seeded mock venue data or the real Polymarket adapter.
- `POLYMARKET_API_BASE_URL`
  REST market discovery base URL for real observation mode.
- `POLYMARKET_WS_URL`
  websocket endpoint for live Polymarket market events.
- `EXTERNAL_HISTORICAL_PROVIDER`
  Selects the historical source used by research flows. Current practical options are `binance` and `csv`.
- `CSV_PROVIDER_PATHS`
  Maps internal symbols such as `BTC`, `ETH`, and `SOL` to local CSV file paths.
- `EXTERNAL_PROVIDER_SYMBOL_MAP`
  Keeps internal symbols decoupled from vendor-specific symbol strings.

## One-Command Startup

From the repo root:

```bash
docker compose --env-file .env -f infrastructure/docker-compose.yml up --build
```

Helper scripts:
- [scripts/dev-up.sh](C:/Users/Mahdi/Documents/Polymarket_Trader/scripts/dev-up.sh)
- [scripts/dev-down.sh](C:/Users/Mahdi/Documents/Polymarket_Trader/scripts/dev-down.sh)
- [scripts/check-health.sh](C:/Users/Mahdi/Documents/Polymarket_Trader/scripts/check-health.sh)
- [scripts/dev-up.ps1](C:/Users/Mahdi/Documents/Polymarket_Trader/scripts/dev-up.ps1)
- [scripts/dev-down.ps1](C:/Users/Mahdi/Documents/Polymarket_Trader/scripts/dev-down.ps1)
- [scripts/check-health.ps1](C:/Users/Mahdi/Documents/Polymarket_Trader/scripts/check-health.ps1)

## Health And Verification

Core URLs:
- frontend: [http://localhost:3000](http://localhost:3000)
- backend docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- backend health: [http://localhost:8000/healthz](http://localhost:8000/healthz)
- system health: [http://localhost:8000/api/v1/system/health](http://localhost:8000/api/v1/system/health)

Sample checks:

```bash
curl http://localhost:8000/healthz
curl http://localhost:8000/api/v1/system/health
curl http://localhost:8000/api/v1/markets
```

Expected mock-mode signs:
- dashboard shows `mock venue`
- `/api/v1/system/health` returns `"mock_polymarket": true`
- market table loads immediately

Expected real-observation signs:
- dashboard shows `real venue`
- dashboard shows websocket status and reconnect count
- `/api/v1/system/health` returns `"mock_polymarket": false`
- API logs include messages like:
  - `Polymarket discovery returned ... selected short-horizon markets`
  - `Polymarket websocket connected for live observation`

## Verification Checklist

- Repo cloned successfully.
- `.env` created from `.env.example`.
- `docker compose --env-file .env -f infrastructure/docker-compose.yml up --build` completes.
- [http://localhost:3000](http://localhost:3000) loads.
- [http://localhost:8000/docs](http://localhost:8000/docs) loads.
- [http://localhost:8000/healthz](http://localhost:8000/healthz) returns `{"status":"ok"}`.
- [http://localhost:8000/api/v1/system/health](http://localhost:8000/api/v1/system/health) returns JSON with market and provider details.
- Dashboard clearly shows:
  - mock vs real Polymarket mode
  - current external provider
  - connection status
  - last event time
- If using CSV backtests, the configured file paths exist and the files have the required columns.
- If using real observation mode, the dashboard shows live venue badges and a recent event timestamp.

## Troubleshooting

### Docker Compose starts but the web page is blank

- Check [http://localhost:8000/healthz](http://localhost:8000/healthz).
- Check `NEXT_PUBLIC_API_BASE_URL` in `.env`.
- Confirm the `api` and `web` containers are both running.

### Dashboard loads but no markets appear

- In mock mode, verify both mock Polymarket flags are `true`.
- In real mode, verify both mock Polymarket flags are `false`.
- Check API logs for discovery messages.
- Call `POST /api/v1/ingestion/bootstrap` to reload the in-memory session.

### Real observation mode connects but shows stale data

- Check the dashboard websocket badge and reconnect count.
- Check `/api/v1/system/health` for `last_event_at`, `dropped_event_count`, and `duplicate_event_count`.
- Restart the stack if the websocket loop is stuck.

### CSV historical mode does not load bars

- Verify `EXTERNAL_HISTORICAL_PROVIDER=csv`.
- Verify `USE_MOCK_EXTERNAL_PROVIDER=false`.
- Verify each `CSV_PROVIDER_PATHS` file exists relative to the repo root or as an absolute path.
- Verify the CSV has `ts` or `timestamp`, plus `open/high/low/close/volume`.

### Paper loop is not running

- Verify `PAPER_TRADING_LOOP_ENABLED=true`.
- Check `/api/v1/paper-trading/status`.
- The current paper loop is dry-run only and intentionally simple. It is for monitoring and research, not live execution.

## API Surface

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
- `POST /api/v1/paper-trading/cycle`
- `POST /api/v1/paper-trading/start`
- `POST /api/v1/paper-trading/stop`
- `GET /api/v1/risk/settings`
- `GET /api/v1/execution/status`
- `GET /api/v1/system/health`

## Monorepo Layout

- `apps/api`: FastAPI backend
- `apps/web`: Next.js dashboard
- `services/polymarket_ingestor`: Polymarket discovery and live observation ingestion
- `services/feature_engine`: feature computation and market window alignment
- `services/backtester`: sequential bar replay backtesting
- `services/paper_trader`: continuous dry-run paper loop
- `packages/clients`: provider and venue adapters
- `packages/core_types`: shared typed models
- `infrastructure/docker-compose.yml`: local stack
- `tests`: focused backend tests

## Truthful Current Status

- Real Polymarket observation mode is usable for multi-hour monitoring.
- Historical backtesting is usable for baseline bar-by-bar research on local 1-minute CSV datasets.
- Live paper mode is partial but useful for continuous dry-run monitoring.
- Live execution is not implemented.
- Weather and broader market-type expansion are not part of the current usable local workflow.
