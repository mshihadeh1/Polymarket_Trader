"use client";

import { useMemo, useState, useTransition } from "react";

import {
  buildMinuteRows,
  runMinuteBatch,
  runMinuteValidationBatch,
  type MinuteBatchReport,
  type MinuteResearchRow,
  type Strategy,
} from "../lib/api";
import { formatLosAngelesDateTime } from "../lib/time";

function metric(report: MinuteBatchReport | undefined, label: string): number {
  return report?.metrics.find((item) => item.label === label)?.value ?? 0;
}

function pct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export function ResearchView({
  initialRows,
  initialMinuteReports,
  initialValidationReports,
  initialStrategies,
}: {
  initialRows: MinuteResearchRow[];
  initialMinuteReports: MinuteBatchReport[];
  initialValidationReports: MinuteBatchReport[];
  initialStrategies: Strategy[];
}) {
  const [rows, setRows] = useState(initialRows);
  const [minuteReports, setMinuteReports] = useState(initialMinuteReports);
  const [validationReports, setValidationReports] = useState(initialValidationReports);
  const [strategies] = useState(initialStrategies);
  const [asset, setAsset] = useState("BTC");
  const [timeframe, setTimeframe] = useState<"all" | "crypto_5m" | "crypto_15m">("all");
  const [strategyName, setStrategyName] = useState(initialStrategies[0]?.name ?? "minute_momentum");
  const [startTime, setStartTime] = useState(defaultRangeStart());
  const [endTime, setEndTime] = useState(defaultRangeEnd());
  const [isPending, startTransition] = useTransition();

  const latest5m = minuteReports.find((report) => report.timeframe_filter === "crypto_5m");
  const latest15m = minuteReports.find((report) => report.timeframe_filter === "crypto_15m");
  const latestValidation5m = validationReports.find((report) => report.timeframe_filter === "crypto_5m");
  const latestValidation15m = validationReports.find((report) => report.timeframe_filter === "crypto_15m");

  const filteredRows = useMemo(() => {
    return rows.filter((row) => row.asset === asset);
  }, [asset, rows]);

  const onBuildRows = () => {
    startTransition(async () => {
      const next = await buildMinuteRows(asset, toIso(startTime), toIso(endTime), true);
      setRows(next);
    });
  };

  const onRunBatch = (selectedTimeframe: "crypto_5m" | "crypto_15m") => {
    startTransition(async () => {
      const report = await runMinuteBatch(asset, selectedTimeframe, strategyName, 500, toIso(startTime), toIso(endTime), false);
      setMinuteReports((current) => [report, ...current.filter((item) => item.run_id !== report.run_id)]);
    });
  };

  const onRunValidation = (selectedTimeframe: "crypto_5m" | "crypto_15m") => {
    startTransition(async () => {
      const report = await runMinuteValidationBatch(asset, selectedTimeframe, strategyName, 50, toIso(startTime), toIso(endTime), false);
      setValidationReports((current) => [report, ...current.filter((item) => item.run_id !== report.run_id)]);
    });
  };

  return (
    <div className="page-grid page-shell">
      <section className="panel span-2">
        <div className="section-head">
          <p className="eyebrow">Minute research</p>
          <div className="hero-title-row">
            <h1>BTC 5m / 15m edge lab</h1>
            <div className="badge-stack">
              <span className="badge badge-historical">layer 1 minute history</span>
              <span className="badge badge-real">layer 2 real validation</span>
            </div>
          </div>
          <p className="muted">
            Build minute-aligned BTC rows from your local 1-minute CSVs, score simple directional strategies, and compare the same logic against recent closed Polymarket markets.
          </p>
        </div>

        <div className="edge-card-grid">
          <div className="metric-card">
            <span className="metric-label">Minute rows</span>
            <span className="metric-value">{rows.length}</span>
            <span className="muted">Cached once and reused across runs.</span>
          </div>
          <div className="metric-card">
            <span className="metric-label">5m synthetic hit rate</span>
            <span className="metric-value">{latest5m ? pct(metric(latest5m, "hit_rate")) : "n/a"}</span>
            <span className="muted">Minute-level history, no lookahead.</span>
          </div>
          <div className="metric-card">
            <span className="metric-label">15m synthetic hit rate</span>
            <span className="metric-value">{latest15m ? pct(metric(latest15m, "hit_rate")) : "n/a"}</span>
            <span className="muted">Same strategy family, longer horizon.</span>
          </div>
          <div className="metric-card">
            <span className="metric-label">Real validation</span>
            <span className="metric-value">{latestValidation5m || latestValidation15m ? "cached" : "none"}</span>
            <span className="muted">Closed Polymarket BTC markets scored separately.</span>
          </div>
        </div>

        <div className="badge-stack">
          <button className="badge badge-type" onClick={onBuildRows} disabled={isPending}>
            {isPending ? "working..." : "build minute dataset"}
          </button>
          <button className="badge badge-provider" onClick={() => onRunBatch("crypto_5m")} disabled={isPending}>
            run 5m batch
          </button>
          <button className="badge badge-provider" onClick={() => onRunBatch("crypto_15m")} disabled={isPending}>
            run 15m batch
          </button>
          <button className="badge badge-real" onClick={() => onRunValidation("crypto_5m")} disabled={isPending}>
            validate 5m
          </button>
          <button className="badge badge-real" onClick={() => onRunValidation("crypto_15m")} disabled={isPending}>
            validate 15m
          </button>
        </div>
      </section>

      <section className="panel">
        <div className="section-head">
          <h2>Run controls</h2>
          <p className="muted">Choose the asset, strategy, and historical range.</p>
        </div>
        <div className="stack">
          <label className="list-card">
            <span className="metric-label">Asset</span>
            <select className="research-select" value={asset} onChange={(event) => setAsset(event.target.value)}>
              <option value="BTC">BTC</option>
              <option value="ETH">ETH</option>
              <option value="SOL">SOL</option>
            </select>
          </label>
          <label className="list-card">
            <span className="metric-label">Strategy</span>
            <select className="research-select" value={strategyName} onChange={(event) => setStrategyName(event.target.value)}>
              {strategies.map((strategy) => (
                <option key={strategy.name} value={strategy.name}>
                  {strategy.name}
                </option>
              ))}
            </select>
          </label>
          <label className="list-card">
            <span className="metric-label">Timeframe filter</span>
            <select className="research-select" value={timeframe} onChange={(event) => setTimeframe(event.target.value as typeof timeframe)}>
              <option value="all">All</option>
              <option value="crypto_5m">BTC 5m</option>
              <option value="crypto_15m">BTC 15m</option>
            </select>
          </label>
          <label className="list-card">
            <span className="metric-label">Start</span>
            <input className="research-select" type="datetime-local" value={startTime} onChange={(event) => setStartTime(event.target.value)} />
          </label>
          <label className="list-card">
            <span className="metric-label">End</span>
            <input className="research-select" type="datetime-local" value={endTime} onChange={(event) => setEndTime(event.target.value)} />
          </label>
        </div>
      </section>

      <section className="panel span-2">
        <div className="section-head">
          <h2>Latest reports</h2>
          <p className="muted">Synthetic discovery and real Polymarket validation stay separate.</p>
        </div>
        <div className="edge-card-grid">
          <div className="metric-card">
            <span className="metric-label">Synthetic 5m</span>
            <span className="metric-value">{latest5m?.strategy_name ?? "none"}</span>
            <span className="muted">{latest5m ? `${latest5m.total_rows} rows | ${pct(metric(latest5m, "hit_rate"))}` : "Run the 5m batch to populate this panel."}</span>
          </div>
          <div className="metric-card">
            <span className="metric-label">Synthetic 15m</span>
            <span className="metric-value">{latest15m?.strategy_name ?? "none"}</span>
            <span className="muted">{latest15m ? `${latest15m.total_rows} rows | ${pct(metric(latest15m, "hit_rate"))}` : "Run the 15m batch to populate this panel."}</span>
          </div>
          <div className="metric-card">
            <span className="metric-label">Validation 5m</span>
            <span className="metric-value">{latestValidation5m?.strategy_name ?? "none"}</span>
            <span className="muted">{latestValidation5m ? `${latestValidation5m.total_rows} markets | ${pct(metric(latestValidation5m, "hit_rate"))}` : "Run real validation for 5m markets."}</span>
          </div>
          <div className="metric-card">
            <span className="metric-label">Validation 15m</span>
            <span className="metric-value">{latestValidation15m?.strategy_name ?? "none"}</span>
            <span className="muted">{latestValidation15m ? `${latestValidation15m.total_rows} markets | ${pct(metric(latestValidation15m, "hit_rate"))}` : "Run real validation for 15m markets."}</span>
          </div>
        </div>
      </section>

      <section className="panel span-2">
        <div className="section-head">
          <h2>Recent minute rows</h2>
          <p className="muted">Each row is one decision minute with 5m and 15m labels already aligned.</p>
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Decision time</th>
                <th>Asset</th>
                <th>Reference</th>
                <th>5m label</th>
                <th>15m label</th>
                <th>5m return</th>
                <th>15m return</th>
              </tr>
            </thead>
            <tbody>
              {filteredRows.length ? (
                filteredRows.slice(0, 20).map((row) => (
                  <tr key={row.row_id}>
                    <td>{formatLosAngelesDateTime(row.decision_time)}</td>
                    <td>
                      <div className="market-title-cell">
                        <span className="market-name">{row.asset}</span>
                        <div className="badge-stack">
                          <span className="badge badge-type">{row.source}</span>
                          <span className="badge badge-provider">{row.source_provider}</span>
                        </div>
                      </div>
                    </td>
                    <td>{formatPrice(row.reference_price)}</td>
                    <td>
                      <span className={`badge ${row.label_up_5m ? "badge-buy" : "badge-sell"}`}>
                        {row.label_up_5m ? "UP" : "DOWN"}
                      </span>
                    </td>
                    <td>
                      <span className={`badge ${row.label_up_15m ? "badge-buy" : "badge-sell"}`}>
                        {row.label_up_15m ? "UP" : "DOWN"}
                      </span>
                    </td>
                    <td>{pct(row.future_return_5m)}</td>
                    <td>{pct(row.future_return_15m)}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={7} className="muted">
                    No minute rows cached yet. Build the dataset to populate this table.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function defaultRangeStart(): string {
  const value = new Date();
  value.setDate(value.getDate() - 14);
  return toLocalInputValue(value);
}

function defaultRangeEnd(): string {
  return toLocalInputValue(new Date());
}

function toLocalInputValue(value: Date): string {
  const local = new Date(value.getTime() - value.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

function toIso(value: string): string | undefined {
  if (!value) return undefined;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return undefined;
  return parsed.toISOString();
}

function formatPrice(value: number): string {
  if (Number.isInteger(value)) {
    return value.toFixed(0);
  }
  return value.toFixed(2);
}
