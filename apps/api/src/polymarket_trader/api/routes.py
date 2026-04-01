from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from polymarket_trader.bootstrap import Container
from packages.utils.time import parse_dt


def build_router(container: Container) -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.get("/markets")
    def list_markets(
        market_type: str | None = Query(default=None),
        category: str | None = Query(default=None),
        short_horizon_only: bool = Query(default=False),
    ):
        return container.market_catalog.list_markets(
            market_type=market_type,
            category=category,
            short_horizon_only=short_horizon_only,
        )

    @router.get("/markets/{market_id}")
    def get_market(market_id: str):
        try:
            return container.market_catalog.get_market(market_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/markets/{market_id}/orderbook")
    def get_orderbook(market_id: str):
        return {
            "polymarket": container.state.polymarket_orderbooks.get(market_id, []),
            "external": container.state.external_orderbooks.get(market_id, []),
        }

    @router.get("/markets/{market_id}/trades")
    def get_trades(market_id: str):
        return {
            "polymarket": container.state.polymarket_trades.get(market_id, []),
            "external": container.state.external_trades.get(market_id, []),
        }

    @router.get("/markets/{market_id}/external-history")
    def get_external_history(market_id: str):
        return {
            "provider": container.state.market_details.get(market_id).external_provider if market_id in container.state.market_details else None,
            "bars": container.state.external_bars.get(market_id, []),
            "raw_payloads": container.state.external_raw_payloads.get(market_id, {}),
        }

    @router.get("/markets/{market_id}/features")
    def get_feature_snapshots(market_id: str):
        try:
            return container.feature_engine.list_snapshots(market_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/markets/{market_id}/live-feature-view")
    def get_live_feature_view(market_id: str):
        try:
            return container.backtester.build_live_feature_view(market_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/replay/{market_id}")
    def get_replay(market_id: str):
        try:
            return container.replay.get_replay(market_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/ingestion/bootstrap")
    def bootstrap():
        count = container.bootstrap_seed_data_sync(force_reload=True)
        return {"markets_loaded": count}

    @router.post("/ingestion/hydrate-closed-markets")
    async def hydrate_closed_markets(identifiers: list[str] | None = Query(default=None), limit: int = Query(default=50)):
        count = await container.polymarket_ingestor.hydrate_closed_markets(identifiers=identifiers, limit=limit)
        return {"markets_hydrated": count, "identifiers": identifiers or [], "limit": limit}

    @router.get("/strategies")
    def list_strategies():
        return container.backtester.list_strategies()

    @router.get("/research/strategies")
    def list_research_strategies():
        return container.synthetic_research.list_strategies()

    @router.get("/research/minute/strategies")
    def list_minute_strategies():
        return container.minute_research.list_strategies()

    @router.get("/research/minute/rows")
    def list_minute_rows(
        asset: str | None = Query(default="BTC"),
        limit: int = Query(default=200),
        start: str | None = Query(default=None),
        end: str | None = Query(default=None),
    ):
        return container.minute_research.list_rows(
            asset=asset,
            limit=limit,
            start=parse_dt(start) if start else None,
            end=parse_dt(end) if end else None,
        )

    @router.post("/research/minute/build")
    def build_minute_rows(
        asset: str | None = Query(default="BTC"),
        start: str | None = Query(default=None),
        end: str | None = Query(default=None),
        refresh: bool = Query(default=False),
    ):
        return container.minute_research.build_minute_dataset(
            asset=asset,
            start=parse_dt(start) if start else None,
            end=parse_dt(end) if end else None,
            refresh=refresh,
        )

    @router.post("/research/minute/run")
    def run_minute_batch(
        asset: str | None = Query(default="BTC"),
        timeframe: str = Query(default="crypto_5m"),
        strategy_name: str = Query(default="minute_momentum"),
        limit: int = Query(default=500),
        start: str | None = Query(default=None),
        end: str | None = Query(default=None),
        refresh: bool = Query(default=False),
    ):
        try:
            return container.minute_research.run_batch(
                asset=asset,
                timeframe=timeframe,
                strategy_name=strategy_name,
                limit=limit,
                start=parse_dt(start) if start else None,
                end=parse_dt(end) if end else None,
                refresh=refresh,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/research/minute/results")
    def list_minute_results(timeframe: str | None = Query(default=None)):
        return container.minute_research.list_synthetic_results(timeframe=timeframe)

    @router.post("/research/validation/run")
    def run_minute_validation(
        asset: str | None = Query(default="BTC"),
        timeframe: str | None = Query(default=None),
        strategy_name: str = Query(default="minute_momentum"),
        limit: int = Query(default=50),
        start: str | None = Query(default=None),
        end: str | None = Query(default=None),
        refresh: bool = Query(default=False),
    ):
        try:
            return container.minute_research.run_real_validation_batch(
                asset=asset,
                timeframe=timeframe,
                strategy_name=strategy_name,
                limit=limit,
                start=parse_dt(start) if start else None,
                end=parse_dt(end) if end else None,
                refresh=refresh,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/research/validation/results")
    def list_minute_validation_results(timeframe: str | None = Query(default=None)):
        return container.minute_research.list_validation_results(timeframe=timeframe)

    @router.get("/research/minute/live-feature-view")
    def get_minute_live_feature_view(asset: str = Query(default="BTC")):
        return container.minute_research.build_live_feature_view(asset=asset)

    @router.get("/research/synthetic/samples")
    def list_synthetic_samples(
        asset: str | None = Query(default=None),
        timeframe: str | None = Query(default=None),
        limit: int = Query(default=100),
        start: str | None = Query(default=None),
        end: str | None = Query(default=None),
    ):
        return container.synthetic_research.list_samples(
            asset=asset,
            timeframe=timeframe,
            limit=limit,
            start=parse_dt(start) if start else None,
            end=parse_dt(end) if end else None,
        )

    @router.post("/research/synthetic/build")
    def build_synthetic_samples(
        asset: str | None = Query(default=None),
        timeframe: str | None = Query(default=None),
        start: str | None = Query(default=None),
        end: str | None = Query(default=None),
    ):
        return container.synthetic_research.build_synthetic_dataset(
            asset=asset,
            timeframe=timeframe,
            start=parse_dt(start) if start else None,
            end=parse_dt(end) if end else None,
        )

    @router.post("/research/synthetic/run")
    def run_synthetic_batch(
        asset: str | None = Query(default=None),
        timeframe: str | None = Query(default=None),
        strategy_name: str = Query(default="synthetic_momentum"),
        decision_time: str = Query(default="open"),
        limit: int = Query(default=200),
        start: str | None = Query(default=None),
        end: str | None = Query(default=None),
    ):
        try:
            return container.synthetic_research.run_synthetic_batch(
                asset=asset,
                timeframe=timeframe,
                strategy_name=strategy_name,
                decision_time=decision_time,
                limit=limit,
                start=parse_dt(start) if start else None,
                end=parse_dt(end) if end else None,
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/research/synthetic/results")
    def list_synthetic_results():
        return container.synthetic_research.list_reports(source="synthetic")

    @router.get("/external-provider")
    def get_external_provider():
        provider = container.external_market_data_provider
        return {
            "provider_name": provider.provider_name,
            "capabilities": provider.capabilities(),
            "symbol_mappings": [
                provider.map_symbol(symbol)
                for symbol in container.settings.default_underlyings.split(",")
                if symbol.strip()
            ],
            "dataset_validation": list(container.state.external_dataset_validation.values()),
        }

    @router.post("/backtests/{market_id}")
    def run_backtest(market_id: str, strategy_name: str = Query(default="no_trade_baseline")):
        try:
            return container.backtester.run_baseline(market_id, strategy_name=strategy_name)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.get("/backtests")
    def list_backtests():
        return container.backtester.list_reports()

    @router.get("/backtests/{run_id}")
    def get_backtest(run_id: str):
        for report in container.backtester.list_reports():
            if report.run_id == run_id:
                return report
        raise HTTPException(status_code=404, detail=f"Unknown run_id={run_id}")

    @router.get("/evaluations/closed-markets")
    async def list_closed_markets(asset: str | None = Query(default=None), timeframe: str | None = Query(default=None), limit: int = Query(default=25)):
        return await container.backtester.list_eligible_closed_markets(asset=asset, timeframe=timeframe, limit=limit)

    @router.post("/evaluations/closed-markets/run")
    async def run_closed_market_batch(
        asset: str | None = Query(default=None),
        timeframe: str | None = Query(default=None),
        limit: int = Query(default=20),
        strategy_name: str = Query(default="combined_cvd_gap"),
        include_hyperliquid_enrichment: bool = Query(default=True),
    ):
        return await container.backtester.run_closed_market_batch(
            asset=asset,
            timeframe=timeframe,
            limit=limit,
            strategy_name=strategy_name,
            include_hyperliquid_enrichment=include_hyperliquid_enrichment,
        )

    @router.get("/evaluations/results")
    def list_closed_market_results():
        return container.backtester.list_closed_market_batch_reports()

    @router.post("/evaluations/compare")
    async def compare_closed_market_batches(
        asset: str | None = Query(default=None),
        timeframe: str | None = Query(default=None),
        limit: int = Query(default=20),
        strategy_name: str = Query(default="combined_cvd_gap"),
    ):
        return await container.backtester.run_closed_market_comparison(
            asset=asset,
            timeframe=timeframe,
            limit=limit,
            strategy_name=strategy_name,
        )

    @router.get("/paper-trading/blotter")
    def blotter():
        return container.paper_trader.blotter()

    @router.get("/paper-trading/status")
    def paper_status():
        return container.paper_trader.status()

    @router.post("/paper-trading/run/{market_id}")
    def run_paper_once(market_id: str):
        try:
            return container.paper_trader.run_once(market_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/paper-trading/cycle")
    def run_paper_cycle():
        return container.paper_trader.run_cycle()

    @router.post("/paper-trading/start")
    async def start_paper_loop():
        await container.paper_trader.start_loop()
        return container.paper_trader.status()

    @router.post("/paper-trading/stop")
    async def stop_paper_loop():
        await container.paper_trader.stop_loop()
        return container.paper_trader.status()

    @router.get("/risk/settings")
    def risk_settings():
        return container.paper_trader.risk_settings()

    @router.get("/execution/status")
    def execution_status():
        return container.execution_engine.status()

    @router.get("/system/health")
    def system_health():
        return {
            "status": "ok",
            "markets_loaded": len(container.state.markets),
            "mock_polymarket": container.polymarket_client.is_mock,
            "polymarket_client": container.polymarket_client.client_name,
            "polymarket_observation": container.state.polymarket_observation,
            "external_historical_provider": container.settings.external_historical_provider,
            "mock_external_provider": container.settings.use_mock_external_provider,
            "mock_hyperliquid_recent": container.settings.use_mock_hyperliquid_recent,
            "dataset_validation": list(container.state.external_dataset_validation.values()),
            "external_provider_capabilities": container.external_market_data_provider.capabilities(),
        }

    return router
