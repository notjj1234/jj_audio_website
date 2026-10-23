"""Chord-recognition baseline spike on the generated fixture.

Ground truth (from eval/generate_fixtures.py): chords.wav = G (0.0-1.5s),
C (2.0-3.5s), G (4.0-5.5s) at 120 BPM. Simple sine/soundfont triads, no drums.

Measures: segment accuracy (mean-chroma template match and per-frame majority
vote) plus CPU seconds per audio minute. Throwaway measurement code, not product.

Run:
    .venv311/bin/python docs/plans/moises-parity/_work/spikes/chord_baseline.py
"""

from __future__ import annotations

import time
from pathlib import Path

import librosa
import numpy as np

ROOT = Path(__file__).resolve().parents[5]
AUDIO = ROOT / "eval" / "fixtures" / "chords.wav"
SEGMENTS = [(0.0, 1.5, "G"), (2.0, 3.5, "C"), (4.0, 5.5, "G")]

PITCHES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
TRIADS = {
    "maj": [0, 4, 7],
    "min": [0, 3, 7],
    "7": [0, 4, 7, 10],
    "maj7": [0, 4, 7, 11],
    "min7": [0, 3, 7, 10],
    "sus4": [0, 5, 7],
    "dim": [0, 3, 6],
    "aug": [0, 4, 8],
}


def build_templates() -> dict[str, np.ndarray]:
    out: dict[str, np.ndarray] = {}
    for quality, intervals in TRIADS.items():
        for i, pitch in enumerate(PITCHES):
            vec = np.zeros(12, dtype=np.float64)
            for interval in intervals:
                vec[(i + interval) % 12] = 1.0
            name = pitch if quality == "maj" else f"{pitch}{quality}"
            out[name] = vec / np.linalg.norm(vec)
    return out


def match(chroma_vec: np.ndarray, templates: dict[str, np.ndarray]) -> str:
    norm = float(np.linalg.norm(chroma_vec))
    if norm < 1e-9:
        return "N"
    unit = chroma_vec / norm
    return max(templates, key=lambda name: float(np.dot(unit, templates[name])))


def main() -> int:
    assert AUDIO.is_file(), f"missing fixture: {AUDIO}"
    templates = build_templates()

    t0 = time.perf_counter()
    y, sr = librosa.load(str(AUDIO), sr=22050, mono=True)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=512)
    times = librosa.frames_to_time(np.arange(chroma.shape[1]), sr=sr, hop_length=512)
    elapsed = time.perf_counter() - t0
    audio_minutes = len(y) / sr / 60.0

    print(f"audio: {len(y) / sr:.2f}s @ {sr} Hz | chroma {chroma.shape} | {elapsed:.2f}s CPU")
    print(f"CPU per audio minute: {elapsed / max(audio_minutes, 1e-9):.1f}s")

    frame_pred = [match(chroma[:, i], templates) for i in range(chroma.shape[1])]
    correct_secs = 0.0
    total_secs = 0.0
    for start, end, truth in SEGMENTS:
        sel = (times >= start) & (times < end)
        if not sel.any():
            continue
        mean_vec = chroma[:, sel].mean(axis=1)
        mean_pred = match(mean_vec, templates)
        votes = {}
        for i in np.where(sel)[0]:
            votes[frame_pred[i]] = votes.get(frame_pred[i], 0) + 1
        frame_winner = max(votes, key=votes.get)
        seg_secs = float(end - start)
        correct_secs += seg_secs if mean_pred == truth else 0.0
        correct_secs += seg_secs if frame_winner == truth else 0.0
        total_secs += 2 * seg_secs
        print(
            f"  {start:.1f}-{end:.1f}s truth={truth:3s} "
            f"mean-chroma={mean_pred:4s} majority={frame_winner:4s}"
        )

    print(f"segment accuracy (both methods pooled): {correct_secs / total_secs:.1%}")
    print("frames:", " ".join(frame_pred))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
