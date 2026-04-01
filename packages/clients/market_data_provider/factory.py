from __future__ import annotations

import json
from pathlib import Path

from packages.clients.market_data_provider.base import HistoricalMarketDataProvider
from packages.clients.market_data_provider.binance import BinanceHistoricalProvider
from packages.clients.market_data_provider.csv import CsvHistoricalProvider
from packages.clients.market_data_provider.dataset import CustomDatasetHistoricalProvider
from packages.clients.market_data_provider.parquet import ParquetHistoricalProvider
from packages.clients.market_data_provider.tardis import TardisHistoricalProvider
from packages.config import Settings


def build_historical_market_data_provider(settings: Settings, root: Path) -> HistoricalMarketDataProvider:
    return build_provider_from_name(settings.external_historical_provider, settings=settings, root=root)


def build_provider_from_name(provider_name: str, settings: Settings, root: Path) -> HistoricalMarketDataProvider:
    symbol_map = json.loads(settings.external_provider_symbol_map)
    csv_paths = json.loads(settings.csv_provider_paths)
    csv_paths.update(
        {
            "BTC": settings.csv_btc_path,
            "ETH": settings.csv_eth_path,
            "SOL": settings.csv_sol_path,
        }
    )
    normalized = provider_name.lower()
    if normalized == "binance":
        return BinanceHistoricalProvider(
            base_url=settings.binance_base_url,
            symbol_map=symbol_map,
            use_mock=settings.use_mock_external_provider,
            seed_path=root / "data" / "seed" / "binance_historical.json",
        )
    if normalized == "csv":
        return CsvHistoricalProvider(path_map=csv_paths, symbol_map=symbol_map, root=root)
    if normalized == "tardis":
        return TardisHistoricalProvider()
    if normalized == "parquet":
        return ParquetHistoricalProvider()
    if normalized in {"custom", "custom_dataset"}:
        return CustomDatasetHistoricalProvider()
    raise ValueError(f"Unsupported external historical provider: {provider_name}")
