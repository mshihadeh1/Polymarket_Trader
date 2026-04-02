from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@postgres:5432/polymarket_trader",
        alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://redis:6379/0", alias="REDIS_URL")
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    use_mock_polymarket: bool = Field(default=True, alias="USE_MOCK_POLYMARKET")
    use_mock_polymarket_client: bool = Field(default=True, alias="USE_MOCK_POLYMARKET_CLIENT")
    live_execution_enabled: bool = Field(default=False, alias="LIVE_EXECUTION_ENABLED")
    feature_trade_windows: str = Field(default="5,15,30", alias="FEATURE_TRADE_WINDOWS")
    max_market_exposure_usd: float = Field(default=500.0, alias="MAX_MARKET_EXPOSURE_USD")
    default_underlyings: str = Field(default="BTC,ETH,SOL", alias="DEFAULT_UNDERLYINGS")
    enable_db_persistence: bool = Field(default=False, alias="ENABLE_DB_PERSISTENCE")
    sqlite_fallback_path: str = Field(default="data/polymarket_trader.db", alias="SQLITE_FALLBACK_PATH")
    external_historical_provider: str = Field(default="binance", alias="EXTERNAL_HISTORICAL_PROVIDER")
    use_mock_external_provider: bool = Field(default=True, alias="USE_MOCK_EXTERNAL_PROVIDER")
    binance_base_url: str = Field(default="https://api.binance.com", alias="BINANCE_BASE_URL")
    csv_btc_path: str = Field(default="data/datasets/BTCUSD-1m-104wks-data.csv", alias="CSV_BTC_PATH")
    csv_eth_path: str = Field(default="data/datasets/ETHUSD-1m-104wks-data.csv", alias="CSV_ETH_PATH")
    csv_sol_path: str = Field(default="data/datasets/SOLUSD-1m-104wks-data.csv", alias="CSV_SOL_PATH")
    csv_provider_paths: str = Field(
        default='{"BTC":"data/datasets/BTCUSD-1m-104wks-data.csv","ETH":"data/datasets/ETHUSD-1m-104wks-data.csv","SOL":"data/datasets/SOLUSD-1m-104wks-data.csv"}',
        alias="CSV_PROVIDER_PATHS",
    )
    hyperliquid_info_url: str = Field(default="https://api.hyperliquid.xyz/info", alias="HYPERLIQUID_INFO_URL")
    use_mock_hyperliquid_recent: bool = Field(default=True, alias="USE_MOCK_HYPERLIQUID_RECENT")
    hyperliquid_recent_trade_limit: int = Field(default=500, alias="HYPERLIQUID_RECENT_TRADE_LIMIT")
    hyperliquid_recent_lookback_minutes: int = Field(default=240, alias="HYPERLIQUID_RECENT_LOOKBACK_MINUTES")
    polymarket_api_base_url: str = Field(default="https://gamma-api.polymarket.com", alias="POLYMARKET_API_BASE_URL")
    polymarket_ws_url: str = Field(default="wss://ws-subscriptions-clob.polymarket.com/ws/market", alias="POLYMARKET_WS_URL")
    external_provider_symbol_map: str = Field(
        default='{"BTC":"BTCUSDT","ETH":"ETHUSDT","SOL":"SOLUSDT"}',
        alias="EXTERNAL_PROVIDER_SYMBOL_MAP",
    )
    backtest_fee_bps: float = Field(default=7.0, alias="BACKTEST_FEE_BPS")
    backtest_slippage_bps: float = Field(default=5.0, alias="BACKTEST_SLIPPAGE_BPS")
    backtest_position_size: float = Field(default=100.0, alias="BACKTEST_POSITION_SIZE")
    paper_trading_loop_enabled: bool = Field(default=False, alias="PAPER_TRADING_LOOP_ENABLED")
    paper_trading_loop_seconds: int = Field(default=30, alias="PAPER_TRADING_LOOP_SECONDS")
    paper_trading_underlyings: str = Field(default="BTC", alias="PAPER_TRADING_UNDERLYINGS")
    paper_trading_market_types: str = Field(default="crypto_5m,crypto_15m", alias="PAPER_TRADING_MARKET_TYPES")
    paper_trading_strategy: str = Field(default="combined_cvd_gap", alias="PAPER_TRADING_STRATEGY")
    mock_startup_demo_enabled: bool = Field(default=False, alias="MOCK_STARTUP_DEMO_ENABLED")


@lru_cache
def get_settings() -> Settings:
    return Settings()
