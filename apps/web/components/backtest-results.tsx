import Link from "next/link";

import { fetchClosedMarkets, fetchClosedMarketResults, fetchStrategies, runClosedMarketComparison } from "../lib/api";

function metric(report: Awaited<ReturnType<typeof fetchClosedMarketResults>>[number], label: string): string {
  const value = report.metrics.find((entry) => entry.label === label)?.value;
  return value === undefined ? "n/a" : value.toFixed(2);
}

export async function BacktestResults({
  asset = "BTC",
  timeframe = "crypto_5m",
  limit = 12,
}: {
  asset?: string;
  timeframe?: string;
  limit?: number;
}) {
  const [strategies, recentClosedMarkets, comparison, priorResults] = await Promise.all([
    fetchStrategies(),
    fetchClosedMarkets(asset, timeframe, limit),
    runClosedMarketComparison(asset, timeframe, limit),
    fetchClosedMarketResults(),
  ]);
  const latestResult = priorResults[0];

  return (
    <div className="page-grid page-shell">
      <section className="panel span-2">
        <div className="section-head">
          <p className="eyebrow">Closed-market evaluator</p>
          <div className="hero-title-row">
            <h1>Backtest results</h1>
            <div className="badge-stack">
              <span className="badge badge-provider">{asset}</span>
              <span className="badge badge-type">{timeframe}</span>
            </div>
          </div>
          <p className="muted">
            This page evaluates closed Polymarket markets using long-history bars as the base layer and recent Hyperliquid flow where available.
          </p>
        </div>
        <div className="badge-stack">
          <Link className="badge badge-type" href="/backtests?asset=BTC&timeframe=crypto_5m&limit=12">BTC 5m</Link>
          <Link className="badge badge-type" href="/backtests?asset=BTC&timeframe=crypto_15m&limit=12">BTC 15m</Link>
          <Link className="badge badge-type" href="/backtests?asset=ETH&timeframe=crypto_5m&limit=12">ETH 5m</Link>
          <Link className="badge badge-type" href="/backtests?asset=SOL&timeframe=crypto_5m&limit=12">SOL 5m</Link>
        </div>
        <div className="kpi-strip">
          <div className="kpi">
            <span className="metric-label">Closed markets</span>
            <strong>{recentClosedMarkets.length}</strong>
          </div>
          <div className="kpi">
            <span className="metric-label">Bars-only accuracy</span>
            <strong>{metric(comparison.bars_only, "accuracy")}</strong>
          </div>
          <div className="kpi">
            <span className="metric-label">Enriched accuracy</span>
            <strong>{metric(comparison.bars_plus_hyperliquid, "accuracy")}</strong>
          </div>
          <div className="kpi">
            <span className="metric-label">Coverage</span>
            <strong>{comparison.bars_plus_hyperliquid.total_markets_evaluated}</strong>
          </div>
        </div>
      </section>

      <section className="panel span-2">
        <div className="section-head">
          <h2>Model comparison</h2>
          <p className="muted">Bars-only baseline versus bars plus recent Hyperliquid enrichment.</p>
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Mode</th>
                <th>Markets</th>
                <th>Accuracy</th>
                <th>Avg confidence</th>
                <th>Score</th>
              </tr>
            </thead>
            <tbody>
              {[comparison.bars_only, comparison.bars_plus_hyperliquid].map((report) => (
                <tr key={report.run_id}>
                  <td>{report.mode}</td>
                  <td>{report.total_markets_evaluated}</td>
                  <td>{metric(report, "accuracy")}</td>
                  <td>{metric(report, "average_confidence")}</td>
                  <td>{metric(report, "simple_contract_score")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <div className="section-head">
          <h2>Coverage</h2>
          <p className="muted">How much Hyperliquid enrichment was actually available.</p>
        </div>
        <div className="stack">
          {Object.entries(comparison.bars_plus_hyperliquid.coverage).map(([label, value]) => (
            <div className="list-card" key={label}>
              <strong>{label}</strong>
              <span>{value}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="section-head">
          <h2>Recent closed markets</h2>
          <p className="muted">Closed Polymarket windows currently eligible for this evaluator.</p>
        </div>
        <div className="stack">
          {recentClosedMarkets.slice(0, 6).map((market) => (
            <div className="list-card" key={market.market_id}>
              <strong>{market.title}</strong>
              <span className="table-meta">{market.asset} | {market.timeframe}</span>
              <span className="muted">{new Date(market.market_close_time).toLocaleString()}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="panel span-2">
        <div className="section-head">
          <h2>Evaluation records</h2>
          <p className="muted">Per-market outcomes from the enriched comparison run.</p>
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Market</th>
                <th>Resolution</th>
                <th>Decision</th>
                <th>Confidence</th>
                <th>Correct</th>
                <th>Coverage</th>
              </tr>
            </thead>
            <tbody>
              {comparison.bars_plus_hyperliquid.records.map((record) => (
                <tr key={record.market_id}>
                  <td>
                    <div className="market-title-cell">
                      <span className="market-name">{record.market_slug}</span>
                      <div className="badge-stack">
                        <span className="badge badge-type">{record.asset}</span>
                        <span className="badge badge-provider">{record.timeframe}</span>
                      </div>
                    </div>
                  </td>
                  <td>{record.actual_resolution}</td>
                  <td>{record.final_decision}</td>
                  <td>{record.final_confidence.toFixed(2)}</td>
                  <td>{record.correctness === null ? "n/a" : record.correctness ? "yes" : "no"}</td>
                  <td>{record.enrichment_availability.notes[0] ?? "ok"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <div className="section-head">
          <h2>Strategy menu</h2>
          <p className="muted">Current strategies reused by both historical evaluation and live dry-run workflows.</p>
        </div>
        <div className="stack">
          {strategies.map((strategy) => (
            <div className="list-card" key={strategy.name}>
              <div className="badge-stack">
                <span className="badge badge-type">{strategy.family}</span>
              </div>
              <strong>{strategy.name}</strong>
              <span>{strategy.description}</span>
            </div>
          ))}
          {latestResult ? (
            <div className="list-card">
              <strong>Last stored batch</strong>
              <span className="muted">{latestResult.mode}</span>
              <span className="table-meta">{latestResult.run_id}</span>
            </div>
          ) : null}
        </div>
      </section>
    </div>
  );
}
