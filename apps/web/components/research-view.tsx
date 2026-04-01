"use client";

import { useMemo, useState, useTransition } from "react";

import {
  buildSyntheticSamples,
  fetchResearchStrategies,
  runRealValidationBatch,
  runSyntheticBatch,
  type Strategy,
  type SyntheticBatchReport,
  type SyntheticMarketSample,
} from "../lib/api";
import { formatLosAngelesDateTime } from "../lib/time";

function metric(report: SyntheticBatchReport | undefined, label: string): number {
  return report?.metrics.find((item) => item.label === label)?.value ?? 0;
}

function pct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export function ResearchView({
  initialSamples,
  initialSyntheticReports,
  initialValidationReports,
  initialStrategies,
}: {
  initialSamples: SyntheticMarketSample[];
  initialSyntheticReports: SyntheticBatchReport[];
  initialValidationReports: SyntheticBatchReport[];
  initialStrategies: Strategy[];
}) {
  const [samples, setSamples] = useState(initialSamples);
  const [syntheticReports, setSyntheticReports] = useState(initialSyntheticReports);
  const [validationReports, setValidationReports] = useState(initialValidationReports);
  const [strategies] = useState(initialStrategies);
  const [asset, setAsset] = useState("BTC");
  const [timeframe, setTimeframe] = useState<"all" | "crypto_5m" | "crypto_15m">("all");
  const [strategyName, setStrategyName] = useState(initialStrategies[0]?.name ?? "synthetic_momentum");
  const [decisionTime, setDecisionTime] = useState("open");
  const [startTime, setStartTime] = useState(defaultRangeStart());
  const [endTime, setEndTime] = useState(defaultRangeEnd());
  const [isPending, startTransition] = useTransition();
  const latestSynthetic = syntheticReports[0];
  const latestValidation = validationReports[0];

  const filteredSamples = useMemo(() => {
    return samples.filter((sample) => sample.asset === asset && (timeframe === "all" || sample.timeframe === timeframe));
  }, [asset, samples, timeframe]);

  const onBuildSynthetic = () => {
    startTransition(async () => {
      const next = await buildSyntheticSamples(asset, timeframe === "all" ? undefined : timeframe, toIso(startTime), toIso(endTime));
      setSamples(next);
    });
  };

  const onRunSynthetic = () => {
    startTransition(async () => {
      const report = await runSyntheticBatch(asset, timeframe === "all" ? undefined : timeframe, strategyName, decisionTime, 200, toIso(startTime), toIso(endTime));
      setSyntheticReports((current) => [report, ...current.filter((item) => item.run_id !== report.run_id)]);
    });
  };

  const onRunValidation = () => {
    startTransition(async () => {
      const report = await runRealValidationBatch(asset, timeframe === "all" ? undefined : timeframe, strategyName, 50, toIso(startTime), toIso(endTime));
      setValidationReports((current) => [report, ...current.filter((item) => item.run_id !== report.run_id)]);
    });
  };

  return (
    <div className="page-grid page-shell">
      <section className="panel span-2">
        <div className="section-head">
          <p className="eyebrow">Synthetic research</p>
          <div className="hero-title-row">
            <h1>BTC up/down discovery lab</h1>
            <div className="badge-stack">
              <span className="badge badge-historical">layer 1 synthetic</span>
              <span className="badge badge-real">layer 2 real validation</span>
            </div>
          </div>
          <p className="muted">
            Generate aligned 1-minute BTC/ETH/SOL windows, score simple strategy families, and compare the synthetic edge to real closed Polymarket BTC markets.
          </p>
        </div>

        <div className="edge-card-grid">
          <div className="metric-card">
            <span className="metric-label">Synthetic samples</span>
            <span className="metric-value">{samples.length}</span>
            <span className="muted">Cached locally and persisted when available.</span>
          </div>
          <div className="metric-card">
            <span className="metric-label">Latest synthetic hit rate</span>
            <span className="metric-value">{latestSynthetic ? pct(metric(latestSynthetic, "hit_rate")) : "n/a"}</span>
            <span className="muted">Bars-only synthetic history.</span>
          </div>
          <div className="metric-card">
            <span className="metric-label">Latest validation hit rate</span>
            <span className="metric-value">{latestValidation ? pct(metric(latestValidation, "hit_rate")) : "n/a"}</span>
            <span className="muted">Real closed Polymarket BTC markets.</span>
          </div>
          <div className="metric-card">
            <span className="metric-label">Strategies</span>
            <span className="metric-value">{strategies.length}</span>
            <span className="muted">Momentum, mean reversion, breakout, regime filter.</span>
          </div>
        </div>

        <div className="badge-stack">
          <button className="badge badge-type" onClick={onBuildSynthetic} disabled={isPending}>
            {isPending ? "working..." : "build synthetic dataset"}
          </button>
          <button className="badge badge-provider" onClick={onRunSynthetic} disabled={isPending}>
            run synthetic batch
          </button>
          <button className="badge badge-real" onClick={onRunValidation} disabled={isPending}>
            run real validation
          </button>
        </div>
      </section>

      <section className="panel">
        <div className="section-head">
          <h2>Run controls</h2>
          <p className="muted">Pick an asset, timeframe, and strategy family.</p>
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
            <span className="metric-label">Timeframe</span>
            <select className="research-select" value={timeframe} onChange={(event) => setTimeframe(event.target.value as typeof timeframe)}>
              <option value="all">All</option>
              <option value="crypto_5m">BTC 5m</option>
              <option value="crypto_15m">BTC 15m</option>
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
            <span className="metric-label">Decision time</span>
            <select className="research-select" value={decisionTime} onChange={(event) => setDecisionTime(event.target.value)}>
              <option value="open">open</option>
              <option value="+1m">+1m</option>
              <option value="+2m">+2m</option>
              <option value="+3m">+3m</option>
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
          <p className="muted">The same strategies are scored first on the synthetic layer and then on recent real closed markets.</p>
        </div>
        <div className="edge-card-grid">
          <div className="metric-card">
            <span className="metric-label">Synthetic report</span>
            <span className="metric-value">{latestSynthetic?.strategy_name ?? "none"}</span>
            <span className="muted">{latestSynthetic ? `${latestSynthetic.total_samples} samples | ${latestSynthetic.source}` : "Run a synthetic batch to populate this panel."}</span>
          </div>
          <div className="metric-card">
            <span className="metric-label">Validation report</span>
            <span className="metric-value">{latestValidation?.strategy_name ?? "none"}</span>
            <span className="muted">{latestValidation ? `${latestValidation.total_samples} closed markets | ${latestValidation.source}` : "Run real validation to populate this panel."}</span>
          </div>
        </div>
      </section>

      <section className="panel span-2">
        <div className="section-head">
          <h2>Cached samples</h2>
          <p className="muted">Synthetic BTC/ETH/SOL windows are stored once and reused across runs.</p>
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Sample</th>
                <th>Source</th>
                <th>Window</th>
                <th>Open</th>
                <th>Close</th>
                <th>Resolution</th>
              </tr>
            </thead>
            <tbody>
              {filteredSamples.length ? (
                filteredSamples.slice(0, 20).map((sample) => (
                  <tr key={sample.sample_id}>
                    <td>
                      <div className="market-title-cell">
                        <span className="market-name">{sample.sample_id}</span>
                        <div className="badge-stack">
                          <span className="badge badge-type">{sample.asset}</span>
                          <span className="badge badge-provider">{sample.timeframe}</span>
                        </div>
                      </div>
                    </td>
                    <td>
                      <span className={`badge ${sample.source === "synthetic" ? "badge-historical" : "badge-real"}`}>
                        {sample.source}
                      </span>
                    </td>
                    <td>{sample.decision_horizon_minutes}m</td>
                    <td>{formatLosAngelesDateTime(sample.market_open_time)}</td>
                    <td>{formatLosAngelesDateTime(sample.market_close_time)}</td>
                    <td>
                      <span className={`badge ${sample.actual_resolution === "yes" ? "badge-buy" : "badge-sell"}`}>
                        {sample.actual_resolution.toUpperCase()}
                      </span>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} className="muted">
                    No cached samples yet. Build the synthetic dataset to populate this table.
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
