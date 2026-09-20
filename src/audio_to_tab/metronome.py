"""Beat-tracked metronome click stem for isolate mixer runs."""

from __future__ import annotations

import itertools
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

from audio_to_tab.tempo import MAX_PLAUSIBLE_BPM, MIN_PLAUSIBLE_BPM

logger = logging.getLogger(__name__)

METRONOME_STEM_ID = "metronome"
METRONOME_DIAGNOSTICS_NAME = "metronome_diagnostics.json"
_ANALYSIS_STEM_PRIORITY = ("drums", "other", "guitar", "vocals", "bass")
_MIN_BEATS = 2
_CLICK_DURATION_SEC = 0.05
_BEAT_CLICK_HZ = 1000.0
_DOWNBEAT_CLICK_HZ = 1500.0
_PEAK = 0.5
_ORDINARY_MIX = 0.7
_RATE_2X_GAP_LIMIT = 1.75
_INTRO_ENERGY_RATIO = 0.2
_STABLE_IOI_REL = 0.2
_STABLE_MIN_BEATS = 4
_DEFAULT_BEATS_PER_MEASURE = 4
_METER_CANDIDATES = (3, 4)
_METER_MIN_MEASURES = 3
_METER_MIN_CONTRAST = 1.15
_METER_WIN_MARGIN = 1.05
_HOP_LENGTH = 512
_TEMPO_SMOOTH_SEC = 6.0
_CURVE_JSON_HZ = 4.0
_LOCAL_CONF_FLOOR = 0.35
_CURVE_IQR_HIGH_BPM = 8.0
_OCTAVE_FACTORS = (0.25, 0.5, 1.0, 2.0, 4.0)
_IMPULSE_INNER_SEC = 0.08
_IMPULSE_OUTER_SEC = 0.35
_IMPULSE_RATIO = 6.0

METRONOME_RATE_CHOICES: tuple[float, ...] = (0.5, 1.0, 2.0)
METRONOME_SOUND_IDS: tuple[str, ...] = ("classic", "soft", "wood", "hi_tick")
METRONOME_SOUND_LABELS: dict[str, str] = {
    "classic": "Classic",
    "soft": "Soft",
    "wood": "Wood",
    "hi_tick": "Hi-tick",
}

_SOUND_PRESETS: dict[str, dict[str, float]] = {
    "classic": {
        "beat_hz": _BEAT_CLICK_HZ,
        "down_hz": _DOWNBEAT_CLICK_HZ,
        "duration": _CLICK_DURATION_SEC,
        "peak": _PEAK,
        "decay": 12.0,
    },
    "soft": {
        "beat_hz": 800.0,
        "down_hz": 1200.0,
        "duration": 0.06,
        "peak": 0.35,
        "decay": 8.0,
    },
    "wood": {
        "beat_hz": 900.0,
        "down_hz": 900.0,
        "duration": 0.018,
        "peak": _PEAK,
        "decay": 22.0,
    },
    "hi_tick": {
        "beat_hz": 2200.0,
        "down_hz": 2800.0,
        "duration": 0.02,
        "peak": _PEAK,
        "decay": 18.0,
    },
}


@dataclass(frozen=True)
class MetronomeRenderOptions:
    accent: bool = True
    rate: float = 1.0
    sound: str = "classic"

    def to_dict(self) -> dict[str, Any]:
        return {
            "accent": bool(self.accent),
            "rate": float(self.rate),
            "sound": str(self.sound),
        }


def coerce_metronome_rate(value: Any) -> float:
    raw = value
    if isinstance(raw, str):
        raw = raw.strip().lower().rstrip("x")
    try:
        rate = float(raw)
    except (TypeError, ValueError):
        return 1.0
    if abs(rate - 0.5) < 1e-9:
        return 0.5
    if abs(rate - 2.0) < 1e-9:
        return 2.0
    return 1.0


def coerce_metronome_sound(value: Any) -> str:
    text = str(value or "classic").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {"hitick": "hi_tick", "hi_tick": "hi_tick"}
    text = aliases.get(text, text)
    if text in METRONOME_SOUND_IDS:
        return text
    return "classic"


def coerce_metronome_render_options(
    *,
    accent: Any = True,
    rate: Any = 1.0,
    sound: Any = "classic",
) -> MetronomeRenderOptions:
    return MetronomeRenderOptions(
        accent=True if accent is None else bool(accent),
        rate=coerce_metronome_rate(rate),
        sound=coerce_metronome_sound(sound),
    )


@dataclass(frozen=True)
class MetronomeResult:
    path: Path
    bpm: float
    beat_count: int
    confidence: str
    source: str
    sr: int = 0
    duration_sec: float = 0.0
    body_start_sec: float = 0.0
    first_detected_sec: float = 0.0
    detected_times: tuple[float, ...] = ()
    click_times_1x: tuple[float, ...] = ()
    beats_per_measure: int = 4
    render: MetronomeRenderOptions = MetronomeRenderOptions()
    bpm_curve_t: tuple[float, ...] = ()
    bpm_curve_bpm: tuple[float, ...] = ()

    def slim_meta(self) -> dict[str, Any]:
        return {
            "bpm": self.bpm,
            "beat_count": self.beat_count,
            "confidence": self.confidence,
            "source": self.source,
            "render": self.render.to_dict(),
        }


def _metronome_source_candidates(
    artifacts: dict[str, Path],
    *,
    fallback: Path | None = None,
) -> list[tuple[Path, str]]:
    """Beat-tracking inputs, best first: the mix, then drums / mix-like stems."""
    candidates: list[tuple[Path, str]] = []
    if fallback is not None:
        path = Path(fallback)
        if path.is_file():
            candidates.append((path, "source"))
    for name in _ANALYSIS_STEM_PRIORITY:
        raw = artifacts.get(name)
        if raw is None:
            continue
        path = Path(raw)
        if path.is_file() and path.suffix.lower() == ".wav":
            candidates.append((path, name))
    return candidates


def pick_metronome_source(
    artifacts: dict[str, Path],
    *,
    fallback: Path | None = None,
) -> tuple[Path, str] | None:
    """Prefer the original/clipped mix, else drums (then other mix-like stems).

    The mix carries rhythmic energy from every instrument, so beat tracking keeps
    working through drum-less sections. A single stem only has onsets while that
    instrument plays, which left verses without usable beats.
    """
    candidates = _metronome_source_candidates(artifacts, fallback=fallback)
    return candidates[0] if candidates else None


