import { MarketDetail } from "../../../components/market-detail";

export default async function MarketDetailPage({
  params,
}: {
  params: Promise<{ marketId: string }>;
}) {
  const { marketId } = await params;
  return <MarketDetail marketId={marketId} />;
}
