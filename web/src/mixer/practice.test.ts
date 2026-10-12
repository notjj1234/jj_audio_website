import { describe, expect, it } from "vitest";
import {
  PRACTICE_KEY_DEFAULT,
  PRACTICE_RATE_DEFAULT,
  clampPracticeRate,
  clampPracticeSemitones,
  formatPracticeKeyLabel,
  formatPracticeSpeedLabel,
} from "./practice";

describe("practice clamps", () => {
  it("clamps speed to 0.5–1.5 in 0.05 steps", () => {
    expect(clampPracticeRate(1)).toBe(PRACTICE_RATE_DEFAULT);
    expect(clampPracticeRate(0.4)).toBe(0.5);
    expect(clampPracticeRate(1.7)).toBe(1.5);
    expect(clampPracticeRate(0.83)).toBe(0.85);
  });

  it("clamps key to integer −6…+6", () => {
    expect(clampPracticeSemitones(0)).toBe(PRACTICE_KEY_DEFAULT);
    expect(clampPracticeSemitones(-9)).toBe(-6);
    expect(clampPracticeSemitones(9)).toBe(6);
    expect(clampPracticeSemitones(2.6)).toBe(3);
  });

  it("formats practice labels", () => {
    expect(formatPracticeSpeedLabel(0.8)).toBe("Speed 0.80×");
    expect(formatPracticeKeyLabel(0)).toBe("Key 0");
    expect(formatPracticeKeyLabel(2)).toBe("Key +2");
    expect(formatPracticeKeyLabel(-3)).toBe("Key -3");
  });
});
