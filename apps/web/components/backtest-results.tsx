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
  const totalTrades = allReports.reduce((sum, report) => sum + report.trade_count, 0);

  return (
    <div className="page-grid page-shell">
      <section className="panel span-2">
        <div className="section-head">
          <p className="eyebrow">Research lab</p>
          <div className="hero-title-row">
            <h1>Backtest results</h1>
            <div className="badge-stack">
              <span className="badge badge-provider">cost-aware</span>
              <span className="badge badge-historical">baseline runs</span>
            </div>
          </div>
          <p className="muted">
            Compare Polymarket-only, Hyperliquid-only, and combined feature strategies with cost-aware baseline metrics.
          </p>
        </div>
        <div className="kpi-strip">
          <div className="kpi">
            <span className="metric-label">Reports</span>
            <strong>{allReports.length}</strong>
          </div>
          <div className="kpi">
            <span className="metric-label">Strategies</span>
            <strong>{strategies.length}</strong>
          </div>
          <div className="kpi">
            <span className="metric-label">Simulated trades</span>
            <strong>{totalTrades}</strong>
          </div>
        </div>
        <div className="table-wrap">
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
                    <div className="market-title-cell">
                      <span className="market-name">{report.strategy_name}</span>
                      <div className="badge-stack">
                        <span className="badge badge-type">{report.market_id.slice(0, 8)}</span>
                        <span className="badge badge-provider">{report.run_id.slice(0, 8)}</span>
                      </div>
                    </div>
                  </td>
                  <td>{report.trade_count}</td>
                  <td>{metric(report, "net_pnl")}</td>
                  <td>{metric(report, "hit_rate")}</td>
                  <td>{metric(report, "expectancy_per_trade")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <div className="section-head">
          <h2>Strategy menu</h2>
          <p className="muted">Initial strategy registry exposed as a compact research menu.</p>
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
        </div>
      </section>
    </div>
  );
}
