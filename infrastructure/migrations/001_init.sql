CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS events (
    id UUID PRIMARY KEY,
    event_slug TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    starts_at TIMESTAMPTZ,
    ends_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS markets (
    id UUID PRIMARY KEY,
    event_id UUID REFERENCES events(id) ON DELETE SET NULL,
    slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    market_type TEXT NOT NULL,
    underlying TEXT,
    status TEXT NOT NULL,
    opens_at TIMESTAMPTZ,
    closes_at TIMESTAMPTZ,
    resolves_at TIMESTAMPTZ,
    price_to_beat DOUBLE PRECISION,
    open_reference_price DOUBLE PRECISION,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS market_tokens (
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

CREATE TABLE IF NOT EXISTS market_rules (
    id UUID PRIMARY KEY,
    market_id UUID NOT NULL REFERENCES markets(id) ON DELETE CASCADE,
    rule_type TEXT NOT NULL,
    source TEXT,
    rule_text TEXT NOT NULL,
    normalized_rule JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS polymarket_raw_events (
    id UUID PRIMARY KEY,
    market_id UUID NOT NULL REFERENCES markets(id) ON DELETE CASCADE,
    ts TIMESTAMPTZ NOT NULL,
    sequence BIGINT,
    channel TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS polymarket_orderbook_updates (
    id UUID PRIMARY KEY,
    market_id UUID NOT NULL REFERENCES markets(id) ON DELETE CASCADE,
    ts TIMESTAMPTZ NOT NULL,
    sequence BIGINT,
    best_bid DOUBLE PRECISION NOT NULL,
    best_ask DOUBLE PRECISION NOT NULL,
    bid_size DOUBLE PRECISION NOT NULL,
    ask_size DOUBLE PRECISION NOT NULL,
    depth_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS polymarket_orderbook_snapshots (
    id UUID PRIMARY KEY,
    market_id UUID NOT NULL REFERENCES markets(id) ON DELETE CASCADE,
    ts TIMESTAMPTZ NOT NULL,
    sequence BIGINT,
    best_bid DOUBLE PRECISION NOT NULL,
    best_ask DOUBLE PRECISION NOT NULL,
    bid_size DOUBLE PRECISION NOT NULL,
    ask_size DOUBLE PRECISION NOT NULL,
    depth_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS polymarket_trades (
    id UUID PRIMARY KEY,
    market_id UUID NOT NULL REFERENCES markets(id) ON DELETE CASCADE,
    ts TIMESTAMPTZ NOT NULL,
    sequence BIGINT,
    price DOUBLE PRECISION NOT NULL,
    size DOUBLE PRECISION NOT NULL,
    side TEXT NOT NULL,
    aggressor_side TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS polymarket_price_history (
    id UUID PRIMARY KEY,
    market_id UUID NOT NULL REFERENCES markets(id) ON DELETE CASCADE,
    ts TIMESTAMPTZ NOT NULL,
    implied_probability DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS hyperliquid_raw_events (
    id UUID PRIMARY KEY,
    market_id UUID NOT NULL REFERENCES markets(id) ON DELETE CASCADE,
    ts TIMESTAMPTZ NOT NULL,
    sequence BIGINT,
    channel TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS hyperliquid_orderbook_updates (
    id UUID PRIMARY KEY,
    market_id UUID NOT NULL REFERENCES markets(id) ON DELETE CASCADE,
    ts TIMESTAMPTZ NOT NULL,
    sequence BIGINT,
    best_bid DOUBLE PRECISION NOT NULL,
    best_ask DOUBLE PRECISION NOT NULL,
    bid_size DOUBLE PRECISION NOT NULL,
    ask_size DOUBLE PRECISION NOT NULL,
    depth_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS hyperliquid_orderbook_snapshots (
    id UUID PRIMARY KEY,
    market_id UUID NOT NULL REFERENCES markets(id) ON DELETE CASCADE,
    ts TIMESTAMPTZ NOT NULL,
    sequence BIGINT,
    best_bid DOUBLE PRECISION NOT NULL,
    best_ask DOUBLE PRECISION NOT NULL,
    bid_size DOUBLE PRECISION NOT NULL,
    ask_size DOUBLE PRECISION NOT NULL,
    depth_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS hyperliquid_trades (
    id UUID PRIMARY KEY,
    market_id UUID NOT NULL REFERENCES markets(id) ON DELETE CASCADE,
    ts TIMESTAMPTZ NOT NULL,
    sequence BIGINT,
    price DOUBLE PRECISION NOT NULL,
    size DOUBLE PRECISION NOT NULL,
    side TEXT NOT NULL,
    aggressor_side TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS hyperliquid_price_series (
    id UUID PRIMARY KEY,
    market_id UUID NOT NULL REFERENCES markets(id) ON DELETE CASCADE,
    ts TIMESTAMPTZ NOT NULL,
    best_bid DOUBLE PRECISION NOT NULL,
    best_ask DOUBLE PRECISION NOT NULL,
    mid_price DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS feature_snapshots (
    id UUID PRIMARY KEY,
    market_id UUID NOT NULL REFERENCES markets(id) ON DELETE CASCADE,
    ts TIMESTAMPTZ NOT NULL,
    feature_payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS strategy_runs (
    id UUID PRIMARY KEY,
    strategy_name TEXT NOT NULL,
    market_id UUID NOT NULL REFERENCES markets(id) ON DELETE CASCADE,
    run_config JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS simulated_fills (
    id UUID PRIMARY KEY,
    strategy_run_id UUID REFERENCES strategy_runs(id) ON DELETE SET NULL,
    market_id UUID NOT NULL REFERENCES markets(id) ON DELETE CASCADE,
    ts TIMESTAMPTZ NOT NULL,
    side TEXT NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    size DOUBLE PRECISION NOT NULL,
    fee DOUBLE PRECISION NOT NULL DEFAULT 0,
    is_paper BOOLEAN NOT NULL DEFAULT TRUE,
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

SELECT create_hypertable('polymarket_raw_events', 'ts', if_not_exists => TRUE);
SELECT create_hypertable('polymarket_orderbook_updates', 'ts', if_not_exists => TRUE);
SELECT create_hypertable('polymarket_orderbook_snapshots', 'ts', if_not_exists => TRUE);
SELECT create_hypertable('polymarket_trades', 'ts', if_not_exists => TRUE);
SELECT create_hypertable('polymarket_price_history', 'ts', if_not_exists => TRUE);
SELECT create_hypertable('hyperliquid_raw_events', 'ts', if_not_exists => TRUE);
SELECT create_hypertable('hyperliquid_orderbook_updates', 'ts', if_not_exists => TRUE);
SELECT create_hypertable('hyperliquid_orderbook_snapshots', 'ts', if_not_exists => TRUE);
SELECT create_hypertable('hyperliquid_trades', 'ts', if_not_exists => TRUE);
SELECT create_hypertable('hyperliquid_price_series', 'ts', if_not_exists => TRUE);
SELECT create_hypertable('feature_snapshots', 'ts', if_not_exists => TRUE);
SELECT create_hypertable('pnl_timeseries', 'ts', if_not_exists => TRUE);
