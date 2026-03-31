import Link from "next/link";

import { fetchMarkets, fetchPaperBlotter } from "../lib/api";

function formatTime(value?: string): string {
  if (!value) return "n/a";
  return new Date(value).toLocaleString();
}

export async function MarketDashboard() {
  const [markets, blotter] = await Promise.all([fetchMarkets(), fetchPaperBlotter()]);

  return (
    <div className="page-grid">
      <section className="panel hero">
        <div>
          <p className="eyebrow">Research-first Polymarket platform</p>
          <h1>Active market monitor</h1>
          <p className="muted">
            Phase 1 focuses on ingesting active crypto markets, storing replayable
            event history, and giving the desk a clean operator view.
          </p>
        </div>
      </section>

      <section className="panel span-2">
        <div className="section-head">
          <h2>Active markets</h2>
          <p className="muted">Filter-ready table grouped for crypto 5m and 15m flows.</p>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Market</th>
              <th>Type</th>
              <th>Status</th>
              <th>Close</th>
              <th>Replay</th>
            </tr>
          </thead>
          <tbody>
            {markets.map((market) => (
              <tr key={market.id}>
                <td>
                  <strong>{market.title}</strong>
                  <div className="table-meta">{market.tags.join(" • ")}</div>
                </td>
                <td>{market.market_type}</td>
                <td>{market.status}</td>
                <td>{formatTime(market.closes_at)}</td>
                <td>
                  <div className="action-links">
                    <Link href={`/markets/${market.id}`}>Inspect</Link>
                    <Link href={`/replay?marketId=${market.id}`}>Replay</Link>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="panel">
        <div className="section-head">
          <h2>Paper blotter</h2>
          <p className="muted">Dry-run only. Live execution remains disabled.</p>
        </div>
        <div className="stack">
          {blotter.map((item) => (
            <div className="list-card" key={`${item.market_id}-${item.ts}`}>
              <strong>{item.action}</strong>
              <span>{item.side}</span>
              <span>
                {item.size} @ {item.price.toFixed(2)}
              </span>
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
          <Link className="list-card" href="/backtests">Backtest results page</Link>
          <Link className="list-card" href="/paper-trading">Paper trading page</Link>
          <div className="list-card">Order book and trade monitor</div>
          <div className="list-card">Fair value and feature panel</div>
          <div className="list-card">Strategy signal inspection</div>
        </div>
      </section>
    </div>
  );
}
