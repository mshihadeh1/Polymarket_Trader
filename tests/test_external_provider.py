from datetime import datetime, timezone
from pathlib import Path

from packages.clients.market_data_provider.binance import BinanceHistoricalProvider
from packages.clients.market_data_provider.factory import build_provider_from_name
from packages.config import Settings


def test_binance_provider_maps_internal_symbol_without_leaking_vendor_format() -> None:
    provider = BinanceHistoricalProvider(
        base_url="https://api.binance.com",
        symbol_map={"BTC": "BTCUSDT"},
        use_mock=True,
        seed_path=Path("C:/Users/Mahdi/Documents/Polymarket_Trader/data/seed/binance_historical.json"),
    )
    mapping = provider.map_symbol("BTC")
    assert mapping.internal_symbol == "BTC"
    assert mapping.provider_symbol == "BTCUSDT"
    assert mapping.provider_name == "binance"


def test_binance_provider_returns_normalized_records_and_raw_payloads() -> None:
    provider = BinanceHistoricalProvider(
        base_url="https://api.binance.com",
        symbol_map={"BTC": "BTCUSDT"},
        use_mock=True,
        seed_path=Path("C:/Users/Mahdi/Documents/Polymarket_Trader/data/seed/binance_historical.json"),
    )
    start = datetime(2026, 3, 31, 11, 58, 0, tzinfo=timezone.utc)
    end = datetime(2026, 3, 31, 12, 0, 0, tzinfo=timezone.utc)
    raw_bars, bars = provider.get_ohlcv("BTC", start, end, "1m")
    raw_trades, trades = provider.get_trades("BTC", start, end)
    raw_books, books = provider.get_orderbook_snapshots("BTC", start, end)
    assert raw_bars
    assert raw_trades
    assert raw_books
    assert bars[0].provider == "binance"
    assert trades[0].venue == "binance"
    assert books[0].venue == "binance"


def test_provider_capabilities_use_requested_flag_names() -> None:
    provider = BinanceHistoricalProvider(
        base_url="https://api.binance.com",
        symbol_map={"BTC": "BTCUSDT"},
        use_mock=True,
        seed_path=Path("C:/Users/Mahdi/Documents/Polymarket_Trader/data/seed/binance_historical.json"),
    )
    capabilities = provider.capabilities()
    assert capabilities.has_ohlcv is True
    assert capabilities.has_trades is True
    assert capabilities.has_l2 is False
    assert capabilities.has_snapshots is True


def test_provider_factory_selects_binance() -> None:
    provider = build_provider_from_name(
        "binance",
        settings=Settings(),
        root=Path("C:/Users/Mahdi/Documents/Polymarket_Trader"),
    )
    assert provider.provider_name == "binance"
