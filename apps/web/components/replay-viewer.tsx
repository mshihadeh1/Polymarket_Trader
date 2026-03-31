import { fetchMarkets, fetchReplay } from "../lib/api";

type ReplayViewerProps = {
  marketId?: string;
};

export async function ReplayViewer({ marketId }: ReplayViewerProps) {
  const markets = await fetchMarkets();
  const selectedMarketId = marketId ?? markets[0]?.id;

  if (!selectedMarketId) {
    return <div className="panel">No replayable markets available.</div>;
  }

  const replay = await fetchReplay(selectedMarketId);

  return (
    <div className="page-grid">
      <section className="panel span-2">
        <div className="section-head">
          <h1>Historical replay</h1>
          <p className="muted">
            Event timeline for market <code>{selectedMarketId}</code>.
          </p>
        </div>
        <div className="timeline-controls">
          <button type="button">Play</button>
          <button type="button">Pause</button>
          <button type="button">Step</button>
        </div>
        <div className="timeline">
          {replay.events.map((event, index) => (
            <div className="timeline-row" key={`${event.ts}-${index}`}>
              <div>
                <strong>{event.event_type}</strong>
                <div className="table-meta">{new Date(event.ts).toLocaleString()}</div>
              </div>
              <pre>{JSON.stringify(event.payload, null, 2)}</pre>
            </div>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="section-head">
          <h2>Replay notes</h2>
          <p className="muted">Designed for future signal and execution overlays.</p>
        </div>
        <div className="stack">
          <div className="list-card">Signal decision lane</div>
          <div className="list-card">Execution decision lane</div>
          <div className="list-card">Feature snapshot lane</div>
        </div>
      </section>
    </div>
  );
}
