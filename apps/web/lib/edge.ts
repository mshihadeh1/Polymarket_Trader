import type { ClosedMarketBatchReport, ClosedMarketEvaluationRecord } from "./api";

export type EdgeVerdictTone = "positive" | "warning" | "negative" | "pending";

export type EdgeSlice = {
  timeframe: "crypto_5m" | "crypto_15m";
  label: string;
  sampleSize: number;
  wins: number;
  losses: number;
  unresolved: number;
  hitRate: number;
  averageConfidence: number;
  averageSignal: number;
  contractScore: number;
  contractScorePerMarket: number;
  edgePercent: number;
  verdict: string;
  summary: string;
  tone: EdgeVerdictTone;
  records: ClosedMarketEvaluationRecord[];
};

export function metricValue(report: ClosedMarketBatchReport, label: string): number {
  return report.metrics.find((entry) => entry.label === label)?.value ?? 0;
}

export function buildEdgeSlice(
  report: ClosedMarketBatchReport,
  timeframe: "crypto_5m" | "crypto_15m",
): EdgeSlice {
  const records = report.records.filter((record) => record.timeframe === timeframe);
  const wins = records.filter((record) => record.correctness === true).length;
  const losses = records.filter((record) => record.correctness === false).length;
  const unresolved = records.filter((record) => record.correctness === null).length;
  const sampleSize = records.length;
  const hitRate = sampleSize ? wins / sampleSize : 0;
  const averageConfidence = sampleSize
    ? records.reduce((sum, record) => sum + record.final_confidence, 0) / sampleSize
    : 0;
  const averageSignal = sampleSize
    ? records.reduce((sum, record) => sum + Math.abs(record.final_signal_value), 0) / sampleSize
    : 0;
  const contractScore = wins - losses;
  const contractScorePerMarket = sampleSize ? contractScore / sampleSize : 0;
  const edgePercent = sampleSize ? (hitRate - 0.5) * 100 : 0;
  const label = timeframe === "crypto_5m" ? "BTC 5m" : "BTC 15m";
  const verdictDetails = classifyEdge(sampleSize, hitRate);

  return {
    timeframe,
    label,
    sampleSize,
    wins,
    losses,
    unresolved,
    hitRate,
    averageConfidence,
    averageSignal,
    contractScore,
    contractScorePerMarket,
    edgePercent,
    verdict: verdictDetails.verdict,
    summary: verdictDetails.summary,
    tone: verdictDetails.tone,
    records,
  };
}

function classifyEdge(sampleSize: number, hitRate: number): {
  verdict: string;
  summary: string;
  tone: EdgeVerdictTone;
} {
  if (sampleSize === 0) {
    return {
      verdict: "No evidence yet",
      summary: "No closed markets evaluated for this window yet.",
      tone: "pending",
    };
  }
  if (sampleSize < 8) {
    return {
      verdict: "Too little history",
      summary: "Closed-market sample is too small to call an edge with confidence.",
      tone: "pending",
    };
  }
  if (sampleSize >= 20 && hitRate >= 0.58) {
    return {
      verdict: "Strong edge",
      summary: "Hit rate is materially above break-even with enough sample to matter.",
      tone: "positive",
    };
  }
  if (sampleSize >= 12 && hitRate >= 0.55) {
    return {
      verdict: "Building edge",
      summary: "The model is outperforming break-even, but still needs more closed markets.",
      tone: "warning",
    };
  }
  if (sampleSize >= 12 && hitRate <= 0.48) {
    return {
      verdict: "Negative edge",
      summary: "This setup is underperforming break-even and should not be trusted yet.",
      tone: "negative",
    };
  }
  return {
    verdict: "Unclear edge",
    summary: "Results are near break-even, so there is no reliable edge yet.",
    tone: "warning",
  };
}
