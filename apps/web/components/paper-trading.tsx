import { fetchPaperBlotter, fetchPaperStatus } from "../lib/api";

export async function PaperTradingPanel() {
  const [status, blotter] = await Promise.all([
    fetchPaperStatus(),
    fetchPaperBlotter(),
  ]);

  return (
    <div className="page-grid">
      <section className="panel">
        <div className="section-head">
          <h1>Paper trading</h1>
          <p className="muted">Dry-run only. Live execution remains opt-in and disabled.</p>
        </div>
        <div className="stack">
          <div className="list-card">
            <strong>Strategy</strong>
            <span>{status.strategy_name}</span>
          </div>
          <div className="list-card">
            <strong>Realized PnL</strong>
            <span>{status.realized_pnl.toFixed(2)}</span>
          </div>
          <div className="list-card">
            <strong>Open positions</strong>
            <span>{Object.keys(status.open_positions).length}</span>
          </div>
        </div>
      </section>

      <section className="panel span-2">
        <div className="section-head">
          <h2>Blotter</h2>
        </div>
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
                <td>{new Date(entry.ts).toLocaleString()}</td>
                <td>{entry.market_id}</td>
                <td>{entry.action}</td>
                <td>{entry.side}</td>
                <td>{entry.price.toFixed(2)}</td>
                <td>{entry.size}</td>
                <td>{entry.status}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
