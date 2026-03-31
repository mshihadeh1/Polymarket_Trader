import Link from "next/link";

import { fetchFeatures, fetchMarketDetail } from "../lib/api";

function pct(value?: number): string {
  if (value === undefined || value === null) return "n/a";
  return `${(value * 100).toFixed(2)}%`;
}

export async function MarketDetail({ marketId }: { marketId: string }) {
  const [market, features] = await Promise.all([
    fetchMarketDetail(marketId),
    fetchFeatures(marketId),
  ]);
  const latestFeature = features.at(-1);

  return (
    <div className="page-grid">
      <section className="panel span-2">
        <div className="section-head">
          <p className="eyebrow">{market.market_type}</p>
          <h1>{market.title}</h1>
          <p className="muted">
            Underlying {market.underlying} • strike {market.price_to_beat ?? "n/a"} • close{" "}
            {market.closes_at ? new Date(market.closes_at).toLocaleString() : "n/a"}
          </p>
        </div>
        <div className="detail-grid">
          <div className="list-card">
            <strong>Polymarket</strong>
            <span>
              {market.latest_polymarket_orderbook?.best_bid?.toFixed(2)} /{" "}
              {market.latest_polymarket_orderbook?.best_ask?.toFixed(2)}
            </span>
            <span className="muted">
              size {market.latest_polymarket_orderbook?.bid_size} x{" "}
              {market.latest_polymarket_orderbook?.ask_size}
            </span>
          </div>
          <div className="list-card">
            <strong>{market.external_context?.provider ?? "External market"}</strong>
            <span>{market.external_context?.current_price?.toFixed(2) ?? "n/a"}</span>
            <span className="muted">since open {pct(market.external_context?.return_since_open)}</span>
          </div>
          <div className="list-card">
            <strong>Feature snapshot</strong>
            <span>Local CVD {latestFeature?.polymarket_cvd ?? "n/a"}</span>
            <span>External CVD {latestFeature?.external_cvd ?? "n/a"}</span>
            <span className="muted">Fair-value gap {pct(latestFeature?.fair_value_gap)}</span>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="section-head">
          <h2>Research links</h2>
        </div>
        <div className="stack">
          <Link className="list-card" href={`/replay?marketId=${marketId}`}>
            Open replay
          </Link>
          <Link className="list-card" href="/backtests">
            Open backtests
          </Link>
          <Link className="list-card" href="/paper-trading">
            Open paper trading
          </Link>
        </div>
      </section>

      <section className="panel span-2">
        <div className="section-head">
          <h2>Feature panel</h2>
          <p className="muted">Point-in-time snapshot series for local and external flow.</p>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Local CVD</th>
              <th>External CVD</th>
              <th>Fair Value</th>
              <th>Gap</th>
              <th>Lead/Lag</th>
              <th>Time to close</th>
            </tr>
          </thead>
          <tbody>
            {features.map((feature) => (
              <tr key={feature.ts}>
                <td>{new Date(feature.ts).toLocaleString()}</td>
                <td>{feature.polymarket_cvd}</td>
                <td>{feature.external_cvd}</td>
                <td>{feature.fair_value_estimate?.toFixed(3) ?? "n/a"}</td>
                <td>{feature.fair_value_gap?.toFixed(3) ?? "n/a"}</td>
                <td>{feature.lead_lag_gap?.toFixed(3) ?? "n/a"}</td>
                <td>{feature.time_to_close_seconds?.toFixed(0) ?? "n/a"}s</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
