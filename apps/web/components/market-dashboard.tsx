import Link from "next/link";

import { fetchMarkets, fetchPaperBlotter, fetchSystemHealth } from "../lib/api";

function formatTime(value?: string): string {
  if (!value) return "n/a";
  return new Date(value).toLocaleString();
}

export async function MarketDashboard() {
  const [markets, blotter, health] = await Promise.all([
    fetchMarkets(),
    fetchPaperBlotter(),
    fetchSystemHealth(),
  ]);
  const liveMarkets = markets.filter((market) => market.status === "active");
  const crypto5m = markets.filter((market) => market.market_type === "crypto_5m").length;
  const crypto15m = markets.filter((market) => market.market_type === "crypto_15m").length;

  return (
    <div className="page-grid page-shell">
      <section className="panel hero span-2">
        <div className="hero-grid">
          <div className="hero-copy">
            <div className="stack">
              <p className="eyebrow">Research-first Polymarket platform</p>
              <div className="hero-title-row">
                <h1>
                  Crypto microstructure
                  <br />
                  <span className="accent-text">research terminal</span>
                </h1>
                <div className="badge-stack">
                  <span className={`badge ${health.mock_polymarket ? "badge-mock" : "badge-real"}`}>
                    {health.mock_polymarket ? "mock venue" : "real venue"}
                  </span>
                  <span className="badge badge-provider">{health.polymarket_client}</span>
                </div>
              </div>
              <p className="muted">
                Monitor active Polymarket contracts, inspect local order flow, and keep replay,
                paper trading, and backtests inside one dark trading workspace.
              </p>
            </div>
            <div className="pill-row">
              <span className="pill pill-blue">Active markets {liveMarkets.length}</span>
              <span className="pill pill-purple">Crypto 5m {crypto5m}</span>
              <span className="pill pill-teal">Crypto 15m {crypto15m}</span>
            </div>
          </div>

          <div className="stack">
            <div className="metric-card">
              <span className="metric-label">Venue state</span>
              <span className="metric-value">{health.status}</span>
              <span className="muted">Clear source badges show when the desk is in mock mode versus a real venue path.</span>
            </div>
            <div className="kpi-strip">
              <div className="kpi">
                <span className="metric-label">Markets loaded</span>
                <strong>{health.markets_loaded}</strong>
              </div>
              <div className="kpi">
                <span className="metric-label">Source mode</span>
                <strong>{health.mock_polymarket ? "Mock" : "Real"}</strong>
              </div>
              <div className="kpi">
                <span className="metric-label">Paper fills</span>
                <strong>{blotter.length}</strong>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="section-head">
          <h2>Terminal status</h2>
          <p className="muted">The front page keeps the operator aware of venue state before drilling into a market.</p>
        </div>
        <div className="stack">
          <div className="signal-card">
            <span className="metric-label">Polymarket client</span>
            <strong>{health.polymarket_client}</strong>
            <div className="badge-stack">
              <span className={`badge ${health.mock_polymarket ? "badge-mock" : "badge-live"}`}>
                {health.mock_polymarket ? "mock feed" : "live feed"}
              </span>
              <span className="badge badge-historical">historical + replay</span>
            </div>
          </div>
          <div className="signal-card">
            <span className="metric-label">Desk focus</span>
            <strong>BTC / ETH short horizon</strong>
            <span className="muted">5-minute and 15-minute contracts stay front and center in the market table.</span>
          </div>
        </div>
      </section>

      <section className="panel span-2">
        <div className="section-head">
          <h2>Active markets</h2>
          <p className="muted">Current Polymarket contracts with quick access into detail and replay.</p>
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Market</th>
                <th>Type</th>
                <th>Status</th>
                <th>Close</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {markets.map((market) => (
                <tr key={market.id}>
                  <td>
                    <div className="market-title-cell">
                      <span className="market-name">{market.title}</span>
                      <div className="badge-stack">
                        <span className="badge badge-type">{market.market_type}</span>
                        <span className={`badge ${market.source === "real" ? "badge-real" : "badge-mock"}`}>
                          {market.source ?? "unknown"}
                        </span>
                      </div>
                      <div className="table-meta">{market.tags.join(" | ")}</div>
                    </div>
                  </td>
                  <td>{market.market_type}</td>
                  <td>{market.status}</td>
                  <td>{formatTime(market.closes_at)}</td>
                  <td>
                    <div className="table-actions">
                      <Link className="terminal-link" href={`/markets/${market.id}`}>Inspect</Link>
                      <Link className="terminal-link" href={`/replay?marketId=${market.id}`}>Replay</Link>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <div className="section-head">
          <h2>Paper blotter</h2>
          <p className="muted">Dry-run only. Live execution remains disabled.</p>
        </div>
        <div className="stack">
          {blotter.map((item) => (
            <div className="list-card" key={`${item.market_id}-${item.ts}`}>
              <div className="badge-stack">
                <span className={`badge ${item.side === "buy" ? "badge-buy" : "badge-sell"}`}>{item.side}</span>
                <span className="badge badge-provider">{item.action}</span>
              </div>
              <strong>{item.size} @ {item.price.toFixed(2)}</strong>
              <span className="muted">{formatTime(item.ts)}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="section-head">
          <h2>Operator panels</h2>
          <p className="muted">Research workflow shortcuts for detail, replay, backtests, and paper trading.</p>
        </div>
        <div className="stack">
          <Link className="list-card" href="/backtests">
            <strong>Backtest lab</strong>
            <span className="muted">Compare baseline reports and strategy families side by side.</span>
          </Link>
          <Link className="list-card" href="/paper-trading">
            <strong>Paper blotter</strong>
            <span className="muted">Track decisions, fills, and dry-run exposure.</span>
          </Link>
          <div className="list-card">
            <strong>Order-flow monitor</strong>
            <span className="muted">Market detail pages surface top-of-book, recent trades, and feature context.</span>
          </div>
        </div>
      </section>
    </div>
  );
}
