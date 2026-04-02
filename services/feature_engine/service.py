from __future__ import annotations

from datetime import datetime

from packages.db import ResearchPersistence
from packages.core_types.schemas import FeatureSnapshot
from packages.utils.cvd import cumulative_volume_delta, rolling_cvd, rolling_trade_imbalance, trade_imbalance
from packages.utils.time import seconds_until
from services.fair_value_models import BaselineFairValueModel
from services.feature_engine.market_window import MarketWindowService
from services.state import InMemoryState


class FeatureEngineService:
    def __init__(
        self,
        state: InMemoryState,
        market_window: MarketWindowService,
        windows: list[int],
        fair_value_model: BaselineFairValueModel | None = None,
        persistence: ResearchPersistence | None = None,
    ) -> None:
        self._state = state
        self._market_window = market_window
        self._windows = windows
        self._fair_value_model = fair_value_model or BaselineFairValueModel()
        self._persistence = persistence

    def compute_snapshot(self, market_id: str, as_of: datetime | None = None) -> FeatureSnapshot:
        market = self._state.market_details.get(market_id)
        if market is None:
            raise KeyError(f"Unknown market_id={market_id}")
        snapshot = self.compute_snapshot_from_series(
            market_id=market_id,
            market=market,
            external_bars_all=self._state.external_bars.get(market_id, []),
            polymarket_trades_all=self._state.polymarket_trades.get(market_id, []),
            external_trades_all=self._state.external_trades.get(market_id, []),
            orderbooks_all=self._state.polymarket_orderbooks.get(market_id, []),
            external_orderbooks_all=self._state.external_orderbooks.get(market_id, []),
            as_of=as_of,
            persist=True,
        )
        self._state.market_details[market_id].external_context = self._market_window.get_external_context(market_id, as_of=snapshot.ts)
        return snapshot

    def compute_snapshot_from_series(
        self,
        market_id: str,
        market,
        external_bars_all,
        polymarket_trades_all,
        external_trades_all,
        orderbooks_all,
        external_orderbooks_all,
        as_of: datetime | None = None,
        persist: bool = False,
    ) -> FeatureSnapshot:
        external_bars = [bar for bar in external_bars_all if as_of is None or bar.ts <= as_of]
        polymarket_trades = [trade for trade in polymarket_trades_all if as_of is None or trade.ts <= as_of]
        external_trades = [trade for trade in external_trades_all if as_of is None or trade.ts <= as_of]
        orderbooks = [book for book in orderbooks_all if as_of is None or book.ts <= as_of]
        external_orderbooks = [book for book in external_orderbooks_all if as_of is None or book.ts <= as_of]
        if as_of is not None:
            current_ts = as_of
        elif orderbooks:
            current_ts = orderbooks[-1].ts
        elif polymarket_trades:
            current_ts = polymarket_trades[-1].ts
        elif external_bars:
            current_ts = external_bars[-1].ts
        else:
            current_ts = market.opens_at
        context = self._market_window.get_external_context_for_series(
            market=market,
            external_bars=external_bars,
            external_orderbooks=external_orderbooks,
            as_of=current_ts,
        )
        top = orderbooks[-1] if orderbooks else None
        external_top = external_orderbooks[-1] if external_orderbooks else None
        midpoint = None
        if top is not None:
            midpoint = top.mid_price or (top.best_bid + top.best_ask) / 2
        realized_vol = None
        if context.open_price and context.current_price:
            realized_vol = abs((context.current_price - context.open_price) / context.open_price)
        if realized_vol is None and len(external_bars) >= 2:
            first_close = external_bars[0].close
            last_close = external_bars[-1].close
            if first_close:
                realized_vol = abs((last_close - first_close) / first_close)
        fair_value_gap = None
        fair_value = None
        if realized_vol is not None and market.price_to_beat is not None and context.current_price is not None:
            fair_value = self._fair_value_model.probability_yes(
                current_price=context.current_price,
                strike_price=market.price_to_beat,
                realized_vol=max(realized_vol, 1e-4),
                time_remaining_seconds=seconds_until(market.closes_at, current_ts) or 0.0,
            )
            if midpoint is not None:
                fair_value_gap = fair_value - midpoint
        venue_divergence = None
        if external_top is not None and top is not None:
            venue_divergence = (top.mid_price or midpoint or 0.0) - fair_value if fair_value is not None else None
        lead_lag_gap = None
        if context.return_since_open is not None:
            lead_lag_gap = context.return_since_open - ((midpoint - 0.5) if midpoint is not None else 0.0)
        polymarket_rolling_cvd = rolling_cvd(polymarket_trades, current_ts, self._windows)
        external_rolling_cvd = rolling_cvd(external_trades, current_ts, self._windows)
        polymarket_rolling_imbalance = rolling_trade_imbalance(polymarket_trades, current_ts, self._windows)
        external_rolling_imbalance = rolling_trade_imbalance(external_trades, current_ts, self._windows)
        polymarket_flow_signal = _weighted_window_signal(polymarket_rolling_imbalance)
        external_flow_signal = _weighted_window_signal(external_rolling_imbalance)
        spread = (top.best_ask - top.best_bid) if top else None
        spread_bps = spread * 10_000 if spread is not None else None
        distance_to_threshold = ((context.current_price - market.price_to_beat) if context.current_price and market.price_to_beat else None)
        distance_to_threshold_bps = (
            (distance_to_threshold / market.price_to_beat) * 10_000
            if distance_to_threshold is not None and market.price_to_beat
            else None
        )
        fair_value_signal = _scaled_signal(fair_value_gap, scale=0.04)
        strike_signal = _scaled_signal(distance_to_threshold_bps, scale=25.0)
        base_alignment = _blend_signals(
            [
                (fair_value_signal, 1.35),
                (external_flow_signal, 1.2),
                (polymarket_flow_signal, 0.95),
                (strike_signal, 0.75),
            ]
        )
        agreement_signal = _agreement_score(
            [
                fair_value_signal,
                external_flow_signal,
                polymarket_flow_signal,
                strike_signal,
            ]
        )
        flow_alignment_score = _clamp_signal(
            ((base_alignment or 0.0) * 0.8) + (agreement_signal * 0.2)
        ) if base_alignment is not None else None
        snapshot = FeatureSnapshot(
            market_id=market.id,
            ts=current_ts,
            polymarket_cvd=cumulative_volume_delta(polymarket_trades),
            polymarket_rolling_cvd=polymarket_rolling_cvd,
            polymarket_rolling_trade_imbalance=polymarket_rolling_imbalance,
            external_cvd=cumulative_volume_delta(external_trades),
            external_rolling_cvd=external_rolling_cvd,
            external_rolling_trade_imbalance=external_rolling_imbalance,
            polymarket_trade_imbalance=trade_imbalance(polymarket_trades),
            external_trade_imbalance=trade_imbalance(external_trades),
            polymarket_flow_signal=polymarket_flow_signal,
            external_flow_signal=external_flow_signal,
            flow_alignment_score=flow_alignment_score,
            best_bid=top.best_bid if top else None,
            best_ask=top.best_ask if top else None,
            spread=spread,
            spread_bps=spread_bps,
            top_of_book_imbalance=((top.bid_size - top.ask_size) / (top.bid_size + top.ask_size)) if top and (top.bid_size + top.ask_size) else None,
            fair_value_estimate=fair_value,
            fair_value_gap=fair_value_gap,
            distance_to_threshold=distance_to_threshold,
            distance_to_threshold_bps=distance_to_threshold_bps,
            time_to_close_seconds=seconds_until(market.closes_at, current_ts),
            external_return_since_open=context.return_since_open,
            lead_lag_gap=lead_lag_gap,
            venue_divergence=venue_divergence,
        )
        snapshots = self._state.feature_snapshots.setdefault(market_id, [])
        if persist and (not snapshots or snapshots[-1].ts != snapshot.ts):
            snapshots.append(snapshot)
        if persist and self._persistence is not None:
            self._persistence.save_feature_snapshot(snapshot)
        return snapshot

    def list_snapshots(self, market_id: str) -> list[FeatureSnapshot]:
        if market_id not in self._state.feature_snapshots:
            self.compute_snapshot(market_id)
        return self._state.feature_snapshots.get(market_id, [])


