/** Live metronome click synthesis for the desktop stem mixer (parity with Python). */

export type MetronomeSoundId = "classic" | "soft" | "wood" | "hi_tick";

export type MetronomeFollow = "smart" | "steady";

export type MetronomeOptions = {
  accent: boolean;
  rate: number;
  sound: MetronomeSoundId;
  follow: MetronomeFollow;
};

export type MetronomeConfig = {
  times1x: number[];
  steadyTimes1x: number[];
  refSec: number;
  beatsPerMeasure: number;
  durationSec: number;
  options: MetronomeOptions;
};

const RATE_2X_GAP_LIMIT = 1.75;
const ORDINARY_MIX = 0.7;

const SOUND_PRESETS: Record<
  MetronomeSoundId,
  { beatHz: number; downHz: number; duration: number; peak: number; decay: number }
> = {
  classic: { beatHz: 1000, downHz: 1500, duration: 0.05, peak: 0.5, decay: 12 },
  soft: { beatHz: 800, downHz: 1200, duration: 0.06, peak: 0.35, decay: 8 },
  wood: { beatHz: 900, downHz: 900, duration: 0.018, peak: 0.5, decay: 22 },
  hi_tick: { beatHz: 2200, downHz: 2800, duration: 0.02, peak: 0.5, decay: 18 },
};

export const METRONOME_SOUND_LABELS: Record<MetronomeSoundId, string> = {
  classic: "Classic",
  soft: "Soft",
  wood: "Wood",
  hi_tick: "Hi-tick",
};

export const METRONOME_RATE_CHOICES = [0.5, 1, 2] as const;

export function coerceMetronomeRate(value: unknown): number {
  const raw =
    typeof value === "string" ? value.trim().toLowerCase().replace(/x$/i, "") : value;
  const rate = Number(raw);
  if (Math.abs(rate - 0.5) < 1e-9) return 0.5;
  if (Math.abs(rate - 2) < 1e-9) return 2;
  return 1;
}

export function coerceMetronomeSound(value: unknown): MetronomeSoundId {
  const text = String(value ?? "classic")
    .trim()
    .toLowerCase()
    .replace(/-/g, "_")
    .replace(/\s+/g, "_");
  if (text === "hitick" || text === "hi_tick") return "hi_tick";
  if (text === "soft" || text === "wood" || text === "classic") return text;
  return "classic";
}

export function coerceMetronomeFollow(value: unknown): MetronomeFollow {
  return String(value ?? "").trim().toLowerCase() === "steady" ? "steady" : "smart";
}

export function coerceMetronomeOptions(raw: Partial<MetronomeOptions> | null | undefined): MetronomeOptions {
  return {
    accent: raw?.accent !== false,
    rate: coerceMetronomeRate(raw?.rate ?? 1),
    sound: coerceMetronomeSound(raw?.sound ?? "classic"),
    follow: coerceMetronomeFollow(raw?.follow),
  };
}

/** Smart times, or the constant-BPM grid when Steady is selected. */
export function metronomeClickTimes(config: MetronomeConfig, follow: MetronomeFollow): number[] {
  const smart = (config.times1x || []).filter((t) => Number.isFinite(t));
  if (follow === "steady" && config.steadyTimes1x && config.steadyTimes1x.length > 0) {
    const steady = config.steadyTimes1x.filter((t) => Number.isFinite(t));
    if (steady.length > 0) return steady;
  }
  return smart;
}

export function applyClickRate(
  times1x: number[],
  rate: number,
  refSec: number
): number[] {
  const times = times1x.filter((t) => Number.isFinite(t)).slice().sort((a, b) => a - b);
  const r = coerceMetronomeRate(rate);
  if (times.length === 0 || r === 1) return times;
  let refIdx = 0;
  let best = Infinity;
  for (let i = 0; i < times.length; i++) {
    const d = Math.abs(times[i]! - refSec);
    if (d < best) {
      best = d;
      refIdx = i;
    }
  }
  if (r === 0.5) {
    return times.filter((_, i) => (i - refIdx) % 2 === 0);
  }
  if (times.length < 2) return times;
  const diffs: number[] = [];
  for (let i = 1; i < times.length; i++) diffs.push(times[i]! - times[i - 1]!);
  const sorted = diffs.slice().sort((a, b) => a - b);
  const median = sorted[Math.floor(sorted.length / 2)] ?? 0;
  const limit = median > 0 ? RATE_2X_GAP_LIMIT * median : Infinity;
  const extra: number[] = [];
  for (let i = 0; i < diffs.length; i++) {
    const gap = diffs[i]!;
    if (gap > 1e-4 && gap <= limit) {
      extra.push(0.5 * (times[i]! + times[i + 1]!));
    }
  }
  const merged = times.concat(extra).sort((a, b) => a - b);
  const out: number[] = [];
  for (const t of merged) {
    if (out.length === 0 || t - out[out.length - 1]! > 1e-4) out.push(t);
  }
  return out;
}

