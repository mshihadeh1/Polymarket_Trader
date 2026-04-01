# Polymarket Trader

Research-first Polymarket platform for short-horizon crypto markets. The current repo is aimed at observation, layered closed-market evaluation, baseline backtesting, and dry-run paper workflows. It is not claiming live-trading readiness and it is not yet a full historical Polymarket trade replay engine.

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

6. Keep `PAPER_TRADING_LOOP_ENABLED=false` for the current observation and CSV backtest runbooks. The paper loop remains out of scope for this validation pass.

## First 10 Minutes After Clone

1. Copy `.env.example` to `.env`.
2. Leave the default mock settings alone for the first run.
3. Start Docker Compose with `docker compose --env-file .env -f infrastructure/docker-compose.yml up --build`.
4. Open the dashboard at [http://localhost:3000](http://localhost:3000).
5. Confirm the dashboard shows `mock venue` and a loaded market table.
6. Open [http://localhost:8000/healthz](http://localhost:8000/healthz) and [http://localhost:8000/api/v1/system/health](http://localhost:8000/api/v1/system/health).
7. Open one market detail page from the dashboard.
8. If you want real observation next, flip the Polymarket mock flags in `.env` and restart.
9. If you want closed-market evaluation on your own data next, switch the external provider to `csv` and point the CSV paths to your files.

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
PAPER_TRADING_LOOP_ENABLED=false
```

Or run the helper:

```bash
./scripts/run-real-observation.sh
```

PowerShell:

```powershell
./scripts/run-real-observation.ps1
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

Best for evaluating closed Polymarket 5m and 15m markets against your own 1-minute historical datasets.

Use:

```bash
EXTERNAL_HISTORICAL_PROVIDER=csv
USE_MOCK_EXTERNAL_PROVIDER=false
CSV_BTC_PATH=data/datasets/BTCUSD-1m-104wks-data.csv
CSV_ETH_PATH=data/datasets/ETHUSD-1m-104wks-data.csv
CSV_SOL_PATH=data/datasets/SOLUSD-1m-104wks-data.csv
USE_MOCK_HYPERLIQUID_RECENT=false
PAPER_TRADING_LOOP_ENABLED=false
```

Run one baseline batch with the helper:

```bash
./scripts/run-csv-backtest.sh
```

PowerShell:

```powershell
./scripts/run-csv-backtest.ps1
```

What it does today:
- loads local 1-minute CSV bars into normalized `OHLCVBar` records
- validates dataset shape, time coverage, and duplicate timestamps
- evaluates recent closed Polymarket crypto markets in batch
- compares bars-only versus bars-plus-Hyperliquid-enriched results
- stores per-market evaluation records and aggregate comparison metrics

Truthful limitation:
- this is a layered closed-market evaluator, not a full historical Polymarket trade-replay engine

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
- `timestamp`, `datetime`, `ts`, or `date`
- `open`
- `high`
- `low`
- `close`
- `volume`

Example config:

```bash
EXTERNAL_HISTORICAL_PROVIDER=csv
USE_MOCK_EXTERNAL_PROVIDER=false
CSV_BTC_PATH=data/datasets/BTCUSD-1m-104wks-data.csv
CSV_ETH_PATH=data/datasets/ETHUSD-1m-104wks-data.csv
CSV_SOL_PATH=data/datasets/SOLUSD-1m-104wks-data.csv
EXTERNAL_PROVIDER_SYMBOL_MAP={"BTC":"BTCUSDT","ETH":"ETHUSDT","SOL":"SOLUSDT"}
```

The repo now includes these local 1-minute datasets:
- `data/datasets/BTCUSD-1m-104wks-data.csv`
- `data/datasets/ETHUSD-1m-104wks-data.csv`
- `data/datasets/SOLUSD-1m-104wks-data.csv`

Startup validation reports:
- symbol
- row count
- first timestamp
- last timestamp
- duplicate count
- schema issues

You can inspect this through:
- `GET /api/v1/external-provider`
- `GET /api/v1/system/health`

Downstream modules remain provider-agnostic:
- feature engine reads normalized bars
- market-window service reads normalized bars
- backtester reads normalized bars
- UI reads API output, not provider payloads

## Hyperliquid Recent Enrichment Layer

The second layer is recent Hyperliquid data used for enrichment where available.

Config:

```bash
HYPERLIQUID_INFO_URL=https://api.hyperliquid.xyz/info
USE_MOCK_HYPERLIQUID_RECENT=false
HYPERLIQUID_RECENT_TRADE_LIMIT=500
HYPERLIQUID_RECENT_LOOKBACK_MINUTES=240
```

What it is used for:
- recent external CVD
- rolling external CVD
- recent trade imbalance
- recent external returns
- recent realized volatility
- current top-of-book imbalance for open markets when available

Important limits:
- Hyperliquid candle snapshots have limited retention
- recent trade coverage is best for recent windows, not deep history
- current L2 book is used for open/live contexts, not for closed historical windows
- if a source is unavailable, the evaluator skips those features cleanly and records that fact

## Closed Polymarket Evaluation Workflow

This repo now supports a practical layered evaluator for closed Polymarket 5m and 15m crypto markets.

Current evaluation flow:
1. discover recent closed Polymarket crypto markets
2. classify underlying and timeframe
3. load the relevant historical bar window from the CSV provider
4. add recent Hyperliquid trades and candles where available
5. compute point-in-time feature snapshots through the same feature pipeline used by live workflows
6. generate a decision timeline and final decision
7. compare the final decision with the actual market outcome or a derived close-vs-strike outcome when needed

What this does not mean:
- this is not a historical Polymarket trade-by-trade replay engine
- this does not reconstruct historical Polymarket queue position or fills
- this does not claim full historical Hyperliquid depth or long-horizon historical trades

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
- `CSV_BTC_PATH`, `CSV_ETH_PATH`, `CSV_SOL_PATH`
  Explicit local dataset paths for the first historical layer.
- `CSV_PROVIDER_PATHS`
  Optional JSON mapping kept for compatibility with the provider factory.
- `EXTERNAL_PROVIDER_SYMBOL_MAP`
  Keeps internal symbols decoupled from vendor-specific symbol strings.
- `USE_MOCK_HYPERLIQUID_RECENT`
  Switches the recent Hyperliquid enrichment layer between mock and real mode.

## One-Command Startup

From the repo root:

```bash
docker compose --env-file .env -f infrastructure/docker-compose.yml up --build
```

Helper scripts:
- [scripts/dev-up.sh](C:/Users/Mahdi/Documents/Polymarket_Trader/scripts/dev-up.sh)
- [scripts/dev-down.sh](C:/Users/Mahdi/Documents/Polymarket_Trader/scripts/dev-down.sh)
- [scripts/check-health.sh](C:/Users/Mahdi/Documents/Polymarket_Trader/scripts/check-health.sh)
- [scripts/run-csv-backtest.sh](C:/Users/Mahdi/Documents/Polymarket_Trader/scripts/run-csv-backtest.sh)
- [scripts/run-real-observation.sh](C:/Users/Mahdi/Documents/Polymarket_Trader/scripts/run-real-observation.sh)
- [scripts/dev-up.ps1](C:/Users/Mahdi/Documents/Polymarket_Trader/scripts/dev-up.ps1)
- [scripts/dev-down.ps1](C:/Users/Mahdi/Documents/Polymarket_Trader/scripts/dev-down.ps1)
- [scripts/check-health.ps1](C:/Users/Mahdi/Documents/Polymarket_Trader/scripts/check-health.ps1)
- [scripts/run-csv-backtest.ps1](C:/Users/Mahdi/Documents/Polymarket_Trader/scripts/run-csv-backtest.ps1)
- [scripts/run-real-observation.ps1](C:/Users/Mahdi/Documents/Polymarket_Trader/scripts/run-real-observation.ps1)

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
curl http://localhost:8000/api/v1/external-provider
curl "http://localhost:8000/api/v1/evaluations/closed-markets?asset=BTC&timeframe=crypto_5m&limit=10"
curl -X POST "http://localhost:8000/api/v1/evaluations/closed-markets/run?asset=BTC&timeframe=crypto_5m&limit=10&include_hyperliquid_enrichment=false"
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

Expected CSV-startup signs:
- API logs include messages like:
  - `CSV dataset validation symbol=BTC rows=... first=... last=... duplicates=... issues=[]`
  - `CSV dataset validation symbol=SOL rows=... first=... last=... duplicates=... issues=[]`
- `/api/v1/external-provider` returns `"provider_name": "csv"`
- `/api/v1/external-provider` includes `dataset_validation` entries with:
  - `row_count`
  - `first_timestamp`
  - `last_timestamp`
  - `duplicate_count`
  - `schema_issues`

Expected backtest-batch signs:
- `POST /api/v1/evaluations/closed-markets/run?...include_hyperliquid_enrichment=false` returns a batch report
- [http://localhost:3000/backtests?asset=BTC&timeframe=crypto_5m&limit=10](http://localhost:3000/backtests?asset=BTC&timeframe=crypto_5m&limit=10) shows eligible markets and batch results

## Verification Checklist

- Repo cloned successfully.
- `.env` created from `.env.example`.
- `docker compose --env-file .env -f infrastructure/docker-compose.yml up --build` completes.
- [http://localhost:3000](http://localhost:3000) loads.
- [http://localhost:8000/docs](http://localhost:8000/docs) loads.
- [http://localhost:8000/healthz](http://localhost:8000/healthz) returns `{"status":"ok"}`.
- [http://localhost:8000/api/v1/system/health](http://localhost:8000/api/v1/system/health) returns JSON with market and provider details.
- [http://localhost:8000/api/v1/external-provider](http://localhost:8000/api/v1/external-provider) returns dataset validation details when CSV mode is active.
- Dashboard clearly shows:
  - mock vs real Polymarket mode
  - current external provider
  - connection status
  - last event time
- Dashboard BTC quick-launch cards open live BTC 5m or BTC 15m detail pages in real observation mode.
- Backtests page shows:
  - recent closed eligible markets
  - bars-only versus enriched comparison
  - enrichment coverage notes
- CSV baseline batch returns a report from `POST /api/v1/evaluations/closed-markets/run?...include_hyperliquid_enrichment=false`.
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
- Verify `CSV_BTC_PATH`, `CSV_ETH_PATH`, and `CSV_SOL_PATH` are correct for the symbols you want to evaluate.
- Verify the CSV has `timestamp` or `datetime`, plus `open/high/low/close/volume`.

### Hyperliquid enrichment is missing

- Check `USE_MOCK_HYPERLIQUID_RECENT`.
- Check `HYPERLIQUID_INFO_URL`.
- Check the evaluation record notes and coverage counts.
- Older closed markets may legitimately have bars only because recent Hyperliquid retention does not reach that far back.

### Paper loop is not running

- Verify `PAPER_TRADING_LOOP_ENABLED=true`.
- Check `/api/v1/paper-trading/status`.
- The current paper loop is dry-run only and intentionally simple. It is for monitoring and research, not live execution.

## Practical Runbook

1. Place your CSV datasets in `data/datasets/` or set absolute paths in `.env`.
2. Set:

```bash
EXTERNAL_HISTORICAL_PROVIDER=csv
USE_MOCK_EXTERNAL_PROVIDER=false
USE_MOCK_HYPERLIQUID_RECENT=false
```

3. Start the stack:

```bash
docker compose --env-file .env -f infrastructure/docker-compose.yml up --build
```

4. Inspect dataset validation:

```bash
curl http://localhost:8000/api/v1/external-provider
```

5. List recent closed markets eligible for evaluation:

```bash
curl "http://localhost:8000/api/v1/evaluations/closed-markets?asset=BTC&timeframe=crypto_5m&limit=10"
```

6. Run a baseline-versus-enriched comparison:

```bash
curl -X POST "http://localhost:8000/api/v1/evaluations/compare?asset=BTC&timeframe=crypto_5m&limit=10"
```

For a baseline-only batch using the current bar-based evaluator:

```bash
curl -X POST "http://localhost:8000/api/v1/evaluations/closed-markets/run?asset=BTC&timeframe=crypto_5m&limit=10&include_hyperliquid_enrichment=false"
```

To hydrate known closed BTC 5m / 15m markets directly by slug or market id:

```bash
curl -X POST "http://localhost:8000/api/v1/ingestion/hydrate-closed-markets?identifiers=btc-updown-5m-1775039700&identifiers=btc-updown-15m-1775039400"
```

7. Open [http://localhost:3000/backtests?asset=BTC&timeframe=crypto_5m&limit=10](http://localhost:3000/backtests?asset=BTC&timeframe=crypto_5m&limit=10) to inspect:
- eligible closed markets
- bars-only vs bars-plus-Hyperliquid comparison
- coverage and missing-data notes

8. For open markets, switch to real observation mode with `./scripts/run-real-observation.sh` or `./scripts/run-real-observation.ps1` and use the same feature stack through the dashboard and market detail pages.

## API Surface

- `GET /healthz`
- `GET /api/v1/markets`
- `GET /api/v1/markets/{market_id}`
- `GET /api/v1/markets/{market_id}/orderbook`
- `GET /api/v1/markets/{market_id}/trades`
- `GET /api/v1/markets/{market_id}/features`
- `GET /api/v1/replay/{market_id}`
- `POST /api/v1/ingestion/bootstrap`
- `POST /api/v1/ingestion/hydrate-closed-markets`
- `GET /api/v1/strategies`
- `POST /api/v1/backtests/{market_id}`
- `GET /api/v1/backtests`
- `GET /api/v1/backtests/{run_id}`
- `GET /api/v1/evaluations/closed-markets`
- `POST /api/v1/evaluations/closed-markets/run`
- `GET /api/v1/evaluations/results`
- `POST /api/v1/evaluations/compare`
- `GET /api/v1/markets/{market_id}/live-feature-view`
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
- Closed-market evaluation is usable for baseline research on local 1-minute CSV datasets plus recent Hyperliquid enrichment where available.
- Live paper mode is partial but useful for continuous dry-run monitoring.
- Live execution is not implemented.
- Weather and broader market-type expansion are not part of the current usable local workflow.