def _window_seconds(label: str) -> int | None:
    if not label.endswith("s"):
        return None
    raw_value = label[:-1]
    if not raw_value.isdigit():
        return None
    return int(raw_value)


def _weighted_window_signal(values: dict[str, float]) -> float | None:
    ordered = []
    for label, value in values.items():
        window = _window_seconds(label)
        if window is None:
            continue
        ordered.append((window, value))
    if not ordered:
        return None
    ordered.sort(key=lambda item: item[0])
    total_weight = 0.0
    weighted_sum = 0.0
    for index, (_, value) in enumerate(ordered):
        weight = float(len(ordered) - index)
        weighted_sum += value * weight
        total_weight += weight
    if total_weight == 0:
        return None
    return _clamp_signal(weighted_sum / total_weight)


def _scaled_signal(value: float | None, *, scale: float) -> float | None:
    if value is None or scale <= 0:
        return None
    return _clamp_signal(value / scale)


def _blend_signals(weighted_signals: list[tuple[float | None, float]]) -> float | None:
    weighted_sum = 0.0
    total_weight = 0.0
    for value, weight in weighted_signals:
        if value is None or weight <= 0:
            continue
        weighted_sum += value * weight
        total_weight += weight
    if total_weight == 0:
        return None
    return _clamp_signal(weighted_sum / total_weight)


def _agreement_score(values: list[float | None]) -> float:
    directional = [value for value in values if value is not None and abs(value) >= 0.05]
    if len(directional) < 2:
        return 0.0
    positive = sum(1 for value in directional if value > 0)
    negative = sum(1 for value in directional if value < 0)
    dominant = max(positive, negative)
    sign = 1.0 if positive >= negative else -1.0
    return sign * (dominant / len(directional))


def _clamp_signal(value: float) -> float:
    return max(-1.0, min(1.0, value))