def _onset_envelope(
    mono: np.ndarray,
    sr: int,
    hop_length: int = _HOP_LENGTH,
) -> np.ndarray:
    import librosa

    return np.asarray(
        librosa.onset.onset_strength(
            y=mono, sr=sr, hop_length=hop_length, aggregate=np.median
        ),
        dtype=np.float64,
    ).reshape(-1)


def tempo_curve_from_onset(
    onset_env: np.ndarray,
    *,
    sr: int | float,
    hop_length: int = _HOP_LENGTH,
) -> np.ndarray:
    """Per-frame tempo from a precomputed onset envelope (``aggregate=None``)."""
    onset = np.asarray(onset_env, dtype=np.float64).reshape(-1)
    if onset.size == 0 or not np.any(onset):
        return np.zeros(0, dtype=np.float64)
    import librosa

    raw = librosa.feature.rhythm.tempo(
        onset_envelope=onset,
        sr=float(sr),
        hop_length=int(hop_length),
        aggregate=None,
        max_tempo=320.0,
    )
    return np.asarray(raw, dtype=np.float64).reshape(-1)


def octave_snap_bpm(bpm: float, anchor_bpm: float) -> float:
    """Snap ``bpm`` to the nearest half/double of ``anchor_bpm`` in log space."""
    value = float(bpm)
    anchor = float(anchor_bpm)
    if not np.isfinite(anchor) or anchor <= 0:
        if not np.isfinite(value) or value <= 0:
            return MIN_PLAUSIBLE_BPM
        return float(np.clip(value, MIN_PLAUSIBLE_BPM, MAX_PLAUSIBLE_BPM))
    if not np.isfinite(value) or value <= 0:
        return float(np.clip(anchor, MIN_PLAUSIBLE_BPM, MAX_PLAUSIBLE_BPM))
    candidates = [
        factor * anchor
        for factor in _OCTAVE_FACTORS
        if MIN_PLAUSIBLE_BPM <= factor * anchor <= MAX_PLAUSIBLE_BPM
    ]
    if not candidates:
        return float(np.clip(value, MIN_PLAUSIBLE_BPM, MAX_PLAUSIBLE_BPM))
    log_v = float(np.log2(value))
    return float(min(candidates, key=lambda c: abs(float(np.log2(c)) - log_v)))


def _odd_window(n: int) -> int:
    win = max(1, int(n))
    if win % 2 == 0:
        win += 1
    return win


def _median_filter_1d(values: np.ndarray, win: int) -> np.ndarray:
    raw = np.asarray(values, dtype=np.float64).reshape(-1)
    width = _odd_window(win)
    if raw.size == 0 or width <= 1 or raw.size < 3:
        return raw.copy()
    pad = width // 2
    padded = np.pad(raw, pad, mode="edge")
    out = np.empty_like(raw)
    for i in range(raw.size):
        out[i] = float(np.median(padded[i : i + width]))
    return out


def stabilize_tempo_curve(
    curve: np.ndarray,
    *,
    sr: int | float,
    hop_length: int = _HOP_LENGTH,
    global_bpm: float,
) -> np.ndarray:
    """Median-smooth, octave-snap to ``global_bpm``, and clamp to a plausible range."""
    anchor = float(np.clip(global_bpm, MIN_PLAUSIBLE_BPM, MAX_PLAUSIBLE_BPM))
    raw = np.asarray(curve, dtype=np.float64).reshape(-1)
    if raw.size == 0:
        return np.asarray([anchor], dtype=np.float64)
    hop = max(1, int(hop_length))
    win = _odd_window(round(_TEMPO_SMOOTH_SEC * float(sr) / float(hop)))
    smoothed = _median_filter_1d(raw, win)
    snapped = np.empty_like(smoothed)
    for i, value in enumerate(smoothed):
        snapped[i] = octave_snap_bpm(float(value), anchor)
    return np.clip(snapped, MIN_PLAUSIBLE_BPM, MAX_PLAUSIBLE_BPM)


def curve_confidence(
    onset_env: np.ndarray,
    curve: np.ndarray,
    *,
    global_bpm: float,
    sr: int | float = 22050,
    hop_length: int = _HOP_LENGTH,
) -> np.ndarray:
    """Per-frame 0–1 confidence: onset energy × local tempo stability."""
    del global_bpm  # reserved: reporting uses the same curve vs the global anchor
    onset = np.asarray(onset_env, dtype=np.float64).reshape(-1)
    curv = np.asarray(curve, dtype=np.float64).reshape(-1)
    n = min(onset.size, curv.size)
    if n == 0:
        return np.zeros(0, dtype=np.float64)
    onset = onset[:n]
    curv = curv[:n]
    med_on = float(np.median(onset)) if onset.size else 0.0
    energy = np.clip(onset / max(med_on, 1e-8), 0.0, 2.0) / 2.0
    hop = max(1, int(hop_length))
    win = _odd_window(round(_TEMPO_SMOOTH_SEC * float(sr) / float(hop)))
    local_med = _median_filter_1d(curv, win)
    rel = np.abs(curv - local_med) / np.maximum(local_med, 1.0)
    stab = np.clip(1.0 - rel / 0.15, 0.0, 1.0)
    return np.clip(0.5 * energy + 0.5 * stab, 0.0, 1.0)


def _sample_series(
    t: float,
    times: np.ndarray,
    values: np.ndarray,
    default: float,
) -> float:
    ts = np.asarray(times, dtype=np.float64).reshape(-1)
    vs = np.asarray(values, dtype=np.float64).reshape(-1)
    if ts.size == 0 or vs.size == 0:
        return float(default)
    idx = int(np.argmin(np.abs(ts - float(t))))
    return float(vs[min(idx, vs.size - 1)])


def local_period_at(
    t: float,
    curve_times: np.ndarray,
    curve_bpm: np.ndarray,
    fallback_bpm: float,
) -> float:
    fallback = 60.0 / float(fallback_bpm) if fallback_bpm and fallback_bpm > 0 else 0.5
    bpm = _sample_series(t, curve_times, curve_bpm, fallback_bpm if fallback_bpm > 0 else 120.0)
    if not np.isfinite(bpm) or bpm <= 0:
        return fallback
    return 60.0 / float(bpm)


