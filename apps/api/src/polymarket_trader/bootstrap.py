from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from packages.clients.market_data_provider import HistoricalMarketDataProvider, build_historical_market_data_provider
from packages.clients.polymarket_client import MockPolymarketClient, PolymarketClient, RealPolymarketClient
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
    polymarket_client: PolymarketClient
    external_market_data_provider: HistoricalMarketDataProvider

    async def bootstrap_seed_data(self, force_reload: bool = False) -> int:
        if self.state.markets and not force_reload:
            return len(self.state.markets)
        if force_reload:
            self.state.markets.clear()
            self.state.market_details.clear()
            self.state.polymarket_orderbooks.clear()
            self.state.polymarket_trades.clear()
            self.state.polymarket_top_of_book.clear()
            self.state.polymarket_trade_events.clear()
            self.state.external_orderbooks.clear()
            self.state.external_trades.clear()
            self.state.external_bars.clear()
            self.state.polymarket_raw_events.clear()
            self.state.polymarket_raw_envelopes.clear()
            self.state.external_raw_payloads.clear()
            self.state.feature_snapshots.clear()
            self.state.backtest_reports.clear()
            self.state.paper_decisions.clear()
            self.state.polymarket_observation.source_mode = "mock" if self.polymarket_client.is_mock else "real"
            self.state.polymarket_observation.stream_task_running = False
            self.state.polymarket_observation.websocket_connected = False
            self.state.polymarket_observation.startup_completed = False
            self.state.polymarket_observation.last_connect_at = None
            self.state.polymarket_observation.last_disconnect_at = None
            self.state.polymarket_observation.last_event_at = None
            self.state.polymarket_observation.reconnect_count = 0
            self.state.polymarket_observation.raw_event_count = 0
            self.state.polymarket_observation.trade_event_count = 0
            self.state.polymarket_observation.book_event_count = 0
            self.state.polymarket_observation.duplicate_event_count = 0
            self.state.polymarket_observation.dropped_event_count = 0
            self.state.polymarket_observation.selected_market_count = 0
            self.state.polymarket_observation.selected_asset_count = 0
            self.state.polymarket_observation.last_error = None
        market_count = await self.polymarket_ingestor.bootstrap()
        self.hyperliquid_ingestor.bootstrap()
        for market_id in self.state.markets:
            self.feature_engine.compute_snapshot(market_id)
        return market_count

    async def start_background_tasks(self) -> None:
        await self.polymarket_ingestor.start_live_ingestion()

    async def stop_background_tasks(self) -> None:
        await self.polymarket_ingestor.stop_live_ingestion()

    def bootstrap_seed_data_sync(self, force_reload: bool = False) -> int:
        return asyncio.run(self.bootstrap_seed_data(force_reload=force_reload))


def build_container(settings: Settings, bootstrap_on_build: bool = True) -> Container:
    state = InMemoryState()
    root = Path(__file__).resolve().parents[4]
    polymarket_client = build_polymarket_client(settings, root=root)
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
        polymarket_ingestor=PolymarketIngestorService(state, client=polymarket_client, persistence=persistence),
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
        polymarket_client=polymarket_client,
        external_market_data_provider=external_provider,
    )
    if bootstrap_on_build:
        container.bootstrap_seed_data_sync()
    return container


def build_polymarket_client(settings: Settings, root: Path) -> PolymarketClient:
    polymarket_seed_path = root / "data" / "seed" / "polymarket_markets.json"
    if settings.use_mock_polymarket or settings.use_mock_polymarket_client:
        return MockPolymarketClient(seed_path=polymarket_seed_path)
    return RealPolymarketClient(
        api_base_url=settings.polymarket_api_base_url,
        ws_url=settings.polymarket_ws_url,
    )
