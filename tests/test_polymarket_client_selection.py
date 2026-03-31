from pathlib import Path

from packages.config import Settings
from polymarket_trader.bootstrap import build_polymarket_client


def test_bootstrap_uses_mock_polymarket_client_when_enabled() -> None:
    client = build_polymarket_client(
        Settings(use_mock_polymarket_client=True),
        root=Path("C:/Users/Mahdi/Documents/Polymarket_Trader"),
    )
    assert client.is_mock is True


def test_bootstrap_uses_real_polymarket_client_when_mock_disabled() -> None:
    client = build_polymarket_client(
        Settings(use_mock_polymarket=False, use_mock_polymarket_client=False),
        root=Path("C:/Users/Mahdi/Documents/Polymarket_Trader"),
    )
    assert client.is_mock is False
