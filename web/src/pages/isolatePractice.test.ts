import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import type { JobResponse } from "../api";
import { practiceFromJob } from "./isolatePractice";

function job(extra: Record<string, unknown> = {}): JobResponse {
  return {
    id: "job",
    status: "succeeded",
    kind: "isolate",
    stage: "done",
    message: "",
    error: null,
    artifacts: { vocals: "/v1/artifacts/job/vocals", tab: "/v1/artifacts/job/tab" },
    ...extra,
  } as JobResponse;
}

describe("isolate practice payload", () => {
  it("ignores stem URLs and the plain-text tab artifact", () => {
    expect(practiceFromJob(job())).toEqual({});
  });

  it("passes analysis and measure JSON already on the job", () => {
    const analysis = { chords: [{ start: 0, end: 1, symbol: "Am" }] };
    const tab = { measures: [{ start: 0, end: 1, text: "e|--0--|" }] };
    expect(practiceFromJob(job({ analysis, tab }))).toEqual({ analysis, tab });
  });

  it("does not treat a tab URL as measures", () => {
    expect(practiceFromJob(job({ tab: "/v1/artifacts/job/tab" })).tab).toBeUndefined();
  });
});

describe("IsolatePage mounts the mixer for stems", () => {
  const page = readFileSync(resolve(process.cwd(), "src/pages/IsolatePage.tsx"), "utf-8");

  it("still requires a succeeded job with stems and does not require analysis", () => {
    expect(page).toContain('job?.status === "succeeded"');
    expect(page).toContain("stems.length > 0");
    expect(page).toContain("<StemMixer");
    expect(page).toContain("practiceFromJob");
    expect(page).not.toContain("load_analysis");
  });
});