function synthClickWave(
  sr: number,
  freq: number,
  duration: number,
  decay: number
): Float32Array {
  const n = Math.max(1, Math.round(sr * duration));
  const out = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const t = i / sr;
    const env = Math.exp((-decay * t) / Math.max(duration, 1e-6));
    out[i] = env * Math.sin(2 * Math.PI * freq * t);
  }
  return out;
}

function placeClicks(
  times: number[],
  sr: number,
  length: number,
  wave: Float32Array
): Float32Array {
  const out = new Float32Array(length);
  for (const t of times) {
    const start = Math.round(t * sr);
    if (start < 0 || start >= length) continue;
    const end = Math.min(length, start + wave.length);
    for (let i = start, j = 0; i < end; i++, j++) {
      out[i]! += wave[j]!;
    }
  }
  return out;
}

function downbeatTimes1x(
  times1x: number[],
  refSec: number,
  beatsPerMeasure: number
): number[] {
  if (times1x.length === 0) return [];
  const measure = Math.max(1, beatsPerMeasure | 0);
  let refIdx = 0;
  let best = Infinity;
  for (let i = 0; i < times1x.length; i++) {
    const d = Math.abs(times1x[i]! - refSec);
    if (d < best) {
      best = d;
      refIdx = i;
    }
  }
  return times1x.filter((_, i) => (i - refIdx) % measure === 0);
}

function timesInSet(candidates: number[], reference: number[], tol = 1e-4): number[] {
  return candidates.filter((t) => reference.some((r) => Math.abs(r - t) <= tol));
}

/** Build a mono AudioBuffer of clicks for the full track duration. */
export function buildMetronomeAudioBuffer(
  ctx: AudioContext,
  config: MetronomeConfig,
  options: MetronomeOptions
): AudioBuffer {
  const sr = ctx.sampleRate;
  const duration = Math.max(0.05, Number(config.durationSec) || 0);
  const n = Math.max(1, Math.round(duration * sr));
  const opts = coerceMetronomeOptions(options);
  const preset = SOUND_PRESETS[opts.sound] ?? SOUND_PRESETS.classic;
  const times1x = metronomeClickTimes(config, opts.follow);
  const audible = applyClickRate(times1x, opts.rate, config.refSec);
  const beatWave = synthClickWave(sr, preset.beatHz, preset.duration, preset.decay);
  const downWave = synthClickWave(sr, preset.downHz, preset.duration, preset.decay);

  let clicks: Float32Array;
  if (opts.accent) {
    const downs1x = downbeatTimes1x(
      times1x,
      config.refSec,
      config.beatsPerMeasure || 4
    );
    const down = timesInSet(audible, downs1x);
    const downSet = new Set(down.map((t) => t.toFixed(6)));
    const others = audible.filter((t) => !downSet.has(t.toFixed(6)));
    clicks = placeClicks(down.length ? down : audible.slice(0, 1), sr, n, downWave);
    if (others.length) {
      const beat = placeClicks(others, sr, n, beatWave);
      for (let i = 0; i < n; i++) clicks[i]! += ORDINARY_MIX * beat[i]!;
    }
  } else {
    clicks = placeClicks(audible, sr, n, beatWave);
  }

  let peak = 0;
  for (let i = 0; i < n; i++) peak = Math.max(peak, Math.abs(clicks[i]!));
  if (peak > 0) {
    const scale = preset.peak / peak;
    for (let i = 0; i < n; i++) clicks[i]! *= scale;
  }

  const buf = ctx.createBuffer(2, n, sr);
  buf.copyToChannel(clicks, 0);
  buf.copyToChannel(clicks.slice(), 1);
  return buf;
}

/** Sparse waveform peaks for the metronome row (click spikes). */
export function metronomePeaksFromTimes(
  times1x: number[],
  durationSec: number,
  options: MetronomeOptions,
  refSec: number,
  numPoints = 220
): number[] {
  const audible = applyClickRate(times1x, options.rate, refSec);
  const peaks = new Array(numPoints).fill(0);
  if (durationSec <= 0) return peaks;
  for (const t of audible) {
    const i = Math.min(numPoints - 1, Math.max(0, Math.round((t / durationSec) * (numPoints - 1))));
    peaks[i] = Math.max(peaks[i]!, 0.72);
  }
  return peaks;
}
