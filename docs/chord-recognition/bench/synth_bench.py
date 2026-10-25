"""Reproducible baseline bench for the chord stage.

Renders synthetic 8-bar progressions with a known chord-per-bar ground truth,
runs the *current* detector (`audio_to_tab.chords.detect_chords`) and a few
diagnostic variants, and scores them with mir_eval.

Run with the project venv:

    .venv311/bin/python docs/chord-recognition/bench/synth_bench.py

Nothing here is imported by the product. It exists so the numbers quoted in
docs/chord-recognition/01-current-system-audit.md can be reproduced.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))

import librosa  # noqa: E402
import mir_eval  # noqa: E402

from audio_to_tab.chords import detect_chords  # noqa: E402

SR = 44100
BPM = 100.0
BEATS_PER_BAR = 4
BARS = 8
BEAT_SEC = 60.0 / BPM
BAR_SEC = BEAT_SEC * BEATS_PER_BAR

PITCH_CLASS = {
    "C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5,
    "F#": 6, "Gb": 6, "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11,
}
QUALITY = {
    "": (0, 4, 7),
    "m": (0, 3, 7),
    "7": (0, 4, 7, 10),
    "maj7": (0, 4, 7, 11),
    "m7": (0, 3, 7, 10),
    "sus4": (0, 5, 7),
    "dim": (0, 3, 6),
    "aug": (0, 4, 8),
}


def parse(symbol: str):
    """'C#m7' -> (root_pc, quality, bass_pc)."""
    if "/" in symbol:
        head, bass = symbol.split("/", 1)
    else:
        head, bass = symbol, None
    for name in sorted(QUALITY, key=len, reverse=True):
        if name and head.endswith(name):
            root, quality = head[: -len(name)], name
            break
        if not name:
            root, quality = head, ""
    return PITCH_CLASS[root], QUALITY[quality], (PITCH_CLASS[bass] if bass else None)


def midi_hz(midi: float) -> float:
    return 440.0 * 2.0 ** ((midi - 69.0) / 12.0)


def render_track(progression: list[str], *, hard: bool = False) -> np.ndarray:
    """Pad + bass + melody + drums, one chord per bar.

    ``hard=True`` approximates a real streamed mix: instruments 30 cents sharp,
    a louder backbeat, a vibrato vocal-like lead, saturation and a short reverb.
    """
    n = int(SR * BAR_SEC * len(progression))
    y = np.zeros(n, dtype=np.float64)
    rng = np.random.default_rng(7)
    detune = 0.30 if hard else 0.0

    for bar, symbol in enumerate(progression):
        root, intervals, bass = parse(symbol)
        start = int(bar * BAR_SEC * SR)
        end = int((bar + 1) * BAR_SEC * SR)
        t = np.arange(end - start) / SR

        # Pad: 4 slightly detuned partials per chord tone, slow attack.
        env = np.minimum(1.0, t / 0.08) * np.exp(-t / (BAR_SEC * 1.4))
        for interval in intervals:
            base = 48 + root + interval  # C3..B3 register
            for det in (-0.06, 0.06):
                f = midi_hz(base + det + detune)
                y[start:end] += 0.055 * env * np.sin(2 * np.pi * f * t)
                y[start:end] += 0.018 * env * np.sin(2 * np.pi * 2 * f * t)

        # Bass: root, octave down, with a pluck envelope on each beat.
        bass_pc = bass if bass is not None else root
        for beat in range(BEATS_PER_BAR):
            bs = int(beat * BEAT_SEC * SR)
            be = min(len(t), int((beat + 1) * BEAT_SEC * SR))
            bt = t[bs:be] - t[bs]
            f = midi_hz(36 + bass_pc + detune)
            benv = np.exp(-bt / 0.35)
            y[start + bs : start + be] += 0.22 * benv * np.sin(2 * np.pi * f * bt)
            y[start + bs : start + be] += 0.05 * benv * np.sin(2 * np.pi * 2 * f * bt)

        # Melody: chord tones an octave up, eighth-note-ish.
        for step in range(8):
            ms = int(step * BEAT_SEC / 2 * SR)
            me = min(len(t), int((step + 1) * BEAT_SEC / 2 * SR))
            if me <= ms:
                continue
            mt = t[ms:me] - t[ms]
            note = 72 + root + int(intervals[rng.integers(0, len(intervals))])
            menv = np.exp(-mt / 0.12) if not hard else np.minimum(1.0, mt / 0.03) * np.exp(-mt / 0.5)
            vibrato = 1.0 + (0.006 * np.sin(2 * np.pi * 5.5 * mt) if hard else 0.0)
            lead = 0.05 if not hard else 0.13
            y[start + ms : start + me] += lead * menv * np.sin(
                2 * np.pi * midi_hz(note + detune) * mt * vibrato
            )
            if hard:
                y[start + ms : start + me] += 0.06 * menv * np.sin(
                    2 * np.pi * 2 * midi_hz(note + detune) * mt * vibrato
                )

        # Drums: kick 1&3, snare 2&4, hats on eighths (broadband noise).
        for beat in range(BEATS_PER_BAR):
            bs = int(beat * BEAT_SEC * SR)
            seg = min(int(0.12 * SR), len(t) - bs)
            if seg <= 0:
                continue
            dt = np.arange(seg) / SR
            if beat % 2 == 0:
                f = 55.0 * np.exp(-dt / 0.05) + 45.0
                y[start + bs : start + bs + seg] += 0.35 * np.exp(-dt / 0.09) * np.sin(
                    2 * np.pi * np.cumsum(f) / SR
                )
            else:
                noise = rng.normal(0, 1, seg)
                mult = 0.10 if not hard else 0.20
                y[start + bs : start + bs + seg] += mult * np.exp(-dt / 0.07) * noise
        for eighth in range(BEATS_PER_BAR * 2):
            hs = int(eighth * BEAT_SEC / 2 * SR)
            seg = min(int(0.04 * SR), len(t) - hs)
            if seg <= 0:
                continue
            dt = np.arange(seg) / SR
            hat = 0.03 if not hard else 0.06
            y[start + hs : start + hs + seg] += hat * np.exp(-dt / 0.02) * rng.normal(0, 1, seg)

    if hard:
        # Saturation + short reverb: the two things that smear chroma most.
        from scipy.signal import fftconvolve

        y = np.tanh(2.2 * y)
        ir = rng.normal(0, 1, int(0.35 * SR)) * np.exp(-np.arange(int(0.35 * SR)) / (0.12 * SR))
        wet = fftconvolve(y, ir / np.max(np.abs(ir)), mode="full")[:n]
        y = 0.82 * y + 0.18 * wet

    y /= max(1e-9, np.max(np.abs(y)))
    return (y * 0.9).astype(np.float32)


QUALITY_TO_MIREVAL = {
    "": "maj", "m": "min", "7": "7", "maj7": "maj7", "m7": "min7",
    "sus4": "sus4", "dim": "dim", "aug": "aug",
}


def to_mireval(symbol: str) -> str:
    """'Am7' -> 'A:min7'. mir_eval 0.8.2 rejects slash chords, so the bass is
    dropped for scoring; inversion support is reported separately.

    Labels outside this bench's triad/seventh vocabulary (power chords, N)
    become ``N`` so a wider detector vocabulary can be scored instead of
    raising. ``N`` does not match a pitched reference.
    """
    if not isinstance(symbol, str) or not symbol.strip() or symbol.strip().upper() == "N":
        return "N"
    head = symbol.split("/", 1)[0]
    root, quality = head, ""
    for name in sorted(QUALITY, key=len, reverse=True):
        if name and head.endswith(name):
            root, quality = head[: -len(name)], name
            break
        if not name:
            root, quality = head, ""
    if root not in PITCH_CLASS or quality not in QUALITY_TO_MIREVAL:
        return "N"
    return f"{root}:{QUALITY_TO_MIREVAL[quality]}"


def ground_truth(progression: list[str]):
    intervals, labels = [], []
    for bar, symbol in enumerate(progression):
        intervals.append((bar * BAR_SEC, (bar + 1) * BAR_SEC))
        labels.append(to_mireval(symbol))
    return np.asarray(intervals), labels


def est_from_events(events):
    intervals = np.asarray([[e.start, e.end] for e in events], dtype=float)
    labels = [to_mireval(e.symbol) for e in events]
    return intervals, labels


def score(ref_iv, ref_lab, est_iv, est_lab) -> dict:
    out = {}
    if len(est_iv) == 0:
        return {"root": 0.0, "majmin": 0.0, "sevenths": 0.0, "mirex": 0.0, "segments": 0}
    scores = mir_eval.chord.evaluate(ref_iv, ref_lab, est_iv, est_lab)
    out.update({k: round(float(v), 3) for k, v in scores.items()})
    out["segments"] = len(est_iv)
    return out


# ---------------------------------------------------------------- variants


def chroma_for(path: Path, *, mode: str) -> np.ndarray:
    y, sr = librosa.load(str(path), sr=22050, mono=True)
    if mode in {"hpss", "full"}:
        y = librosa.effects.harmonic(y, margin=3.0)
    if mode == "cens":
        return librosa.feature.chroma_cens(y=y, sr=sr, hop_length=512)
    tuning = librosa.estimate_tuning(y=y, sr=sr)
    return librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=512, tuning=tuning)


def _templates(vocab):
    table, names = [], []
    for quality, intervals in vocab.items():
        for pc in range(12):
            v = np.zeros(12)
            v[(pc + np.asarray(intervals)) % 12] = 1.0
            table.append(v / np.linalg.norm(v))
            names.append(pc)
    return np.stack(table), names


VOCAB_SMALL = {"": (0, 4, 7), "m": (0, 3, 7)}
VOCAB_FULL = {
    "": (0, 4, 7), "m": (0, 3, 7), "7": (0, 4, 7, 10), "maj7": (0, 4, 7, 11),
    "m7": (0, 3, 7, 10), "sus4": (0, 5, 7), "dim": (0, 3, 6), "aug": (0, 4, 8),
}
KEY_SCALE = {
    "maj": {0: "", 2: "m", 4: "m", 5: "", 7: "", 9: "m", 11: "dim"},
    "min": {0: "m", 2: "dim", 3: "", 5: "m", 7: "m", 8: "", 10: ""},
}


def improved_events(path: Path, beats: np.ndarray, *, mode: str, vocab, key: str | None,
                    change_penalty: float, use_key_prior: bool):
    chroma = chroma_for(path, mode=mode)
    frames = librosa.time_to_frames(beats, sr=22050, hop_length=512)
    frames = np.clip(frames, 0, chroma.shape[1] - 1)
    vectors, spans = [], []
    for i in range(len(frames) - 1):
        a, b = int(frames[i]), int(frames[i + 1])
        if b <= a:
            continue
        vectors.append(chroma[:, a:b].mean(axis=1))
        spans.append((beats[i], beats[i + 1]))
    if not vectors:
        return []
    m = np.stack(vectors)
    m = m / np.maximum(1e-9, np.linalg.norm(m, axis=1, keepdims=True))

    table, roots = _templates(vocab)
    quality = []
    for q, _iv in vocab.items():
        quality.extend([q] * 12)
    scores = m @ table.T

    if use_key_prior and key:
        mode = "min" if key.endswith("m") else "maj"
        tonic = PITCH_CLASS[key[:-1] if mode == "min" else key]
        allowed = {(tonic + d) % 12: q for d, q in KEY_SCALE[mode].items()}
        for j, (root, q) in enumerate(zip(roots, quality)):
            if allowed.get(root) == q:
                scores[:, j] += 0.12

    # Viterbi with a stay bonus proportional to how much evidence it takes to switch.
    n, s = scores.shape
    dp = scores[0].copy()
    back = np.zeros((n, s), dtype=np.int32)
    for i in range(1, n):
        new = np.empty(s)
        for st in range(s):
            stay = dp[st]
            jumps = dp - change_penalty
            jumps[st] = -np.inf
            prev = int(np.argmax(jumps)) if s > 1 else st
            if stay >= jumps[prev]:
                back[i, st] = st
                new[st] = scores[i, st] + stay
            else:
                back[i, st] = prev
                new[st] = scores[i, st] + jumps[prev]
        dp = new
    path = [int(np.argmax(dp))]
    for i in range(n - 1, 0, -1):
        path.append(int(back[i, path[-1]]))
    path.reverse()

    from audio_to_tab.analysis import ChordEvent

    events = []
    for (start, end), st in zip(spans, path):
        root, q = roots[st], quality[st]
        symbol = f"{'C C# D D# E F F# G G# A A# B'.split()[root]}{q}"
        events.append(ChordEvent(start=float(start), end=float(end), symbol=symbol, confidence=0.0))
    merged = []
    for e in events:
        if merged and merged[-1].symbol == e.symbol and abs(merged[-1].end - e.start) < 1e-9:
            merged[-1] = merged[-1].__class__(merged[-1].start, e.end, e.symbol, 0.0)
        else:
            merged.append(e)
    return merged


PROGRESSIONS = {
    "C_major_pop": ["C", "G", "Am", "F"] * 2,
    "G_major_pop": ["G", "D", "Em", "C"] * 2,
    "A_minor": ["Am", "F", "C", "G"] * 2,
    "jazz_ii_V_I": ["Dm7", "G7", "Cmaj7", "Cmaj7"] * 2,
    "slash_chords": ["C/E", "G/B", "Am/C", "F/A"] * 2,
    "quality_zoom": ["C", "Cm", "C7", "Cmaj7", "Csus4", "Cdim", "C", "Cmaj7"],
}
KEY_OF = {
    "C_major_pop": "C", "G_major_pop": "G", "A_minor": "Am",
    "jazz_ii_V_I": "C", "slash_chords": "C", "quality_zoom": "C",
}


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="chordbench-"))
    rows = []
    for mode_name, hard in (("clean", False), ("realistic", True)):
        for name, progression in PROGRESSIONS.items():
            wav = tmp / f"{name}-{mode_name}.wav"
            sf.write(wav, render_track(progression, hard=hard), SR)
            ref_iv, ref_lab = ground_truth(progression)
            gt_beats = np.arange(len(progression) * BEATS_PER_BAR + 1) * BEAT_SEC

            # End-to-end beats: what the product actually passes in.
            y_mono, _sr = librosa.load(str(wav), sr=22050, mono=True)
            onset = librosa.onset.onset_strength(y=y_mono, sr=22050, hop_length=512)
            _bpm, est_beats = librosa.beat.beat_track(
                onset_envelope=onset, sr=22050, hop_length=512, units="time", trim=False
            )
            est_beats = np.asarray(est_beats, dtype=float)
            # align phase to the true downbeat by picking the best global shift
            est_beats = est_beats - (est_beats[0] % BEAT_SEC)

            variants = {}
            variants["current, GT beats"] = score(
                ref_iv, ref_lab, *est_from_events(detect_chords(wav, beats=gt_beats, bpm=BPM))
            )
            variants["current, est. beats"] = score(
                ref_iv, ref_lab, *est_from_events(detect_chords(wav, beats=est_beats, bpm=BPM))
            )
            for label, mode, vocab, penalty, kp in [
                ("tuning+CQT (triads)", "cqt", VOCAB_SMALL, 0.06, False),
                ("HPSS+tuning (triads)", "hpss", VOCAB_SMALL, 0.06, False),
                ("HPSS+tuning (full vocab)", "hpss", VOCAB_FULL, 0.06, False),
                ("HPSS+CENS+key+penalty0.6", "cens", VOCAB_FULL, 0.6, True),
            ]:
                variants[label] = score(
                    ref_iv, ref_lab,
                    *est_from_events(
                        improved_events(wav, gt_beats, mode=mode, vocab=vocab,
                                        key=KEY_OF[name], change_penalty=penalty,
                                        use_key_prior=kp)
                    ),
                )
            rows.append({"track": f"{name}-{mode_name}", "variants": variants})
            print(f"\n== {name}  [{mode_name}]  ({len(progression)} bars)")
            for label, s in variants.items():
                print(f"  {label:28s} root={s.get('root', 0):.3f} majmin={s.get('majmin', 0):.3f} "
                      f"7ths={s.get('sevenths', 0):.3f} mirex={s.get('mirex', 0):.3f} segs={s.get('segments')}")

    print("\n== AGGREGATE (mean over tracks)")
    labels = list(rows[0]["variants"])
    for label in labels:
        mean = {k: float(np.mean([r["variants"][label].get(k, 0.0) for r in rows]))
                for k in ("root", "majmin", "sevenths", "mirex", "segments")}
        print(f"  {label:28s} root={mean['root']:.3f} majmin={mean['majmin']:.3f} "
              f"7ths={mean['sevenths']:.3f} mirex={mean['mirex']:.3f} segs={mean['segments']:.1f}")

    for subset in ("clean", "realistic"):
        subset_rows = [r for r in rows if r["track"].endswith(subset)]
        print(f"\n== {subset.upper()} only")
        for label in labels:
            mean = {k: float(np.mean([r["variants"][label].get(k, 0.0) for r in subset_rows]))
                    for k in ("root", "majmin", "sevenths", "mirex")}
            print(f"  {label:28s} root={mean['root']:.3f} majmin={mean['majmin']:.3f} "
                  f"7ths={mean['sevenths']:.3f} mirex={mean['mirex']:.3f}")

    out = Path(__file__).with_name("synth_bench_results.json")
    out.write_text(json.dumps(rows, indent=2))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
