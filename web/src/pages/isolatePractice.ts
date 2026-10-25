import type { JobResponse } from "../api";
import type { AnalysisData, TabData } from "../mixer/analysis";

function isRecord(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

function isAnalysis(value: unknown): value is AnalysisData {
  return isRecord(value);
}

function isTab(value: unknown): value is TabData {
  return isRecord(value) && Array.isArray(value.measures);
}

/** Analysis and tab already stored on the job. Artifact URLs stay out. */
export function practiceFromJob(job: JobResponse | null | undefined): {
  analysis?: AnalysisData;
  tab?: TabData;
} {
  if (!job) return {};
  const extra = job as JobResponse & { analysis?: unknown; tab?: unknown };
  const analysis = isAnalysis(extra.analysis) ? extra.analysis : undefined;
  const tab = isTab(extra.tab) ? extra.tab : undefined;
  if (!analysis && !tab) return {};
  return { ...(analysis ? { analysis } : {}), ...(tab ? { tab } : {}) };
}
