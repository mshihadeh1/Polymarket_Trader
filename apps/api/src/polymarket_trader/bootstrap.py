from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from packages.clients.market_data_provider import HistoricalMarketDataProvider, build_historical_market_data_provider
from packages.clients.polymarket_client import MockPolymarketClient
from packages.config import Settings
from packages.db import ResearchPersistence, create_session_factory
from services.backtester import BacktesterService
from services.execution_engine import ExecutionEngineService
from services.feature_engine import FeatureEngineService, MarketWindowService
from services.fair_value_models import BaselineFairValueModel
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
    persistence: ResearchPersistence
    mock_polymarket: MockPolymarketClient
    external_market_data_provider: HistoricalMarketDataProvider

    def bootstrap_seed_data(self, force_reload: bool = False) -> int:
        if self.state.markets and not force_reload:
            return len(self.state.markets)
        if force_reload:
            self.state.markets.clear()
            self.state.market_details.clear()
            self.state.polymarket_orderbooks.clear()
            self.state.polymarket_trades.clear()
            self.state.external_orderbooks.clear()
            self.state.external_trades.clear()
            self.state.external_bars.clear()
            self.state.polymarket_raw_events.clear()
            self.state.external_raw_payloads.clear()
            self.state.feature_snapshots.clear()
            self.state.backtest_reports.clear()
            self.state.paper_decisions.clear()
        market_count = self.polymarket_ingestor.bootstrap()
        self.hyperliquid_ingestor.bootstrap()
        for market_id in self.state.markets:
            self.feature_engine.compute_snapshot(market_id)
        return market_count


def build_container(settings: Settings) -> Container:
    state = InMemoryState()
    root = Path(__file__).resolve().parents[4]
    polymarket_seed_path = root / "data" / "seed" / "polymarket_markets.json"
    mock_polymarket = MockPolymarketClient(seed_path=polymarket_seed_path)
    external_provider = build_historical_market_data_provider(settings, root=root)
    persistence = ResearchPersistence(create_session_factory(settings))
    market_window = MarketWindowService(state)
    feature_windows = [int(value.strip()) for value in settings.feature_trade_windows.split(",") if value.strip()]
    feature_engine = FeatureEngineService(
        state,
        market_window=market_window,
        windows=feature_windows,
        fair_value_model=BaselineFairValueModel(),
        persistence=persistence,
    )
    container = Container(
        settings=settings,
        state=state,
        market_catalog=MarketCatalogService(state),
        polymarket_ingestor=PolymarketIngestorService(state, client=mock_polymarket),
        hyperliquid_ingestor=HyperliquidIngestorService(state, provider=external_provider),
        market_window=market_window,
        feature_engine=feature_engine,
        backtester=BacktesterService(state, feature_engine=feature_engine, persistence=persistence),
        replay=ReplayService(state),
        paper_trader=PaperTraderService(
            settings=settings,
            state=state,
            feature_engine=feature_engine,
            persistence=persistence,
        ),
        execution_engine=ExecutionEngineService(),
        rules_engine=RulesEngineService(),
        persistence=persistence,
        mock_polymarket=mock_polymarket,
        external_market_data_provider=external_provider,
    )
    container.bootstrap_seed_data()
    return container
