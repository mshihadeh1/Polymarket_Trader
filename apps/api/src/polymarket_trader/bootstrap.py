from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from packages.clients.hyperliquid_client import MockHyperliquidClient, RealHyperliquidClient
from packages.clients.polymarket_client import PolymarketExecutionAdapter
from packages.clients.market_data_provider import HistoricalMarketDataProvider, build_historical_market_data_provider
from packages.clients.polymarket_client import MockPolymarketClient, PolymarketClient, RealPolymarketClient
from packages.config import Settings
from packages.db import ResearchPersistence, create_session_factory
from services.backtester import BacktesterService, MinuteResearchService
from services.backtester.synthetic_research import SyntheticResearchService
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

logger = logging.getLogger(__name__)


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
    minute_research: MinuteResearchService
    synthetic_research: SyntheticResearchService
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
            self.paper_trader.reset_state()
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
            self.state.external_feature_availability.clear()
            self.state.feature_snapshots.clear()
            self.state.backtest_reports.clear()
            self.state.synthetic_market_samples.clear()
            self.state.synthetic_feature_snapshots.clear()
            self.state.synthetic_batch_reports.clear()
            self.state.minute_research_rows.clear()
            self.state.minute_feature_snapshots.clear()
            self.state.minute_batch_reports.clear()
            self.state.closed_market_batch_reports.clear()
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
        if self.settings.mock_startup_demo_enabled and self.polymarket_client.is_mock:
            if not self.backtester.list_closed_market_batch_reports():
                logger.info("Running mock startup closed-market demo batch")
                await self.backtester.run_closed_market_comparison(asset="BTC", timeframe=None, limit=10, strategy_name="combined_cvd_gap")
            if not self.paper_trader.blotter():
                logger.info("Running mock startup paper cycle")
                self.paper_trader.run_cycle()
        return market_count

    async def start_background_tasks(self) -> None:
        await self.polymarket_ingestor.start_live_ingestion()
        await self.paper_trader.start_loop()

    async def stop_background_tasks(self) -> None:
        await self.paper_trader.stop_loop()
        await self.polymarket_ingestor.stop_live_ingestion()

    def bootstrap_seed_data_sync(self, force_reload: bool = False) -> int:
        return asyncio.run(self.bootstrap_seed_data(force_reload=force_reload))


def build_container(settings: Settings, bootstrap_on_build: bool = True) -> Container:
    state = InMemoryState()
    root = Path(__file__).resolve().parents[4]
    polymarket_client = build_polymarket_client(settings, root=root)
    external_provider = build_historical_market_data_provider(settings, root=root)
    hyperliquid_recent_client = build_hyperliquid_recent_client(settings, root=root)
    persistence = ResearchPersistence(create_session_factory(settings))
    execution_adapter = build_polymarket_execution_adapter(settings)
    if hasattr(external_provider, "validate_datasets"):
        for report in external_provider.validate_datasets():
            state.external_dataset_validation[report.symbol] = report
            logger.info(
                "CSV dataset validation symbol=%s rows=%s first=%s last=%s duplicates=%s issues=%s",
                report.symbol,
                report.row_count,
                report.first_timestamp,
                report.last_timestamp,
                report.duplicate_count,
                report.schema_issues,
            )
    market_window = MarketWindowService(state)
    feature_windows = [int(value.strip()) for value in settings.feature_trade_windows.split(",") if value.strip()]
    feature_engine = FeatureEngineService(
        state,
        market_window=market_window,
        windows=feature_windows,
        fair_value_model=BaselineFairValueModel(),
        persistence=persistence,
    )
    hyperliquid_ingestor = HyperliquidIngestorService(state, provider=external_provider, recent_client=hyperliquid_recent_client)
    synthetic_research = SyntheticResearchService(
        settings=settings,
        state=state,
        historical_provider=external_provider,
        polymarket_client=polymarket_client,
        persistence=persistence,
    )
    minute_research = MinuteResearchService(
        settings=settings,
        state=state,
        historical_provider=external_provider,
        polymarket_client=polymarket_client,
        market_window=market_window,
        persistence=persistence,
    )
    polymarket_ingestor = PolymarketIngestorService(state, client=polymarket_client, persistence=persistence)

    async def refresh_live_markets() -> int:
        async def hydrate_new_markets(market_ids: list[str]) -> None:
            now = datetime.now(timezone.utc)
            for market_id in market_ids:
                market = state.market_details.get(market_id)
                if market is None or market.underlying is None or market.opens_at is None:
                    continue
                end = market.closes_at or now
                if end > now:
                    end = now
                assembled = hyperliquid_ingestor.assemble_window(
                    market.underlying,
                    start=market.opens_at,
                    end=end,
                    include_recent_enrichment=True,
                    include_current_orderbook=market.status == "active",
                )
                state.external_bars[market_id] = assembled["bars"]
                state.external_trades[market_id] = assembled["trades"]
                state.external_orderbooks[market_id] = assembled["orderbooks"]
                state.external_raw_payloads[market_id] = assembled["raw_payloads"]
                state.external_feature_availability[market_id] = assembled["availability"].model_dump(mode="json")
                market.external_provider = external_provider.provider_name
                if assembled["orderbooks"]:
                    market.latest_external_orderbook = assembled["orderbooks"][-1]
                if assembled["trades"]:
                    market.recent_external_trades = assembled["trades"][-20:]
                if market.external_context is not None:
                    market.external_context.provider = external_provider.provider_name

        return await polymarket_ingestor.refresh_active_markets(
            hydrate_external_callback=hydrate_new_markets if settings.paper_trading_auto_hydrate_external else None,
        )

    container = Container(
        settings=settings,
        state=state,
        market_catalog=MarketCatalogService(state),
        polymarket_ingestor=polymarket_ingestor,
        hyperliquid_ingestor=hyperliquid_ingestor,
        market_window=market_window,
        feature_engine=feature_engine,
        backtester=BacktesterService(
            settings=settings,
            state=state,
            feature_engine=feature_engine,
            polymarket_client=polymarket_client,
            external_ingestor=hyperliquid_ingestor,
            persistence=persistence,
        ),
        minute_research=minute_research,
        synthetic_research=synthetic_research,
        replay=ReplayService(state),
        paper_trader=PaperTraderService(
            settings=settings,
            state=state,
            feature_engine=feature_engine,
            market_refresh_callback=refresh_live_markets,
            persistence=persistence,
        ),
        execution_engine=ExecutionEngineService(
            settings=settings,
            state=state,
            persistence=persistence,
            adapter=execution_adapter,
        ),
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


def build_hyperliquid_recent_client(settings: Settings, root: Path):
    if settings.use_mock_hyperliquid_recent:
        return MockHyperliquidClient(seed_path=root / "data" / "seed" / "hyperliquid_recent.json")
    return RealHyperliquidClient(
        info_url=settings.hyperliquid_info_url,
        trade_limit=settings.hyperliquid_recent_trade_limit,
    )


def build_polymarket_execution_adapter(settings: Settings) -> PolymarketExecutionAdapter:
    return PolymarketExecutionAdapter(
        host=settings.polymarket_clob_host,
        chain_id=settings.polymarket_chain_id,
        private_key=settings.polymarket_private_key,
        funder=settings.polymarket_funder,
        signature_type=settings.polymarket_signature_type,
    )
