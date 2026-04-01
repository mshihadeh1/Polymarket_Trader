import {
  fetchMinuteResults,
  fetchMinuteRows,
  fetchMinuteStrategies,
  fetchMinuteValidationResults,
} from "../../../lib/api";
import { ResearchView } from "../../../components/research-view";

export default async function BtcUpDownResearchPage() {
  const [rows, minuteResults, validationResults, strategies] = await Promise.all([
    fetchMinuteRows("BTC", 200),
    fetchMinuteResults(),
    fetchMinuteValidationResults(),
    fetchMinuteStrategies(),
  ]);

  return (
    <ResearchView
      initialRows={rows}
      initialMinuteReports={minuteResults}
      initialValidationReports={validationResults}
      initialStrategies={strategies}
    />
  );
}
