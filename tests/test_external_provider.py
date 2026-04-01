from datetime import datetime, timezone
from pathlib import Path

from packages.clients.market_data_provider.binance import BinanceHistoricalProvider
from packages.clients.market_data_provider.csv import CsvHistoricalProvider
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


def test_csv_provider_normalizes_local_ohlcv() -> None:
    tmp_path = Path("C:/Users/Mahdi/Documents/Polymarket_Trader/data/test_tmp")
    tmp_path.mkdir(parents=True, exist_ok=True)
    csv_path = tmp_path / "btc_1m.csv"
    try:
        csv_path.write_text(
            "ts,open,high,low,close,volume\n"
            "2026-03-31T11:58:00Z,84000,84020,83980,84010,12.5\n"
            "2026-03-31T11:59:00Z,84010,84030,84000,84025,10.0\n",
            encoding="utf-8",
        )
        provider = CsvHistoricalProvider(
            path_map={"BTC": str(csv_path)},
            symbol_map={"BTC": "BTCUSD_LOCAL"},
            root=tmp_path,
        )
        raw_rows, bars = provider.get_ohlcv(
            "BTC",
            datetime(2026, 3, 31, 11, 58, 0, tzinfo=timezone.utc),
            datetime(2026, 3, 31, 11, 59, 0, tzinfo=timezone.utc),
            "1m",
        )
        assert len(raw_rows) == 2
        assert bars[0].provider == "csv"
        assert bars[0].symbol == "BTC"
        assert bars[1].close == 84025.0
    finally:
        csv_path.unlink(missing_ok=True)


def test_provider_factory_selects_csv() -> None:
    tmp_path = Path("C:/Users/Mahdi/Documents/Polymarket_Trader/data/test_tmp")
    tmp_path.mkdir(parents=True, exist_ok=True)
    csv_path = tmp_path / "btc_factory_1m.csv"
    try:
        csv_path.write_text(
            "ts,open,high,low,close,volume\n2026-03-31T11:58:00Z,1,2,1,2,3\n",
            encoding="utf-8",
        )
        settings = Settings(
            EXTERNAL_HISTORICAL_PROVIDER="csv",
            CSV_PROVIDER_PATHS=f'{{"BTC":"{csv_path.as_posix()}"}}',
        )
        provider = build_provider_from_name("csv", settings=settings, root=tmp_path)
        assert provider.provider_name == "csv"
        assert provider.capabilities().has_ohlcv is True
    finally:
        csv_path.unlink(missing_ok=True)


def test_csv_provider_validation_reports_duplicates_and_schema_issues() -> None:
    tmp_path = Path("C:/Users/Mahdi/Documents/Polymarket_Trader/data/test_tmp")
    tmp_path.mkdir(parents=True, exist_ok=True)
    dup_path = tmp_path / "btc_duplicates.csv"
    bad_path = tmp_path / "eth_bad.csv"
    try:
        dup_path.write_text(
            "datetime,open,high,low,close,volume\n"
            "2026-03-31 11:58:00,1,2,1,2,3\n"
            "2026-03-31 11:58:00,1,2,1,2,4\n",
            encoding="utf-8",
        )
        bad_path.write_text(
            "datetime,open,high,close\n2026-03-31 11:58:00,1,2,2\n",
            encoding="utf-8",
        )
        provider = CsvHistoricalProvider(
            path_map={"BTC": str(dup_path), "ETH": str(bad_path)},
            symbol_map={"BTC": "BTC", "ETH": "ETH"},
            root=tmp_path,
        )
        reports = {report.symbol: report for report in provider.validate_datasets()}
        assert reports["BTC"].duplicate_count == 1
        assert reports["BTC"].row_count == 2
        assert reports["ETH"].schema_issues
    finally:
        dup_path.unlink(missing_ok=True)
        bad_path.unlink(missing_ok=True)
