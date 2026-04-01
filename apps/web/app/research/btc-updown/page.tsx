import {
  fetchResearchStrategies,
  fetchSyntheticResults,
  fetchSyntheticSamples,
  fetchValidationResults,
} from "../../../lib/api";
import { ResearchView } from "../../../components/research-view";

export default async function BtcUpDownResearchPage() {
  const [samples, syntheticResults, validationResults, strategies] = await Promise.all([
    fetchSyntheticSamples("BTC", undefined, 100),
    fetchSyntheticResults(),
    fetchValidationResults(),
    fetchResearchStrategies(),
  ]);

  return (
    <ResearchView
      initialSamples={samples}
      initialSyntheticReports={syntheticResults}
      initialValidationReports={validationResults}
      initialStrategies={strategies}
    />
  );
}
