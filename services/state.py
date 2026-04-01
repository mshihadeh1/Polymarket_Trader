from __future__ import annotations

from dataclasses import dataclass, field

from packages.core_types.schemas import (
    BacktestReport,
    ClosedMarketBatchReport,
    DatasetValidationReport,
    FeatureSnapshot,
    HistoricalBar,
    MarketDetail,
    MarketSummary,
    OrderBookSnapshot,
    PaperTradeDecision,
    SyntheticBatchReport,
    SyntheticFeatureSnapshot,
    SyntheticMarketSample,
    PolymarketTopOfBook,
    PolymarketTrade,
    PolymarketObservationStatus,
    RawPolymarketEvent,
    Trade,
)


@dataclass
class InMemoryState:
    markets: dict[str, MarketSummary] = field(default_factory=dict)
    market_details: dict[str, MarketDetail] = field(default_factory=dict)
    polymarket_orderbooks: dict[str, list[OrderBookSnapshot]] = field(default_factory=dict)
    polymarket_trades: dict[str, list[Trade]] = field(default_factory=dict)
    polymarket_raw_events: dict[str, list[dict]] = field(default_factory=dict)
    polymarket_top_of_book: dict[str, list[PolymarketTopOfBook]] = field(default_factory=dict)
    polymarket_trade_events: dict[str, list[PolymarketTrade]] = field(default_factory=dict)
    polymarket_raw_envelopes: dict[str, list[RawPolymarketEvent]] = field(default_factory=dict)
    external_orderbooks: dict[str, list[OrderBookSnapshot]] = field(default_factory=dict)
    external_trades: dict[str, list[Trade]] = field(default_factory=dict)
    external_bars: dict[str, list[HistoricalBar]] = field(default_factory=dict)
    external_raw_payloads: dict[str, dict[str, list[dict]]] = field(default_factory=dict)
    external_dataset_validation: dict[str, DatasetValidationReport] = field(default_factory=dict)
    external_feature_availability: dict[str, dict] = field(default_factory=dict)
    feature_snapshots: dict[str, list[FeatureSnapshot]] = field(default_factory=dict)
    synthetic_market_samples: dict[str, SyntheticMarketSample] = field(default_factory=dict)
    synthetic_feature_snapshots: dict[str, list[SyntheticFeatureSnapshot]] = field(default_factory=dict)
    synthetic_batch_reports: list[SyntheticBatchReport] = field(default_factory=list)
    backtest_reports: list[BacktestReport] = field(default_factory=list)
    closed_market_batch_reports: list[ClosedMarketBatchReport] = field(default_factory=list)
    paper_decisions: list[PaperTradeDecision] = field(default_factory=list)
    polymarket_observation: PolymarketObservationStatus = field(
        default_factory=lambda: PolymarketObservationStatus(source_mode="mock")
    )
