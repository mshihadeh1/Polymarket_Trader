# Polymarket Trader

Research-first Polymarket platform for short-horizon crypto markets. The goal of this repo is to help you:

- inspect live Polymarket markets
- observe real BTC 5m / 15m venue behavior
- run bar-based backtests on local 1-minute CSV data
- run EV-first backtests on executable Polymarket quotes with dynamic fee and slippage assumptions
- compare bars-only research against recent Hyperliquid enrichment
- keep paper trading dry-run only until you explicitly enable live routing

This is **not** a live trading bot by default. Live execution is scaffolded, disabled by default, and should be treated as opt-in only.

## What’s In The Box

- FastAPI backend with market discovery, replay, research, paper trading, and execution scaffolding
- Next.js dashboard with market, replay, backtest, research, and paper views
- Provider-pluggable historical data layer with CSV, Binance, and placeholder adapters
- Local 1-minute BTC / ETH / SOL datasets for research
- Real Polymarket observation mode with reconnect supervision
- Closed-market evaluation for BTC 5m / 15m research
- EV-first evaluation with maker/taker simulation, replayable decision points, and fee-aware accounting
- Dynamic fee and tick metadata persisted from market payloads and updates
- Cached reports and persistence so the UI is not recomputing everything on every page load

## Requirements

- Docker and Docker Compose
- Python 3.12 for local tests and scripts
- Node is only needed if you want to run the Next.js app outside Docker

## Quick Start

### 1. Clone the repo

```bash
git clone https://github.com/mshihadeh1/Polymarket_Trader.git
cd Polymarket_Trader
```

### 2. Copy the env file

```bash
cp .env.example .env
```

PowerShell:

```powershell
Copy-Item .env.example .env
```

### 3. Start the stack

```bash
docker compose --env-file .env -f infrastructure/docker-compose.yml up --build
```

Helper scripts:

```bash
./scripts/dev-up.sh
./scripts/check-health.sh
```

PowerShell:

```powershell
./scripts/dev-up.ps1
./scripts/check-health.ps1
```

### 4. Open the app

