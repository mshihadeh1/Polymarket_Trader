# TODO

## Live routing

- Implement authenticated Polymarket order adapter behind `execution_engine`
- Add signed request flow and nonce management
- Add cancel/replace and idempotent order tracking
- Add venue-specific fee schedule support

## Research platform

- Add feature engine for crypto and weather market families
- Add fair value baseline model training and calibration pipeline
- Add event-driven backtester with queue position and latency models
- Add experiment comparison page and saved strategy runs

## Weather expansion

- Build rules parser with exact-source normalization
- Add station metadata and forecast feed adapters
- Implement forecast distribution ingestion and feature extraction

## Ops

- Add alembic or migrator runner container
- Add CI for API tests and frontend linting
- Add auth and role-based controls for production deployment
