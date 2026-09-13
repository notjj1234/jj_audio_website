"""Beat-tracked metronome click stem for isolate mixer runs."""

from __future__ import annotations

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

    def slim_meta(self) -> dict[str, Any]:
        return {
            "bpm": self.bpm,
            "beat_count": self.beat_count,
            "confidence": self.confidence,
            "source": self.source,
            "render": self.render.to_dict(),
        }


def pick_metronome_source(
    artifacts: dict[str, Path],
    *,
    fallback: Path | None = None,
) -> tuple[Path, str] | None:
    """Prefer drums (then mix-like stems), else the original/clipped source."""
    for name in _ANALYSIS_STEM_PRIORITY:
        raw = artifacts.get(name)
        if raw is None:
            continue
        path = Path(raw)
        if path.is_file() and path.suffix.lower() == ".wav":
            return path, name
    if fallback is not None:
        path = Path(fallback)
        if path.is_file():
            return path, "source"
    return None


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
) -> np.ndarray:
    """Hybrid click times: detected beats in the body, extrapolated at the edges.

    A single global BPM grid drifts over long songs. Keeping librosa's beat times
    for the body follows the performance; walking backward from the first beat
    (and optionally forward past the last) still fills lead-in / trailing gaps.
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

    lead: list[float] = []
    t = float(body[0]) - period
    while t >= 0.0:
        lead.append(t)
        t -= period
    lead.reverse()

    tail: list[float] = []
    last = float(body[-1])
    if duration_sec - last > 1.5 * period:
        t = last + period
        while t < duration_sec:
            tail.append(t)
            t += period

    parts: list[np.ndarray] = []
    if lead:
        parts.append(np.asarray(lead, dtype=np.float64))
    parts.append(body)
    if tail:
        parts.append(np.asarray(tail, dtype=np.float64))
    times = np.concatenate(parts)
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


def _first_stable_run_index(
    detected: np.ndarray,
    period: float,
    *,
    min_beats: int = _STABLE_MIN_BEATS,
) -> int:
    if detected.size < min_beats or period <= 0:
        return 0
    need = min_beats - 1
    intervals = np.diff(detected)
    ok = np.abs(intervals - period) <= (_STABLE_IOI_REL * period)
    for i in range(ok.size - need + 1):
        if bool(np.all(ok[i : i + need])):
            return i
    return 0


def gate_unreliable_intro_beats(
    detected: np.ndarray,
    mono: np.ndarray,
    sr: int,
    period: float,
) -> tuple[np.ndarray, float]:
    """Drop weak/irregular intro onsets; keep a trusted body start.

    Lead-in clicks are still filled from this origin back to t=0.
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
    loud_idx = int(np.argmax(loud)) if np.any(loud) else 0
    stable_idx = _first_stable_run_index(times, period)
    start_idx = max(loud_idx, stable_idx)
    body_start = float(times[start_idx])
    gated = times[start_idx:]
    if gated.size < _MIN_BEATS:
        return times, float(times[0])
    return gated, body_start


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
    beats_per_measure: int = 4,
    source: str = "source",
    render: MetronomeRenderOptions | None = None,
) -> MetronomeResult | None:
    """Beat-track the source, then write clicks on detected beats (plus lead-in)."""
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
        tempo, beats = librosa.beat.beat_track(
            y=mono, sr=native_sr, units="time", trim=False
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
    period = 60.0 / bpm if bpm > 0 else 0.0
    gated, body_start = gate_unreliable_intro_beats(detected, mono, native_sr, period)
    if gated.size >= 3:
        bpm, _phase = refine_tempo_phase(gated, bpm)
    if gated.size < _MIN_BEATS:
        gated = detected
        body_start = float(detected[0])

    times = build_click_times(gated, duration_sec=duration_sec, bpm=bpm)
    if times.size < _MIN_BEATS:
        return None

    n = len(mono)
    ref_sec = float(gated[0])
    if not render_metronome_wav(
        times,
        dest,
        sr=native_sr,
        n_samples=n,
        options=opts,
        ref_sec=ref_sec,
        beats_per_measure=beats_per_measure,
    ):
        return None

    confidence = (
        "high"
        if gated.size >= 8 and MIN_PLAUSIBLE_BPM <= bpm <= MAX_PLAUSIBLE_BPM
        else "low"
    )
    return MetronomeResult(
        path=dest,
        bpm=bpm,
        beat_count=int(times.size),
        confidence=confidence,
        source=source,
        sr=native_sr,
        duration_sec=float(duration_sec),
        body_start_sec=float(body_start),
        first_detected_sec=ref_sec,
        detected_times=tuple(float(t) for t in gated),
        click_times_1x=tuple(float(t) for t in times),
        beats_per_measure=max(1, int(beats_per_measure)),
        render=opts,
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


def _pick_source_from_dir(
    output_dir: Path,
    *,
    artifacts: dict[str, Path] | None = None,
    fallback: Path | None = None,
) -> tuple[Path, str] | None:
    if artifacts:
        picked = pick_metronome_source(artifacts, fallback=fallback)
        if picked is not None:
            return picked
    for name in _ANALYSIS_STEM_PRIORITY:
        path = output_dir / f"{name}.wav"
        if path.is_file():
            return path, name
    if fallback is not None and Path(fallback).is_file():
        return Path(fallback), "source"
    return None


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
    ref_sec = float(payload.get("first_detected_sec") or (detected[0] if detected.size else 0.0))
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

    picked = _pick_source_from_dir(out_dir, artifacts=artifacts, fallback=fallback)
    if picked is None:
        return None
    audio_path, source = picked
    result = generate_metronome_stem(
        audio_path,
        dest,
        source=source,
        render=opts,
        beats_per_measure=measure,
    )
    if result is None:
        return None
    write_metronome_diagnostics(diag_path, result)
    return result


def attach_metronome_artifact(
    artifacts: dict[str, Path],
    output_dir: Path,
    *,
    fallback: Path | None = None,
    render: MetronomeRenderOptions | None = None,
) -> MetronomeResult | None:
    """Write metronome.wav into ``artifacts`` when beat tracking succeeds."""
    picked = pick_metronome_source(artifacts, fallback=fallback)
    if picked is None:
        return None
    audio_path, source = picked
    out_dir = Path(output_dir)
    result = generate_metronome_stem(
        audio_path,
        out_dir / f"{METRONOME_STEM_ID}.wav",
        source=source,
        render=render,
    )
    if result is None:
        return None
    artifacts[METRONOME_STEM_ID] = result.path
    artifacts["metronome_diagnostics"] = write_metronome_diagnostics(
        out_dir / METRONOME_DIAGNOSTICS_NAME, result
    )
    return result