def integrate_tempo_curve(
    t0: float,
    t1: float,
    *,
    curve_times: np.ndarray,
    curve_bpm: np.ndarray,
    fallback_bpm: float,
    include_start: bool = False,
) -> np.ndarray:
    """Walk ``t += 60/local_bpm(t)`` from ``t0`` until ``t1`` (lead/tail/hole fill)."""
    start = float(t0)
    end = float(t1)
    if end <= start:
        return np.zeros(0, dtype=np.float64)
    times: list[float] = []
    t = start
    if include_start:
        times.append(t)
        step = local_period_at(t, curve_times, curve_bpm, fallback_bpm)
        if step <= 1e-6:
            return np.asarray(times, dtype=np.float64)
        t += step
    guard = 0
    while t < end - 1e-9 and guard < 100_000:
        times.append(t)
        step = local_period_at(t, curve_times, curve_bpm, fallback_bpm)
        if step <= 1e-6:
            break
        t += step
        guard += 1
    return np.asarray(times, dtype=np.float64)


def _downsample_bpm_curve(
    curve_times: np.ndarray,
    curve_bpm: np.ndarray,
    duration_sec: float,
) -> tuple[tuple[float, ...], tuple[float, ...]]:
    ts = np.asarray(curve_times, dtype=np.float64).reshape(-1)
    bp = np.asarray(curve_bpm, dtype=np.float64).reshape(-1)
    if ts.size == 0 or bp.size == 0 or duration_sec <= 0:
        return (), ()
    step = 1.0 / float(_CURVE_JSON_HZ)
    targets = np.arange(0.0, float(duration_sec) + 0.5 * step, step, dtype=np.float64)
    out_t: list[float] = []
    out_b: list[float] = []
    n = min(ts.size, bp.size)
    ts = ts[:n]
    bp = bp[:n]
    for t in targets:
        if t > duration_sec + 1e-9:
            break
        idx = int(np.argmin(np.abs(ts - float(t))))
        out_t.append(float(t))
        out_b.append(float(bp[idx]))
    return tuple(out_t), tuple(out_b)


def _bpm_curve_from_payload(raw: Any) -> tuple[tuple[float, ...], tuple[float, ...]]:
    if not isinstance(raw, dict):
        return (), ()
    t_raw = raw.get("t")
    b_raw = raw.get("bpm")
    if not isinstance(t_raw, list) or not isinstance(b_raw, list):
        return (), ()
    times: list[float] = []
    bpms: list[float] = []
    for item in t_raw:
        try:
            times.append(float(item))
        except (TypeError, ValueError):
            continue
    for item in b_raw:
        try:
            bpms.append(float(item))
        except (TypeError, ValueError):
            continue
    n = min(len(times), len(bpms))
    return tuple(times[:n]), tuple(bpms[:n])


def _wrapped_residuals(times: np.ndarray, phase: float, period: float) -> np.ndarray:
    """Absolute distance of each time to the nearest ``phase + k*period``."""
    return np.abs(np.mod(times - phase + period / 2.0, period) - period / 2.0)


def _best_phase(times: np.ndarray, period: float) -> float:
    """Phase in ``[0, period)`` that best fits ``times`` on a periodic grid.

    Tries each detected onset as a candidate origin and picks the phase with the
    lowest mean wrapped residual. This stays stable when beat intervals jitter
    (circular mean of ``t % period`` can land anti-phase in that case).
    """
    if times.size == 0 or period <= 0:
        return 0.0
    best_phase = 0.0
    best_cost = float("inf")
    for candidate in np.mod(times, period):
        cost = float(np.mean(_wrapped_residuals(times, float(candidate), period)))
        if cost < best_cost:
            best_cost = cost
            best_phase = float(candidate)
    # Snap near the seam to 0 so a locked grid can start cleanly at t=0.
    if best_phase < 0.02 * period or best_phase > 0.98 * period:
        return 0.0
    return best_phase


def refine_tempo_phase(
    detected: np.ndarray,
    bpm_hint: float,
) -> tuple[float, float]:
    """Return ``(bpm, phase_sec)`` locked to detected beat onsets."""
    bpm = float(np.clip(bpm_hint, MIN_PLAUSIBLE_BPM, MAX_PLAUSIBLE_BPM))
    period = 60.0 / bpm
    if detected.size >= 3:
        intervals = np.diff(np.sort(detected))
        lo = 60.0 / MAX_PLAUSIBLE_BPM * 0.85
        hi = 60.0 / MIN_PLAUSIBLE_BPM * 1.15
        intervals = intervals[(intervals >= lo) & (intervals <= hi)]
        if intervals.size >= 2:
            # Mean (not median): librosa often alternates slightly long/short
            # intervals; median then picks one side and the phase fit breaks.
            mean_iv = float(np.mean(intervals))
            mean_bpm = 60.0 / mean_iv
            candidates = [mean_iv]
            if abs(mean_bpm * 2.0 - bpm) / bpm < 0.2:
                candidates.append(mean_iv * 2.0)
            if abs(mean_bpm * 0.5 - bpm) / bpm < 0.2:
                candidates.append(mean_iv * 0.5)
            if MIN_PLAUSIBLE_BPM <= mean_bpm <= MAX_PLAUSIBLE_BPM:
                period = mean_iv
            else:
                period = min(candidates, key=lambda c: abs(c - period))
            bpm = float(np.clip(60.0 / period, MIN_PLAUSIBLE_BPM, MAX_PLAUSIBLE_BPM))
            period = 60.0 / bpm
    phase = _best_phase(detected, period)
    return bpm, phase


def metronome_grid_times(
    *,
    duration_sec: float,
    bpm: float,
    phase_sec: float = 0.0,
) -> np.ndarray:
    """Steady click times locked to ``bpm`` / ``phase_sec``, covering from the start.

    Used for lead-in math/tests. Full-song clicks use :func:`build_click_times`
    so the body follows detected beats instead of a rigid grid that drifts.
    """
    if duration_sec <= 0 or bpm <= 0:
        return np.zeros(0, dtype=np.float64)
    period = 60.0 / float(bpm)
    if period <= 0:
        return np.zeros(0, dtype=np.float64)
    phase = float(phase_sec) % period
    if phase < 1e-9 or period - phase < 1e-9:
        phase = 0.0
    times = np.arange(phase, duration_sec, period, dtype=np.float64)
    if times.size == 0:
        return np.asarray([phase if phase < duration_sec else 0.0], dtype=np.float64)
    return times


