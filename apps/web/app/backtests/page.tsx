import { BacktestResults } from "../../components/backtest-results";

export default async function BacktestsPage({
  searchParams,
}: {
  searchParams?: Promise<{ asset?: string; timeframe?: string; limit?: string }>;
}) {
  const params = await searchParams;
  return (
    <BacktestResults
      asset={params?.asset}
      timeframe={params?.timeframe}
      limit={params?.limit ? Number(params.limit) : undefined}
    />
  );
}
