import { describe, expect, it } from "vitest";
import {
  fullFileTrimNotice,
  isolateRepairBody,
  isolateStartDisabled,
  isolateStartLabel,
} from "./isolateSubmit";

describe("hosted full-file cap notice", () => {
  it("tells the user a longer file will use the first N seconds", () => {
    expect(fullFileTrimNotice(180, 90, false)).toBe(
      "This mode uses the first 90 s of the file.",
    );
  });

  it("stays quiet for a short file, a section, or an unknown length", () => {
    expect(fullFileTrimNotice(60, 90, false)).toBeNull();
    expect(fullFileTrimNotice(180, 90, true)).toBeNull();
    expect(fullFileTrimNotice(null, 90, false)).toBeNull();
  });
});

describe("hosted isolate start button", () => {
  it("stays on Job running until the job leaves pending or running", () => {
    expect(isolateStartLabel(true, undefined)).toBe("Starting…");
    expect(isolateStartLabel(false, "pending")).toBe("Job running…");
    expect(isolateStartLabel(false, "running")).toBe("Job running…");
    expect(isolateStartLabel(false, "succeeded")).toBe("Start isolation");
    expect(isolateStartLabel(false, undefined)).toBe("Start isolation");
    expect(isolateStartDisabled(false, "pending")).toBe(true);
    expect(isolateStartDisabled(false, "running")).toBe(true);
    expect(isolateStartDisabled(true, "succeeded")).toBe(true);
    expect(isolateStartDisabled(false, "succeeded")).toBe(false);
    expect(isolateStartDisabled(false, undefined)).toBe(false);
  });
});

describe("hosted isolate guitar repair fields", () => {
  it("sends low-end and debleed only when those controls are on", () => {
    expect(isolateRepairBody({ lowEndRestoreDb: 3, subBassDebleed: true })).toEqual({
      low_end_restore_db: 3,
      sub_bass_debleed: true,
    });
    expect(isolateRepairBody({ lowEndRestoreDb: 0, subBassDebleed: false })).toEqual({});
    expect(isolateRepairBody({ lowEndRestoreDb: 2, subBassDebleed: false })).toEqual({
      low_end_restore_db: 2,
    });
  });
});
