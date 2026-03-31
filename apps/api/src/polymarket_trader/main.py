from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from packages.config import get_settings
from polymarket_trader.api.routes import build_router
from polymarket_trader.bootstrap import build_container
from polymarket_trader.core.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)
container = build_container(settings, bootstrap_on_build=False)


@asynccontextmanager
async def lifespan(_: FastAPI):
    await container.bootstrap_seed_data()
    await container.start_background_tasks()
    try:
        yield
    finally:
        await container.stop_background_tasks()


app = FastAPI(
    title="Polymarket Trader API",
    version="0.1.0",
    description="Research-first Polymarket trading platform Phase 1 API",
    lifespan=lifespan,
)


@app.get("/healthz")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(build_router(container))
