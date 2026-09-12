"""Beat-tracked metronome click stem for isolate mixer runs."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

from audio_to_tab.tempo import MAX_PLAUSIBLE_BPM, MIN_PLAUSIBLE_BPM

logger = logging.getLogger(__name__)

METRONOME_STEM_ID = "metronome"
_ANALYSIS_STEM_PRIORITY = ("drums", "other", "guitar", "vocals", "bass")
_MIN_BEATS = 2
_CLICK_DURATION_SEC = 0.05
_BEAT_CLICK_HZ = 1000.0
_DOWNBEAT_CLICK_HZ = 1500.0
_PEAK = 0.5


@dataclass(frozen=True)
class MetronomeResult:
    path: Path
    bpm: float
    beat_count: int
    confidence: str
    source: str


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


def generate_metronome_stem(
    audio_path: str | Path,
    output_path: str | Path,
    *,
    sr: int | None = None,
    beats_per_measure: int = 4,
    source: str = "source",
) -> MetronomeResult | None:
    """Beat-track the source, then write clicks on detected beats (plus lead-in)."""
    try:
        import librosa
    except ImportError:
        logger.debug("librosa missing; skipping metronome stem")
        return None

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
    times = build_click_times(detected, duration_sec=duration_sec, bpm=bpm)
    if times.size < _MIN_BEATS:
        return None

    n = len(mono)
    measure = max(1, int(beats_per_measure))
    # Accent by sequential index relative to the first detected beat so lead-in
    # downbeats stay consistent when we extrapolate backward into silence.
    ref_idx = int(np.argmin(np.abs(times - float(detected[0]))))
    beat_index = np.arange(times.size, dtype=np.int64) - ref_idx
    down_mask = beat_index % measure == 0
    down = times[down_mask]
    others = times[~down_mask]
    try:
        click_down = librosa.clicks(
            times=down if down.size else times[:1],
            sr=native_sr,
            click_freq=_DOWNBEAT_CLICK_HZ,
            click_duration=_CLICK_DURATION_SEC,
            length=n,
        )
        if others.size:
            click_beat = librosa.clicks(
                times=others,
                sr=native_sr,
                click_freq=_BEAT_CLICK_HZ,
                click_duration=_CLICK_DURATION_SEC,
                length=n,
            )
        else:
            click_beat = np.zeros(n, dtype=np.float32)
    except Exception as exc:
        logger.debug("metronome: clicks failed: %s", exc)
        return None

    clicks = np.asarray(click_down, dtype=np.float32) + 0.7 * np.asarray(
        click_beat, dtype=np.float32
    )
    peak = float(np.max(np.abs(clicks))) if clicks.size else 0.0
    if peak <= 0:
        return None
    clicks = clicks * (_PEAK / peak)
    stereo = np.column_stack([clicks, clicks]).astype(np.float32)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        sf.write(str(dest), stereo, native_sr, subtype="PCM_16")
    except Exception as exc:
        logger.debug("metronome: write failed: %s", exc)
        return None

    confidence = (
        "high"
        if detected.size >= 8 and MIN_PLAUSIBLE_BPM <= bpm <= MAX_PLAUSIBLE_BPM
        else "low"
    )
    return MetronomeResult(
        path=dest,
        bpm=bpm,
        beat_count=int(times.size),
        confidence=confidence,
        source=source,
    )


def write_metronome_diagnostics(path: Path, result: MetronomeResult) -> Path:
    payload = {
        "bpm": result.bpm,
        "beat_count": result.beat_count,
        "confidence": result.confidence,
        "source": result.source,
        "path": str(result.path),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def attach_metronome_artifact(
    artifacts: dict[str, Path],
    output_dir: Path,
    *,
    fallback: Path | None = None,
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
    )
    if result is None:
        return None
    artifacts[METRONOME_STEM_ID] = result.path
    artifacts["metronome_diagnostics"] = write_metronome_diagnostics(
        out_dir / "metronome_diagnostics.json", result
    )
    return result
