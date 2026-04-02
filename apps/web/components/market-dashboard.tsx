import Link from "next/link";

import {
  fetchDashboardSummary,
  fetchMarkets,
  fetchPaperBlotter,
  type DashboardResearchSlice,
} from "../lib/api";
import { formatLosAngelesDateTime, losAngelesTimeZoneLabel } from "../lib/time";

function formatTime(value?: string): string {
  return formatLosAngelesDateTime(value);
}

function dashboardHitRateLabel(hitRate: number, sampleSize: number): string {
  return sampleSize ? `${(hitRate * 100).toFixed(1)}%` : "n/a";
}

export async function MarketDashboard() {
  const [markets, blotter, summary] = await Promise.all([
    fetchMarkets(),
    fetchPaperBlotter(),
    fetchDashboardSummary(),
  ]);
  const liveMarkets = markets.filter((market) => market.status === "active");
  const crypto5m = markets.filter((market) => market.market_type === "crypto_5m").length;
  const crypto15m = markets.filter((market) => market.market_type === "crypto_15m").length;
  const btc5mMarket = markets.find((market) => market.underlying === "BTC" && market.market_type === "crypto_5m");
  const btc15mMarket = markets.find((market) => market.underlying === "BTC" && market.market_type === "crypto_15m");
  const observation = summary.observation;
  const execution = summary.execution;
  const paper = summary.paper;
  const btc5mBars = summary.research_slices.find((slice) => slice.timeframe === "crypto_5m" && slice.mode === "bars_only");
  const btc5mEnriched = summary.research_slices.find((slice) => slice.timeframe === "crypto_5m" && slice.mode === "bars_plus_hyperliquid");
  const btc15mBars = summary.research_slices.find((slice) => slice.timeframe === "crypto_15m" && slice.mode === "bars_only");
  const btc15mEnriched = summary.research_slices.find((slice) => slice.timeframe === "crypto_15m" && slice.mode === "bars_plus_hyperliquid");
  const selectedResearch: DashboardResearchSlice[] = summary.research_slices;

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
                  <span className={`badge ${summary.source_mode === "mock" ? "badge-mock" : "badge-real"}`}>
                    {summary.source_mode === "mock" ? "mock venue" : "real venue"}
                  </span>
                  <span className="badge badge-provider">{summary.polymarket_client}</span>
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
              <span className="metric-value">{summary.observation.websocket_connected ? "Live observation" : "Starting"}</span>
              <span className="muted">Clear source badges show when the desk is in mock mode versus a real venue path.</span>
            </div>
            <div className="kpi-strip">
              <div className="kpi">
                <span className="metric-label">Markets loaded</span>
                <strong>{markets.length}</strong>
              </div>
              <div className="kpi">
                <span className="metric-label">Source mode</span>
                <strong>{summary.source_mode === "mock" ? "Mock" : "Real"}</strong>
              </div>
              <div className="kpi">
                <span className="metric-label">External provider</span>
                <strong>{summary.historical_provider}</strong>
              </div>
              <div className="kpi">
                <span className="metric-label">Paper fills</span>
                <strong>{blotter.length}</strong>
              </div>
            </div>
            <div className="badge-stack">
              <span className={`badge ${observation.websocket_connected ? "badge-live" : "badge-pending"}`}>
                {observation.websocket_connected ? "websocket connected" : "awaiting live stream"}
              </span>
              <span className="badge badge-provider">reconnects {observation.reconnect_count}</span>
            </div>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="section-head">
          <h2>Observation status</h2>
          <p className="muted">Live-session health for a multi-hour monitoring run.</p>
        </div>
        <div className="stack">
            <div className="signal-card">
              <span className="metric-label">Polymarket client</span>
              <strong>{summary.polymarket_client}</strong>
              <div className="badge-stack">
                <span className={`badge ${summary.source_mode === "mock" ? "badge-mock" : "badge-live"}`}>
                  {summary.source_mode === "mock" ? "mock feed" : "live feed"}
                </span>
                <span className="badge badge-provider">{summary.historical_provider}</span>
                <span className={`badge ${summary.execution.enabled ? "badge-live" : "badge-pending"}`}>
                  {summary.execution.enabled ? "execution ready" : "execution guarded"}
                </span>
              </div>
            </div>
          <div className="signal-card">
            <span className="metric-label">Last event</span>
            <strong>{observation.last_event_at ? formatTime(observation.last_event_at) : "none yet"}</strong>
            <span className="muted">
              raw {observation.raw_event_count} | trades {observation.trade_event_count} | books {observation.book_event_count}
            </span>
          </div>
          <div className="signal-card">
            <span className="metric-label">Connection health</span>
            <strong>{observation.dropped_event_count} / {observation.duplicate_event_count}</strong>
            <span className="muted">
              dropped / duplicate
              <br />
              {observation.last_error ?? `last connect ${formatTime(observation.last_connect_at)}`}
            </span>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="section-head">
          <h2>Research edge board</h2>
          <p className="muted">Separate bars-only baseline from bars + Hyperliquid enrichment, with 5m and 15m tracked independently.</p>
        </div>
        <div className="stack">
          <Link className="list-card" href="/backtests?asset=BTC&timeframe=crypto_5m&limit=24">
            <div className="badge-stack">
              <span className={`badge ${(btc5mEnriched?.tone ?? "neutral") === "positive" ? "badge-positive" : (btc5mEnriched?.tone ?? "neutral") === "negative" ? "badge-negative" : (btc5mEnriched?.tone ?? "neutral") === "warning" ? "badge-historical" : "badge-pending"}`}>
                {btc5mEnriched?.verdict ?? "No data"}
              </span>
              <span className="badge badge-type">BTC 5m</span>
            </div>
            <strong>{dashboardHitRateLabel(btc5mEnriched?.hitRate ?? 0, btc5mEnriched?.sampleSize ?? 0)} hit rate over {btc5mEnriched?.sampleSize ?? 0} closed markets</strong>
            <span className="muted">
              bars-only {dashboardHitRateLabel(btc5mBars?.hitRate ?? 0, btc5mBars?.sampleSize ?? 0)} | enriched {dashboardHitRateLabel(btc5mEnriched?.hitRate ?? 0, btc5mEnriched?.sampleSize ?? 0)}
            </span>
          </Link>
          <Link className="list-card" href="/backtests?asset=BTC&timeframe=crypto_15m&limit=24">
            <div className="badge-stack">
              <span className={`badge ${(btc15mEnriched?.tone ?? "neutral") === "positive" ? "badge-positive" : (btc15mEnriched?.tone ?? "neutral") === "negative" ? "badge-negative" : (btc15mEnriched?.tone ?? "neutral") === "warning" ? "badge-historical" : "badge-pending"}`}>
                {btc15mEnriched?.verdict ?? "No data"}
              </span>
              <span className="badge badge-type">BTC 15m</span>
            </div>
            <strong>{dashboardHitRateLabel(btc15mEnriched?.hitRate ?? 0, btc15mEnriched?.sampleSize ?? 0)} hit rate over {btc15mEnriched?.sampleSize ?? 0} closed markets</strong>
            <span className="muted">
              bars-only {dashboardHitRateLabel(btc15mBars?.hitRate ?? 0, btc15mBars?.sampleSize ?? 0)} | enriched {dashboardHitRateLabel(btc15mEnriched?.hitRate ?? 0, btc15mEnriched?.sampleSize ?? 0)}
            </span>
          </Link>
          <Link className="terminal-link" href="/backtests?asset=BTC&timeframe=all&limit=24">Open full edge workspace</Link>
        </div>
      </section>

      <section className="panel">
        <div className="section-head">
          <h2>BTC quick launch</h2>
          <p className="muted">One-click entry points for the two market families we want to observe live.</p>
        </div>
        <div className="stack">
          {btc5mMarket ? (
            <Link className="list-card" href={`/markets/${btc5mMarket.id}`}>
              <div className="badge-stack">
                <span className="badge badge-type">BTC 5m</span>
                <span className={`badge ${btc5mMarket.source === "real" ? "badge-real" : "badge-mock"}`}>
                  {btc5mMarket.source ?? "unknown"}
                </span>
              </div>
              <strong>{btc5mMarket.title}</strong>
              <span className="muted">Observe the live market detail panel.</span>
            </Link>
          ) : (
            <div className="empty-state">No BTC 5m market currently loaded.</div>
          )}
          {btc15mMarket ? (
            <Link className="list-card" href={`/markets/${btc15mMarket.id}`}>
              <div className="badge-stack">
                <span className="badge badge-type">BTC 15m</span>
                <span className={`badge ${btc15mMarket.source === "real" ? "badge-real" : "badge-mock"}`}>
                  {btc15mMarket.source ?? "unknown"}
                </span>
              </div>
              <strong>{btc15mMarket.title}</strong>
              <span className="muted">Keep this open in a second tab during the observation run.</span>
            </Link>
          ) : (
            <div className="empty-state">No BTC 15m market currently loaded.</div>
          )}
        </div>
      </section>

      <section className="panel">
        <div className="section-head">
          <h2>Desk focus</h2>
          <p className="muted">Observation mode stays centered on short-horizon crypto flow.</p>
        </div>
        <div className="stack">
          <div className="signal-card">
            <span className="metric-label">Selected markets</span>
            <strong>{observation.selected_market_count}</strong>
            <span className="muted">Assets subscribed: {observation.selected_asset_count}</span>
            <span className="muted">Signals {paper.signal_count} | simulated fills {paper.simulated_fill_count} | fill rate {(paper.fill_rate * 100).toFixed(1)}%</span>
          </div>
        </div>
      </section>

      <section className="panel span-2">
        <div className="section-head">
          <h2>Execution and paper quality</h2>
          <p className="muted">Separate the live routing scaffold from the dry-run paper loop.</p>
        </div>
        <div className="edge-card-grid">
          <div className="metric-card">
            <span className="metric-label">Paper win rate proxy</span>
            <span className="metric-value">{(paper.fill_rate * 100).toFixed(1)}%</span>
            <span className="muted">Simulated fills divided by live paper signals.</span>
          </div>
          <div className="metric-card">
            <span className="metric-label">Paper cycles</span>
            <span className="metric-value">{paper.cycle_count}</span>
            <span className="muted">Continuous loop iterations observed.</span>
          </div>
          <div className="metric-card">
            <span className="metric-label">Execution fill rate</span>
            <span className="metric-value">{(execution.fill_rate * 100).toFixed(1)}%</span>
            <span className="muted">{execution.fill_count} fills across {execution.order_count} orders.</span>
          </div>
          <div className="metric-card">
            <span className="metric-label">Execution mode</span>
            <span className="metric-value">{execution.enabled ? "Ready" : "Guarded"}</span>
            <span className="muted">{execution.message || "No message"}</span>
          </div>
        </div>
        {selectedResearch.length ? (
          <div className="table-wrap" style={{ marginTop: "1rem" }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Timeframe</th>
                  <th>Mode</th>
                  <th>Hit rate</th>
                  <th>Edge</th>
                  <th>Avg conf</th>
                  <th>Contract score</th>
                  <th>Verdict</th>
                </tr>
              </thead>
              <tbody>
                {selectedResearch.map((slice) => (
                  <tr key={`${slice.timeframe}-${slice.mode}`}>
                    <td>{slice.timeframe}</td>
                    <td>{slice.mode}</td>
                    <td>{dashboardHitRateLabel(slice.hit_rate, slice.sample_size)}</td>
                    <td>{slice.edge_over_50.toFixed(1)} pts</td>
                    <td>{(slice.avg_confidence * 100).toFixed(1)}%</td>
                    <td>{slice.contract_score.toFixed(0)}</td>
                    <td>{slice.verdict}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="empty-state">No research slices stored yet.</div>
        )}
      </section>

      <section className="panel span-2">
        <div className="section-head">
          <h2>Active markets</h2>
          <p className="muted">Current Polymarket contracts with quick access into detail and replay.</p>
          <p className="muted">Times shown in {losAngelesTimeZoneLabel()}.</p>
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
