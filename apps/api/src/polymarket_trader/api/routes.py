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
            "hyperliquid": container.state.hyperliquid_orderbooks.get(market_id, []),
        }

    @router.get("/markets/{market_id}/trades")
    def get_trades(market_id: str):
        return {
            "polymarket": container.state.polymarket_trades.get(market_id, []),
            "hyperliquid": container.state.hyperliquid_trades.get(market_id, []),
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
        return [
            {
                "name": "no_trade_baseline",
                "family": "baseline",
                "description": "Control strategy that never trades.",
                "configurable_fields": [],
            },
            {
                "name": "cvd_combined_scaffold",
                "family": "microstructure",
                "description": "Placeholder comparison strategy using local/external CVD and fair-value gap.",
                "configurable_fields": ["trade_size", "min_gap"],
            },
        ]

    @router.post("/backtests/{market_id}")
    def run_backtest(market_id: str, strategy_name: str = Query(default="no_trade_baseline")):
        try:
            return container.backtester.run_baseline(market_id, strategy_name=strategy_name)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/paper-trading/blotter")
    def blotter():
        return container.paper_trader.blotter()

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
            "mock_hyperliquid": container.settings.use_mock_hyperliquid,
        }

    return router
