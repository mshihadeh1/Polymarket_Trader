import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Polymarket Trader",
  description: "Research-first Polymarket monitoring and replay platform",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