def build_click_times(
    detected: np.ndarray,
    *,
    duration_sec: float,
    bpm: float,
    tempo_curve: np.ndarray | None = None,
    curve_times: np.ndarray | None = None,
    curve_conf: np.ndarray | None = None,
    conf_floor: float = _LOCAL_CONF_FLOOR,
) -> np.ndarray:
    """Hybrid click times: detected beats in the body, extrapolated across gaps.

    A single global BPM grid drifts over long songs. Keeping librosa's beat times
    for the body follows the performance; walking backward from the first beat
    (and optionally forward past the last) still fills lead-in / trailing gaps.
    Holes inside the body — sections where the analysis source went quiet — are
    subdivided so the click keeps going instead of dropping out mid-song.

    When a confident local tempo curve is provided, lead/tail/holes step at the
    local period instead of the global BPM.
    """
    if duration_sec <= 0 or bpm <= 0:
        return np.zeros(0, dtype=np.float64)
    period = 60.0 / float(bpm)
    if period <= 0:
        return np.zeros(0, dtype=np.float64)

    body = np.asarray(detected, dtype=np.float64).reshape(-1)
    body = body[np.isfinite(body)]
    body = np.sort(body[(body >= 0.0) & (body < duration_sec)])
    if body.size == 0:
        return np.zeros(0, dtype=np.float64)

    hop_t = (
        np.asarray(curve_times, dtype=np.float64).reshape(-1)
        if curve_times is not None
        else np.zeros(0, dtype=np.float64)
    )
    hop_b = (
        np.asarray(tempo_curve, dtype=np.float64).reshape(-1)
        if tempo_curve is not None
        else np.zeros(0, dtype=np.float64)
    )
    hop_c = (
        np.asarray(curve_conf, dtype=np.float64).reshape(-1)
        if curve_conf is not None
        else np.zeros(0, dtype=np.float64)
    )
    use_curve = hop_t.size > 0 and hop_b.size > 0

    def _period_at(t: float) -> float:
        if not use_curve:
            return period
        conf = _sample_series(t, hop_t, hop_c, 0.0) if hop_c.size else 1.0
        if conf < float(conf_floor):
            return period
        return local_period_at(t, hop_t, hop_b, bpm)

    def _conf_at(t: float) -> float:
        if hop_c.size == 0:
            return 1.0 if use_curve else 0.0
        return _sample_series(t, hop_t, hop_c, 0.0)

    lead: list[float] = []
    t = float(body[0])
    guard = 0
    while guard < 100_000:
        t -= _period_at(t)
        if t < 0.0:
            break
        lead.append(t)
        guard += 1
    lead.reverse()

    tail: list[float] = []
    last = float(body[-1])
    if duration_sec - last > 1.5 * period:
        t = last
        guard = 0
        while guard < 100_000:
            t += _period_at(t)
            if t >= duration_sec:
                break
            tail.append(t)
            guard += 1

    infill: list[float] = []
    if body.size > 1:
        for t0, t1 in itertools.pairwise(body):
            gap = float(t1) - float(t0)
            mid = 0.5 * (float(t0) + float(t1))
            local = _period_at(mid)
            if gap <= 1.5 * local:
                continue
            if use_curve and _conf_at(mid) >= float(conf_floor):
                raw = integrate_tempo_curve(
                    float(t0),
                    float(t1),
                    curve_times=hop_t,
                    curve_bpm=hop_b,
                    fallback_bpm=bpm,
                    include_start=False,
                )
                if raw.size:
                    last_raw = float(raw[-1])
                    t_end = last_raw + local_period_at(last_raw, hop_t, hop_b, bpm)
                    span = t_end - float(t0)
                    if span > 1e-9:
                        scale = gap / span
                        warped = float(t0) + (raw - float(t0)) * scale
                        infill.extend(
                            float(x)
                            for x in warped
                            if float(t0) + 1e-4 < float(x) < float(t1) - 1e-4
                        )
                    continue
            steps = max(2, round(gap / local))
            step = gap / steps
            infill.extend(float(t0) + i * step for i in range(1, steps))

    parts: list[np.ndarray] = []
    if lead:
        parts.append(np.asarray(lead, dtype=np.float64))
    parts.append(body)
    if infill:
        parts.append(np.asarray(infill, dtype=np.float64))
    if tail:
        parts.append(np.asarray(tail, dtype=np.float64))
    times = np.concatenate(parts)
    times.sort()
    if times.size > 1:
        keep = np.ones(times.size, dtype=bool)
        keep[1:] = np.diff(times) > 1e-4
        times = times[keep]
    return times


def _beat_local_rms(
    detected: np.ndarray,
    mono: np.ndarray,
    sr: int,
    *,
    win_sec: float = 0.04,
) -> np.ndarray:
    win = max(1, int(win_sec * sr))
    out = np.zeros(detected.size, dtype=np.float64)
    n = len(mono)
    for i, t in enumerate(detected):
        center = round(float(t) * sr)
        sl = mono[max(0, center - win) : min(n, center + win)]
        if sl.size:
            samples = sl.astype(np.float64, copy=False)
            out[i] = float(np.sqrt(np.mean(samples * samples)))
    return out


def _beat_impulse_ratios(
    detected: np.ndarray,
    mono: np.ndarray,
    sr: int,
    *,
    inner_sec: float = _IMPULSE_INNER_SEC,
    outer_sec: float = _IMPULSE_OUTER_SEC,
) -> np.ndarray:
    """Peak in a short window vs RMS of the surrounding audio (impulse vs noise)."""
    times = np.asarray(detected, dtype=np.float64).reshape(-1)
    out = np.zeros(times.size, dtype=np.float64)
    if sr <= 0 or len(mono) == 0:
        return out
    inner = max(1, int(inner_sec * sr))
    outer = max(inner + 1, int(outer_sec * sr))
    n = len(mono)
    samples = np.asarray(mono, dtype=np.float64).reshape(-1)
    for i, t in enumerate(times):
        center = round(float(t) * sr)
        lo_i = max(0, center - inner)
        hi_i = min(n, center + inner)
        lo_o = max(0, center - outer)
        hi_o = min(n, center + outer)
        peak = float(np.max(np.abs(samples[lo_i:hi_i]))) if hi_i > lo_i else 0.0
        left = samples[lo_o:lo_i]
        right = samples[hi_i:hi_o]
        if left.size + right.size:
            outer_seg = np.concatenate([left, right])
            rms = float(np.sqrt(np.mean(outer_seg * outer_seg)))
        else:
            rms = 0.0
        out[i] = peak / max(rms, 1e-5)
    return out


