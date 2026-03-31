import { fetchBacktests, fetchMarkets, fetchStrategies, runBacktest } from "../lib/api";

function metric(report: Awaited<ReturnType<typeof fetchBacktests>>[number], label: string): string {
  const value = report.metrics.find((entry) => entry.label === label)?.value;
  return value === undefined ? "n/a" : value.toFixed(2);
}

export async function BacktestResults() {
  const [markets, strategies, reports] = await Promise.all([
    fetchMarkets(),
    fetchStrategies(),
    fetchBacktests(),
  ]);
  const latestMarket = markets[0];
  const sampleRun =
    latestMarket !== undefined ? await runBacktest(latestMarket.id, "combined_cvd_gap") : null;
  const allReports = sampleRun
    ? [sampleRun, ...reports.filter((report) => report.run_id !== sampleRun.run_id)]
    : reports;

  return (
    <div className="page-grid">
      <section className="panel span-2">
        <div className="section-head">
          <h1>Backtest results</h1>
          <p className="muted">
            Compare Polymarket-only, Hyperliquid-only, and combined feature strategies with cost-aware baseline metrics.
          </p>
        </div>
        <table className="data-table">
          <thead>
            <tr>
              <th>Run</th>
              <th>Trades</th>
              <th>Net PnL</th>
              <th>Hit rate</th>
              <th>Expectancy</th>
            </tr>
          </thead>
          <tbody>
            {allReports.map((report) => (
              <tr key={report.run_id}>
                <td>
                  <strong>{report.strategy_name}</strong>
                  <div className="table-meta">{report.run_id}</div>
                </td>
                <td>{report.trade_count}</td>
                <td>{metric(report, "net_pnl")}</td>
                <td>{metric(report, "hit_rate")}</td>
                <td>{metric(report, "expectancy_per_trade")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="panel">
        <div className="section-head">
          <h2>Strategy menu</h2>
        </div>
        <div className="stack">
          {strategies.map((strategy) => (
            <div className="list-card" key={strategy.name}>
              <strong>{strategy.name}</strong>
              <span>{strategy.description}</span>
              <span className="muted">{strategy.family}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
