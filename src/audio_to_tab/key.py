"""Key estimation: chord-histogram first, chroma profiles as the fallback.

The chord path is preferred because a song's tonic is usually stated by its harmony, while raw
chroma on guitar/pop mixes is biased by open strings, bass, and drums. The chroma path exists for
the no-chord case (silence is rejected, never guessed).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from audio_to_tab.analysis import ChordEvent

logger = logging.getLogger(__name__)

PITCHES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
_FLAT_TO_SHARP = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#"}

MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

_MAJOR_DEGREES = {0: "maj", 2: "min", 4: "min", 5: "maj", 7: "maj", 9: "min", 11: "dim"}
_MINOR_DEGREES = {0: "min", 2: "dim", 3: "maj", 5: "min", 7: "min", 8: "maj", 10: "maj"}
_ROOT_RE = re.compile(r"^([A-Ga-g])([#b]?)(.*)$")


@dataclass(frozen=True)
class _ParsedChord:
    root: int
    quality: str  # "maj" | "min" | "dim" | "sus"


def _parse_chord(symbol: str) -> _ParsedChord | None:
    if not isinstance(symbol, str):
        return None
    head = symbol.split("/", 1)[0].strip()
    match = _ROOT_RE.match(head)
    if not match:
        return None
    letter, accidental, rest = match.groups()
    root_name = (letter.upper() + accidental) if accidental else letter.upper()
    root_name = _FLAT_TO_SHARP.get(root_name, root_name)
    if root_name not in PITCHES:
        return None
    lowered = rest.lower()
    if lowered.startswith(("dim", "°", "o")):
        quality = "dim"
    elif lowered.startswith(("aug", "+")):
        quality = "maj"
    elif lowered.startswith("sus"):
        quality = "sus"
    elif lowered.startswith("m") and not lowered.startswith("maj"):
        quality = "min"
    else:
        quality = "maj"
    return _ParsedChord(root=PITCHES.index(root_name), quality=quality)


def _key_from_chords(chords: Sequence[ChordEvent]) -> tuple[str | None, str]:
    parsed: list[tuple[float, _ParsedChord]] = []
    for chord in chords:
        duration = float(chord.end) - float(chord.start)
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


def estimate_key(
    audio_path: Path,
    *,
    bpm: float | None = None,
    beats: Sequence[float] = (),
    chords: Sequence[ChordEvent] = (),
) -> tuple[str | None, str]:
    """Return ``(key, confidence)``; ``(None, "low")`` when the audio is silent/unreadable.

    ``chords`` is optional. When present and parseable it wins; otherwise the chroma path runs.
    ``bpm`` is accepted for API symmetry with the analysis orchestrator and does not change the
    result.
    """
    del bpm
    if chords:
        key, confidence = _key_from_chords(chords)
        if key is not None:
            return key, confidence
    return _chroma_key(Path(audio_path), beats)


__all__ = ["PITCHES", "estimate_key"]
