export type Market = {
  id: string;
  event_id?: string;
  slug: string;
  title: string;
  category: string;
  market_type: string;
  underlying?: string;
  status: string;
  source?: string;
  tags: string[];
  closes_at?: string;
  price_to_beat?: number;
  open_reference_price?: number;
};

export type ReplayEvent = {
  ts: string;
  venue: string;
  event_type: "orderbook" | "trade" | "raw";
  payload: Record<string, unknown>;
};

export type VenueTrade = {
  ts: string;
  venue: string;
  symbol?: string;
  price: number;
  size: number;
  side: "buy" | "sell";
};

export type VenueOrderBook = {
  ts: string;
  venue: string;
  best_bid: number;
  best_ask: number;
  bid_size: number;
  ask_size: number;
};

export type FeatureSnapshot = {
  market_id: string;
  ts: string;
  polymarket_cvd: number;
  polymarket_rolling_cvd?: Record<string, number>;
  external_cvd: number;
  external_rolling_cvd?: Record<string, number>;
  fair_value_estimate?: number;
  fair_value_gap?: number;
  external_return_since_open?: number;
  time_to_close_seconds?: number;
  lead_lag_gap?: number;
  venue_divergence?: number;
};

export type FeatureAvailability = {
  bars_available: boolean;
  trades_available: boolean;
  orderbook_available: boolean;
  enriched_with_hyperliquid: boolean;
  notes: string[];
};

export type Strategy = {
  name: string;
  family: string;
  description: string;
  configurable_fields: string[];
};

export type BacktestReport = {
  run_id: string;
  strategy_name: string;
  market_id: string;
  created_at?: string;
  trade_count: number;
  metrics: { label: string; value: number }[];
  notes: string[];
  decisions: { decision: string; confidence: number; reason: string; signal_value: number }[];
  trades?: {
    ts: string;
    action: string;
    side: string;
    price: number;
    size: number;
    gross_pnl: number;
    net_pnl: number;
    cost: number;
  }[];
  equity_curve?: {
    ts: string;
    equity: number;
    realized_pnl: number;
    unrealized_pnl: number;
    position: number;
  }[];
};

export type ClosedMarketEvaluationRecord = {
  market_id: string;
  market_slug: string;
  asset: string;
  timeframe: string;
  market_open_time: string;
  market_close_time: string;
  strike_price?: number;
  actual_resolution: "yes" | "no" | "unknown";
  actual_resolution_source?: string;
  historical_window_start?: string;
  historical_window_end?: string;
  enrichment_availability: FeatureAvailability;
  feature_snapshot_summary: Record<string, number | string | null>;
  final_decision: string;
  final_confidence: number;
  final_signal_value: number;
  correctness?: boolean | null;
  notes: string[];
};

export type ClosedMarketBatchReport = {
  run_id: string;
  strategy_name: string;
  mode: "bars_only" | "bars_plus_hyperliquid";
  asset_filter?: string;
  timeframe_filter?: string;
  limit: number;
  created_at?: string;
  total_markets_evaluated: number;
  metrics: { label: string; value: number }[];
  coverage: Record<string, number>;
  records: ClosedMarketEvaluationRecord[];
};

export type SyntheticMarketSample = {
  sample_id: string;
  market_id?: string | null;
  source: "synthetic" | "real_validation";
  asset: string;
  timeframe: string;
  market_open_time: string;
  market_close_time: string;
  decision_time: string;
  decision_horizon_minutes: number;
  price_to_beat: number;
  close_price: number;
  actual_resolution: "yes" | "no" | "unknown";
  source_provider: string;
  window_index: number;
  notes: string[];
};

