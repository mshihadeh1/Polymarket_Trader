import { fetchMarkets, fetchReplay } from "../lib/api";
import { formatLosAngelesDateTime, losAngelesTimeZoneLabel } from "../lib/time";

type ReplayViewerProps = {
  marketId?: string;
};

export async function ReplayViewer({ marketId }: ReplayViewerProps) {
  const markets = await fetchMarkets();
  const selectedMarketId = marketId ?? markets[0]?.id;
  const selectedMarket = markets.find((market) => market.id === selectedMarketId);

  if (!selectedMarketId) {
    return <div className="panel">No replayable markets available.</div>;
  }

  const replay = await fetchReplay(selectedMarketId);

  return (
    <div className="page-grid page-shell">
      <section className="panel span-2">
        <div className="section-head">
          <p className="eyebrow">Replay terminal</p>
          <div className="hero-title-row">
            <h1>{selectedMarket?.title ?? "Historical replay"}</h1>
            <div className="badge-stack">
              <span className="badge badge-type">{selectedMarket?.market_type ?? "replay"}</span>
              <span className={`badge ${selectedMarket?.source === "real" ? "badge-real" : "badge-mock"}`}>
                {selectedMarket?.source ?? "unknown"}
              </span>
            </div>
          </div>
          <p className="muted">Event timeline for market <span className="mono">{selectedMarketId}</span>.</p>
          <p className="muted">Times shown in {losAngelesTimeZoneLabel()}.</p>
        </div>
        <div className="timeline-controls">
          <button type="button">Play</button>
          <button type="button">Pause</button>
          <button type="button">Step</button>
        </div>
        <div className="timeline">
          {replay.events.map((event, index) => (
            <div className="timeline-row" key={`${event.ts}-${index}`}>
              <div className="timeline-meta">
                <span className="event-type">{event.event_type}</span>
                <div className="badge-stack">
                  <span className={`badge ${event.venue === "polymarket" ? "badge-real" : "badge-provider"}`}>
                    {event.venue}
                  </span>
                  <span className="badge badge-historical">{formatLosAngelesDateTime(event.ts)}</span>
                </div>
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
          <div className="list-card">
            <strong>Signal lane</strong>
            <span className="muted">Future model scores and trigger overlays will sit here.</span>
          </div>
          <div className="list-card">
            <strong>Execution lane</strong>
            <span className="muted">Fill simulation and order decisions can be layered onto the same timeline.</span>
          </div>
          <div className="list-card">
            <strong>Feature lane</strong>
            <span className="muted">Snapshot overlays will stay visually separate from raw market events.</span>
          </div>
        </div>
      </section>
    </div>
  );
}
