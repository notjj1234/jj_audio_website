import { describe, expect, it } from "vitest";
import { FALLBACK_MODES, helperText, resolveProcessingMode } from "./ProcessingModeSelect";
import type { SystemCapabilities } from "../api";

const caps: SystemCapabilities = {
  device_options: ["cpu"],
  recommended_mode: "fast_cpu",
  detected_device: "cpu",
  ram_gb: 8,
  notes: "",
  low_ram: false,
  allow_youtube: false,
  modes: [
    { id: "auto", label: "Auto", enabled: true, reason: null, device: "cpu", max_duration_sec: 90 },
    { id: "fast_cpu", label: "Fast (CPU)", enabled: true, reason: null, device: "cpu", max_duration_sec: 90 },
    { id: "balanced", label: "Balanced", enabled: true, reason: null, device: "cpu", max_duration_sec: 300 },
  ],
};

describe("ProcessingModeSelect Auto", () => {
  it("lists Auto first and does not treat it as Balanced", () => {
    expect(FALLBACK_MODES[0]?.id).toBe("auto");
    expect(FALLBACK_MODES.some((m) => m.id === "balanced")).toBe(true);
    const lite = FALLBACK_MODES.find((m) => m.id === "lite");
    expect(lite?.label).toBe("Low RAM (60 s)");
  });

  it("helper text uses Auto's resolved device and duration cap", () => {
    const text = helperText(caps, "auto", false);
    expect(text).toContain("Auto will use CPU");
    expect(text).toContain("90s");
  });

  it("uses the fallback cap when capabilities cannot be loaded", () => {
    const selected = resolveProcessingMode(null, "lite");

    expect(selected?.label).toBe("Low RAM (60 s)");
    expect(selected?.max_duration_sec).toBe(60);
  });

  it("keeps the server-provided cap when capabilities are available", () => {
    const selected = resolveProcessingMode(caps, "balanced");

    expect(selected?.label).toBe("Balanced");
    expect(selected?.max_duration_sec).toBe(300);
  });
});
