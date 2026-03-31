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
};

export type PaperStatus = {
  strategy_name: string;
  dry_run_only: boolean;
  active_market_ids: string[];
  open_positions: Record<string, number>;
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
}> {
  const response = await fetch(`${baseUrl}/api/v1/system/health`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error("Failed to fetch system health");
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
