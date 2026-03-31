import { ReplayViewer } from "../../components/replay-viewer";

export default async function ReplayPage({
  searchParams,
}: {
  searchParams: Promise<{ marketId?: string }>;
}) {
  const params = await searchParams;
  return <ReplayViewer marketId={params.marketId} />;
}