- Frontend: [http://localhost:3000](http://localhost:3000)
- API docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Health: [http://localhost:8000/healthz](http://localhost:8000/healthz)
- System status: [http://localhost:8000/api/v1/system/health](http://localhost:8000/api/v1/system/health)

## Run Modes

### Mock mode

Use this for the first launch and general development.

```bash
USE_MOCK_POLYMARKET=true
USE_MOCK_POLYMARKET_CLIENT=true
EXTERNAL_HISTORICAL_PROVIDER=binance
USE_MOCK_EXTERNAL_PROVIDER=true
ENABLE_DB_PERSISTENCE=true
MOCK_STARTUP_DEMO_ENABLED=true
PAPER_TRADING_LOOP_ENABLED=false
```

What you get:

- seeded markets
- seeded observation data
- loaded dashboard widgets
- cached demo research results if persistence is on

### Real Polymarket observation mode

Use this to watch live venue behavior for a few hours.

```bash
USE_MOCK_POLYMARKET=false
USE_MOCK_POLYMARKET_CLIENT=false
POLYMARKET_API_BASE_URL=https://gamma-api.polymarket.com
POLYMARKET_WS_URL=wss://ws-subscriptions-clob.polymarket.com/ws/market
ENABLE_DB_PERSISTENCE=true
PAPER_TRADING_LOOP_ENABLED=false
```

Helpful script:

```bash
./scripts/run-real-observation.sh
```

PowerShell:

```powershell
./scripts/run-real-observation.ps1
```

What is real:

- active market discovery
- BTC / ETH short-horizon classification
- websocket observation with reconnect supervision
- live status in the dashboard

What is not claimed:

- no live trading
- no trading-grade execution reliability
- no historical trade replay

### Historical backtest mode

Use this to run bar-based research on your local 1-minute datasets and compare them against the EV-first closed-market path.

```bash
EXTERNAL_HISTORICAL_PROVIDER=csv
USE_MOCK_EXTERNAL_PROVIDER=false
CSV_BTC_PATH=data/datasets/BTCUSD-1m-104wks-data.csv
CSV_ETH_PATH=data/datasets/ETHUSD-1m-104wks-data.csv
CSV_SOL_PATH=data/datasets/SOLUSD-1m-104wks-data.csv
USE_MOCK_HYPERLIQUID_RECENT=false
PAPER_TRADING_LOOP_ENABLED=false
```

Run the baseline batch:

```bash
./scripts/run-csv-backtest.sh
```

PowerShell:

```powershell
./scripts/run-csv-backtest.ps1
```

What it does:

- loads local 1-minute CSV bars into normalized internal records
- validates row count, timestamps, duplicates, and schema issues
- evaluates closed Polymarket BTC 5m / 15m markets
- compares bars-only versus bars + recent Hyperliquid enrichment
- can run EV-first evaluation with executable prices, dynamic fee metadata, and taker or maker assumptions
- caches reports for the UI

What it does not do:

- it is not a historical Polymarket trade-by-trade replay engine

### EV-first closed-market research

This is the recommended path when you want to answer the real question: is there positive net EV after executable prices, fees, slippage, and timing are treated honestly?

Use it to:

- compare `lead_lag_dislocation`, `late_window_reversion`, and `maker_edge_v2` against the existing baseline strategies
- keep `combined_cvd_gap` and `flow_alignment_5m` as baseline comparisons
- compare `midpoint`, `taker`, `maker`, and `ev_first` execution modes
- inspect replayable decision points with exact features and execution context
- measure net PnL, EV/share, calibration, drawdown, spread buckets, time-to-close buckets, and distance-to-threshold buckets

Example runs:

```bash
curl -X POST "http://localhost:8000/api/v1/evaluations/ev-first/run?asset=BTC&timeframe=crypto_5m&limit=30&strategy_name=lead_lag_dislocation"
curl -X POST "http://localhost:8000/api/v1/evaluations/closed-markets/run?asset=BTC&timeframe=crypto_15m&limit=20&strategy_name=maker_edge_v2&execution_mode=maker"
```

Important assumptions:

- Polymarket fee configuration is fetched dynamically from market metadata and fee snapshots when available
- top-of-book prices are preferred over midpoint-only logic
- Hyperliquid remains the external microstructure source for enrichment and lead-lag context
- missing fee or tick metadata is treated as a degraded report, not as a hardcoded guess

How to read the report:

- positive net EV/share and positive holdout net PnL matter more than headline hit rate
- calibration by confidence bucket tells you whether the signal is overconfident
- maker-vs-taker comparisons tell you whether the edge survives venue friction
- a `warning` or `no-go` flag means the sample is not yet strong enough to treat as durable

### Live paper mode

Use this for a supervised dry-run loop.

```bash
USE_MOCK_POLYMARKET=false
USE_MOCK_POLYMARKET_CLIENT=false
PAPER_TRADING_LOOP_ENABLED=true
PAPER_TRADING_LOOP_SECONDS=30
PAPER_TRADING_UNDERLYINGS=BTC
PAPER_TRADING_MARKET_TYPES=crypto_5m,crypto_15m
PAPER_TRADING_STRATEGY=flow_alignment_5m
PAPER_TRADING_MARKET_REFRESH_ENABLED=true
PAPER_TRADING_MARKET_REFRESH_CYCLES=2
PAPER_TRADING_AUTO_HYDRATE_EXTERNAL=true
PAPER_TRADING_MIN_CONFIDENCE=0.62
PAPER_TRADING_SINGLE_FILL_PER_WINDOW=true
LIVE_EXECUTION_ENABLED=false
POLYMARKET_CLOB_HOST=https://clob.polymarket.com
POLYMARKET_PRIVATE_KEY=
POLYMARKET_FUNDER=
POLYMARKET_SIGNATURE_TYPE=1
```

What it does today:

- evaluates selected live markets on a loop
- appends dry-run decisions with one-fill-per-window guards
- refreshes active short-horizon markets on cadence
- tracks open positions, realized PnL, unrealized PnL, cycle count, and loop health
- auto-settles expired windows from the observed external close when available
- uses fee-aware maker/taker simulation when paper execution is enabled

Truthful limitation:

- this is a paper monitoring loop, not a full live execution simulator

### Live execution scaffold

This exists for future opt-in live routing, but remains disabled by default.

```bash
LIVE_EXECUTION_ENABLED=false
POLYMARKET_CLOB_HOST=https://clob.polymarket.com
POLYMARKET_PRIVATE_KEY=
POLYMARKET_FUNDER=
POLYMARKET_SIGNATURE_TYPE=1
POLYMARKET_CHAIN_ID=137
```

If you do not intend to route real orders, leave `LIVE_EXECUTION_ENABLED=false`.

## Local Historical Datasets

The repo supports local 1-minute CSV datasets through the external provider layer.

Expected columns:

- `timestamp`, `datetime`, `ts`, or `date`
- `open`
- `high`
- `low`
- `close`
- `volume`

Default dataset paths:

- `data/datasets/BTCUSD-1m-104wks-data.csv`
- `data/datasets/ETHUSD-1m-104wks-data.csv`
- `data/datasets/SOLUSD-1m-104wks-data.csv`

Example config:

```bash
EXTERNAL_HISTORICAL_PROVIDER=csv
USE_MOCK_EXTERNAL_PROVIDER=false
CSV_BTC_PATH=data/datasets/BTCUSD-1m-104wks-data.csv
CSV_ETH_PATH=data/datasets/ETHUSD-1m-104wks-data.csv
CSV_SOL_PATH=data/datasets/SOLUSD-1m-104wks-data.csv
EXTERNAL_PROVIDER_SYMBOL_MAP={"BTC":"BTCUSDT","ETH":"ETHUSDT","SOL":"SOLUSDT"}
```

Startup validation reports include:

- row count
- first timestamp
- last timestamp
- duplicate count
- schema issues

## Main Workflows

### 1. Closed-market evaluation

This is the current closed-market research flow for BTC 5m / 15m.

- load local CSV history
- pull recent Hyperliquid enrichment when available
- evaluate closed BTC 5m / 15m Polymarket markets
- compare bars-only versus bars + enrichment
- compare midpoint versus taker/maker/executable EV assumptions
- inspect decision replay points for any single market

Open:

- [http://localhost:3000/backtests?asset=BTC&timeframe=all&limit=24](http://localhost:3000/backtests?asset=BTC&timeframe=all&limit=24)
- [http://localhost:8000/api/v1/evaluations/results](http://localhost:8000/api/v1/evaluations/results)
- [http://localhost:8000/api/v1/evaluations/closed-markets?asset=BTC&timeframe=crypto_5m&limit=10](http://localhost:8000/api/v1/evaluations/closed-markets?asset=BTC&timeframe=crypto_5m&limit=10)

### 2. Minute research layer

This is the Layer 1 research workflow.

- minute-aligned BTC rows
- 5m / 15m labels
- point-in-time features
- momentum / mean reversion / breakout / regime filters
- synthetic discovery plus real validation
- use it as a hypothesis generator only, not as the final live-edge claim

Open:

- [http://localhost:3000/research/btc-updown](http://localhost:3000/research/btc-updown)
- [http://localhost:8000/api/v1/research/minute/rows](http://localhost:8000/api/v1/research/minute/rows)
- [http://localhost:8000/api/v1/research/minute/results](http://localhost:8000/api/v1/research/minute/results)

### 3. Real Polymarket observation

This is for watching live market behavior.

Open:

- [http://localhost:3000](http://localhost:3000)
- [http://localhost:8000/api/v1/system/health](http://localhost:8000/api/v1/system/health)
- [http://localhost:8000/api/v1/markets](http://localhost:8000/api/v1/markets)

## Health And Verification

Typical checks:

```bash
curl http://localhost:8000/healthz
curl http://localhost:8000/api/v1/system/health
curl http://localhost:8000/api/v1/external-provider
curl http://localhost:8000/api/v1/markets
curl "http://localhost:8000/api/v1/evaluations/closed-markets?asset=BTC&timeframe=crypto_5m&limit=10"
```

Expected signals:

- mock mode: dashboard shows `mock venue`
- real observation mode: dashboard shows `real venue`, websocket status, and reconnect count
- CSV backtest mode: `/api/v1/external-provider` includes dataset validation details
- paper mode: `/api/v1/paper-trading/status` shows loop health and dry-run state

## API Surface

The most useful endpoints are:

- `GET /api/v1/markets`
- `GET /api/v1/markets/{market_id}`
- `GET /api/v1/markets/{market_id}/orderbook`
- `GET /api/v1/markets/{market_id}/trades`
- `GET /api/v1/markets/{market_id}/features`
- `GET /api/v1/markets/{market_id}/live-feature-view`
- `GET /api/v1/markets/{market_id}/decision-replay`
- `GET /api/v1/replay/{market_id}`
- `GET /api/v1/external-provider`
- `GET /api/v1/evaluations/closed-markets`
- `POST /api/v1/evaluations/closed-markets/run`
- `GET /api/v1/evaluations/results`
- `POST /api/v1/evaluations/compare`
- `POST /api/v1/evaluations/ev-first/run`
- `POST /api/v1/evaluations/flow-alignment/run`
- `GET /api/v1/research/minute/rows`
- `GET /api/v1/research/minute/strategies`
- `POST /api/v1/research/minute/build`
- `POST /api/v1/research/minute/run`
- `GET /api/v1/research/minute/results`
- `POST /api/v1/research/validation/run`
- `GET /api/v1/research/validation/results`
- `GET /api/v1/paper-trading/status`
- `GET /api/v1/paper-trading/blotter`
- `POST /api/v1/paper-trading/start`
- `POST /api/v1/paper-trading/stop`
- `POST /api/v1/paper-trading/cycle`
- `GET /api/v1/execution/status`
- `GET /api/v1/execution/orders`
- `GET /api/v1/execution/fills`
- `GET /api/v1/dashboard/summary`

## How To Read The Dashboard

The home page is the quickest way to inspect the system:

- top banner shows mock vs real Polymarket mode
- live status shows websocket health and event counts
- research edge board shows bars-only versus enrichment performance
- rolling edge chart shows whether edge is trending up or down
- paper/execution cards separate dry-run paper behavior from the execution scaffold
- BTC quick-launch cards open the two market families we care about most

## Troubleshooting

### Web UI is blank

- check `NEXT_PUBLIC_API_BASE_URL`
- confirm the API container is up
- open [http://localhost:8000/docs](http://localhost:8000/docs)

### No markets show up

- check `USE_MOCK_POLYMARKET` and `USE_MOCK_POLYMARKET_CLIENT`
- check `POST /api/v1/ingestion/bootstrap`
- check `GET /api/v1/system/health`

### CSV backtest returns nothing

- verify `EXTERNAL_HISTORICAL_PROVIDER=csv`
- verify `USE_MOCK_EXTERNAL_PROVIDER=false`
- verify the dataset paths exist
- verify the CSV has the required columns

### Real observation mode looks stale

- check the websocket badge on the dashboard
- check `last_event_at`, `dropped_event_count`, and `duplicate_event_count` in system health
- restart the API container if the stream is stuck

### Paper loop is not running

- verify `PAPER_TRADING_LOOP_ENABLED=true`
- call `POST /api/v1/paper-trading/start`
- check `GET /api/v1/paper-trading/status`

### Live execution is not routing orders

- this is expected unless `LIVE_EXECUTION_ENABLED=true`
- even then, keep it disabled until you intentionally want to test live routing with real credentials

## Truthful Current Status

- Real Polymarket observation mode is usable for monitoring.
- Closed-market evaluation is usable for baseline research on local CSV datasets plus recent Hyperliquid enrichment where available.
- EV-first closed-market evaluation is available with maker/taker simulation, replayable decision points, and dynamic fee handling.
- Minute-based BTC research is cached and viewable in the UI.
- Live paper mode is partial but useful for dry-run monitoring.
- Live execution is scaffolded through the official Polymarket CLOB client but remains disabled by default.
- This repo still does **not** claim a full historical Polymarket trade replay engine for every venue nuance, so use the EV-first reports as research rather than a guarantee.

## Useful Scripts

- `./scripts/dev-up.sh`
- `./scripts/dev-down.sh`
- `./scripts/check-health.sh`
- `./scripts/run-csv-backtest.sh`
- `./scripts/run-real-observation.sh`
- `python scripts/download_hyperliquid_btc_ticks.py --start 2025-03-22 --end 2026-04-01 --out data/hyperliquid/btc_ticks.csv`

PowerShell:

- `./scripts/dev-up.ps1`
- `./scripts/dev-down.ps1`
- `./scripts/check-health.ps1`
- `./scripts/run-csv-backtest.ps1`
- `./scripts/run-real-observation.ps1`

### Hyperliquid BTC tick export

This downloader pulls market-wide BTC ticks from Hyperliquid's public S3 archive and writes them to CSV.

Install the extra Python packages first:

```bash
python -m pip install boto3 lz4
```

Then run:

```bash
python scripts/download_hyperliquid_btc_ticks.py --start 2025-03-22 --end 2026-04-01 --out data/hyperliquid/btc_ticks.csv
```

Useful flags:

- `--source auto` spans the known `node_trades`, `node_fills`, and `node_fills_by_block` windows
- `--coin BTC` keeps BTC rows only
- `--max-keys 5` is handy for a smoke test before downloading a full range
