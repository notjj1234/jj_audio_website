"""Tempo estimation from audio and MIDI."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pretty_midi

logger = logging.getLogger(__name__)

MIN_PLAUSIBLE_BPM = 60.0
MAX_PLAUSIBLE_BPM = 180.0
TEMPO_DISAGREEMENT_RATIO = 0.15


@dataclass
class TempoEstimate:
    bpm: float
    confidence: str  # "high" | "low"
    source: str  # "audio" | "midi" | "override" | "default"


def _clamp_bpm(bpm: float) -> float:
    return float(np.clip(bpm, MIN_PLAUSIBLE_BPM, MAX_PLAUSIBLE_BPM))


def estimate_tempo_from_audio(audio_path: str | Path) -> TempoEstimate | None:
    """Estimate tempo from audio onset envelope via librosa."""
    try:
        import librosa
    except ImportError:
        return None

    try:
        y, sr = librosa.load(str(audio_path), sr=22050, mono=True, duration=120.0)
        if len(y) < sr:
            return None
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        tempo = librosa.feature.rhythm.tempo(onset_envelope=onset_env, sr=sr)
        bpm = float(np.atleast_1d(tempo)[0])
        if not bpm or np.isnan(bpm):
            return None
        return TempoEstimate(bpm=_clamp_bpm(bpm), confidence="high", source="audio")
    except Exception as exc:
        logger.debug("Audio tempo estimation failed: %s", exc)
        return None


def estimate_tempo_from_midi_robust(pm: pretty_midi.PrettyMIDI) -> float:
    """Robust MIDI tempo from median inter-onset interval with outlier rejection."""
    starts: list[float] = []
    for inst in pm.instruments:
        if inst.is_drum:
            continue
        starts.extend(n.start for n in inst.notes)

    if len(starts) < 4:
        try:
            t = float(pm.estimate_tempo())
            if t and not np.isnan(t):
                return _clamp_bpm(t)
        except Exception:
            pass
        return 120.0

    starts = sorted({round(s, 3) for s in starts})
    intervals = [starts[i + 1] - starts[i] for i in range(len(starts) - 1)]
    intervals = [iv for iv in intervals if iv >= 0.1]  # reject drum doubles <100ms
    if not intervals:
        return 120.0

    median_iv = float(np.median(intervals))
    beat_iv = median_iv
    if median_iv < 0.25:
        beat_iv = median_iv * 2
    elif median_iv > 1.0:
        beat_iv = median_iv / 2

    bpm = 60.0 / beat_iv if beat_iv > 0 else 120.0
    return _clamp_bpm(bpm)


def resolve_tempo(
    *,
    audio_path: str | Path | None,
    midi_path: str | Path,
    override_bpm: float | None = None,
) -> TempoEstimate:
    """Pick best tempo from override, audio, or robust MIDI estimate."""
    if override_bpm is not None and override_bpm > 0:
        return TempoEstimate(bpm=_clamp_bpm(override_bpm), confidence="high", source="override")

    audio_est = estimate_tempo_from_audio(audio_path) if audio_path else None
    pm = pretty_midi.PrettyMIDI(str(midi_path))
    midi_bpm = estimate_tempo_from_midi_robust(pm)

    if audio_est is None:
        return TempoEstimate(bpm=midi_bpm, confidence="low", source="midi")

    ratio = abs(audio_est.bpm - midi_bpm) / max(audio_est.bpm, midi_bpm)
    if ratio > TEMPO_DISAGREEMENT_RATIO:
        return TempoEstimate(bpm=audio_est.bpm, confidence="low", source="audio")

    return TempoEstimate(bpm=audio_est.bpm, confidence="high", source="audio")
