"""Key estimation: chord-histogram first, chroma profiles as the fallback."""

from __future__ import annotations

import numpy as np
import pytest
import soundfile as sf

from audio_to_tab.analysis import ChordEvent
from audio_to_tab.key import MAJOR_PROFILE, estimate_key, provisional_key


def _write_chord(path, freqs, *, duration: float = 2.0, sr: int = 22050) -> None:
    t = np.arange(int(sr * duration), dtype=np.float64) / sr
    y = sum(0.2 * np.sin(2.0 * np.pi * f * t) for f in freqs)
    sf.write(path, y, sr)


def _chords(*symbols: str) -> tuple[ChordEvent, ...]:
    return tuple(
        ChordEvent(start=float(i), end=float(i + 1), symbol=symbol, confidence=0.9)
        for i, symbol in enumerate(symbols)
    )


def test_major_triad_is_detected(tmp_path):
    path = tmp_path / "c-major.wav"
    _write_chord(path, (261.63, 329.63, 392.00))

    key, confidence = estimate_key(path)

    assert key == "C"
    assert confidence in {"high", "medium"}


def test_minor_triad_is_detected(tmp_path):
    path = tmp_path / "a-minor.wav"
    _write_chord(path, (220.00, 261.63, 329.63))

    key, confidence = estimate_key(path)

    assert key == "Am"
    assert confidence in {"high", "medium"}


def test_beat_synchronous_path_still_works(tmp_path):
    path = tmp_path / "c-major.wav"
    _write_chord(path, (261.63, 329.63, 392.00))

    key, _ = estimate_key(path, bpm=120.0, beats=(0.0, 0.5, 1.0, 1.5))

    assert key == "C"


def test_silence_returns_none(tmp_path):
    path = tmp_path / "silence.wav"
    sf.write(path, np.zeros(22050 * 2), 22050)

    assert estimate_key(path) == (None, "low")


def test_missing_file_returns_none(tmp_path):
    assert estimate_key(tmp_path / "nope.wav") == (None, "low")


def test_chords_win_over_chroma(tmp_path):
    # Audio is C major, but the supplied progression is unambiguously A minor.
    path = tmp_path / "c-major.wav"
    _write_chord(path, (261.63, 329.63, 392.00))

    key, confidence = estimate_key(path, chords=_chords("Am", "Dm", "E7", "Am"))

    assert key == "Am"
    assert confidence in {"high", "medium"}


def test_major_progression_with_slash_chord(tmp_path):
    path = tmp_path / "c-major.wav"
    _write_chord(path, (261.63, 329.63, 392.00))

    key, _ = estimate_key(path, chords=_chords("C", "F", "G", "C/G"))

    assert key == "C"


def test_flat_chord_spelling_is_normalised(tmp_path):
    path = tmp_path / "c-major.wav"
    _write_chord(path, (261.63, 329.63, 392.00))

    key, _ = estimate_key(path, chords=_chords("Bb", "Eb", "F", "Bb"))

    assert key == "A#"


def test_noisy_chords_do_not_invent_a_key(tmp_path):
    path = tmp_path / "c-major.wav"
    _write_chord(path, (261.63, 329.63, 392.00))
    nonsense = tuple(
        ChordEvent(start=float(i), end=float(i + 1), symbol=f"X{i}", confidence=0.1) for i in range(4)
    )

    key, confidence = estimate_key(path, chords=nonsense)

    # An unparseable progression falls back to chroma rather than returning garbage.
    assert key == "C"
    assert confidence in {"high", "medium", "low"}


def test_relative_minor_broken_by_bass():
    minor = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
    chroma = MAJOR_PROFILE + np.roll(minor, 9)
    bass_a = np.zeros(12)
    bass_a[9] = 1.0
    bass_c = np.zeros(12)
    bass_c[0] = 1.0

    minor_name, _minor_score = provisional_key(chroma, bass_a)
    major_name, _major_score = provisional_key(chroma, bass_c)

    assert minor_name == "Am"
    assert major_name == "C"


def test_provisional_key_matches_profile_on_c_major_scale():
    name, score = provisional_key(MAJOR_PROFILE, np.zeros(12))

    assert name == "C"
    assert score > 0.8


@pytest.mark.parametrize("symbol", ["C", "Cm", "C7", "Cmaj7", "Cm7", "Csus4", "Cdim"])
def test_common_symbols_parse(tmp_path, symbol):
    path = tmp_path / "c-major.wav"
    _write_chord(path, (261.63, 329.63, 392.00))

    key, _ = estimate_key(path, chords=_chords(symbol, symbol, symbol, symbol))

    assert key is not None