def _first_stable_run_index(
    detected: np.ndarray,
    period: float,
    *,
    min_beats: int = _STABLE_MIN_BEATS,
    local_periods: np.ndarray | None = None,
    trust: np.ndarray | None = None,
) -> int:
    """Index of the first locally-stable run, or -1 if none is long enough."""
    if detected.size < min_beats or period <= 0:
        return -1
    need = min_beats - 1
    intervals = np.diff(detected)
    if (
        local_periods is not None
        and np.asarray(local_periods).size == detected.size
    ):
        refs = np.asarray(local_periods, dtype=np.float64).reshape(-1)[:-1]
        refs = np.where(refs > 0, refs, period)
    else:
        refs = np.full(intervals.size, period, dtype=np.float64)
    ok = np.abs(intervals - refs) <= (_STABLE_IOI_REL * np.maximum(refs, 1e-9))
    trusted = (
        np.asarray(trust, dtype=bool).reshape(-1)
        if trust is not None and np.asarray(trust).size == detected.size
        else None
    )
    for i in range(ok.size - need + 1):
        if not bool(np.all(ok[i : i + need])):
            continue
        if trusted is not None and not bool(np.all(trusted[i : i + min_beats])):
            continue
        return i
    return -1


def gate_unreliable_intro_beats(
    detected: np.ndarray,
    mono: np.ndarray,
    sr: int,
    period: float,
    *,
    local_periods: np.ndarray | None = None,
) -> tuple[np.ndarray, float]:
    """Drop weak/irregular intro onsets; keep a trusted body start.

    A locally stable pulse (sung intro) is kept even when quieter than drums,
    as long as those beats look like impulses rather than noise. Speech/noise
    intros still get gated. ``body_start`` is the first *loud* stable beat
    (drum entry) and may be later than the first gated time.
    """
    times = np.asarray(detected, dtype=np.float64).reshape(-1)
    times = times[np.isfinite(times)]
    times = np.sort(times)
    if times.size == 0:
        return times, 0.0
    if times.size < _MIN_BEATS or period <= 0 or sr <= 0 or len(mono) == 0:
        return times, float(times[0])

    energies = _beat_local_rms(times, mono, sr)
    split = max(1, energies.size // 2)
    body_energy = float(np.median(energies[split:]))
    floor = max(body_energy * _INTRO_ENERGY_RATIO, 1e-5)
    loud = energies >= floor
    impulse = _beat_impulse_ratios(times, mono, sr) >= _IMPULSE_RATIO
    trust = loud | impulse
    loud_idx = int(np.argmax(loud)) if np.any(loud) else 0
    stable_idx = _first_stable_run_index(
        times, period, local_periods=local_periods, trust=trust
    )
    start_idx = stable_idx if stable_idx >= 0 else loud_idx
    start_idx = min(start_idx, times.size - 1)
    body_idx = start_idx
    for i in range(start_idx, times.size):
        if bool(loud[i]):
            body_idx = i
            break
    body_start = float(times[body_idx])
    gated = times[start_idx:]
    if gated.size < _MIN_BEATS:
        return times, float(times[0])
    return gated, body_start


def detect_beats_per_measure(
    detected: np.ndarray,
    mono: np.ndarray,
    sr: int,
    bpm: float,
) -> int:
    """Infer 3 or 4 beats per measure from where the accents land.

    Scores each candidate meter by how much louder its strongest beat class is
    than the rest (per-beat RMS). A 4/4 accent pattern read as 3 (or vice versa)
    smears across every class and scores ~1.0, so the contrast separates them.
    Falls back to 4 whenever the audio is too short or the accents are flat.
    """
    times = np.asarray(detected, dtype=np.float64).reshape(-1)
    times = np.sort(times[np.isfinite(times)])
    if sr <= 0 or bpm <= 0 or len(mono) == 0:
        return _DEFAULT_BEATS_PER_MEASURE
    if times.size < _METER_MIN_MEASURES * min(_METER_CANDIDATES):
        return _DEFAULT_BEATS_PER_MEASURE

    energies = _beat_local_rms(times, mono, sr)
    if not np.any(energies > 0):
        return _DEFAULT_BEATS_PER_MEASURE

    index = np.arange(times.size, dtype=np.int64)
    scores: dict[int, float] = {}
    for meter in _METER_CANDIDATES:
        if times.size < _METER_MIN_MEASURES * meter:
            continue
        best = 0.0
        for phase in range(meter):
            on = energies[index % meter == phase]
            off = energies[index % meter != phase]
            if on.size == 0 or off.size == 0:
                continue
            off_mean = float(np.mean(off))
            if off_mean <= 0:
                continue
            best = max(best, float(np.mean(on)) / off_mean)
        if best > 0:
            scores[meter] = best
    if not scores:
        return _DEFAULT_BEATS_PER_MEASURE

    winner = max(scores, key=lambda m: scores[m])
    runner_up = max((s for m, s in scores.items() if m != winner), default=0.0)
    if scores[winner] < _METER_MIN_CONTRAST:
        return _DEFAULT_BEATS_PER_MEASURE
    if scores[winner] < _METER_WIN_MARGIN * runner_up:
        return _DEFAULT_BEATS_PER_MEASURE
    return int(winner)


def apply_click_rate(
    times_1x: np.ndarray,
    *,
    rate: float,
    ref_sec: float,
) -> np.ndarray:
    """Map a 1x hybrid grid to 0.5x / 1x / 2x audible click times."""
    times = np.asarray(times_1x, dtype=np.float64).reshape(-1)
    times = times[np.isfinite(times)]
    times = np.sort(times)
    rate = coerce_metronome_rate(rate)
    if times.size == 0 or rate == 1.0:
        return times
    ref_idx = int(np.argmin(np.abs(times - float(ref_sec))))
    if rate == 0.5:
        beat_index = np.arange(times.size, dtype=np.int64) - ref_idx
        return times[beat_index % 2 == 0]
    if times.size < 2:
        return times
    diffs = np.diff(times)
    median_period = float(np.median(diffs)) if diffs.size else 0.0
    limit = _RATE_2X_GAP_LIMIT * median_period if median_period > 0 else float("inf")
    extra = [
        0.5 * (float(t0) + float(t1))
        for t0, t1, gap in zip(times[:-1], times[1:], diffs, strict=True)
        if 1e-4 < float(gap) <= limit
    ]
    if not extra:
        return times
    merged = np.concatenate([times, np.asarray(extra, dtype=np.float64)])
    merged.sort()
    keep = np.ones(merged.size, dtype=bool)
    keep[1:] = np.diff(merged) > 1e-4
    return merged[keep]


def _synth_click_wave(
    sr: int,
    freq: float,
    duration: float,
    *,
    decay: float,
) -> np.ndarray:
    n = max(1, round(float(sr) * float(duration)))
    t = np.arange(n, dtype=np.float64) / float(sr)
    env = np.exp(-float(decay) * t / max(float(duration), 1e-6))
    return (env * np.sin(2.0 * np.pi * float(freq) * t)).astype(np.float32)


def _place_clicks(
    times: np.ndarray,
    *,
    sr: int,
    length: int,
    wave: np.ndarray,
) -> np.ndarray:
    out = np.zeros(int(length), dtype=np.float32)
    wave = np.asarray(wave, dtype=np.float32).reshape(-1)
    if wave.size == 0 or sr <= 0:
        return out
    n = int(length)
    for t in times:
        start = round(float(t) * sr)
        if start < 0 or start >= n:
            continue
        end = min(n, start + wave.size)
        out[start:end] += wave[: end - start]
    return out


def _downbeat_times_1x(
    times_1x: np.ndarray,
    *,
    ref_sec: float,
    beats_per_measure: int,
) -> np.ndarray:
    times = np.asarray(times_1x, dtype=np.float64).reshape(-1)
    if times.size == 0:
        return times
    measure = max(1, int(beats_per_measure))
    ref_idx = int(np.argmin(np.abs(times - float(ref_sec))))
    beat_index = np.arange(times.size, dtype=np.int64) - ref_idx
    return times[beat_index % measure == 0]


def _times_in_set(candidates: np.ndarray, reference: np.ndarray, *, tol: float = 1e-4) -> np.ndarray:
    if candidates.size == 0 or reference.size == 0:
        return np.zeros(0, dtype=np.float64)
    keep = np.zeros(candidates.size, dtype=bool)
    for i, t in enumerate(candidates):
        keep[i] = bool(np.any(np.abs(reference - float(t)) <= tol))
    return candidates[keep]


def render_metronome_wav(
    times_1x: np.ndarray,
    output_path: str | Path,
    *,
    sr: int,
    n_samples: int,
    options: MetronomeRenderOptions | None = None,
    ref_sec: float,
    beats_per_measure: int = 4,
) -> bool:
    """Write a stereo click WAV from a stored 1x grid. Does not beat-track."""
    opts = options or MetronomeRenderOptions()
    opts = coerce_metronome_render_options(
        accent=opts.accent, rate=opts.rate, sound=opts.sound
    )
    preset = _SOUND_PRESETS.get(opts.sound, _SOUND_PRESETS["classic"])
    times_1x = np.asarray(times_1x, dtype=np.float64).reshape(-1)
    times_1x = np.sort(times_1x[np.isfinite(times_1x)])
    audible = apply_click_rate(times_1x, rate=opts.rate, ref_sec=ref_sec)
    if audible.size < 1 or sr <= 0 or n_samples <= 0:
        return False

    beat_wave = _synth_click_wave(
        sr, float(preset["beat_hz"]), float(preset["duration"]), decay=float(preset["decay"])
    )
    down_wave = _synth_click_wave(
        sr, float(preset["down_hz"]), float(preset["duration"]), decay=float(preset["decay"])
    )
    if opts.accent:
        downs_1x = _downbeat_times_1x(
            times_1x, ref_sec=ref_sec, beats_per_measure=beats_per_measure
        )
        down = _times_in_set(audible, downs_1x)
        others = audible
        if down.size:
            mask = np.zeros(audible.size, dtype=bool)
            for i, t in enumerate(audible):
                mask[i] = bool(np.any(np.abs(down - float(t)) <= 1e-4))
            others = audible[~mask]
        clicks = _place_clicks(down if down.size else audible[:1], sr=sr, length=n_samples, wave=down_wave)
        if others.size:
            clicks = clicks + _ORDINARY_MIX * _place_clicks(
                others, sr=sr, length=n_samples, wave=beat_wave
            )
    else:
        clicks = _place_clicks(audible, sr=sr, length=n_samples, wave=beat_wave)

    peak = float(np.max(np.abs(clicks))) if clicks.size else 0.0
    if peak <= 0:
        return False
    target = float(preset["peak"])
    clicks = clicks * (target / peak)
    stereo = np.column_stack([clicks, clicks]).astype(np.float32)
    dest = Path(output_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        sf.write(str(dest), stereo, int(sr), subtype="PCM_16")
    except Exception as exc:
        logger.debug("metronome: write failed: %s", exc)
        return False
    return True


def generate_metronome_stem(
    audio_path: str | Path,
    output_path: str | Path,
    *,
    sr: int | None = None,
    beats_per_measure: int = _DEFAULT_BEATS_PER_MEASURE,
    source: str = "source",
    render: MetronomeRenderOptions | None = None,
) -> MetronomeResult | None:
    """Beat-track the source, then write clicks on detected beats (plus lead-in).

    ``beats_per_measure`` left at the default is detected from the audio; any
    other value is treated as an explicit override.

    Accent phase uses ``body_start_sec`` (loud groove), which may be later than
    ``first_detected_sec`` when a quieter locally-stable intro pulse is kept.
    """
    try:
        import librosa
    except ImportError:
        logger.debug("librosa missing; skipping metronome stem")
        return None

    opts = coerce_metronome_render_options(
        accent=True if render is None else render.accent,
        rate=1.0 if render is None else render.rate,
        sound="classic" if render is None else render.sound,
    )
    src = Path(audio_path)
    dest = Path(output_path)
    if not src.is_file():
        return None
    try:
        y, file_sr = sf.read(str(src), always_2d=True)
    except Exception as exc:
        logger.debug("metronome: could not read %s: %s", src, exc)
        return None
    if y.size == 0:
        return None
    mono = y.mean(axis=1).astype(np.float32)
    native_sr = int(file_sr if sr is None else sr)
    if native_sr <= 0 or len(mono) < native_sr // 4:
        return None
    if float(np.max(np.abs(mono))) < 1e-6:
        return None

    duration_sec = len(mono) / float(native_sr)
    try:
        onset = _onset_envelope(mono, native_sr, hop_length=_HOP_LENGTH)
        tempo, beats = librosa.beat.beat_track(
            onset_envelope=onset,
            sr=native_sr,
            hop_length=_HOP_LENGTH,
            units="time",
            trim=False,
        )
    except Exception as exc:
        logger.debug("metronome: beat_track failed: %s", exc)
        return None

    bpm_hint = float(np.atleast_1d(tempo)[0]) if tempo is not None else 0.0
    detected = np.asarray(beats, dtype=np.float64).reshape(-1)
    detected = detected[np.isfinite(detected)]
    detected = detected[(detected >= 0.0) & (detected < duration_sec)]
    if detected.size < _MIN_BEATS or not np.isfinite(bpm_hint) or bpm_hint <= 0:
        return None

    bpm, _phase = refine_tempo_phase(detected, bpm_hint)
    hop_times = librosa.times_like(onset, sr=native_sr, hop_length=_HOP_LENGTH)
    hop_times = np.asarray(hop_times, dtype=np.float64).reshape(-1)
    try:
        raw_curve = tempo_curve_from_onset(
            onset, sr=native_sr, hop_length=_HOP_LENGTH
        )
    except Exception as exc:
        logger.debug("metronome: tempo curve failed: %s", exc)
        raw_curve = np.zeros(0, dtype=np.float64)
    if raw_curve.size != onset.size:
        raw_curve = np.full(max(onset.size, 1), bpm, dtype=np.float64)
    curve = stabilize_tempo_curve(
        raw_curve, sr=native_sr, hop_length=_HOP_LENGTH, global_bpm=bpm
    )
    if curve.size != hop_times.size:
        hop_times = librosa.times_like(curve, sr=native_sr, hop_length=_HOP_LENGTH)
        hop_times = np.asarray(hop_times, dtype=np.float64).reshape(-1)
    conf = curve_confidence(
        onset[: curve.size],
        curve,
        global_bpm=bpm,
        sr=native_sr,
        hop_length=_HOP_LENGTH,
    )
    local_beats = detected
    try:
        _tempo_local, tracked = librosa.beat.beat_track(
            onset_envelope=onset,
            sr=native_sr,
            hop_length=_HOP_LENGTH,
            bpm=curve if curve.size == onset.size else None,
            units="time",
            trim=False,
        )
        tracked = np.asarray(tracked, dtype=np.float64).reshape(-1)
        tracked = tracked[np.isfinite(tracked)]
        tracked = tracked[(tracked >= 0.0) & (tracked < duration_sec)]
        if tracked.size >= _MIN_BEATS:
            local_beats = tracked
    except Exception as exc:
        logger.debug("metronome: local beat_track failed: %s", exc)

    period = 60.0 / bpm if bpm > 0 else 0.0
    local_periods = np.asarray(
        [local_period_at(float(t), hop_times, curve, bpm) for t in local_beats],
        dtype=np.float64,
    )
    gated, body_start = gate_unreliable_intro_beats(
        local_beats, mono, native_sr, period, local_periods=local_periods
    )
    if gated.size < _MIN_BEATS:
        gated, body_start = gate_unreliable_intro_beats(
            detected, mono, native_sr, period
        )
    if gated.size < _MIN_BEATS:
        gated = detected
        body_start = float(detected[0])

    body_beats = gated[gated >= float(body_start) - 1e-9]
    if body_beats.size >= 3:
        bpm, _phase = refine_tempo_phase(body_beats, bpm)
    high = conf >= _LOCAL_CONF_FLOOR if conf.size else np.zeros(0, dtype=bool)
    if high.size and np.any(high):
        reported = float(np.median(curve[: high.size][high[: curve.size]]))
        if np.isfinite(reported) and reported > 0:
            bpm = float(np.clip(reported, MIN_PLAUSIBLE_BPM, MAX_PLAUSIBLE_BPM))

    times = build_click_times(
        gated,
        duration_sec=duration_sec,
        bpm=bpm,
        tempo_curve=curve,
        curve_times=hop_times,
        curve_conf=conf,
    )
    if times.size < _MIN_BEATS:
        return None

    measure = max(1, int(beats_per_measure))
    meter_beats = body_beats if body_beats.size >= _MIN_BEATS else gated
    if measure == _DEFAULT_BEATS_PER_MEASURE:
        measure = detect_beats_per_measure(meter_beats, mono, native_sr, bpm)

    n = len(mono)
    ref_sec = float(body_start)
    if not render_metronome_wav(
        times,
        dest,
        sr=native_sr,
        n_samples=n,
        options=opts,
        ref_sec=ref_sec,
        beats_per_measure=measure,
    ):
        return None

    body_n = int(body_beats.size)
    if high.size and np.any(high):
        selected = curve[: high.size][high[: curve.size]]
        iqr = float(np.subtract(*np.percentile(selected, [75, 25]))) if selected.size else 0.0
    else:
        iqr = 0.0
    confidence = (
        "high"
        if body_n >= 8
        and iqr <= _CURVE_IQR_HIGH_BPM
        and MIN_PLAUSIBLE_BPM <= bpm <= MAX_PLAUSIBLE_BPM
        else "low"
    )
    curve_t, curve_b = _downsample_bpm_curve(hop_times, curve, duration_sec)
    return MetronomeResult(
        path=dest,
        bpm=bpm,
        beat_count=int(times.size),
        confidence=confidence,
        source=source,
        sr=native_sr,
        duration_sec=float(duration_sec),
        body_start_sec=float(body_start),
        first_detected_sec=float(gated[0]),
        detected_times=tuple(float(t) for t in gated),
        click_times_1x=tuple(float(t) for t in times),
        beats_per_measure=measure,
        render=opts,
        bpm_curve_t=curve_t,
        bpm_curve_bpm=curve_b,
    )


def write_metronome_diagnostics(path: Path, result: MetronomeResult) -> Path:
    payload = {
        "bpm": result.bpm,
        "beat_count": result.beat_count,
        "confidence": result.confidence,
        "source": result.source,
        "path": str(result.path),
        "sr": result.sr,
        "duration_sec": result.duration_sec,
        "body_start_sec": result.body_start_sec,
        "first_detected_sec": result.first_detected_sec,
        "detected_times": list(result.detected_times),
        "click_times_1x": list(result.click_times_1x),
        "beats_per_measure": result.beats_per_measure,
        "render": result.render.to_dict(),
    }
    if result.bpm_curve_t and result.bpm_curve_bpm:
        payload["bpm_curve"] = {
            "t": list(result.bpm_curve_t),
            "bpm": list(result.bpm_curve_bpm),
        }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def load_metronome_diagnostics(path: str | Path) -> dict[str, Any] | None:
    dest = Path(path)
    if not dest.is_file():
        return None
    try:
        raw = json.loads(dest.read_text(encoding="utf-8"))
    except Exception:
        return None
    return raw if isinstance(raw, dict) else None


def _times_from_payload(raw: Any) -> np.ndarray:
    if not isinstance(raw, list):
        return np.zeros(0, dtype=np.float64)
    values = []
    for item in raw:
        try:
            values.append(float(item))
        except (TypeError, ValueError):
            continue
    return np.asarray(values, dtype=np.float64)


def _source_candidates_from_dir(
    output_dir: Path,
    *,
    artifacts: dict[str, Path] | None = None,
    fallback: Path | None = None,
) -> list[tuple[Path, str]]:
    if artifacts:
        candidates = _metronome_source_candidates(artifacts, fallback=fallback)
        if candidates:
            return candidates
    candidates = []
    if fallback is not None and Path(fallback).is_file():
        candidates.append((Path(fallback), "source"))
    for name in _ANALYSIS_STEM_PRIORITY:
        path = output_dir / f"{name}.wav"
        if path.is_file():
            candidates.append((path, name))
    return candidates


def _result_from_payload(
    dest: Path,
    payload: dict[str, Any],
    *,
    options: MetronomeRenderOptions,
    times_1x: np.ndarray,
    detected: np.ndarray,
) -> MetronomeResult:
    first = float(detected[0]) if detected.size else float(payload.get("first_detected_sec") or 0.0)
    body = float(payload.get("body_start_sec") or first)
    sr = int(payload.get("sr") or 0)
    duration = float(payload.get("duration_sec") or 0.0)
    bpm = float(payload.get("bpm") or 0.0)
    confidence = str(payload.get("confidence") or "low")
    source = str(payload.get("source") or "source")
    measure = max(1, int(payload.get("beats_per_measure") or 4))
    curve_t, curve_b = _bpm_curve_from_payload(payload.get("bpm_curve"))
    return MetronomeResult(
        path=dest,
        bpm=bpm,
        beat_count=int(times_1x.size),
        confidence=confidence,
        source=source,
        sr=sr,
        duration_sec=duration,
        body_start_sec=body,
        first_detected_sec=first,
        detected_times=tuple(float(t) for t in detected),
        click_times_1x=tuple(float(t) for t in times_1x),
        beats_per_measure=measure,
        render=options,
        bpm_curve_t=curve_t,
        bpm_curve_bpm=curve_b,
    )


def rebake_metronome_artifact(
    output_dir: str | Path,
    options: MetronomeRenderOptions | None = None,
    *,
    diagnostics_path: str | Path | None = None,
    artifacts: dict[str, Path] | None = None,
    fallback: Path | None = None,
) -> MetronomeResult | None:
    """Rewrite metronome.wav from a stored 1x grid (or re-track if needed)."""
    opts = options or MetronomeRenderOptions()
    opts = coerce_metronome_render_options(
        accent=opts.accent, rate=opts.rate, sound=opts.sound
    )
    out_dir = Path(output_dir)
    diag_path = Path(diagnostics_path) if diagnostics_path else out_dir / METRONOME_DIAGNOSTICS_NAME
    dest = out_dir / f"{METRONOME_STEM_ID}.wav"
    payload = load_metronome_diagnostics(diag_path) or {}
    times_1x = _times_from_payload(payload.get("click_times_1x"))
    detected = _times_from_payload(payload.get("detected_times"))
    sr = int(payload.get("sr") or 0)
    n_samples = 0
    if dest.is_file():
        try:
            info = sf.info(str(dest))
            if sr <= 0:
                sr = int(info.samplerate)
            n_samples = int(info.frames)
        except Exception:
            n_samples = 0
    duration = float(payload.get("duration_sec") or 0.0)
    if n_samples <= 0 and sr > 0 and duration > 0:
        n_samples = round(duration * sr)
    if "body_start_sec" in payload:
        ref_sec = float(payload.get("body_start_sec") or 0.0)
    else:
        ref_sec = float(
            payload.get("first_detected_sec")
            or (detected[0] if detected.size else 0.0)
        )
    measure = max(1, int(payload.get("beats_per_measure") or 4))

    if times_1x.size >= _MIN_BEATS and sr > 0 and n_samples > 0:
        if render_metronome_wav(
            times_1x,
            dest,
            sr=sr,
            n_samples=n_samples,
            options=opts,
            ref_sec=ref_sec,
            beats_per_measure=measure,
        ):
            result = _result_from_payload(
                dest, payload, options=opts, times_1x=times_1x, detected=detected
            )
            write_metronome_diagnostics(diag_path, result)
            return result
        return None

    # Try each candidate: a mix that cannot be decoded must not block the stems.
    for audio_path, source in _source_candidates_from_dir(
        out_dir, artifacts=artifacts, fallback=fallback
    ):
        result = generate_metronome_stem(
            audio_path,
            dest,
            source=source,
            render=opts,
            beats_per_measure=measure,
        )
        if result is None:
            continue
        write_metronome_diagnostics(diag_path, result)
        return result
    return None


def attach_metronome_artifact(
    artifacts: dict[str, Path],
    output_dir: Path,
    *,
    fallback: Path | None = None,
    render: MetronomeRenderOptions | None = None,
) -> MetronomeResult | None:
    """Write metronome.wav into ``artifacts`` when beat tracking succeeds."""
    out_dir = Path(output_dir)
    # Mix first; fall through to stems when it cannot be read or tracked.
    for audio_path, source in _metronome_source_candidates(artifacts, fallback=fallback):
        result = generate_metronome_stem(
            audio_path,
            out_dir / f"{METRONOME_STEM_ID}.wav",
            source=source,
            render=render,
        )
        if result is None:
            continue
        artifacts[METRONOME_STEM_ID] = result.path
        artifacts["metronome_diagnostics"] = write_metronome_diagnostics(
            out_dir / METRONOME_DIAGNOSTICS_NAME, result
        )
        return result
    return None