export type SyntheticEvaluationRecord = {
  sample_id: string;
  market_id?: string | null;
  source: "synthetic" | "real_validation";
  asset: string;
  timeframe: string;
  market_open_time: string;
  market_close_time: string;
  decision_time: string;
  price_to_beat: number;
  close_price: number;
  actual_resolution: "yes" | "no" | "unknown";
  actual_resolution_source?: string | null;
  strategy_name: string;
  signal_value: number;
  confidence: number;
  decision: string;
  correctness?: boolean | null;
  contract_score: number;
  feature_snapshot_summary: Record<string, number | string | null>;
  notes: string[];
};

export type SyntheticBatchReport = {
  run_id: string;
  strategy_name: string;
  source: "synthetic" | "real_validation";
  asset_filter?: string;
  timeframe_filter?: string;
  decision_time: string;
  limit: number;
  created_at?: string;
  total_samples: number;
  metrics: { label: string; value: number }[];
  coverage: Record<string, number>;
  records: SyntheticEvaluationRecord[];
};

export type MinuteResearchRow = {
  row_id: string;
  asset: string;
  source: "synthetic" | "real_validation";
  decision_time: string;
  reference_price: number;
  close_5m: number;
  close_15m: number;
  label_up_5m: boolean;
  label_up_15m: boolean;
  future_return_5m: number;
  future_return_15m: number;
  source_provider: string;
  market_id?: string | null;
  notes: string[];
};

export type MinuteFeatureSnapshot = {
  row_id: string;
  asset: string;
  source: "synthetic" | "real_validation";
  decision_time: string;
  current_price: number;
  ret_1m?: number | null;
  ret_3m?: number | null;
  ret_5m?: number | null;
  ret_15m?: number | null;
  ret_30m?: number | null;
  vol_5m?: number | null;
  vol_15m?: number | null;
  vol_30m?: number | null;
  distance_from_mean?: number | null;
  distance_from_recent_high?: number | null;
  distance_from_recent_low?: number | null;
  range_percentile?: number | null;
  slope_5m?: number | null;
  slope_15m?: number | null;
  acceleration?: number | null;
  regime: string;
  session_bucket: string;
  feature_summary: Record<string, number | string | null>;
};

export type MinuteEvaluationRecord = {
  row_id: string;
  asset: string;
  source: "synthetic" | "real_validation";
  decision_time: string;
  horizon_minutes: number;
  strategy_name: string;
  decision: "higher" | "lower" | "hold";
  confidence: number;
  signal_value: number;
  actual_label_up: boolean;
  correctness?: boolean | null;
  future_return: number;
  reference_price: number;
  close_price: number;
  feature_snapshot_summary: Record<string, number | string | null>;
  notes: string[];
};

export type MinuteBatchReport = {
  run_id: string;
  strategy_name: string;
  source: "synthetic" | "real_validation";
  asset_filter?: string;
  timeframe_filter?: string;
  limit: number;
  created_at?: string;
  total_rows: number;
  metrics: { label: string; value: number }[];
  coverage: Record<string, number>;
  records: MinuteEvaluationRecord[];
};

export type PaperStatus = {
  strategy_name: string;
  dry_run_only: boolean;
  active_market_ids: string[];
  selected_market_ids: string[];
  signal_count: number;
  simulated_fill_count: number;
  blocked_signal_count: number;
  market_refresh_count: number;
  last_market_refresh_at?: string | null;
  last_market_refresh_error?: string | null;
  fill_rate: number;
  open_positions: Record<string, number>;
  position_details: {
    market_id: string;
    side: "buy_yes" | "buy_no";
    size: number;
    avg_price: number;
    mark_price: number;
    unrealized_pnl: number;
    opened_at: string;
  }[];
  latest_signals: {
    market_id: string;
    ts: string;
    signal_value: number;
    decision: string;
    confidence: number;
    reason?: string | null;
    fair_value_gap?: number;
    midpoint?: number;
    execution_price?: number;
    market_window_id?: string | null;
    flow_alignment_score?: number;
    external_flow_signal?: number;
    polymarket_flow_signal?: number;
    spread_bps?: number;
    distance_to_threshold_bps?: number;
    time_to_close_seconds?: number;
    executed: boolean;
    blocked_reason?: string | null;
  }[];
  last_decision?: {
    ts: string;
    market_id: string;
    action: string;
    side: string;
    price: number;
    size: number;
    status: string;
    reason?: string;
    signal_value?: number;
    confidence?: number;
  } | null;
  loop_running: boolean;
  last_update_at?: string;
  cycle_count: number;
  loop_error?: string | null;
  unrealized_pnl: number;
  realized_pnl: number;
};

