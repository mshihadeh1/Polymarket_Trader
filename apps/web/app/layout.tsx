import "./globals.css";
import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Polymarket Trader",
  description: "Research-first Polymarket monitoring and replay platform",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <div className="app-shell">
          <div className="page-shell">
            <header className="app-topbar">
              <div className="app-brand">
                <strong>Polymarket Trader</strong>
                <span>Dark research terminal for short-horizon crypto markets</span>
              </div>
              <nav className="app-nav" aria-label="Primary">
                <Link className="nav-link" href="/">Dashboard</Link>
                <Link className="nav-link" href="/research/btc-updown">Research</Link>
                <Link className="nav-link" href="/backtests">Backtests</Link>
                <Link className="nav-link" href="/paper-trading">Paper Trading</Link>
                <Link className="nav-link" href="/replay">Replay</Link>
              </nav>
            </header>
            {children}
          </div>
        </div>
      </body>
    </html>
  );
}
