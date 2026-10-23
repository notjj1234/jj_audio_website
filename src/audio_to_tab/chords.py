"""Chord detection for the practice player.

P0 is the zero-dependency template baseline: beat-synchronous chroma, triad-first template
scoring, and Viterbi smoothing with a chord-change penalty. It is deliberately a *draft*
detector, so every event carries ``confidence=0.0``; the UI must not present it as certain.
A future neural model can plug into ``model_dir`` without changing the event contract.
"""

from __future__ import annotations

import logging
import math
import re
from collections.abc import Callable, Sequence
from itertools import pairwise
from pathlib import Path
from statistics import median

import numpy as np

from audio_to_tab.analysis import ChordEvent

logger = logging.getLogger(__name__)

PITCHES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
_FLAT_TO_SHARP = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#"}
_ROOT_RE = re.compile(r"^([A-Ga-g])([#b]?)(.*)$")

_QUALITY_INTERVALS: dict[str, tuple[int, ...]] = {
    "maj": (0, 4, 7),
    "min": (0, 3, 7),
    "7": (0, 4, 7, 10),
    "maj7": (0, 4, 7, 11),
    "m7": (0, 3, 7, 10),
    "sus4": (0, 5, 7),
    "dim": (0, 3, 6),
    "aug": (0, 4, 8),
}
_QUALITY_SUFFIX = {
    "maj": "",
    "min": "m",
    "7": "7",
    "maj7": "maj7",
    "m7": "m7",
    "sus4": "sus4",
    "dim": "dim",
    "aug": "aug",
}
_HOP = 512
_FALLBACK_WINDOW_SEC = 0.5
_MIN_EVENT_SEC = 0.10
_CHANGE_PENALTY = 0.06
_EXTENSION_PENALTY = 0.03


def _build_templates() -> dict[str, np.ndarray]:
    templates: dict[str, np.ndarray] = {}
    for quality, intervals in _QUALITY_INTERVALS.items():
        for index, pitch in enumerate(PITCHES):
            vector = np.zeros(12, dtype=np.float64)
            for interval in intervals:
                vector[(index + interval) % 12] = 1.0
            templates[f"{pitch}{_QUALITY_SUFFIX[quality]}"] = vector / np.linalg.norm(vector)
    return templates


_TEMPLATES = _build_templates()
_TEMPLATE_NAMES = tuple(_TEMPLATES)
_TEMPLATE_TABLE = np.stack([_TEMPLATES[name] for name in _TEMPLATE_NAMES])
_EXTENSION_PRIOR = np.array([_EXTENSION_PENALTY if name.endswith("7") else 0.0 for name in _TEMPLATE_NAMES])


def _root_name(letter: str, accidental: str) -> str:
    name = letter.upper() + accidental
    return _FLAT_TO_SHARP.get(name, name)


def _parse_head(head: str) -> tuple[str, str] | None:
    match = _ROOT_RE.match(head.strip())
    if not match:
        return None
    letter, accidental, rest = match.groups()
    root = _root_name(letter, accidental)
    if root not in PITCHES:
        return None
    return root, rest


def _quality_from_rest(rest: str) -> str | None:
    lowered = rest.strip().lower()
    if lowered in {"", "maj", "major"} or rest.strip() == "M":
        return "maj"
    if lowered in {"m", "min", "minor"}:
        return "min"
    if lowered in {"7", "dom7"}:
        return "7"
    if lowered in {"maj7", "major7"} or rest.strip() == "M7":
        return "maj7"
    if lowered in {"m7", "min7", "minor7"}:
        return "m7"
    if lowered in {"sus", "sus4"}:
        return "sus4"
    if lowered in {"dim", "°", "o"}:
        return "dim"
    if lowered in {"aug", "+"}:
        return "aug"
    return None


def _normalize_symbol(raw: object) -> str | None:
    """Return a canonical symbol from the small vocabulary, or ``None`` for garbage."""
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    if not text or text.upper() == "N":
        return None
    parts = text.split("/")
    if len(parts) > 2:
        return None
    head = _parse_head(parts[0])
    if head is None:
        return None
    root, rest = head
    quality = _quality_from_rest(rest)
    if quality is None:
        return None
    symbol = f"{root}{_QUALITY_SUFFIX[quality]}"
    if len(parts) == 2:
        bass = _parse_head(parts[1])
        if bass is None:
            return None
        symbol = f"{symbol}/{bass[0]}"
    return symbol


def _snap_to_beat(time: float, beats: Sequence[float], tolerance: float) -> float:
    if not beats:
        return float(time)
    nearest = min(float(b) for b in beats)
    for beat in beats:
        if abs(float(beat) - time) < abs(nearest - time):
            nearest = float(beat)
    return nearest if abs(nearest - time) <= tolerance else float(time)


def _merge_events(events: list[ChordEvent], *, min_duration: float = _MIN_EVENT_SEC) -> list[ChordEvent]:
    merged: list[ChordEvent] = []
    for event in sorted(events, key=lambda item: (item.start, item.end)):
        if event.end - event.start < min_duration:
            continue
        if merged and merged[-1].symbol == event.symbol and abs(merged[-1].end - event.start) <= 1e-6:
            previous = merged[-1]
            merged[-1] = ChordEvent(
                start=previous.start,
                end=event.end,
                symbol=previous.symbol,
                confidence=min(previous.confidence, event.confidence),
            )
        else:
            merged.append(event)
    return merged