export type PolymarketObservationStatus = {
  source_mode: "mock" | "real";
  stream_task_running: boolean;
  websocket_connected: boolean;
  startup_completed: boolean;
  last_connect_at?: string;
  last_disconnect_at?: string;
  last_event_at?: string;
  reconnect_count: number;
  raw_event_count: number;
  trade_event_count: number;
  book_event_count: number;
  duplicate_event_count: number;
  dropped_event_count: number;
  selected_market_count: number;
  selected_asset_count: number;
  last_error?: string | null;
};

export type DashboardBucketStat = {
  bucket: string;
  sample_size: number;
  hit_rate: number;
  edge_over_50: number;
};

export type DashboardResearchSlice = {
  timeframe: string;
  mode: "bars_only" | "bars_plus_hyperliquid";
  sample_size: number;
  hit_rate: number;
  edge_over_50: number;
  avg_confidence: number;
  contract_score: number;
  verdict: string;
  tone: "positive" | "negative" | "warning" | "neutral";
  confidence_buckets: DashboardBucketStat[];
  hour_buckets: DashboardBucketStat[];
};

export type DashboardEdgePoint = {
  ts: string;
  timeframe: string;
  mode: "bars_only" | "bars_plus_hyperliquid";
  sample_size: number;
  hit_rate: number;
  edge_over_50: number;
  rolling_edge_over_50: number;
};

export type ExecutionStatus = {
  enabled: boolean;
  dry_run_default: boolean;
  live_execution_enabled: boolean;
  adapter_name?: string | null;
  order_count: number;
  open_order_count: number;
  fill_count: number;
  fill_rate: number;
  last_order_at?: string | null;
  last_fill_at?: string | null;
  last_error?: string | null;
  message?: string | null;
};

export type DashboardSummary = {
  generated_at: string;
  source_mode: "mock" | "real";
  historical_provider: string;
  polymarket_client: string;
  observation: PolymarketObservationStatus;
  paper: PaperStatus;
  execution: ExecutionStatus;
  research_slices: DashboardResearchSlice[];
  rolling_edge_series: DashboardEdgePoint[];
  notes: string[];
};

const baseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function fetchMarkets(): Promise<Market[]> {
  const response = await fetch(`${baseUrl}/api/v1/markets`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error("Failed to fetch markets");
  }
  return response.json();
}

