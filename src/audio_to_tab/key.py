"""Key estimation: chord-histogram first, chroma profiles as the fallback.

The chord path is preferred because a song's tonic is usually stated by its harmony, while raw
chroma on guitar/pop mixes is biased by open strings, bass, and drums. The chroma path exists for
the no-chord case (silence is rejected, never guessed).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

import numpy as np

from audio_to_tab.analysis import ChordEvent
from audio_to_tab.chord_symbols import parse as parse_symbol

logger = logging.getLogger(__name__)

PITCHES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")

MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

_MAJOR_DEGREES = {0: "maj", 2: "min", 4: "min", 5: "maj", 7: "maj", 9: "min", 11: "dim"}
_MINOR_DEGREES = {0: "min", 2: "dim", 3: "maj", 5: "min", 7: "min", 8: "maj", 10: "maj"}


@dataclass(frozen=True)
class _ParsedChord:
    root: int
    quality: str  # "maj" | "min" | "dim" | "sus"


def _parse_chord(symbol: str) -> _ParsedChord | None:
    chord = parse_symbol(symbol)
    if chord is None:
        return None
    if chord.quality in {"dim", "dim7", "m7b5"}:
        quality = "dim"
    elif chord.quality in {"sus2", "sus4", "5"}:
        quality = "sus"
    elif chord.quality in {"min", "m7", "m6", "mMaj7", "m9"}:
        quality = "min"
    else:
        quality = "maj"
    return _ParsedChord(root=PITCHES.index(chord.root), quality=quality)


def _event_weight(chord: ChordEvent, downbeats: Sequence[float], beat_sec: float) -> float:
    duration = float(chord.end) - float(chord.start)
    if duration <= 0 or beat_sec <= 0 or not downbeats:
        return duration
    tolerance = 0.45 * beat_sec
    for downbeat in downbeats:
        if abs(float(chord.start) - float(downbeat)) <= tolerance:
            return duration * 1.5
    return duration


def _key_from_chords(
    chords: Sequence[ChordEvent],
    *,
    downbeats: Sequence[float] = (),
    beat_sec: float = 0.0,
) -> tuple[str | None, str]:
    parsed: list[tuple[float, _ParsedChord]] = []
    for chord in chords:
        if str(chord.symbol).upper() == "N":
            continue
        duration = _event_weight(chord, downbeats, beat_sec)
        item = _parse_chord(chord.symbol)
        if item is not None and duration > 0:
            parsed.append((duration, item))
    if not parsed:
        return None, "low"

    total = sum(duration for duration, _ in parsed)
    scored: list[tuple[float, str, int, str]] = []
    for tonic_index, tonic in enumerate(PITCHES):
        for mode, table in (("maj", _MAJOR_DEGREES), ("min", _MINOR_DEGREES)):
            score = 0.0
            for duration, item in parsed:
                degree = (item.root - tonic_index) % 12
                expected = table.get(degree)
                if expected is None:
                    continue
                if item.quality == "sus":
                    score += duration * 0.5
                elif item.quality == expected:
                    score += duration
                elif degree == 7 and item.quality == "maj":
                    # Harmonic-minor V, or a secondary dominant resolving home.
                    score += duration * (1.0 if mode == "maj" else 0.8)
                elif degree == 0:
                    # Tonic root with the wrong third: keep the option alive, but weakly.
                    score += duration * 0.3
            last_duration, last = parsed[-1]
            if last.root == tonic_index:
                score += last_duration * 0.25
            name = tonic if mode == "maj" else f"{tonic}m"
            scored.append((score / total, name, tonic_index, mode))

    scored.sort(key=lambda row: row[0], reverse=True)
    top_score, top_name, top_tonic, _ = scored[0]
    second_score, second_name, second_tonic, _ = scored[1]
    if top_score < 0.30:
        return None, "low"

    margin = top_score - second_score
    confidence = "low"
    if top_score >= 0.55 and margin >= 0.03:
        confidence = "high"
    elif top_score >= 0.45:
        confidence = "medium"
    if top_tonic == second_tonic and margin < 0.08:
        confidence = "medium" if confidence == "high" else confidence
    logger.debug(
        "Chord key %s (%.3f) over %s (%.3f), margin %.3f",
        top_name,
        top_score,
        second_name,
        second_score,
        margin,
    )
    return top_name, confidence


def _chroma_key(audio_path: Path, beats: Sequence[float]) -> tuple[str | None, str]:
    audio_path = Path(audio_path)
    if not audio_path.is_file():
        return None, "low"
    try:
        import librosa
    except ImportError:
        return None, "low"
    try:
        y, sr = librosa.load(str(audio_path), sr=22050, mono=True)
    except Exception as exc:
        logger.debug("Key audio load failed: %s", exc)
        return None, "low"
    if y.size < int(sr * 1.0):
        return None, "low"
    if float(np.sqrt(np.mean(y**2))) < 1e-4:
        return None, "low"

    try:
        hop = 512
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop)
        beat_times = np.asarray([float(b) for b in beats if isinstance(b, (int, float)) and b >= 0])
        if beat_times.size >= 2:
            frames = librosa.time_to_frames(beat_times, sr=sr, hop_length=hop)
            frames = np.unique(frames[(frames >= 0) & (frames < chroma.shape[1])])
            if frames.size >= 2:
                chroma = librosa.util.sync(chroma, frames, aggregate=np.mean, pad=False)
        mean = chroma.mean(axis=1)
    except Exception as exc:
        logger.debug("Chroma key estimation failed: %s", exc)
        return None, "low"

    norm = float(np.linalg.norm(mean))
    if norm < 1e-9:
        return None, "low"
    mean = mean / norm
    scored: list[tuple[float, str]] = []
    for index, tonic in enumerate(PITCHES):
        for mode, profile in (("maj", MAJOR_PROFILE), ("min", MINOR_PROFILE)):
            rotated = np.roll(profile, index)
            rotated = rotated / np.linalg.norm(rotated)
            name = tonic if mode == "maj" else f"{tonic}m"
            scored.append((float(np.dot(mean, rotated)), name))
    scored.sort(reverse=True)
    top_score, top_name = scored[0]
    second_score, _ = scored[1]
    if top_score < 0.50:
        return None, "low"
    margin = top_score - second_score
    if top_score >= 0.85 and margin >= 0.06:
        confidence = "high"
    elif top_score >= 0.70:
        confidence = "medium"
    else:
        confidence = "low"
    return top_name, confidence


def _pearson(left: np.ndarray, right: np.ndarray) -> float:
    left = np.asarray(left, dtype=np.float64) - float(np.mean(left))
    right = np.asarray(right, dtype=np.float64) - float(np.mean(right))
    denom = float(np.linalg.norm(left) * np.linalg.norm(right))
    if denom < 1e-12:
        return 0.0
    return float(np.dot(left, right) / denom)


def _relative_pair(left: tuple[int, str], right: tuple[int, str]) -> bool:
    if left[1] == right[1]:
        return False
    major, minor = (left, right) if left[1] == "maj" else (right, left)
    if major[1] != "maj" or minor[1] != "min":
        return False
    return (minor[0] - major[0]) % 12 == 9


def provisional_key(chroma_mean: np.ndarray, bass_mean: np.ndarray) -> tuple[str, float]:
    """Krumhansl correlation over 24 keys. Bass energy breaks a close relative maj/min tie."""
    chroma = np.asarray(chroma_mean, dtype=np.float64).reshape(-1)
    bass = np.asarray(bass_mean, dtype=np.float64).reshape(-1)
    if chroma.size != 12:
        chroma = np.resize(chroma, 12)
    if bass.size != 12:
        bass = np.resize(bass, 12)
    scored: list[tuple[float, str, int, str]] = []
    for index, tonic in enumerate(PITCHES):
        for mode, profile in (("maj", MAJOR_PROFILE), ("min", MINOR_PROFILE)):
            name = tonic if mode == "maj" else f"{tonic}m"
            scored.append((_pearson(chroma, np.roll(profile, index)), name, index, mode))
    scored.sort(key=lambda row: row[0], reverse=True)
    top_score, top_name, top_tonic, top_mode = scored[0]
    second_score, second_name, second_tonic, second_mode = scored[1]
    margin = top_score - second_score
    relative = _relative_pair((top_tonic, top_mode), (second_tonic, second_mode))
    if margin < 0.05 and relative and float(bass[second_tonic]) > float(bass[top_tonic]):
        return second_name, float(second_score)
    return top_name, float(top_score)


def provisional_key_from_audio(audio_path: Path) -> tuple[str | None, float]:
    """Chroma provisional key. Missing or silent audio returns ``(None, 0)``."""
    audio_path = Path(audio_path)
    if not audio_path.is_file():
        return None, 0.0
    try:
        import librosa
    except ImportError:
        return None, 0.0
    try:
        y, sr = librosa.load(str(audio_path), sr=22050, mono=True)
    except Exception as exc:
        logger.debug("Provisional key audio load failed: %s", exc)
        return None, 0.0
    if y.size < int(sr * 0.5) or float(np.sqrt(np.mean(y**2))) < 1e-4:
        return None, 0.0
    try:
        harmonic, _percussive = librosa.effects.hpss(y)
        tuning = float(librosa.estimate_tuning(y=y, sr=sr))
        tuning_bins = tuning * (36 / 12.0)
        chroma = librosa.feature.chroma_cqt(
            y=harmonic,
            sr=sr,
            hop_length=512,
            tuning=tuning_bins,
            bins_per_octave=36,
            norm=None,
        )
        bass = librosa.feature.chroma_cqt(
            y=y,
            sr=sr,
            hop_length=512,
            fmin=librosa.note_to_hz("C2"),
            n_octaves=3,
            tuning=tuning_bins,
            bins_per_octave=36,
            norm=None,
        )
    except Exception as exc:
        logger.debug("Provisional chroma failed: %s", exc)
        return None, 0.0
    name, score = provisional_key(chroma.mean(axis=1), bass.mean(axis=1))
    return name, float(score)


def estimate_key(
    audio_path: Path,
    *,
    bpm: float | None = None,
    beats: Sequence[float] = (),
    chords: Sequence[ChordEvent] = (),
    downbeats: Sequence[float] = (),
    beats_per_measure: int = 4,
) -> tuple[str | None, str]:
    """Return ``(key, confidence)``; ``(None, "low")`` when the audio is silent/unreadable.

    ``chords`` is optional. When present and parseable it wins; otherwise the chroma path runs.
    ``bpm`` and ``downbeats`` weight beat-1 chords more heavily on that chord path.
    """
    beat_sec = 60.0 / float(bpm) if bpm and bpm > 0 else 0.0
    if beat_sec <= 0 and len(beats) >= 2:
        spacing = [float(b) - float(a) for a, b in pairwise(beats) if float(b) > float(a)]
        if spacing:
            beat_sec = float(sorted(spacing)[len(spacing) // 2])
    del beats_per_measure
    if chords:
        key, confidence = _key_from_chords(chords, downbeats=downbeats, beat_sec=beat_sec)
        if key is not None:
            return key, confidence
    return _chroma_key(Path(audio_path), beats)


__all__ = ["PITCHES", "estimate_key", "provisional_key", "provisional_key_from_audio"]
