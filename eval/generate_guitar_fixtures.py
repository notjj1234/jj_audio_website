"""Generate realistic-ish guitar fixtures for the audio-to-tab evaluation.

These are synthesized with a Karplus-Strong plucked-string model (not sine
tones), with optional strum spread, body filtering, reverb, bass and drums.
Everything here is generated locally, so the fixtures are ours to use.

Run from the repo root:

    .venv311/bin/python eval/generate_guitar_fixtures.py

Outputs land in ``eval/fixtures/audio_to_tab/`` together with a manifest that
records the reference MIDI and the source/licence of each item.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pretty_midi
import soundfile as sf
from scipy.signal import butter, fftconvolve, lfilter, sosfilt

OUT_DIR = Path(__file__).resolve().parent / "fixtures" / "audio_to_tab"
SR = 44100

# Open-string MIDI pitches, low E -> high e (standard tuning).
STANDARD = (40, 45, 50, 55, 59, 64)

CHORDS = {
    "G": [43, 47, 50, 55, 59, 67],   # G2 B2 D3 G3 B3 G4
    "C": [48, 52, 55, 60, 64],       # C3 E3 G3 C4 E4
    "D": [50, 57, 62, 66],           # D3 A3 D4 F#4
    "Em": [40, 47, 52, 55, 59, 64],  # E2 B2 E3 G3 B3 E4
}

# (pitch, start_beat, duration_beats, string, fret)
MELODY = [
    (64, 0.0, 0.9, 5, 0),   # E4 open high e
    (65, 1.0, 0.9, 5, 1),   # F4
    (67, 2.0, 0.9, 5, 3),   # G4
    (69, 3.0, 0.9, 5, 5),   # A4
    (71, 4.0, 0.9, 5, 7),   # B4
    (72, 5.0, 0.9, 5, 8),   # C5
    (71, 6.0, 0.9, 5, 7),   # B4
    (69, 7.0, 0.9, 5, 5),   # A4
    (67, 8.0, 0.9, 5, 3),   # G4
    (65, 9.0, 0.9, 5, 1),   # F4
    (64, 10.0, 0.9, 5, 0),  # E4
    (62, 11.0, 1.5, 4, 3),  # D4 on the B string
]


def _body_filter(x: np.ndarray) -> np.ndarray:
    """Crude guitar-body colour: band-limit plus a low resonance."""
    sos = butter(2, [70, 6500], btype="bandpass", fs=SR, output="sos")
    y = sosfilt(sos, x)
    # A gentle 190 Hz resonance adds some wooden body.
    r = 0.97
    theta = 2 * np.pi * 190 / SR
    b = [1 - r]
    a = [1, -2 * r * np.cos(theta), r * r]
    return lfilter(b, a, y)


def _pluck(freq: float, dur: float, rng: np.random.Generator, decay: float = 0.996) -> np.ndarray:
    """Karplus-Strong plucked string with a pick-position comb."""
    n = max(2, int(SR / freq))
    buf = rng.uniform(-1.0, 1.0, n)
    pick_delay = max(1, int(n * 0.18))
    buf = buf - 0.55 * np.roll(buf, pick_delay)
    length = int(dur * SR)
    out = np.empty(length, dtype=np.float32)
    for i in range(length):
        j = i % n
        v = buf[j]
        out[i] = v
        nxt = buf[(j + 1) % n]
        buf[j] = 0.5 * (v + nxt) * decay
    return out


def _add_reverb(x: np.ndarray, rng: np.random.Generator, wet: float = 0.16) -> np.ndarray:
    n = int(0.9 * SR)
    t = np.arange(n) / SR
    ir = rng.normal(0, 1, n) * np.exp(-t / 0.22)
    ir[: int(0.02 * SR)] *= np.linspace(0.4, 1.0, int(0.02 * SR))
    ir[0] = 1.0
    ir /= np.max(np.abs(ir)) + 1e-9
    wet_sig = fftconvolve(x, ir)[: len(x)]
    return (x * (1 - wet) + wet_sig * wet).astype(np.float32)


def _note_track(pitch: int, start: float, dur: float, rng: np.random.Generator) -> np.ndarray:
    freq = pretty_midi.note_number_to_hz(pitch)
    tone = _pluck(freq, dur + 0.15, rng)
    tone = _body_filter(tone)
    # Short fade-out so rings do not click when the buffer ends.
    fade = min(len(tone), int(0.05 * SR))
    tone[-fade:] *= np.linspace(1.0, 0.0, fade)
    return tone[: int(dur * SR)]


def _render_notes(
    notes: list[tuple[int, float, float]],
    total: float,
    rng: np.random.Generator,
    *,
    stereo: bool,
) -> np.ndarray:
    channels = 2 if stereo else 1
    out = np.zeros((int(total * SR) + SR, channels), dtype=np.float32)
    for pitch, start, dur in notes:
        tone = _note_track(pitch, start, dur, rng)
        i0 = int(start * SR)
        out[i0 : i0 + len(tone), 0] += tone
        if stereo:
            out[i0 : i0 + len(tone), 1] += np.roll(tone, 13)
    out = out[: int(total * SR)]
    if stereo:
        out[:, 0] = _add_reverb(out[:, 0], rng)
        out[:, 1] = _add_reverb(out[:, 1], rng)
    else:
        out[:, 0] = _add_reverb(out[:, 0], rng)
    peak = float(np.max(np.abs(out))) or 1.0
    return (out / peak * 0.72).astype(np.float32)


def _write_midi(path: Path, notes: list[tuple[int, float, float]], tempo: float) -> None:
    pm = pretty_midi.PrettyMIDI(initial_tempo=tempo)
    inst = pretty_midi.Instrument(program=25, name="Guitar")
    for pitch, start, dur in notes:
        inst.notes.append(pretty_midi.Note(velocity=88, pitch=pitch, start=start, end=start + dur))
    pm.instruments.append(inst)
    pm.write(str(path))


def _melody_notes() -> list[tuple[int, float, float]]:
    bpm = 100.0
    spb = 60.0 / bpm
    return [(p, b * spb, d * spb) for p, b, d, _s, _f in MELODY]


def _chord_notes() -> list[tuple[int, float, float]]:
    bpm = 90.0
    spb = 60.0 / bpm
    events: list[tuple[int, float, float]] = []
    order = ["G", "C", "D", "Em"]
    strum_gap = 0.022
    for bar, name in enumerate(order):
        chord = CHORDS[name]
        for strum_beat, ring_beats in ((0.0, 2.0), (2.0, 1.6)):
            base = (bar * 4 + strum_beat) * spb
            for i, pitch in enumerate(chord):
                start = base + i * strum_gap
                events.append((pitch, start, max(0.25, ring_beats * spb - i * strum_gap)))
    return events


def _add_backing(guitar: np.ndarray, total: float, rng: np.random.Generator) -> np.ndarray:
    """Bass + kick/snare/hats, so the separation path is exercised."""
    bpm = 90.0
    spb = 60.0 / bpm
    out = np.array(guitar, copy=True)
    roots = {"G": 43, "C": 48, "D": 50, "Em": 40}
    for bar, name in enumerate(["G", "C", "D", "Em"]):
        root = roots[name]
        for beat in (0.0, 1.5, 2.0, 3.5):
            start = (bar * 4 + beat) * spb
            dur = 0.4 * spb
            t = np.arange(int(dur * SR)) / SR
            f = pretty_midi.note_number_to_hz(root)
            tone = 0.5 * np.sin(2 * np.pi * f * t) + 0.2 * np.sin(4 * np.pi * f * t)
            tone *= np.exp(-t / 0.35)
            i0 = int(start * SR)
            out[i0 : i0 + len(tone), 0] += tone.astype(np.float32)
            out[i0 : i0 + len(tone), 1] += tone.astype(np.float32)

    def kick(at: float) -> None:
        dur = 0.18
        t = np.arange(int(dur * SR)) / SR
        f = 95 * np.exp(-t / 0.035) + 42
        tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.09)
        i0 = int(at * SR)
        out[i0 : i0 + len(tone), 0] += 0.75 * tone.astype(np.float32)
        out[i0 : i0 + len(tone), 1] += 0.75 * tone.astype(np.float32)

    def snare(at: float) -> None:
        dur = 0.16
        tone = rng.normal(0, 1, int(dur * SR)) * np.exp(-np.arange(int(dur * SR)) / SR / 0.05)
        sos = butter(2, [180, 3200], btype="bandpass", fs=SR, output="sos")
        tone = sosfilt(sos, tone) * 0.33
        i0 = int(at * SR)
        out[i0 : i0 + len(tone), 0] += tone.astype(np.float32)
        out[i0 : i0 + len(tone), 1] += tone.astype(np.float32)

    for bar in range(4):
        for beat in (0.0, 2.0):
            kick((bar * 4 + beat) * spb)
        for beat in (1.0, 3.0):
            snare((bar * 4 + beat) * spb)
    peak = float(np.max(np.abs(out))) or 1.0
    return (out / peak * 0.8).astype(np.float32)


def main() -> list[dict]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(7)

    melody_notes = _melody_notes()
    melody_total = max(s + d for _p, s, d in melody_notes) + 0.6
    melody = _render_notes(melody_notes, melody_total, rng, stereo=False)
    sf.write(OUT_DIR / "clean_line.wav", melody, SR)
    _write_midi(OUT_DIR / "clean_line.mid", melody_notes, 100.0)

    chord_notes = _chord_notes()
    chord_total = max(s + d for _p, s, d in chord_notes) + 0.5
    chords = _render_notes(chord_notes, chord_total, rng, stereo=True)
    sf.write(OUT_DIR / "chord_progression.wav", chords, SR)
    _write_midi(OUT_DIR / "chord_progression.mid", chord_notes, 90.0)

    mixed = _add_backing(chords, chord_total, rng)
    sf.write(OUT_DIR / "mixed_band.wav", mixed, SR)
    _write_midi(OUT_DIR / "mixed_band.mid", chord_notes, 90.0)

    manifest = [
        {
            "id": "clean_line",
            "category": "monophonic",
            "wav": "clean_line.wav",
            "midi": "clean_line.mid",
            "note_count": len(melody_notes),
            "tempo_bpm": 100.0,
            "source": "synthesized (Karplus-Strong) by eval/generate_guitar_fixtures.py",
            "licence": "same as this repository (MIT)",
        },
        {
            "id": "chord_progression",
            "category": "polyphonic-strummed",
            "wav": "chord_progression.wav",
            "midi": "chord_progression.mid",
            "note_count": len(chord_notes),
            "tempo_bpm": 90.0,
            "source": "synthesized (Karplus-Strong) by eval/generate_guitar_fixtures.py",
            "licence": "same as this repository (MIT)",
        },
        {
            "id": "mixed_band",
            "category": "full-mix",
            "wav": "mixed_band.wav",
            "midi": "mixed_band.mid",
            "note_count": len(chord_notes),
            "tempo_bpm": 90.0,
            "source": "synthesized guitar + bass + drums by eval/generate_guitar_fixtures.py",
            "licence": "same as this repository (MIT)",
        },
        {
            "id": "real_guitar_el_noi_30s",
            "category": "real-recording",
            "wav": "real_guitar_el_noi_30s.wav",
            "midi": None,
            "note_count": None,
            "tempo_bpm": None,
            "source": (
                "Wikimedia Commons, 'El Noi de la Mare (guitar).ogg', performer/uploader "
                "Jujutacular, first 30 s; https://commons.wikimedia.org/wiki/File:El_Noi_de_la_Mare_(guitar).ogg"
            ),
            "licence": "Public domain",
        },
    ]
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    for item in manifest:
        print(f"  {item['id']}: {item['note_count']} ref notes, {item['category']}")
    return manifest


if __name__ == "__main__":
    main()