export async function fetchReplay(
  marketId: string,
): Promise<{ events: ReplayEvent[] }> {
  const response = await fetch(`${baseUrl}/api/v1/replay/${marketId}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error("Failed to fetch replay");
  }
  return response.json();
}

export async function fetchMarketDetail(marketId: string): Promise<Market & {
  external_context?: {
    symbol: string;
    provider?: string;
    open_price?: number;
    current_price?: number;
    return_since_open?: number;
    time_to_close_seconds?: number;
  };
  latest_polymarket_orderbook?: { best_bid: number; best_ask: number; bid_size: number; ask_size: number };
  latest_external_orderbook?: { best_bid: number; best_ask: number; mid_price?: number };
}> {
  const response = await fetch(`${baseUrl}/api/v1/markets/${marketId}`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error("Failed to fetch market detail");
  }
  return response.json();
}

export async function fetchFeatures(marketId: string): Promise<FeatureSnapshot[]> {
  const response = await fetch(`${baseUrl}/api/v1/markets/${marketId}/features`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error("Failed to fetch features");
  }
  return response.json();
}

export async function fetchTrades(marketId: string): Promise<{
  polymarket: VenueTrade[];
  external: VenueTrade[];
}> {
  const response = await fetch(`${baseUrl}/api/v1/markets/${marketId}/trades`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error("Failed to fetch trades");
  }
  return response.json();
}

export async function fetchOrderBook(marketId: string): Promise<{
  polymarket: VenueOrderBook[];
  external: VenueOrderBook[];
}> {
  const response = await fetch(`${baseUrl}/api/v1/markets/${marketId}/orderbook`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error("Failed to fetch order book");
  }
  return response.json();
}

export async function fetchSystemHealth(): Promise<{
  status: string;
  markets_loaded: number;
  mock_polymarket: boolean;
  polymarket_client: string;
  polymarket_observation: PolymarketObservationStatus;
  external_historical_provider: string;
  mock_external_provider: boolean;
}> {
  const response = await fetch(`${baseUrl}/api/v1/system/health`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error("Failed to fetch system health");
  }
  return response.json();
}

export async function fetchClosedMarkets(asset?: string, timeframe?: string, limit = 25): Promise<{
  market_id: string;
  slug: string;
  title: string;
  asset: string;
  timeframe: string;
  market_open_time: string;
  market_close_time: string;
  strike_price?: number;
  resolution_source?: string;
}[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (asset) params.set("asset", asset);
  if (timeframe) params.set("timeframe", timeframe);
  const response = await fetch(`${baseUrl}/api/v1/evaluations/closed-markets?${params.toString()}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Failed to fetch closed markets");
  }
  return response.json();
}

export async function runClosedMarketComparison(asset?: string, timeframe?: string, limit = 20): Promise<{
  bars_only: ClosedMarketBatchReport;
  bars_plus_hyperliquid: ClosedMarketBatchReport;
}> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (asset) params.set("asset", asset);
  if (timeframe) params.set("timeframe", timeframe);
  const response = await fetch(`${baseUrl}/api/v1/evaluations/compare?${params.toString()}`, {
    method: "POST",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error("Failed to compare closed market batches");
  }
  return response.json();
}

export async function fetchClosedMarketResults(): Promise<ClosedMarketBatchReport[]> {
  const response = await fetch(`${baseUrl}/api/v1/evaluations/results`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Failed to fetch closed-market results");
  }
  return response.json();
}

export function findLatestClosedMarketReport(
  reports: ClosedMarketBatchReport[],
  {
    mode,
    asset,
    timeframe,
  }: {
  mode: ClosedMarketBatchReport["mode"];
  asset?: string;
  timeframe?: string;
}): ClosedMarketBatchReport | null {
  const normalizedAsset = asset?.toUpperCase();
  const filtered = reports.filter((report) => {
    if (report.mode !== mode) return false;
    if (normalizedAsset && (report.asset_filter ?? "").toUpperCase() !== normalizedAsset) return false;
    if (timeframe && report.timeframe_filter !== timeframe) return false;
    return true;
  });
  return filtered[0] ?? null;
}

export async function fetchLiveFeatureView(marketId: string): Promise<{
  market_id: string;
  market_type: string;
  asset: string;
  status: string;
  snapshot: FeatureSnapshot;
  availability: FeatureAvailability | Record<string, unknown>;
  notes: string[];
}> {
  const response = await fetch(`${baseUrl}/api/v1/markets/${marketId}/live-feature-view`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error("Failed to fetch live feature view");
  }
  return response.json();
}

export async function fetchStrategies(): Promise<Strategy[]> {
  const response = await fetch(`${baseUrl}/api/v1/strategies`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Failed to fetch strategies");
  }
  return response.json();
}

export async function fetchResearchStrategies(): Promise<Strategy[]> {
  const response = await fetch(`${baseUrl}/api/v1/research/strategies`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Failed to fetch research strategies");
  }
  return response.json();
}

export async function fetchMinuteStrategies(): Promise<Strategy[]> {
  const response = await fetch(`${baseUrl}/api/v1/research/minute/strategies`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Failed to fetch minute strategies");
  }
  return response.json();
}

