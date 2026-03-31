# Architecture Notes

## Research-first flow

1. `services/polymarket_ingestor` loads market metadata, order books, trades, and raw events.
2. `packages/clients/market_data_provider` defines the provider-pluggable historical market data interface and Binance-first implementation.
3. `services/hyperliquid_ingestor` currently acts as the external market data ingestor and loads normalized external bars, order books, trades, and raw payloads aligned by Polymarket market id.
4. `services/feature_engine/market_window.py` maps a Polymarket market to its external open/current context.
5. `services/feature_engine/service.py` computes point-in-time local and external CVD-based feature snapshots.
6. `services/backtester/strategies.py` provides swappable Polymarket-only, external-only, combined, passive, and no-trade baseline strategies.
7. `services/backtester/service.py` consumes feature snapshots and strategy callbacks to produce comparable baseline reports.
8. `services/paper_trader` and `services/execution_engine` keep live-routing pathways disabled by default.

## Current storage model

- SQL schema in `infrastructure/migrations/001_init.sql` defines the production-oriented Timescale/Postgres tables.
- Runtime services currently use in-memory repositories backed by seed data for a testable vertical slice.
- `packages/db/repository.py` adds an optional local SQLAlchemy persistence cache for feature snapshots, backtest reports, and paper decisions.
- External providers store both raw vendor payloads and normalized internal records in memory today, so feature and replay code never touches Binance-specific payload formats directly.
- This keeps uncertain external integrations behind adapters while preserving the eventual database contract.

## Venue separation

- Polymarket-local microstructure is stored and queried separately from Hyperliquid microstructure.
- Cross-venue context is assembled only in the feature/window layer so research can compare:
  - Polymarket-only
  - Hyperliquid-only
  - combined features

## Known next steps

- Persist ingested events into PostgreSQL/Timescale tables rather than only in-memory state.
- Expand replay into a full event-store reader and deterministic state reconstructor.
- Replace the baseline backtester placeholder cost model with queue, latency, and fill uncertainty simulation.
- Add explicit strategy classes and comparison runners for Model A, Model B, and Model C.
- Add API-triggered ingestion workers rather than only bootstrap-style seed hydration.
