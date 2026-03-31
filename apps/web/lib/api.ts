export type Market = {
  id: string;
  event_id?: string;
  slug: string;
  title: string;
  category: string;
  market_type: string;
  underlying?: string;
  status: string;
  tags: string[];
  closes_at?: string;
  price_to_beat?: number;
  open_reference_price?: number;
};

export type ReplayEvent = {
  ts: string;
  event_type: "orderbook" | "trade";
  payload: Record<string, unknown>;
};

export type FeatureSnapshot = {
  market_id: string;
  ts: string;
  polymarket_cvd: number;
  hyperliquid_cvd: number;
  fair_value_estimate?: number;
  fair_value_gap?: number;
  external_return_since_open?: number;
  time_to_close_seconds?: number;
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
    open_price?: number;
    current_price?: number;
    return_since_open?: number;
    time_to_close_seconds?: number;
  };
  latest_polymarket_orderbook?: { best_bid: number; best_ask: number; bid_size: number; ask_size: number };
  latest_hyperliquid_orderbook?: { best_bid: number; best_ask: number; mid_price?: number };
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
