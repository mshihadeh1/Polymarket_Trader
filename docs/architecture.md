# Architecture Notes

## Research-first flow

1. `services/polymarket_ingestor` loads market metadata, order books, trades, and raw events.
2. `services/hyperliquid_ingestor` loads external order books, trades, and raw events aligned by Polymarket market id.
3. `services/feature_engine/market_window.py` maps a Polymarket market to its external open/current context.
4. `services/feature_engine/service.py` computes point-in-time local and external CVD-based feature snapshots.
5. `services/backtester/service.py` consumes feature snapshots and replayable state to produce comparable baseline reports.
6. `services/paper_trader` and `services/execution_engine` keep live-routing pathways disabled by default.

## Current storage model

- SQL schema in `infrastructure/migrations/001_init.sql` defines the production-oriented Timescale/Postgres tables.
- Runtime services currently use in-memory repositories backed by seed data for a testable vertical slice.
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
