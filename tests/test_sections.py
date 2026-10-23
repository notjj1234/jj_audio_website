"""Section detection: coverage, minimum length, and conservative labels."""

from __future__ import annotations

from itertools import pairwise

import numpy as np
import pytest
import soundfile as sf

from audio_to_tab.analysis import Section
from audio_to_tab.sections import _pick_boundaries, _sections_from_features, detect_sections

SR = 22050


def _write_track(path, *, sections=(("C", 0.10), ("G", 0.40), ("C", 0.10)), section_sec: float = 8.0) -> None:
    chords = {
        "C": (261.63, 329.63, 392.00),
        "G": (392.00, 493.88, 587.33),
    }
    total = int(SR * section_sec * len(sections))
    y = np.zeros(total, dtype=np.float64)
    for index, (symbol, level) in enumerate(sections):
        start = int(index * section_sec * SR)
        end = int((index + 1) * section_sec * SR)
        local = np.arange(end - start, dtype=np.float64) / SR
        for frequency in chords[symbol]:
            y[start:end] += level * np.sin(2 * np.pi * frequency * local)
    sf.write(path, y, SR)


def _assert_cover(sections: list[Section], duration: float) -> None:
    assert sections
    assert sections[0].start == 0.0
    assert sections[-1].end == pytest.approx(duration, abs=1e-6)
    assert [s.start for s in sections] == sorted(s.start for s in sections)
    for previous, current in pairwise(sections):
        assert current.start == pytest.approx(previous.end, abs=1e-6)
    assert all(s.end >= s.start for s in sections)
    assert all(0.0 <= s.confidence <= 1.0 for s in sections)


def test_sections_cover_song_without_gaps(tmp_path):
    path = tmp_path / "track.wav"
    _write_track(path)

    sections = detect_sections(path, beats=tuple(i * 0.5 for i in range(49)), duration_sec=24.0)

    _assert_cover(sections, 24.0)
    assert all(s.end - s.start >= 7.5 for s in sections)
    assert all(s.label for s in sections)


def test_short_song_returns_full_song(tmp_path):
    path = tmp_path / "short.wav"
    _write_track(path, sections=(("C", 0.1),), section_sec=5.0)

    sections = detect_sections(path, beats=(0.0, 0.5, 1.0), duration_sec=5.0)

    assert sections == [Section(0.0, 5.0, "Full song", 0.0)]


def test_silence_returns_full_song(tmp_path):
    path = tmp_path / "silence.wav"
    sf.write(path, np.zeros(SR * 20), SR)

    sections = detect_sections(path, beats=tuple(i * 0.5 for i in range(40)), duration_sec=20.0)

    assert sections == [Section(0.0, 20.0, "Full song", 0.0)]


def test_missing_file_returns_full_song(tmp_path):
    sections = detect_sections(tmp_path / "nope.wav", beats=(0.0, 0.5), duration_sec=12.0)

    assert sections == [Section(0.0, 12.0, "Full song", 0.0)]


def test_repeated_structure_gets_conservative_labels():
    major = np.zeros(12)
    major[[0, 4, 7]] = 1.0
    dominant = np.zeros(12)
    dominant[[7, 11, 2]] = 1.0
    chroma = np.hstack(
        [
            np.tile(major[:, None], (1, 16)),
            np.tile(dominant[:, None], (1, 16)),
            np.tile(major[:, None], (1, 16)),
            np.tile(dominant[:, None], (1, 16)),
        ]
    )
    rms = np.concatenate(
        [np.full(16, 0.10), np.full(16, 0.40), np.full(16, 0.10), np.full(16, 0.40)]
    )
    times = tuple(index * 0.5 for index in range(64))

    sections = _sections_from_features(chroma, rms, times, 32.0)

    _assert_cover(sections, 32.0)
    assert [s.label for s in sections] == ["Intro", "Chorus", "Verse", "Outro"]


def test_single_repeated_section_stays_full_song():
    chroma = np.tile(np.ones((12, 1)), (1, 32))
    rms = np.full(32, 0.2)
    times = tuple(index * 0.5 for index in range(32))

    sections = _sections_from_features(chroma, rms, times, 16.0)

    assert sections == [Section(0.0, 16.0, "Full song", 0.0)]


def test_boundaries_respect_minimum_length():
    novelty = np.zeros(80)
    novelty[[8, 16, 24, 32, 40, 48, 56, 64]] = 1.0

    boundaries = _pick_boundaries(novelty, min_beats=16)

    assert boundaries[0] == 0
    assert boundaries[-1] == 80
    assert all(b - a >= 16 for a, b in pairwise(boundaries))


def test_detection_is_deterministic(tmp_path):
    path = tmp_path / "track.wav"
    _write_track(path)
    beats = tuple(i * 0.5 for i in range(49))

    first = detect_sections(path, beats=beats, duration_sec=24.0)
    second = detect_sections(path, beats=beats, duration_sec=24.0)

    assert first == second
