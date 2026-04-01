import { BacktestResults } from "../../components/backtest-results";

export default function BacktestsPage({
  searchParams,
}: {
  searchParams?: { asset?: string; timeframe?: string; limit?: string };
}) {
  return (
    <BacktestResults
      asset={searchParams?.asset}
      timeframe={searchParams?.timeframe}
      limit={searchParams?.limit ? Number(searchParams.limit) : undefined}
    />
  );
}
