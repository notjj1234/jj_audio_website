import { useEffect, useState } from "react";
import * as api from "../api";

const FALLBACK_MODES: api.ProcessingModeInfo[] = [
  { id: "auto", label: "Auto", enabled: true, reason: null, device: "cpu", max_duration_sec: 90 },
  { id: "fast_cpu", label: "Fast (CPU)", enabled: true, reason: null, device: "cpu", max_duration_sec: 90 },
  { id: "balanced", label: "Balanced", enabled: true, reason: null, device: "cpu", max_duration_sec: 300 },
  {
    id: "high_gpu",
    label: "High (GPU)",
    enabled: false,
    reason: "Needs NVIDIA CUDA on this host",
    device: "cuda",
    max_duration_sec: 300,
  },
  { id: "lite", label: "Lite / low RAM", enabled: true, reason: null, device: "cpu", max_duration_sec: 60 },
];

type Props = {
  value: string;
  onChange: (mode: string) => void;
};

function deviceLabel(device: string): string {
  if (device === "cuda") return "CUDA";
  if (device === "mps") return "MPS";
  return "CPU";
}

function helperText(
  caps: api.SystemCapabilities | null,
  mode: string,
  loadError: boolean
): string {
  if (loadError || !caps) {
    return "Could not detect host; jobs will use CPU Fast.";
  }
  const ram = caps.ram_gb != null ? ` · ~${caps.ram_gb} GB RAM` : "";
  const detected = deviceLabel(caps.detected_device);
  const selected =
    caps.modes.find((m) => m.id === mode) ?? caps.modes.find((m) => m.id === "auto");
  const using = deviceLabel(selected?.device ?? "cpu");
  if (caps.detected_device === "mps" && mode === "auto") {
    return `Detected: ${detected}${ram}. Auto uses CPU; Balanced may use MPS.`;
  }
  return `Detected: ${detected}${ram}. This job will use ${using}.`;
}

export function ProcessingModeSelect({ value, onChange }: Props) {
  const [caps, setCaps] = useState<api.SystemCapabilities | null>(null);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .getSystemCapabilities()
      .then((c) => {
        if (!cancelled) setCaps(c);
      })
      .catch(() => {
        if (!cancelled) setLoadError(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const modes = caps?.modes ?? FALLBACK_MODES;

  return (
    <label className="field">
      Processing mode
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-label="Processing mode"
      >
        {modes.map((m) => (
          <option
            key={m.id}
            value={m.id}
            disabled={!m.enabled}
            title={m.reason ?? undefined}
          >
            {m.enabled ? m.label : `${m.label} — ${m.reason ?? "unavailable"}`}
          </option>
        ))}
      </select>
      <span className="hint">{helperText(caps, value, loadError)}</span>
    </label>
  );
}
