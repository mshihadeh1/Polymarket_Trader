import { fetchExecutionStatus, fetchPaperBlotter, fetchPaperStatus } from "../lib/api";
import { formatLosAngelesDateTime, losAngelesTimeZoneLabel } from "../lib/time";

export async function PaperTradingPanel() {
  const [status, blotter, execution] = await Promise.all([
    fetchPaperStatus(),
    fetchPaperBlotter(),
    fetchExecutionStatus(),
  ]);

  return (
    <div className="page-grid page-shell">
      <section className="panel span-2">
        <div className="section-head">
          <p className="eyebrow">Dry-run desk</p>
          <div className="hero-title-row">
            <h1>Paper trading</h1>
            <div className="badge-stack">
              <span className="badge badge-historical">dry run only</span>
              <span className="badge badge-provider">{status.strategy_name}</span>
            </div>
          </div>
          <p className="muted">Dry-run only. Live execution remains opt-in and disabled.</p>
          <p className="muted">Times shown in {losAngelesTimeZoneLabel()}.</p>
        </div>
          <div className="quad-grid">
            <div className="metric-card">
              <span className="metric-label">Strategy</span>
              <span className="metric-value">{status.strategy_name}</span>
            </div>
            <div className="metric-card">
              <span className="metric-label">Loop health</span>
              <span className="metric-value">{status.loop_running ? "Running" : "Stopped"}</span>
            </div>
            <div className="metric-card">
              <span className="metric-label">Realized PnL</span>
              <span className="metric-value">{status.realized_pnl.toFixed(2)}</span>
            </div>
            <div className="metric-card">
              <span className="metric-label">Unrealized PnL</span>
              <span className="metric-value">{status.unrealized_pnl.toFixed(2)}</span>
            </div>
            <div className="metric-card">
              <span className="metric-label">Open positions</span>
              <span className="metric-value">{Object.keys(status.open_positions).length}</span>
            </div>
            <div className="metric-card">
              <span className="metric-label">Signal fill rate</span>
              <span className="metric-value">{(status.fill_rate * 100).toFixed(1)}%</span>
            </div>
          </div>
      </section>

      <section className="panel">
        <div className="section-head">
          <h2>Session state</h2>
          <p className="muted">Quick visibility into the current dry-run process.</p>
        </div>
        <div className="stack">
          <div className="list-card">
            <strong>Active markets</strong>
            <span>{status.active_market_ids.length}</span>
          </div>
          <div className="list-card">
            <strong>Selected markets</strong>
            <span className="table-meta">{status.selected_market_ids.join(", ") || "none"}</span>
          </div>
          <div className="list-card">
            <strong>Mode</strong>
            <span>{status.dry_run_only ? "Dry run" : "Live"}</span>
          </div>
          <div className="list-card">
            <strong>Last update</strong>
            <span>{formatLosAngelesDateTime(status.last_update_at)}</span>
          </div>
          <div className="list-card">
            <strong>Cycles</strong>
            <span>{status.cycle_count}</span>
          </div>
          <div className="list-card">
            <strong>Signals / fills</strong>
            <span>{status.signal_count} / {status.simulated_fill_count} / blocked {status.blocked_signal_count}</span>
          </div>
          <div className="list-card">
            <strong>Market refresh</strong>
            <span>{status.market_refresh_count} / {formatLosAngelesDateTime(status.last_market_refresh_at)}</span>
          </div>
          <div className="list-card">
            <strong>Refresh error</strong>
            <span className="table-meta">{status.last_market_refresh_error || "none"}</span>
          </div>
          <div className="list-card">
            <strong>Loop error</strong>
            <span className="table-meta">{status.loop_error || "none"}</span>
          </div>
          <div className="list-card">
            <strong>Open position ids</strong>
            <span className="table-meta">{Object.keys(status.open_positions).join(", ") || "none"}</span>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="section-head">
          <h2>Execution scaffold</h2>
          <p className="muted">Live routing remains guarded, but the order ledger is ready for inspection.</p>
        </div>
        <div className="stack">
          <div className="signal-card">
            <span className="metric-label">Execution mode</span>
            <strong>{execution.enabled ? "Ready" : "Guarded"}</strong>
            <div className="badge-stack">
              <span className={`badge ${execution.enabled ? "badge-live" : "badge-pending"}`}>{execution.live_execution_enabled ? "live enabled" : "dry-run only"}</span>
              <span className="badge badge-provider">{execution.adapter_name ?? "no adapter"}</span>
            </div>
          </div>
          <div className="signal-card">
            <span className="metric-label">Orders / fills</span>
            <strong>{execution.order_count} / {execution.fill_count}</strong>
            <span className="muted">Fill rate {(execution.fill_rate * 100).toFixed(1)}%</span>
          </div>
          <div className="signal-card">
            <span className="metric-label">Last execution update</span>
            <strong>{execution.last_order_at ?? execution.last_fill_at ?? "none yet"}</strong>
            <span className="muted">{execution.message ?? "No execution message"}</span>
          </div>
        </div>
      </section>

      <section className="panel">
        <div className="section-head">
          <h2>Latest signal</h2>
          <p className="muted">Most recent loop decision for live observation.</p>
        </div>
        <div className="stack">
          {status.last_decision ? (
            <div className="list-card">
              <strong>{status.last_decision.side}</strong>
              <span className="muted">{status.last_decision.reason || "No reason provided"}</span>
              <span className="table-meta">
                signal {status.last_decision.signal_value?.toFixed(3) ?? "n/a"} | confidence {status.last_decision.confidence?.toFixed(2) ?? "n/a"}
              </span>
            </div>
          ) : (
            <div className="empty-state">No loop decision yet.</div>
          )}
          {status.latest_signals.slice(0, 4).map((signal) => (
            <div className="list-card" key={`${signal.market_id}-${signal.ts}`}>
              <strong>{signal.decision}</strong>
              <span className="table-meta">{signal.market_id}</span>
              <span className="muted">
                signal {signal.signal_value.toFixed(3)} | align {signal.flow_alignment_score?.toFixed(3) ?? "n/a"} | gap {signal.fair_value_gap?.toFixed(3) ?? "n/a"} | exec {signal.execution_price?.toFixed(3) ?? "n/a"}
              </span>
              <span className="muted">
                spread {signal.spread_bps?.toFixed(0) ?? "n/a"} bps | strike gap {signal.distance_to_threshold_bps?.toFixed(1) ?? "n/a"} bps | {signal.executed ? "executed" : signal.blocked_reason ?? "watching"}
              </span>
            </div>
          ))}
        </div>
      </section>

      <section className="panel span-2">
        <div className="section-head">
          <h2>Open positions</h2>
          <p className="muted">Current dry-run inventory and mark-to-market.</p>
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Market</th>
                <th>Side</th>
                <th>Size</th>
                <th>Avg price</th>
                <th>Mark</th>
                <th>Unrealized PnL</th>
              </tr>
            </thead>
            <tbody>
              {status.position_details.length ? status.position_details.map((position) => (
                <tr key={position.market_id}>
                  <td className="mono">{position.market_id}</td>
                  <td><span className={`badge ${position.side === "buy_yes" ? "badge-buy" : "badge-sell"}`}>{position.side}</span></td>
                  <td>{position.size.toFixed(0)}</td>
                  <td>{position.avg_price.toFixed(3)}</td>
                  <td>{position.mark_price.toFixed(3)}</td>
                  <td>{position.unrealized_pnl.toFixed(2)}</td>
                </tr>
              )) : (
                <tr>
                  <td colSpan={6} className="muted">No open dry-run positions.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel span-2">
        <div className="section-head">
          <h2>Blotter</h2>
          <p className="muted">Chronological dry-run decisions and fill outcomes.</p>
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Market</th>
                <th>Action</th>
                <th>Side</th>
                <th>Price</th>
                <th>Size</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {blotter.map((entry) => (
                <tr key={`${entry.market_id}-${entry.ts}-${entry.action}`}>
                  <td>{formatLosAngelesDateTime(entry.ts)}</td>
                  <td className="mono">{entry.market_id}</td>
                  <td>{entry.action}</td>
                  <td>
                    <span className={`badge ${entry.side.includes("yes") ? "badge-buy" : entry.side.includes("no") ? "badge-sell" : "badge-pending"}`}>{entry.side}</span>
                  </td>
                  <td>{entry.price.toFixed(2)}</td>
                  <td>{entry.size}</td>
                  <td>
                    <span className={`badge ${entry.status === "simulated_fill" ? "badge-positive" : "badge-pending"}`}>
                      {entry.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