def _viterbi(scores: np.ndarray, penalty: float = _CHANGE_PENALTY) -> list[int]:
    frames, states = scores.shape
    if frames == 0:
        return []
    dp = scores[0].copy()
    back = np.zeros((frames, states), dtype=np.int16)
    for index in range(1, frames):
        order = np.argsort(dp)[::-1]
        best, second = int(order[0]), int(order[1])
        best_value = float(dp[best])
        second_value = float(dp[second]) - penalty
        for state in range(states):
            stay = float(dp[state])
            other = second_value if state == best else best_value - penalty
            if stay >= other:
                back[index, state] = state
                dp[state] = scores[index, state] + stay
            else:
                back[index, state] = best if state != best else second
                dp[state] = scores[index, state] + other
    path = np.zeros(frames, dtype=np.int16)
    path[-1] = int(np.argmax(dp))
    for index in range(frames - 1, 0, -1):
        path[index - 1] = back[index, path[index]]
    return [int(value) for value in path]


def _notify(progress: Callable[[str], None] | None, message: str) -> None:
    if progress is None:
        return
    try:
        progress(message)
    except Exception:
        logger.debug("Chord progress callback failed", exc_info=True)


def _boundaries(beats: Sequence[float], duration: float) -> tuple[list[float], float]:
    valid = sorted(
        {
            float(beat)
            for beat in beats
            if isinstance(beat, (int, float)) and math.isfinite(float(beat)) and 0.0 < float(beat) < duration
        }
    )
    if len(valid) >= 2:
        period = median([b - a for a, b in pairwise(valid) if b > a])
        tolerance = min(0.12, 0.25 * period)
    else:
        tolerance = 0.08
    if not valid:
        valid = [
            round(index * _FALLBACK_WINDOW_SEC, 6)
            for index in range(1, int(duration / _FALLBACK_WINDOW_SEC) + 1)
            if index * _FALLBACK_WINDOW_SEC < duration
        ]
    boundaries = [0.0, *valid, duration]
    deduped: list[float] = []
    for boundary in sorted(set(boundaries)):
        if not deduped or boundary - deduped[-1] > 1e-6:
            deduped.append(boundary)
    return deduped, tolerance


def detect_chords(
    audio_path: Path,
    *,
    beats: Sequence[float],
    bpm: float | None,
    model_dir: Path | None = None,
    progress: Callable[[str], None] | None = None,
) -> list[ChordEvent]:
    """Detect chords on ``audio_path``; returns an empty list on silence/unreadable audio.

    ``model_dir`` is reserved for a future neural checkpoint. When supplied but missing, the
    function returns no chords and logs a warning instead of raising. The P0 baseline does not
    need a model directory. ``bpm`` is accepted for API compatibility.
    """
    del bpm
    path = Path(audio_path)
    if model_dir is not None:
        model_path = Path(model_dir)
        if not model_path.is_dir():
            logger.warning("Chord model directory not found: %s", model_path)
            return []
        logger.debug("No neural chord loader in this build; using the template baseline")

    if not path.is_file():
        logger.warning("Chord audio not found: %s", path)
        return []

    _notify(progress, "chords: loading audio")
    try:
        import librosa

        y, sr = librosa.load(str(path), sr=22050, mono=True)
    except Exception as exc:
        logger.warning("Chord detection could not read %s: %s", path, exc)
        return []
    if y.size < int(sr * 0.2) or float(np.sqrt(np.mean(y**2))) < 1e-5:
        return []

    duration = float(y.size) / float(sr)
    try:
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=_HOP)
    except Exception as exc:
        logger.warning("Chord chroma failed for %s: %s", path, exc)
        return []
    if chroma.shape[1] < 2:
        return []

    boundaries, tolerance = _boundaries(beats, duration)
    frames = librosa.time_to_frames(np.asarray(boundaries), sr=sr, hop_length=_HOP)
    frames = np.clip(frames, 0, chroma.shape[1] - 1)

    windows: list[tuple[float, float, np.ndarray]] = []
    for index in range(len(boundaries) - 1):
        start_frame = int(frames[index])
        end_frame = int(frames[index + 1])
        if end_frame <= start_frame:
            continue
        vector = chroma[:, start_frame:end_frame].mean(axis=1)
        windows.append((boundaries[index], boundaries[index + 1], vector))
    if not windows:
        return []

    _notify(progress, f"chords: analysing {len(windows)} windows")
    matrix = np.stack([vector for _, _, vector in windows])
    norms = np.linalg.norm(matrix, axis=1)
    silent = norms < 1e-6
    matrix = np.divide(matrix, norms[:, None], out=np.zeros_like(matrix), where=norms[:, None] > 1e-9)
    scores = matrix @ _TEMPLATE_TABLE.T - _EXTENSION_PRIOR
    path_indices = _viterbi(scores)

    events: list[ChordEvent] = []
    for index, state in enumerate(path_indices):
        if silent[index]:
            continue
        start, end, _ = windows[index]
        start = _snap_to_beat(start, boundaries[1:-1], tolerance)
        end = _snap_to_beat(end, boundaries[1:-1], tolerance)
        start = max(0.0, min(duration, start))
        end = max(start, min(duration, end))
        symbol = _normalize_symbol(_TEMPLATE_NAMES[state])
        if symbol is None:
            continue
        events.append(ChordEvent(start=start, end=end, symbol=symbol, confidence=0.0))

    merged = _merge_events(events)
    _notify(progress, f"chords: {len(merged)} segments")
    return merged


__all__ = ["detect_chords"]
