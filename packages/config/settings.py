from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

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
    live_execution_enabled: bool = Field(default=False, alias="LIVE_EXECUTION_ENABLED")
    feature_trade_windows: str = Field(default="5,15,30", alias="FEATURE_TRADE_WINDOWS")
    max_market_exposure_usd: float = Field(default=500.0, alias="MAX_MARKET_EXPOSURE_USD")
    default_underlyings: str = Field(default="BTC,ETH", alias="DEFAULT_UNDERLYINGS")
    enable_db_persistence: bool = Field(default=False, alias="ENABLE_DB_PERSISTENCE")
    sqlite_fallback_path: str = Field(default="data/polymarket_trader.db", alias="SQLITE_FALLBACK_PATH")
    external_historical_provider: str = Field(default="binance", alias="EXTERNAL_HISTORICAL_PROVIDER")
    use_mock_external_provider: bool = Field(default=True, alias="USE_MOCK_EXTERNAL_PROVIDER")
    binance_base_url: str = Field(default="https://api.binance.com", alias="BINANCE_BASE_URL")
    external_provider_symbol_map: str = Field(
        default='{"BTC":"BTCUSDT","ETH":"ETHUSDT"}',
        alias="EXTERNAL_PROVIDER_SYMBOL_MAP",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
