"""Stage A profile: tempo, key, beat-synchronous chords, sections, intro energy.

Throwaway measurement code for the two user-supplied reference songs. No product
imports. Run:

    .venv311/bin/python docs/plans/moises-parity/_work/spikes/song_profile.py \
        "/path/a.mp3" "/path/b.mp3"
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import librosa
import numpy as np

PITCHES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
TRIADS = {
    "maj": [0, 4, 7],
    "min": [0, 3, 7],
    "7": [0, 4, 7, 10],
    "maj7": [0, 4, 7, 11],
    "min7": [0, 3, 7, 10],
    "sus4": [0, 5, 7],
    "dim": [0, 3, 6],
}
MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def load_audio(path: Path, sr: int = 22050) -> tuple[np.ndarray, int]:
    try:
        y, _ = librosa.load(str(path), sr=sr, mono=True)
        return y, sr
    except Exception:
        tmp = Path(tempfile.gettempdir()) / f"att-spike-{path.stem[:20]}.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(sr), str(tmp)],
            check=True,
        )
        y, _ = librosa.load(str(tmp), sr=sr, mono=True)
        return y, sr


def templates() -> dict[str, np.ndarray]:
    out: dict[str, np.ndarray] = {}
    for quality, intervals in TRIADS.items():
        for i, pitch in enumerate(PITCHES):
            vec = np.zeros(12)
            for interval in intervals:
                vec[(i + interval) % 12] = 1.0
            name = pitch if quality == "maj" else f"{pitch}{quality}"
            out[name] = vec / np.linalg.norm(vec)
    return out


def match(vec: np.ndarray, tmpl: dict[str, np.ndarray]) -> tuple[str, float]:
    norm = float(np.linalg.norm(vec))
    if norm < 1e-9:
        return "N", 0.0
    unit = vec / norm
    scores = {name: float(np.dot(unit, t)) for name, t in tmpl.items()}
    best = max(scores, key=scores.get)
    return best, scores[best]


def estimate_key(chroma: np.ndarray, beat_frames: np.ndarray | None = None) -> tuple[str, float]:
    if beat_frames is not None and len(beat_frames) > 2:
        cols = [chroma[:, a:b].mean(axis=1) for a, b in zip(beat_frames[:-1], beat_frames[1:]) if b > a]
        mean = np.mean(cols, axis=0) if cols else chroma.mean(axis=1)
    else:
        mean = chroma.mean(axis=1)
    mean = mean / (np.linalg.norm(mean) + 1e-9)
    scored = []
    for i, pitch in enumerate(PITCHES):
        for quality, profile in (("maj", MAJOR), ("min", MINOR)):
            rotated = np.roll(profile, i)
            rotated = rotated / np.linalg.norm(rotated)
            scored.append((float(np.dot(mean, rotated)), pitch if quality == "maj" else f"{pitch}m"))
    scored.sort(reverse=True)
    return scored[0][1], scored[0][0], scored[:3]


def viterbi_chords(
    chroma: np.ndarray,
    beat_frames: np.ndarray,
    tmpl: dict[str, np.ndarray],
    penalty: float = 0.06,
):
    names = list(tmpl)
    cols = []
    for start, end in zip(beat_frames[:-1], beat_frames[1:]):
        vec = chroma[:, start:end].mean(axis=1) if end > start else np.zeros(12)
        norm = float(np.linalg.norm(vec))
        cols.append(vec / norm if norm > 1e-9 else vec)
    mat = np.stack(cols) if cols else np.zeros((0, 12))
    table = np.stack([tmpl[name] for name in names])
    scores = mat @ table.T
    # Prefer triads: a 7th chord must beat the best triad by a margin.
    scores[:, [i for i, n in enumerate(names) if n.endswith("7")]] -= 0.03

    n, states = scores.shape
    if n == 0:
        return []
    dp = scores[0].copy()
    back = np.zeros((n, states), dtype=np.int16)
    for t in range(1, n):
        order = np.argsort(dp)[::-1]
        best, second = int(order[0]), int(order[1])
        best_val, second_val = float(dp[best]), float(dp[second]) - penalty
        for j in range(states):
            stay = float(dp[j])
            other = second_val if j == best else best_val - penalty
            if stay >= other:
                back[t, j] = j
                dp[j] = scores[t, j] + stay
            else:
                back[t, j] = best if j != best else second
                dp[j] = scores[t, j] + other
    path = np.zeros(n, dtype=np.int16)
    path[-1] = int(np.argmax(dp))
    for t in range(n - 1, 0, -1):
        path[t - 1] = back[t, path[t]]
    return [(names[int(path[i])], float(scores[i, int(path[i])])) for i in range(n)]


def beat_chords(chroma: np.ndarray, beat_frames: np.ndarray, tmpl: dict[str, np.ndarray]):
    chords = []
    for start, end in zip(beat_frames[:-1], beat_frames[1:]):
        if end <= start:
            chords.append(("N", 0.0))
            continue
        chords.append(match(chroma[:, start:end].mean(axis=1), tmpl))
    # 5-beat majority filter, center beat weighted 3x: chord changes are usually
    # per bar/half-bar, not per beat.
    smoothed = list(chords)
    for i in range(2, len(chords) - 2):
        votes = [
            chords[i - 2][0],
            chords[i - 1][0],
            chords[i][0],
            chords[i][0],
            chords[i][0],
            chords[i + 1][0],
            chords[i + 2][0],
        ]
        smoothed[i] = (max(set(votes), key=votes.count), chords[i][1])
    return smoothed


def parse_chord(symbol: str) -> tuple[int, str] | None:
    if not symbol or symbol == "N":
        return None
    root = symbol[0]
    rest = symbol[1:]
    if rest.startswith("#"):
        root += "#"
        rest = rest[1:]
    if root not in PITCHES:
        return None
    quality = "min" if rest.startswith("m") and not rest.startswith("maj") else "maj"
    if rest.startswith("dim"):
        quality = "dim"
    return PITCHES.index(root), quality


MAJOR_TRIADS = {0: "maj", 2: "min", 4: "min", 5: "maj", 7: "maj", 9: "min", 11: "dim"}
MINOR_TRIADS = {0: "min", 2: "dim", 3: "maj", 5: "min", 7: "min", 8: "maj", 10: "maj"}


def key_from_chords(runs: list[tuple[float, float, str, float]]) -> tuple[str, float, list[tuple[float, str]]]:
    parsed = [(max(0.0, b - a), parse_chord(s)) for a, b, s, _ in runs]
    total = sum(d for d, p in parsed if p) or 1.0
    scored: list[tuple[float, str]] = []
    for tonic_i, tonic in enumerate(PITCHES):
        for mode, table in (("maj", MAJOR_TRIADS), ("min", MINOR_TRIADS)):
            score = 0.0
            for dur, p in parsed:
                if not p:
                    continue
                root, quality = p
                degree = (root - tonic_i) % 12
                expected = table.get(degree)
                if expected is None:
                    continue
                if expected == quality or (expected == "maj" and quality == "dim"):
                    score += dur
                elif expected == "min" and quality == "min":
                    score += dur
                elif degree == 7 and quality in ("maj", "min"):
                    score += dur * 0.6  # dominant 7th
            name = tonic if mode == "maj" else f"{tonic}m"
            scored.append((score / total, name))
    scored.sort(reverse=True)
    return scored[0][1], scored[0][0], scored[:3]


def chord_histogram(runs: list[tuple[float, float, str, float]], limit: int = 12):
    totals: dict[str, float] = {}
    for a, b, symbol, _ in runs:
        totals[symbol] = totals.get(symbol, 0.0) + max(0.0, b - a)
    return sorted(((round(v, 1), k) for k, v in totals.items()), reverse=True)[:limit]


def run_lengths(times: list[float], chords: list[tuple[str, float]]) -> list[tuple[float, float, str, float]]:
    out: list[tuple[float, float, str, float]] = []
    for i, (symbol, conf) in enumerate(chords):
        start = times[i]
        end = times[i + 1] if i + 1 < len(times) else start
        if out and out[-1][2] == symbol:
            out[-1] = (out[-1][0], end, symbol, max(out[-1][3], conf))
        else:
            out.append((start, end, symbol, conf))
    return out


def sections(chroma: np.ndarray, beat_frames: np.ndarray, beat_times: np.ndarray, duration: float):
    if len(beat_frames) < 10:
        return [(0.0, duration, "Full song")]
    cols = [
        chroma[:, a:b].mean(axis=1)
        for a, b in zip(beat_frames[:-1], beat_frames[1:])
        if b > a
    ]
    if len(cols) < 8:
        return [(0.0, duration, "Full song")]
    x = np.stack(cols).astype(np.float64)
    x = x / (np.linalg.norm(x, axis=1, keepdims=True) + 1e-9)
    sim = x @ x.T
    n = len(x)
    k = min(6, max(2, n // 8))
    novelty = np.zeros(n)
    for i in range(k, n - k):
        before = sim[i - k : i, i - k : i]
        after = sim[i : i + k, i : i + k]
        cross = sim[i - k : i, i : i + k]
        novelty[i] = before.mean() + after.mean() - 2.0 * cross.mean()
    novelty = np.maximum(novelty, 0)
    if novelty.max() > 0:
        novelty = novelty / novelty.max()
    peaks = librosa.util.peak_pick(
        novelty, pre_max=4, post_max=4, pre_avg=8, post_avg=8, delta=0.08, wait=4
    )
    beat_sec = float(np.median(np.diff(beat_times))) if len(beat_times) > 1 else 0.5
    min_beats = max(4, int(round(8.0 / max(beat_sec, 0.1))))
    kept = [0]
    for b in [int(p) for p in peaks if p > 0]:
        if b - kept[-1] >= min_beats:
            kept.append(b)
    if n - kept[-1] < min_beats // 2 and len(kept) > 1:
        kept.pop()
    kept.append(n)
    out = []
    for a, b in zip(kept[:-1], kept[1:]):
        start = float(beat_times[a]) if a < len(beat_times) else duration
        end = float(beat_times[b]) if b < len(beat_times) else duration
        out.append((start, end, float(novelty[min(a, n - 1)])))
    return out


def profile(path: Path) -> dict:
    assert path.is_file(), f"missing {path}"
    t0 = time.perf_counter()
    y, sr = load_audio(path)
    duration = len(y) / sr
    hop = 512
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=hop)
    rms = librosa.feature.rms(y=y, hop_length=hop)[0]
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr, hop_length=hop, units="frames")
    beat_frames = np.asarray(beat_frames)
    beat_times = librosa.frames_to_time(beat_frames, sr=sr, hop_length=hop)
    key, key_score, key_top = estimate_key(chroma, beat_frames)
    tmpl = templates()
    chords = viterbi_chords(chroma, beat_frames, tmpl)
    runs = run_lengths(list(beat_times), chords)
    key_chords, key_chords_score, key_chords_top = key_from_chords(runs)
    hist = chord_histogram(runs)
    secs = sections(chroma, beat_frames, beat_times, duration)
    intro_rms = float(np.sqrt(np.mean(y[: min(len(y), 10 * sr)] ** 2)))
    body_rms = float(np.sqrt(np.mean(y**2)))
    elapsed = time.perf_counter() - t0
    return {
        "path": str(path),
        "duration_sec": round(duration, 1),
        "sr": sr,
        "tempo_bpm": round(float(np.atleast_1d(tempo)[0]), 1),
        "key": key,
        "key_score": round(key_score, 3),
        "key_top": [(round(s, 3), k) for s, k in key_top],
        "key_from_chords": key_chords,
        "key_from_chords_score": round(key_chords_score, 3),
        "key_from_chords_top": [(round(s, 3), k) for s, k in key_chords_top],
        "chord_histogram": [(v, k) for v, k in hist],
        "intro_rms": intro_rms,
        "body_rms": body_rms,
        "elapsed_sec": round(elapsed, 1),
        "beat_count": int(len(beat_times)),
        "chord_runs": [(round(a, 1), round(b, 1), s, round(c, 2)) for a, b, s, c in runs],
        "sections": [(round(a, 1), round(b, 1), round(c, 2)) for a, b, c in secs],
    }


def main(argv: list[str]) -> int:
    paths = [Path(p) for p in argv[1:]]
    if not paths:
        print("usage: song_profile.py <audio> [audio...]")
        return 2
    results = [profile(p) for p in paths]
    print(json.dumps(results, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
