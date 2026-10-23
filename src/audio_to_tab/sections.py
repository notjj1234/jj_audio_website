"""Song-section navigation: beat-synchronous novelty with conservative labels.

Sections are a navigation aid, not semantic truth. The detector covers the whole song, never
emits a gap, enforces a minimum section length, and degrades to one ``Full song`` section on any
failure so a practice job always opens.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Sequence
from itertools import pairwise
from pathlib import Path
from statistics import median

import numpy as np

from audio_to_tab.analysis import Section

logger = logging.getLogger(__name__)

_MIN_SECTION_SEC = 8.0
_MIN_SONG_SEC = 12.0
_FALLBACK_WINDOW_SEC = 0.5
_HOP = 512


def _pick_boundaries(novelty: np.ndarray, *, min_beats: int) -> list[int]:
    """Peak-pick section starts, keep the first/last, enforce a minimum spacing."""
    values = np.asarray(novelty, dtype=np.float64).reshape(-1)
    count = values.size
    if count == 0:
        return [0, 0]
    peak = values.max() if values.size else 0.0
    if peak > 0:
        values = values / peak
    try:
        import librosa

        peaks = librosa.util.peak_pick(
            values,
            pre_max=4,
            post_max=4,
            pre_avg=8,
            post_avg=8,
            delta=0.08,
            wait=max(1, min_beats // 2),
        )
    except Exception:
        peaks = np.zeros(0, dtype=int)

    kept = [0]
    for raw in peaks:
        index = int(raw)
        if 0 < index < count and index - kept[-1] >= min_beats:
            kept.append(index)
    while len(kept) > 1 and count - kept[-1] < min_beats:
        kept.pop()
    kept.append(count)
    return kept


def _normalise_rows(values: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    return np.divide(values, norms, out=np.zeros_like(values), where=norms > 1e-9)


def _cluster_labels(section_chroma: list[np.ndarray], section_rms: list[float]) -> list[str]:
    count = len(section_chroma)
    if count == 0:
        return []
    max_rms = max(section_rms) or 1.0
    features: list[np.ndarray] = []
    for chroma, rms in zip(section_chroma, section_rms, strict=True):
        vector = chroma / (np.linalg.norm(chroma) + 1e-9)
        feature = np.concatenate([vector, [1.5 * rms / max_rms]])
        norm = np.linalg.norm(feature)
        features.append(feature / norm if norm > 1e-9 else feature)

    centroids: list[np.ndarray] = []
    members: list[list[int]] = []
    for index, feature in enumerate(features):
        best_index = -1
        best_similarity = -2.0
        for cluster_index, centroid in enumerate(centroids):
            similarity = float(np.dot(feature, centroid))
            if similarity > best_similarity:
                best_similarity = similarity
                best_index = cluster_index
        if best_index >= 0 and best_similarity >= 0.97:
            members[best_index].append(index)
            centroid = np.mean([features[i] for i in members[best_index]], axis=0)
            norm = np.linalg.norm(centroid)
            centroids[best_index] = centroid / norm if norm > 1e-9 else centroid
        else:
            centroids.append(feature)
            members.append([index])

    cluster_rms = {
        cluster_index: float(np.mean([section_rms[i] for i in indexes]))
        for cluster_index, indexes in enumerate(members)
    }
    repeated = [cluster_index for cluster_index, indexes in enumerate(members) if len(indexes) >= 2]
    labels = ["Section"] * count
    if repeated:
        ranked = sorted(repeated, key=lambda cluster_index: cluster_rms[cluster_index], reverse=True)
        if len(ranked) == 1:
            label = "Chorus" if cluster_rms[ranked[0]] >= median(section_rms) else "Verse"
            for index in members[ranked[0]]:
                labels[index] = label
        else:
            for index in members[ranked[0]]:
                labels[index] = "Chorus"
            for cluster_index in ranked[1:]:
                for index in members[cluster_index]:
                    labels[index] = "Verse"
    labels[0] = "Intro"
    labels[-1] = "Outro"
    if count == 1:
        labels[0] = "Full song"
    return labels


def _sections_from_features(
    chroma: np.ndarray,
    rms: np.ndarray,
    times: Sequence[float],
    duration_sec: float,
) -> list[Section]:
    """Build sections from beat-synchronous chroma (12 x n) and RMS (n)."""
    matrix = np.asarray(chroma, dtype=np.float64)
    levels = np.asarray(rms, dtype=np.float64).reshape(-1)
    count = matrix.shape[1]
    duration = max(0.0, float(duration_sec))
    if count < 8 or levels.size != count or duration <= 0:
        return [Section(0.0, duration, "Full song", 0.0)]

    unit = _normalise_rows(matrix.T)
    similarity = unit @ unit.T
    window = min(6, max(2, count // 8))
    novelty = np.zeros(count)
    for index in range(window, count - window):
        before = similarity[index - window : index, index - window : index]
        after = similarity[index : index + window, index : index + window]
        cross = similarity[index - window : index, index : index + window]
        novelty[index] = max(0.0, float(before.mean() + after.mean() - 2.0 * cross.mean()))
    if novelty.max() > 0:
        novelty = novelty / novelty.max()

    period = median([b - a for a, b in pairwise(times) if b > a]) if len(times) > 1 else 1.0
    min_beats = max(2, round(_MIN_SECTION_SEC / max(period, 0.1)))
    if count < 2 * min_beats:
        return [Section(0.0, duration, "Full song", 0.0)]

    boundaries = _pick_boundaries(novelty, min_beats=min_beats)
    if len(boundaries) <= 2:
        return [Section(0.0, duration, "Full song", 0.0)]

    starts = [0.0 if index == 0 else float(times[index]) for index in boundaries[:-1]]
    ends = [duration if index == count else float(times[index]) for index in boundaries[1:]]
    section_chroma: list[np.ndarray] = []
    section_rms: list[float] = []
    for start_index, end_index in pairwise(boundaries):
        section_chroma.append(matrix[:, start_index:end_index].mean(axis=1))
        section_rms.append(float(levels[start_index:end_index].mean()))
    labels = _cluster_labels(section_chroma, section_rms)

    sections: list[Section] = []
    for index, (start, end) in enumerate(zip(starts, ends, strict=True)):
        start = max(0.0, min(duration, start))
        end = max(start, min(duration, end))
        if end <= start:
            continue
        strength = float(novelty[boundaries[index]]) if boundaries[index] < count else 0.0
        confidence = 0.5 if index in (0, len(starts) - 1) else min(0.9, 0.35 + 0.55 * strength)
        sections.append(Section(start=start, end=end, label=labels[index], confidence=round(confidence, 3)))
    return sections or [Section(0.0, duration, "Full song", 0.0)]


def detect_sections(
    audio_path: Path,
    *,
    beats: Sequence[float],
    duration_sec: float,
) -> list[Section]:
    """Detect navigation sections; always returns a gap-free list."""
    duration = float(duration_sec) if isinstance(duration_sec, (int, float)) else 0.0
    if not math.isfinite(duration) or duration < _MIN_SONG_SEC:
        safe = max(0.0, duration) if math.isfinite(duration) else 0.0
        return [Section(0.0, safe, "Full song", 0.0)]

    path = Path(audio_path)
    if not path.is_file():
        logger.warning("Section audio not found: %s", path)
        return [Section(0.0, duration, "Full song", 0.0)]

    try:
        import librosa

        y, sr = librosa.load(str(path), sr=22050, mono=True)
        if y.size < int(sr * _MIN_SONG_SEC) or float(np.sqrt(np.mean(y**2))) < 1e-5:
            return [Section(0.0, duration, "Full song", 0.0)]
        audio_duration = float(y.size) / float(sr)
        duration = min(duration, audio_duration)
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=_HOP)
        rms = librosa.feature.rms(y=y, hop_length=_HOP)[0]
    except Exception as exc:
        logger.warning("Section detection failed for %s: %s", path, exc)
        return [Section(0.0, duration, "Full song", 0.0)]

    valid = sorted(
        {
            float(beat)
            for beat in beats
            if isinstance(beat, (int, float)) and math.isfinite(float(beat)) and 0.0 < float(beat) < duration
        }
    )
    if not valid:
        valid = [
            round(index * _FALLBACK_WINDOW_SEC, 6)
            for index in range(1, int(duration / _FALLBACK_WINDOW_SEC) + 1)
            if index * _FALLBACK_WINDOW_SEC < duration
        ]
    boundaries = [0.0, *valid, duration]
    frames = librosa.time_to_frames(np.asarray(boundaries), sr=sr, hop_length=_HOP)
    frames = np.clip(frames, 0, chroma.shape[1] - 1)

    beat_chroma: list[np.ndarray] = []
    beat_rms: list[float] = []
    times: list[float] = []
    for index in range(len(boundaries) - 1):
        start_frame = int(frames[index])
        end_frame = int(frames[index + 1])
        if end_frame <= start_frame:
            continue
        beat_chroma.append(chroma[:, start_frame:end_frame].mean(axis=1))
        beat_rms.append(float(rms[start_frame:end_frame].mean()))
        times.append(boundaries[index])
    if len(beat_chroma) < 8:
        return [Section(0.0, duration, "Full song", 0.0)]

    return _sections_from_features(
        np.stack(beat_chroma, axis=1),
        np.asarray(beat_rms),
        times,
        duration,
    )


__all__ = ["detect_sections"]
