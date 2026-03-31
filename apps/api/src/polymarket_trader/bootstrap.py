from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from packages.clients.hyperliquid_client import MockHyperliquidClient
from packages.clients.polymarket_client import MockPolymarketClient
from packages.config import Settings
from services.backtester import BacktesterService
from services.execution_engine import ExecutionEngineService
from services.feature_engine import FeatureEngineService, MarketWindowService
from services.hyperliquid_ingestor import HyperliquidIngestorService
from services.market_catalog import MarketCatalogService
from services.paper_trader import PaperTraderService
from services.polymarket_ingestor import PolymarketIngestorService
from services.rules_engine import RulesEngineService
from services.state import InMemoryState
from polymarket_trader.replay import ReplayService


@dataclass
class Container:
    settings: Settings
    state: InMemoryState
    market_catalog: MarketCatalogService
    polymarket_ingestor: PolymarketIngestorService
    hyperliquid_ingestor: HyperliquidIngestorService
    market_window: MarketWindowService
    feature_engine: FeatureEngineService
    backtester: BacktesterService
    replay: ReplayService
    paper_trader: PaperTraderService
    execution_engine: ExecutionEngineService
    rules_engine: RulesEngineService
    mock_polymarket: MockPolymarketClient
    mock_hyperliquid: MockHyperliquidClient

    def bootstrap_seed_data(self, force_reload: bool = False) -> int:
        if self.state.markets and not force_reload:
            return len(self.state.markets)
        if force_reload:
            self.state.markets.clear()
            self.state.market_details.clear()
            self.state.polymarket_orderbooks.clear()
            self.state.polymarket_trades.clear()
            self.state.hyperliquid_orderbooks.clear()
            self.state.hyperliquid_trades.clear()
            self.state.polymarket_raw_events.clear()
            self.state.hyperliquid_raw_events.clear()
            self.state.feature_snapshots.clear()
        market_count = self.polymarket_ingestor.bootstrap()
        self.hyperliquid_ingestor.bootstrap()
        for market_id in self.state.markets:
            self.feature_engine.compute_snapshot(market_id)
        return market_count


def build_container(settings: Settings) -> Container:
    state = InMemoryState()
    root = Path(__file__).resolve().parents[4]
    polymarket_seed_path = root / "data" / "seed" / "polymarket_markets.json"
    hyperliquid_seed_path = root / "data" / "seed" / "hyperliquid_btc_eth.json"
    mock_polymarket = MockPolymarketClient(seed_path=polymarket_seed_path)
    mock_hyperliquid = MockHyperliquidClient(seed_path=hyperliquid_seed_path)
    market_window = MarketWindowService(state)
    feature_windows = [int(value.strip()) for value in settings.feature_trade_windows.split(",") if value.strip()]
    feature_engine = FeatureEngineService(state, market_window=market_window, windows=feature_windows)
    container = Container(
        settings=settings,
        state=state,
        market_catalog=MarketCatalogService(state),
        polymarket_ingestor=PolymarketIngestorService(state, client=mock_polymarket),
        hyperliquid_ingestor=HyperliquidIngestorService(state, client=mock_hyperliquid),
        market_window=market_window,
        feature_engine=feature_engine,
        backtester=BacktesterService(state, feature_engine=feature_engine),
        replay=ReplayService(state),
        paper_trader=PaperTraderService(settings=settings),
        execution_engine=ExecutionEngineService(),
        rules_engine=RulesEngineService(),
        mock_polymarket=mock_polymarket,
        mock_hyperliquid=mock_hyperliquid,
    )
    container.bootstrap_seed_data()
    return container
