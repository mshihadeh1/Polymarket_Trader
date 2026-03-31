from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from polymarket_trader.bootstrap import Container


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

    @router.get("/replay/{market_id}")
    def get_replay(market_id: str):
        try:
            return container.replay.get_replay(market_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/ingestion/bootstrap")
    def bootstrap():
        count = container.bootstrap_seed_data(force_reload=True)
        return {"markets_loaded": count}

    @router.get("/strategies")
    def list_strategies():
        return container.backtester.list_strategies()

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
            "mock_polymarket": container.settings.use_mock_polymarket,
            "external_historical_provider": container.settings.external_historical_provider,
            "mock_external_provider": container.settings.use_mock_external_provider,
            "external_provider_capabilities": container.external_market_data_provider.capabilities(),
        }

    return router
