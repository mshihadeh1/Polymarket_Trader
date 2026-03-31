import Link from "next/link";

import { fetchFeatures, fetchMarketDetail, fetchOrderBook, fetchSystemHealth, fetchTrades } from "../lib/api";

function pct(value?: number): string {
  if (value === undefined || value === null) return "n/a";
  return `${(value * 100).toFixed(2)}%`;
}

export async function MarketDetail({ marketId }: { marketId: string }) {
  const [market, features, trades, orderbook, health] = await Promise.all([
    fetchMarketDetail(marketId),
    fetchFeatures(marketId),
    fetchTrades(marketId),
    fetchOrderBook(marketId),
    fetchSystemHealth(),
  ]);
  const latestFeature = features.at(-1);
  const recentTrades = trades.polymarket.slice(-10).reverse();
  const latestBook = orderbook.polymarket.at(-1);
  const observation = health.polymarket_observation;

  return (
    <div className="page-grid page-shell">
      <section className="panel span-2">
        <div className="section-head">
          <p className="eyebrow">{market.market_type}</p>
          <div className="hero-title-row">
            <h1>{market.title}</h1>
            <div className="badge-stack">
              <span className="badge badge-type">{market.market_type}</span>
              <span className={`badge ${market.source === "real" ? "badge-real" : "badge-mock"}`}>
                {market.source ?? "unknown"}
              </span>
              <span className="badge badge-provider">{market.external_context?.provider ?? "external context"}</span>
              <span className={`badge ${observation.websocket_connected ? "badge-live" : "badge-pending"}`}>
                {observation.websocket_connected ? "live stream" : "stream pending"}
              </span>
            </div>
          </div>
          <p className="muted">
            Underlying {market.underlying} | strike {market.price_to_beat ?? "n/a"} | close{" "}
            {market.closes_at ? new Date(market.closes_at).toLocaleString() : "n/a"}
          </p>
        </div>
        <div className="detail-grid">
          <div className="metric-card">
            <span className="metric-label">Polymarket top of book</span>
            <span className="metric-value">
              {latestBook?.best_bid?.toFixed(2) ?? "n/a"} / {latestBook?.best_ask?.toFixed(2) ?? "n/a"}
            </span>
            <span className="muted">Local venue quote state for the selected contract.</span>
          </div>
          <div className="metric-card">
            <span className="metric-label">{market.external_context?.provider ?? "External market"}</span>
            <span className="metric-value">{market.external_context?.current_price?.toFixed(2) ?? "n/a"}</span>
            <span className="muted">Since open {pct(market.external_context?.return_since_open)}</span>
          </div>
          <div className="metric-card">
            <span className="metric-label">Feature snapshot</span>
            <span className="metric-value">{latestFeature?.fair_value_estimate?.toFixed(3) ?? "n/a"}</span>
            <span className="muted">Fair-value gap {pct(latestFeature?.fair_value_gap)}</span>
          </div>
          <div className="metric-card">
            <span className="metric-label">Observation stream</span>
            <span className="metric-value">{observation.last_event_at ? new Date(observation.last_event_at).toLocaleTimeString() : "n/a"}</span>
            <span className="muted">
              reconnects {observation.reconnect_count} | dropped {observation.dropped_event_count}
            </span>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="section-head">
          <h2>Recent trades</h2>
          <p className="muted">Most recent local prints on the selected Polymarket contract.</p>
        </div>
        <div className="stack">
          {recentTrades.length === 0 ? (
            <div className="empty-state">No local trade prints available yet.</div>
          ) : (
            recentTrades.map((trade, index) => (
              <div className="list-card" key={`${trade.ts}-${index}`}>
                <div className="badge-stack">
                  <span className={`badge ${trade.side === "buy" ? "badge-buy" : "badge-sell"}`}>{trade.side}</span>
                  <span className="badge badge-provider">{trade.venue}</span>
                </div>
                <strong>{trade.size} @ {trade.price.toFixed(3)}</strong>
                <span className="muted">{new Date(trade.ts).toLocaleString()}</span>
              </div>
            ))
          )}
        </div>
      </section>

      <section className="panel">
        <div className="section-head">
          <h2>Research links</h2>
          <p className="muted">Jump between replay, backtests, and paper monitoring without losing market context.</p>
        </div>
        <div className="stack">
          <Link className="list-card" href={`/replay?marketId=${marketId}`}>
            <strong>Open replay</strong>
            <span className="muted">Inspect the event stream for this market.</span>
          </Link>
          <Link className="list-card" href="/backtests">
            <strong>Open backtests</strong>
            <span className="muted">Compare baseline reports and strategy families.</span>
          </Link>
          <Link className="list-card" href="/paper-trading">
            <strong>Open paper trading</strong>
            <span className="muted">Track dry-run fills and current exposure.</span>
          </Link>
        </div>
      </section>

      <section className="panel span-2">
        <div className="section-head">
          <h2>Feature panel</h2>
          <p className="muted">Point-in-time local flow, external flow, and fair-value context in a research-table layout.</p>
        </div>
        <div className="table-wrap">
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
        </div>
      </section>
    </div>
  );
}
