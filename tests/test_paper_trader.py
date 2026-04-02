import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from packages.config import Settings
from packages.core_types.schemas import MarketDetail, MarketSummary, MarketToken
from polymarket_trader.bootstrap import build_container


def _activate_btc_market(container, market_type: str = "crypto_5m") -> str:
    market_id = next(
        market_id
        for market_id, market in container.state.markets.items()
        if market.underlying == "BTC" and market.market_type == market_type
    )
    future_close = datetime.now(timezone.utc) + timedelta(minutes=5)
    summary = container.state.markets[market_id]
    summary.status = "active"
    summary.opens_at = min(summary.opens_at or future_close, future_close - timedelta(minutes=5))
    summary.closes_at = future_close
    detail = container.state.market_details[market_id]
    detail.status = "active"
    detail.opens_at = summary.opens_at
    detail.closes_at = future_close
    detail.resolves_at = future_close
    return market_id


def test_paper_trader_status_is_dry_run() -> None:
    container = build_container(Settings())
    status = container.paper_trader.status()
    assert status.dry_run_only is True
    assert status.strategy_name == "combined_cvd_gap"


def test_paper_trader_run_once_appends_blotter_entry() -> None:
    container = build_container(Settings())
    before = len(container.paper_trader.blotter())
    container.paper_trader.run_once("6fd5b43f-b7c7-4f63-bf57-3a91e89e8c30")
    after = len(container.paper_trader.blotter())
    assert after == before + 1


def test_paper_trader_cycle_updates_live_status() -> None:
    settings = Settings(PAPER_TRADING_UNDERLYINGS="BTC", PAPER_TRADING_MARKET_TYPES="crypto_5m,crypto_15m")
    container = build_container(settings)
    _activate_btc_market(container)
    decisions = container.paper_trader.run_cycle()
    status = container.paper_trader.status()
    assert decisions
    assert status.cycle_count == 1
    assert status.last_update_at is not None
    assert status.selected_market_ids
    assert status.signal_count >= len(decisions)
    assert status.fill_rate >= 0.0


def test_paper_trader_blocks_repeat_fill_in_same_market_window() -> None:
    settings = Settings(
        PAPER_TRADING_UNDERLYINGS="BTC",
        PAPER_TRADING_MARKET_TYPES="crypto_5m",
        PAPER_TRADING_STRATEGY="combined_cvd_gap",
        PAPER_TRADING_MIN_CONFIDENCE=0.0,
    )
    container = build_container(settings)
    market_id = _activate_btc_market(container)
    first = container.paper_trader.run_once(market_id)
    second = container.paper_trader.run_once(market_id)
    status = container.paper_trader.status()
    assert first.status == "simulated_fill"
    assert second.status == "no_action"
    assert "single_fill_per_window_guard" in (second.reason or "")
    assert status.blocked_signal_count >= 1


def test_paper_trader_auto_settles_expired_positions() -> None:
    settings = Settings(
        PAPER_TRADING_UNDERLYINGS="BTC",
        PAPER_TRADING_MARKET_TYPES="crypto_5m",
        PAPER_TRADING_STRATEGY="combined_cvd_gap",
        PAPER_TRADING_MIN_CONFIDENCE=0.0,
    )
    container = build_container(settings)
    market_id = _activate_btc_market(container)
    first = container.paper_trader.run_once(market_id)
    assert first.status == "simulated_fill"
    market = container.state.market_details[market_id]
    market.closes_at = market.opens_at
    summary = container.state.markets[market_id]
    summary.closes_at = market.opens_at
    container.paper_trader.run_cycle()
    assert all(position.market_id != first.market_id for position in container.paper_trader.status().position_details)
    assert any(entry.action == "auto_settle" for entry in container.paper_trader.blotter())


def test_paper_trader_refresh_picks_up_new_market_mid_run() -> None:
    settings = Settings(
        PAPER_TRADING_UNDERLYINGS="BTC",
        PAPER_TRADING_MARKET_TYPES="crypto_5m",
        PAPER_TRADING_STRATEGY="flow_alignment_5m",
        PAPER_TRADING_MIN_CONFIDENCE=0.0,
        PAPER_TRADING_MARKET_REFRESH_ENABLED=True,
        PAPER_TRADING_MARKET_REFRESH_CYCLES=1,
        PAPER_TRADING_AUTO_HYDRATE_EXTERNAL=False,
    )
    container = build_container(settings)
    template_id = next(
        market_id
        for market_id, market in container.state.markets.items()
        if market.underlying == "BTC" and market.market_type == "crypto_5m"
    )
    template_summary = container.state.markets[template_id]
    template_detail = container.state.market_details[template_id]
    new_market_id = str(uuid4())
    new_token_yes = MarketToken(id=uuid4(), token_id=f"{new_market_id}:YES", outcome="YES")
    new_token_no = MarketToken(id=uuid4(), token_id=f"{new_market_id}:NO", outcome="NO")
    new_summary = MarketSummary(
        id=UUID(new_market_id),
        slug=f"{template_summary.slug}-rotated",
        title=template_summary.title,
        category=template_summary.category,
        market_type="crypto_5m",
        underlying="BTC",
        market_family=template_summary.market_family,
        event_slug=f"{template_summary.event_slug}-rotated" if template_summary.event_slug else None,
        event_epoch=template_summary.event_epoch,
        duration_minutes=template_summary.duration_minutes,
        status="inactive",
        opens_at=template_summary.opens_at,
        closes_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        resolves_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        price_to_beat=template_summary.price_to_beat,
        open_reference_price=template_summary.open_reference_price,
        resolved_outcome="unknown",
        resolution_price=None,
        source="mock",
        tags=list(template_summary.tags),
        tokens=[new_token_yes, new_token_no],
    )
    new_detail = MarketDetail(
        **new_summary.model_dump(),
        rules=list(template_detail.rules),
        latest_polymarket_orderbook=template_detail.latest_polymarket_orderbook,
        latest_external_orderbook=template_detail.latest_external_orderbook,
        recent_polymarket_trades=list(template_detail.recent_polymarket_trades),
        recent_external_trades=list(template_detail.recent_external_trades),
        external_context=template_detail.external_context,
    )
    container.state.markets[new_market_id] = new_summary
    container.state.market_details[new_market_id] = new_detail
    container.state.external_bars[new_market_id] = list(container.state.external_bars[template_id])
    container.state.external_trades[new_market_id] = list(container.state.external_trades[template_id])
    container.state.external_orderbooks[new_market_id] = list(container.state.external_orderbooks[template_id])

    async def _refresh() -> int:
        container.state.markets[new_market_id].status = "active"
        container.state.market_details[new_market_id].status = "active"
        return 1

    container.paper_trader._market_refresh_callback = _refresh  # type: ignore[attr-defined]

    asyncio.run(container.paper_trader.refresh_markets())
    status = container.paper_trader.status()
    assert new_market_id in {str(market_id) for market_id in status.selected_market_ids}
    assert status.market_refresh_count == 1
    assert status.last_market_refresh_at is not None
