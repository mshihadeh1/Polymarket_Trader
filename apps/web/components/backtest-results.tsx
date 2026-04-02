import Link from "next/link";

import {
  type ClosedMarketBatchReport,
  type ClosedMarketEvaluationRecord,
  fetchClosedMarketResults,
  findLatestClosedMarketReport,
  fetchStrategies,
} from "../lib/api";
import { buildEdgeSlice, metricValue, type EdgeSlice } from "../lib/edge";
import { formatLosAngelesDateTime, losAngelesTimeZoneLabel } from "../lib/time";

function pct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function maybePct(value: number, hasSample: boolean): string {
  return hasSample ? pct(value) : "n/a";
}

function signed(value: number, digits = 1): string {
  const prefix = value > 0 ? "+" : "";
  return `${prefix}${value.toFixed(digits)}`;
}

function verdictBadgeClass(tone: EdgeSlice["tone"]): string {
  if (tone === "positive") return "badge-positive";
  if (tone === "negative") return "badge-negative";
  if (tone === "warning") return "badge-historical";
  return "badge-pending";
}

function summarizeLift(enriched: EdgeSlice, baseline: EdgeSlice): string {
  if (enriched.sampleSize === 0 || baseline.sampleSize === 0) {
    return "No closed-market overlap yet between baseline and enriched runs.";
  }
  const hitRateLift = enriched.hitRate - baseline.hitRate;
  const contractLift = enriched.contractScore - baseline.contractScore;
  if (Math.abs(hitRateLift) < 0.005 && contractLift === 0) {
    return "Hyperliquid enrichment is currently not moving the result for this window.";
  }
  if (hitRateLift > 0) {
    return `Enrichment is improving hit rate by ${signed(hitRateLift * 100)} pts and contract score by ${signed(contractLift, 0)}.`;
  }
  return `Enrichment is reducing hit rate by ${signed(hitRateLift * 100)} pts and contract score by ${signed(contractLift, 0)}.`;
}

function recordBadge(record: ClosedMarketEvaluationRecord): string {
  if (record.correctness === true) return "badge-positive";
  if (record.correctness === false) return "badge-negative";
  return "badge-pending";
}

function decisionLabel(decision: string): string {
  if (decision === "buy_yes" || decision === "passive_yes") return "UP";
  if (decision === "buy_no" || decision === "passive_no") return "DOWN";
  return decision.toUpperCase();
}

function confidenceBucket(confidence: number): string {
  if (confidence >= 0.7) return "high conviction";
  if (confidence >= 0.58) return "medium conviction";
  return "low conviction";
}

function emptyBatchReport(mode: ClosedMarketBatchReport["mode"], asset: string): ClosedMarketBatchReport {
  return {
    run_id: `ui-empty-${mode}-${asset.toLowerCase()}`,
    strategy_name: "combined_cvd_gap",
    mode,
    asset_filter: asset,
    timeframe_filter: undefined,
    limit: 0,
    created_at: undefined,
    total_markets_evaluated: 0,
    metrics: [],
    coverage: {
      bars_only: 0,
      bars_plus_trades: 0,
      bars_plus_trades_plus_orderbook: 0,
    },
    records: [],
  };
}