export async function fetchMinuteRows(
  asset = "BTC",
  limit = 200,
  start?: string,
  end?: string,
): Promise<MinuteResearchRow[]> {
  const params = new URLSearchParams({ asset, limit: String(limit) });
  if (start) params.set("start", start);
  if (end) params.set("end", end);
  const response = await fetch(`${baseUrl}/api/v1/research/minute/rows?${params.toString()}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Failed to fetch minute rows");
  }
  return response.json();
}

export async function buildMinuteRows(
  asset = "BTC",
  start?: string,
  end?: string,
  refresh = false,
): Promise<MinuteResearchRow[]> {
  const params = new URLSearchParams({ asset, refresh: String(refresh) });
  if (start) params.set("start", start);
  if (end) params.set("end", end);
  const response = await fetch(`${baseUrl}/api/v1/research/minute/build?${params.toString()}`, {
    method: "POST",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error("Failed to build minute rows");
  }
  return response.json();
}

export async function runMinuteBatch(
  asset = "BTC",
  timeframe = "crypto_5m",
  strategyName = "minute_momentum",
  limit = 500,
  start?: string,
  end?: string,
  refresh = false,
): Promise<MinuteBatchReport> {
  const params = new URLSearchParams({
    asset,
    timeframe,
    strategy_name: strategyName,
    limit: String(limit),
    refresh: String(refresh),
  });
  if (start) params.set("start", start);
  if (end) params.set("end", end);
  const response = await fetch(`${baseUrl}/api/v1/research/minute/run?${params.toString()}`, {
    method: "POST",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error("Failed to run minute batch");
  }
  return response.json();
}

export async function fetchMinuteResults(timeframe?: string): Promise<MinuteBatchReport[]> {
  const params = new URLSearchParams();
  if (timeframe) params.set("timeframe", timeframe);
  const url = params.toString()
    ? `${baseUrl}/api/v1/research/minute/results?${params.toString()}`
    : `${baseUrl}/api/v1/research/minute/results`;
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Failed to fetch minute results");
  }
  return response.json();
}

export async function runMinuteValidationBatch(
  asset = "BTC",
  timeframe?: string,
  strategyName = "minute_momentum",
  limit = 50,
  start?: string,
  end?: string,
  refresh = false,
): Promise<MinuteBatchReport> {
  const params = new URLSearchParams({ asset, strategy_name: strategyName, limit: String(limit), refresh: String(refresh) });
  if (timeframe) params.set("timeframe", timeframe);
  if (start) params.set("start", start);
  if (end) params.set("end", end);
  const response = await fetch(`${baseUrl}/api/v1/research/validation/run?${params.toString()}`, {
    method: "POST",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error("Failed to run minute validation batch");
  }
  return response.json();
}

export async function fetchMinuteValidationResults(timeframe?: string): Promise<MinuteBatchReport[]> {
  const params = new URLSearchParams();
  if (timeframe) params.set("timeframe", timeframe);
  const url = params.toString()
    ? `${baseUrl}/api/v1/research/validation/results?${params.toString()}`
    : `${baseUrl}/api/v1/research/validation/results`;
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Failed to fetch minute validation results");
  }
  return response.json();
}

export async function fetchSyntheticSamples(asset?: string, timeframe?: string, limit = 100, start?: string, end?: string): Promise<SyntheticMarketSample[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (asset) params.set("asset", asset);
  if (timeframe) params.set("timeframe", timeframe);
  if (start) params.set("start", start);
  if (end) params.set("end", end);
  const response = await fetch(`${baseUrl}/api/v1/research/synthetic/samples?${params.toString()}`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Failed to fetch synthetic samples");
  }
  return response.json();
}

export async function buildSyntheticSamples(asset?: string, timeframe?: string, start?: string, end?: string): Promise<SyntheticMarketSample[]> {
  const params = new URLSearchParams();
  if (asset) params.set("asset", asset);
  if (timeframe) params.set("timeframe", timeframe);
  if (start) params.set("start", start);
  if (end) params.set("end", end);
  const response = await fetch(`${baseUrl}/api/v1/research/synthetic/build?${params.toString()}`, {
    method: "POST",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error("Failed to build synthetic samples");
  }
  return response.json();
}

export async function runSyntheticBatch(
  asset?: string,
  timeframe?: string,
  strategyName = "synthetic_momentum",
  decisionTime = "open",
  limit = 200,
  start?: string,
  end?: string,
): Promise<SyntheticBatchReport> {
  const params = new URLSearchParams({ strategy_name: strategyName, decision_time: decisionTime, limit: String(limit) });
  if (asset) params.set("asset", asset);
  if (timeframe) params.set("timeframe", timeframe);
  if (start) params.set("start", start);
  if (end) params.set("end", end);
  const response = await fetch(`${baseUrl}/api/v1/research/synthetic/run?${params.toString()}`, {
    method: "POST",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error("Failed to run synthetic batch");
  }
  return response.json();
}

export async function fetchSyntheticResults(): Promise<SyntheticBatchReport[]> {
  const response = await fetch(`${baseUrl}/api/v1/research/synthetic/results`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Failed to fetch synthetic results");
  }
  return response.json();
}

export async function runRealValidationBatch(
  asset = "BTC",
  timeframe?: string,
  strategyName = "synthetic_momentum",
  limit = 50,
  start?: string,
  end?: string,
): Promise<SyntheticBatchReport> {
  const params = new URLSearchParams({ asset, strategy_name: strategyName, limit: String(limit) });
  if (timeframe) params.set("timeframe", timeframe);
  if (start) params.set("start", start);
  if (end) params.set("end", end);
  const response = await fetch(`${baseUrl}/api/v1/research/validation/run?${params.toString()}`, {
    method: "POST",
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error("Failed to run real validation batch");
  }
  return response.json();
}

export async function fetchValidationResults(): Promise<SyntheticBatchReport[]> {
  const response = await fetch(`${baseUrl}/api/v1/research/validation/results`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Failed to fetch validation results");
  }
  return response.json();
}

export async function runBacktest(
  marketId: string,
  strategyName: string,
): Promise<BacktestReport> {
  const response = await fetch(
    `${baseUrl}/api/v1/backtests/${marketId}?strategy_name=${encodeURIComponent(strategyName)}`,
    {
      method: "POST",
      cache: "no-store",
    },
  );
  if (!response.ok) {
    throw new Error("Failed to run backtest");
  }
  return response.json();
}

export async function fetchBacktests(): Promise<BacktestReport[]> {
  const response = await fetch(`${baseUrl}/api/v1/backtests`, { cache: "no-store" });
  if (!response.ok) {
    throw new Error("Failed to fetch backtests");
  }
  return response.json();
}

export async function fetchPaperBlotter(): Promise<
  {
    ts: string;
    market_id: string;
    action: string;
    side: string;
    price: number;
    size: number;
    status: string;
  }[]
> {
  const response = await fetch(`${baseUrl}/api/v1/paper-trading/blotter`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error("Failed to fetch blotter");
  }
  return response.json();
}

export async function fetchPaperStatus(): Promise<PaperStatus> {
  const response = await fetch(`${baseUrl}/api/v1/paper-trading/status`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error("Failed to fetch paper trading status");
  }
  return response.json();
}

export async function fetchExecutionStatus(): Promise<ExecutionStatus> {
  const response = await fetch(`${baseUrl}/api/v1/execution/status`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error("Failed to fetch execution status");
  }
  return response.json();
}

export async function fetchDashboardSummary(): Promise<DashboardSummary> {
  const response = await fetch(`${baseUrl}/api/v1/dashboard/summary`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error("Failed to fetch dashboard summary");
  }
  return response.json();
}
