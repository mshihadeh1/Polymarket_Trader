from datetime import datetime, timezone
from pathlib import Path

from packages.clients.hyperliquid_client.real_client import RealHyperliquidClient
from packages.clients.market_data_provider.csv import CsvHistoricalProvider
from services.hyperliquid_ingestor import HyperliquidIngestorService
from services.state import InMemoryState


class _MockResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _MockHttpClient:
    def __init__(self):
        self.calls = []

    def post(self, url, json=None):
        self.calls.append((url, json))
        request_type = json["type"]
        if request_type == "recentTrades":
            return _MockResponse([
                {"time": 1774958285000, "px": "84500", "sz": "0.2", "side": "buy"},
                {"time": 1774958345000, "px": "84510", "sz": "0.3", "side": "sell"},
            ])
        if request_type == "candleSnapshot":
            return _MockResponse([
                {"t": 1774958280000, "o": "84495", "h": "84505", "l": "84490", "c": "84500", "v": "10"}
            ])
        if request_type == "l2Book":
            return _MockResponse({"time": 1774958345000, "levels": [[{"px": "84509", "sz": "1.2"}], [{"px": "84511", "sz": "1.1"}]]})
        raise AssertionError(f"unexpected request type {request_type}")

    def close(self):
        return None


def test_hyperliquid_recent_client_normalizes_trades_and_books() -> None:
    client = RealHyperliquidClient(
        info_url="https://api.hyperliquid.xyz/info",
        client=_MockHttpClient(),
    )
    start = datetime(2026, 3, 31, 11, 58, 0, tzinfo=timezone.utc)
    end = datetime(2026, 3, 31, 12, 0, 0, tzinfo=timezone.utc)
    _, trades, _ = client.fetch_recent_trades("BTC", start=start, end=end)
    _, book, _ = client.fetch_l2_book("BTC")
    assert len(trades) == 2
    assert trades[0].venue == "hyperliquid"
    assert book is not None and book.best_bid == 84509.0


def test_hyperliquid_enrichment_availability_skips_orderbook_when_not_point_in_time() -> None:
    tmp_path = Path("C:/Users/Mahdi/Documents/Polymarket_Trader/data/test_tmp")
    tmp_path.mkdir(parents=True, exist_ok=True)
    csv_path = tmp_path / "btc_eval.csv"
    try:
        csv_path.write_text(
            "datetime,open,high,low,close,volume\n"
            "2026-03-31 11:58:00,84495,84505,84490,84500,10\n",
            encoding="utf-8",
        )
        provider = CsvHistoricalProvider(
            path_map={"BTC": str(csv_path)},
            symbol_map={"BTC": "BTC"},
            root=tmp_path,
        )
        service = HyperliquidIngestorService(
            state=InMemoryState(),
            provider=provider,
            recent_client=RealHyperliquidClient(info_url="https://api.hyperliquid.xyz/info", client=_MockHttpClient()),
        )
        assembled = service.assemble_window(
            "BTC",
            start=datetime(2026, 3, 31, 11, 58, 0, tzinfo=timezone.utc),
            end=datetime(2026, 3, 31, 12, 0, 0, tzinfo=timezone.utc),
            include_recent_enrichment=True,
            include_current_orderbook=False,
        )
        assert assembled["availability"].bars_available is True
        assert assembled["availability"].trades_available is True
        assert assembled["availability"].orderbook_available is False
        assert any("avoid lookahead" in note for note in assembled["availability"].notes)
    finally:
        csv_path.unlink(missing_ok=True)
