"""Chord detection: symbol normalisation, boundary handling, and the P0 baseline."""

from __future__ import annotations

import numpy as np
import pytest
import soundfile as sf

from audio_to_tab.analysis import ChordEvent
from audio_to_tab.chords import (
    _merge_events,
    _normalize_symbol,
    _snap_to_beat,
    detect_chords,
)

SR = 22050
CHORDS = {
    "C": (261.63, 329.63, 392.00),
    "F": (349.23, 440.00, 523.25),
    "G": (392.00, 493.88, 587.33),
}


def _write_progression(path, symbols=("C", "F", "G", "C"), *, chord_sec: float = 2.0) -> None:
    t = np.arange(int(SR * chord_sec * len(symbols)), dtype=np.float64) / SR
    y = np.zeros_like(t)
    for index, symbol in enumerate(symbols):
        start = int(index * chord_sec * SR)
        end = int((index + 1) * chord_sec * SR)
        local = t[start:end] - t[start]
        for frequency in CHORDS[symbol]:
            y[start:end] += 0.12 * np.sin(2 * np.pi * frequency * local)
            y[start:end] += 0.04 * np.sin(2 * np.pi * frequency * 2 * local)
    sf.write(path, y, SR)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("C", "C"),
        ("Cm", "Cm"),
        ("Cmin", "Cm"),
        ("C7", "C7"),
        ("Cmaj7", "Cmaj7"),
        ("CM7", "Cmaj7"),
        ("Cm7", "Cm7"),
        ("Cmin7", "Cm7"),
        ("Csus4", "Csus4"),
        ("Csus", "Csus4"),
        ("Cdim", "Cdim"),
        ("C°", "Cdim"),
        ("Caug", "Caug"),
        ("C+", "Caug"),
        ("Bb", "A#"),
        ("C/G", "C/G"),
        ("C/E", "C/E"),
        ("H", None),
        ("Cadd9", None),
        ("C6", None),
        ("N", None),
        ("", None),
        (None, None),
    ],
)
def test_symbol_normalisation(raw, expected):
    assert _normalize_symbol(raw) == expected


def test_snap_to_beat_within_tolerance():
    assert _snap_to_beat(1.04, [0.0, 1.0, 2.0], tolerance=0.06) == 1.0
    assert _snap_to_beat(1.10, [0.0, 1.0, 2.0], tolerance=0.06) == 1.10
    assert _snap_to_beat(0.4, [], tolerance=0.06) == 0.4


def test_merge_events_merges_and_drops_short():
    events = [
        ChordEvent(0.0, 1.0, "C", 0.0),
        ChordEvent(1.0, 2.0, "C", 0.0),
        ChordEvent(2.0, 2.05, "G", 0.0),
        ChordEvent(2.5, 3.5, "F", 0.0),
    ]

    merged = _merge_events(events, min_duration=0.10)

    assert [(e.start, e.end, e.symbol) for e in merged] == [(0.0, 2.0, "C"), (2.5, 3.5, "F")]


def test_detect_chords_on_synthetic_progression(tmp_path):
    path = tmp_path / "progression.wav"
    _write_progression(path)
    beats = tuple(i * 0.5 for i in range(17))

    events = detect_chords(path, beats=beats, bpm=120.0)

    assert events
    symbols = [event.symbol for event in events]
    assert symbols[0] == "C"
    assert "F" in symbols
    assert "G" in symbols
    assert symbols[-1] == "C"
    assert all(event.confidence == 0.0 for event in events)
    assert [e.start for e in events] == sorted(e.start for e in events)
    assert all(0.0 <= e.start < e.end <= 8.05 for e in events)
    assert all(e.end - e.start >= 0.10 - 1e-9 for e in events)


def test_detect_chords_without_beats_uses_fixed_grid(tmp_path):
    path = tmp_path / "progression.wav"
    _write_progression(path)

    events = detect_chords(path, beats=(), bpm=None)

    assert events
    assert all(e.confidence == 0.0 for e in events)
    assert [e.start for e in events] == sorted(e.start for e in events)


def test_silence_returns_empty(tmp_path):
    path = tmp_path / "silence.wav"
    sf.write(path, np.zeros(SR * 2), SR)

    assert detect_chords(path, beats=(0.0, 0.5, 1.0), bpm=120.0) == []


def test_missing_audio_returns_empty(tmp_path):
    assert detect_chords(tmp_path / "nope.wav", beats=(0.0, 0.5), bpm=120.0) == []


def test_missing_model_dir_returns_empty(tmp_path, caplog):
    path = tmp_path / "progression.wav"
    _write_progression(path)

    with caplog.at_level("WARNING"):
        events = detect_chords(
            path,
            beats=(0.0, 0.5, 1.0),
            bpm=120.0,
            model_dir=tmp_path / "missing-model",
        )

    assert events == []
    assert "chord model" in caplog.text.lower()


def test_progress_callback_is_called(tmp_path):
    path = tmp_path / "progression.wav"
    _write_progression(path)
    messages: list[str] = []

    detect_chords(path, beats=(0.0, 0.5, 1.0), bpm=120.0, progress=messages.append)

    assert messages
    assert any("chord" in message.lower() for message in messages)