function renderEvidenceTable(
  title: string,
  subtitle: string,
  slice: EdgeSlice,
  baselineSlice: EdgeSlice,
) {
  return (
    <section className="panel span-2">
      <div className="section-head">
        <h2>{title}</h2>
        <p className="muted">{subtitle}</p>
        <p className="muted">Times shown in {losAngelesTimeZoneLabel()}.</p>
      </div>

      <div className="edge-card-grid">
        <div className="metric-card edge-callout">
          <span className="metric-label">Verdict</span>
          <span className="metric-value">{slice.verdict}</span>
          <div className="badge-stack">
            <span className={`badge ${verdictBadgeClass(slice.tone)}`}>{slice.label}</span>
            <span className="badge badge-provider">{slice.sampleSize} closed markets</span>
            <span className="badge badge-type">{confidenceBucket(slice.averageConfidence)}</span>
          </div>
          <span className="muted">{slice.summary}</span>
          <span className="muted">{summarizeLift(slice, baselineSlice)}</span>
        </div>

        <div className="metric-card">
          <span className="metric-label">Hit rate</span>
          <span className="metric-value">{maybePct(slice.hitRate, slice.sampleSize > 0)}</span>
          <span className="muted">Break-even baseline is 50.0%.</span>
        </div>

        <div className="metric-card">
          <span className="metric-label">Edge over break-even</span>
          <span className="metric-value">{slice.sampleSize > 0 ? `${signed(slice.edgePercent)} pts` : "n/a"}</span>
          <span className="muted">Computed as hit rate minus 50%.</span>
        </div>

        <div className="metric-card">
          <span className="metric-label">Contract score</span>
          <span className="metric-value">{signed(slice.contractScore, 0)}</span>
          <span className="muted">
            Wins {slice.wins} | losses {slice.losses} | unresolved {slice.unresolved}
          </span>
        </div>

        <div className="metric-card">
          <span className="metric-label">Avg confidence</span>
          <span className="metric-value">{maybePct(slice.averageConfidence, slice.sampleSize > 0)}</span>
          <span className="muted">Average model confidence on final market call.</span>
        </div>

        <div className="metric-card">
          <span className="metric-label">Avg signal strength</span>
          <span className="metric-value">{slice.sampleSize > 0 ? slice.averageSignal.toFixed(3) : "n/a"}</span>
          <span className="muted">Absolute final signal value for this timeframe.</span>
        </div>
      </div>

      <div className="table-wrap edge-table">
        <table className="data-table">
          <thead>
            <tr>
              <th>Closed market</th>
              <th>Model call</th>
              <th>Actual</th>
              <th>Result</th>
              <th>Confidence</th>
              <th>Signal</th>
              <th>Feature edge</th>
              <th>Closed</th>
            </tr>
          </thead>
          <tbody>
            {slice.records.length ? (
              slice.records.map((record) => (
                <tr key={`${record.market_id}-${record.market_close_time}`}>
                  <td>
                    <div className="market-title-cell">
                      <span className="market-name">{record.market_slug}</span>
                      <div className="badge-stack">
                        <span className="badge badge-type">{record.asset}</span>
                        <span className="badge badge-provider">{record.timeframe}</span>
                      </div>
                      <div className="table-meta">
                        strike {record.strike_price?.toFixed(2) ?? "n/a"} | source {record.actual_resolution_source ?? "n/a"}
                      </div>
                    </div>
                  </td>
                  <td>
                    <span className={`badge ${record.final_decision.includes("yes") ? "badge-buy" : record.final_decision.includes("no") ? "badge-sell" : "badge-pending"}`}>
                      {decisionLabel(record.final_decision)}
                    </span>
                  </td>
                  <td>
                    <span className={`badge ${record.actual_resolution === "yes" ? "badge-buy" : record.actual_resolution === "no" ? "badge-sell" : "badge-pending"}`}>
                      {record.actual_resolution.toUpperCase()}
                    </span>
                  </td>
                  <td>
                    <span className={`badge ${recordBadge(record)}`}>
                      {record.correctness === true ? "Correct" : record.correctness === false ? "Miss" : "Open"}
                    </span>
                  </td>
                  <td>{pct(record.final_confidence)}</td>
                  <td>{record.final_signal_value.toFixed(3)}</td>
                  <td>
                    <div className="market-title-cell">
                      <span>fair value gap {(Number(record.feature_snapshot_summary.fair_value_gap) || 0).toFixed(3)}</span>
                      <span className="table-meta">
                        ext ret {(Number(record.feature_snapshot_summary.external_return_since_open) || 0).toFixed(4)}
                      </span>
                    </div>
                  </td>
                  <td>{formatLosAngelesDateTime(record.market_close_time)}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={8} className="muted">
                  No evaluated BTC {slice.timeframe === "crypto_5m" ? "5 minute" : "15 minute"} markets are available in stored results yet. Run or persist a comparison batch to populate this table.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function renderRunModePanel(
  title: string,
  report: ClosedMarketBatchReport,
  edge5m: EdgeSlice,
  edge15m: EdgeSlice,
) {
  const totalMarkets = report.total_markets_evaluated;
  const accuracy = metricValue(report, "accuracy");
  const averageConfidence = metricValue(report, "average_confidence");
  const simpleScore = metricValue(report, "simple_contract_score");

  return (
    <section className="panel">
      <div className="section-head">
        <h2>{title}</h2>
        <p className="muted">{report.mode === "bars_only" ? "Baseline using bars only." : "Comparison run with Hyperliquid enrichment."}</p>
      </div>
      <div className="stack">
        <div className="list-card">
          <strong>{totalMarkets}</strong>
          <span className="muted">closed markets evaluated</span>
        </div>
        <div className="list-card">
          <strong>{pct(accuracy)}</strong>
          <span className="muted">aggregate hit rate</span>
        </div>
        <div className="list-card">
          <strong>{pct(averageConfidence)}</strong>
          <span className="muted">average confidence</span>
        </div>
        <div className="list-card">
          <strong>{signed(simpleScore, 0)}</strong>
          <span className="muted">simple contract score</span>
        </div>
        <div className="list-card">
          <strong>{pct(edge5m.hitRate)}</strong>
          <span className="muted">BTC 5m hit rate</span>
        </div>
        <div className="list-card">
          <strong>{pct(edge15m.hitRate)}</strong>
          <span className="muted">BTC 15m hit rate</span>
        </div>
      </div>
    </section>
  );
}

export async function BacktestResults({
  asset = "BTC",
  timeframe = "all",
  limit = 24,
}: {
  asset?: string;
  timeframe?: string;
  limit?: number;
}) {
  const normalizedAsset = asset?.toUpperCase() ?? "BTC";
  const normalizedTimeframe = timeframe === "crypto_5m" || timeframe === "crypto_15m" ? timeframe : "all";

  const [strategies, priorResults] = await Promise.all([
    fetchStrategies(),
    fetchClosedMarketResults(),
  ]);
  const comparison = {
    bars_only:
      findLatestClosedMarketReport(priorResults, { mode: "bars_only", asset: normalizedAsset }) ??
      emptyBatchReport("bars_only", normalizedAsset),
    bars_plus_hyperliquid:
      findLatestClosedMarketReport(priorResults, { mode: "bars_plus_hyperliquid", asset: normalizedAsset }) ??
      emptyBatchReport("bars_plus_hyperliquid", normalizedAsset),
  };

  const enriched5m = buildEdgeSlice(comparison.bars_plus_hyperliquid, "crypto_5m");
  const enriched15m = buildEdgeSlice(comparison.bars_plus_hyperliquid, "crypto_15m");
  const bars5m = buildEdgeSlice(comparison.bars_only, "crypto_5m");
  const bars15m = buildEdgeSlice(comparison.bars_only, "crypto_15m");
  const latestResult = priorResults[0];
  const totalClosedBTC = comparison.bars_plus_hyperliquid.total_markets_evaluated || comparison.bars_only.total_markets_evaluated;

  const visibleSections =
    normalizedTimeframe === "crypto_5m"
      ? [{ enriched: enriched5m, bars: bars5m, title: "BTC 5 minute edge", subtitle: "Closed 5 minute markets, model calls, and outcome evidence." }]
      : normalizedTimeframe === "crypto_15m"
        ? [{ enriched: enriched15m, bars: bars15m, title: "BTC 15 minute edge", subtitle: "Closed 15 minute markets, model calls, and outcome evidence." }]
        : [
            { enriched: enriched5m, bars: bars5m, title: "BTC 5 minute edge", subtitle: "Closed 5 minute markets, model calls, and outcome evidence." },
            { enriched: enriched15m, bars: bars15m, title: "BTC 15 minute edge", subtitle: "Closed 15 minute markets, model calls, and outcome evidence." },
          ];

  return (
    <div className="page-grid page-shell">
      <section className="panel span-2">
        <div className="section-head">
        <p className="eyebrow">Closed-market evaluations</p>
        <div className="hero-title-row">
            <h1>Bitcoin closed-market evaluations</h1>
            <div className="badge-stack">
              <span className="badge badge-provider">{normalizedAsset}</span>
              <span className="badge badge-type">{normalizedTimeframe === "all" ? "5m + 15m" : normalizedTimeframe}</span>
              <span className="badge badge-historical">closed-market evidence</span>
            </div>
          </div>
          <p className="muted">
            This page shows closed BTC up/down evaluations. It emphasizes hit rate, sample size, and per-market evidence rather than raw backend objects or generic sequential backtests.
          </p>
        </div>

        <div className="badge-stack">
          <Link className="badge badge-type" href="/backtests?asset=BTC&timeframe=all&limit=24">BTC closed markets</Link>
          <Link className="badge badge-type" href="/backtests?asset=BTC&timeframe=crypto_5m&limit=24">BTC 5m closed markets</Link>
          <Link className="badge badge-type" href="/backtests?asset=BTC&timeframe=crypto_15m&limit=24">BTC 15m closed markets</Link>
          <Link className="badge badge-provider" href="/replay">Replay tape</Link>
        </div>

        <div className="edge-card-grid">
          <div className="metric-card edge-callout">
            <span className="metric-label">Current read</span>
            <span className="metric-value">
              {enriched5m.verdict === "Strong edge" || enriched15m.verdict === "Strong edge"
                ? "Actionable edge"
                : enriched5m.verdict === "Building edge" || enriched15m.verdict === "Building edge"
                  ? "Promising but early"
                  : "No proven edge yet"}
            </span>
            <span className="muted">
              BTC closed markets available: {totalClosedBTC}. Evaluated markets in enriched run: {comparison.bars_plus_hyperliquid.total_markets_evaluated}.
            </span>
            <span className="muted">
              Use the 5m and 15m sections below to inspect where the evidence is coming from and whether enrichment is actually helping.
            </span>
          </div>

          <div className="metric-card">
            <span className="metric-label">BTC 5m verdict</span>
            <span className="metric-value">{enriched5m.verdict}</span>
            <span className="muted">{enriched5m.summary}</span>
          </div>

          <div className="metric-card">
            <span className="metric-label">BTC 15m verdict</span>
            <span className="metric-value">{enriched15m.verdict}</span>
            <span className="muted">{enriched15m.summary}</span>
          </div>

          <div className="metric-card">
            <span className="metric-label">Enriched aggregate hit rate</span>
            <span className="metric-value">{pct(metricValue(comparison.bars_plus_hyperliquid, "accuracy"))}</span>
            <span className="muted">Across all evaluated BTC closed markets in this run.</span>
          </div>

          <div className="metric-card">
            <span className="metric-label">Bars-only aggregate hit rate</span>
            <span className="metric-value">{pct(metricValue(comparison.bars_only, "accuracy"))}</span>
            <span className="muted">Baseline without recent Hyperliquid enrichment.</span>
          </div>

          <div className="metric-card">
            <span className="metric-label">Edge lift</span>
            <span className="metric-value">
              {signed((metricValue(comparison.bars_plus_hyperliquid, "accuracy") - metricValue(comparison.bars_only, "accuracy")) * 100)} pts
            </span>
            <span className="muted">Difference in aggregate hit rate from baseline to enriched.</span>
          </div>
        </div>
      </section>

      {renderRunModePanel("Bars only baseline", comparison.bars_only, bars5m, bars15m)}
      {renderRunModePanel("Bars + Hyperliquid", comparison.bars_plus_hyperliquid, enriched5m, enriched15m)}

      {visibleSections.map((section) => (
        <div key={section.enriched.timeframe}>
          {renderEvidenceTable(
            section.title,
            section.subtitle,
            section.enriched,
            section.bars,
          )}
        </div>
      ))}

      <section className="panel">
        <div className="section-head">
          <h2>Strategy context</h2>
          <p className="muted">Current strategy inventory and the latest stored batch.</p>
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
              <span className="table-meta">
                {latestResult.run_id} | {formatLosAngelesDateTime(latestResult.created_at)}
              </span>
            </div>
          ) : (
            <div className="list-card">
              <strong>No stored batch yet</strong>
              <span className="muted">The API has not persisted a prior comparison run on this machine.</span>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
