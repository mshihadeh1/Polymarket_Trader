CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS markets (
    id UUID PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    market_type TEXT NOT NULL,
    resolution_source TEXT,
    rules_text TEXT,
    status TEXT NOT NULL,
    opens_at TIMESTAMPTZ,
    closes_at TIMESTAMPTZ,
    resolves_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tokens (
    id UUID PRIMARY KEY,
    market_id UUID NOT NULL REFERENCES markets(id) ON DELETE CASCADE,
    token_id TEXT NOT NULL,
    outcome TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS market_tags (
    market_id UUID NOT NULL REFERENCES markets(id) ON DELETE CASCADE,
    tag TEXT NOT NULL,
    PRIMARY KEY (market_id, tag)
);

CREATE TABLE IF NOT EXISTS orderbook_snapshots (
    id UUID PRIMARY KEY,
    market_id UUID NOT NULL REFERENCES markets(id) ON DELETE CASCADE,
    ts TIMESTAMPTZ NOT NULL,
    best_bid DOUBLE PRECISION NOT NULL,
    best_ask DOUBLE PRECISION NOT NULL,
    bid_size DOUBLE PRECISION NOT NULL,
    ask_size DOUBLE PRECISION NOT NULL,
    depth_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS trades (
    id UUID PRIMARY KEY,
    market_id UUID NOT NULL REFERENCES markets(id) ON DELETE CASCADE,
    ts TIMESTAMPTZ NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    size DOUBLE PRECISION NOT NULL,
    side TEXT NOT NULL,
    aggressor_side TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS external_reference_prices (
    id UUID PRIMARY KEY,
    symbol TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    source TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS strategy_runs (
    id UUID PRIMARY KEY,
    strategy_name TEXT NOT NULL,
    market_type TEXT NOT NULL,
    config_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fills (
    id UUID PRIMARY KEY,
    strategy_run_id UUID REFERENCES strategy_runs(id) ON DELETE SET NULL,
    market_id UUID NOT NULL REFERENCES markets(id) ON DELETE CASCADE,
    ts TIMESTAMPTZ NOT NULL,
    side TEXT NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    size DOUBLE PRECISION NOT NULL,
    fee DOUBLE PRECISION NOT NULL DEFAULT 0,
    is_hypothetical BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pnl_timeseries (
    id UUID PRIMARY KEY,
    strategy_run_id UUID NOT NULL REFERENCES strategy_runs(id) ON DELETE CASCADE,
    ts TIMESTAMPTZ NOT NULL,
    gross_pnl DOUBLE PRECISION NOT NULL,
    net_pnl DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

SELECT create_hypertable('orderbook_snapshots', 'ts', if_not_exists => TRUE);
SELECT create_hypertable('trades', 'ts', if_not_exists => TRUE);
SELECT create_hypertable('external_reference_prices', 'ts', if_not_exists => TRUE);
SELECT create_hypertable('pnl_timeseries', 'ts', if_not_exists => TRUE);
