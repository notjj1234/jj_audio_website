"""Tests for stem mixer helpers and dual-guitar heuristic."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from audio_to_tab.isolate import analyze_dual_guitar_candidate, split_dual_guitar_stem
from audio_to_tab.mixer import audible_stems, mix_stems_to_wav, waveform_peaks


def _write_stereo_wav(path: Path, left: np.ndarray, right: np.ndarray, sr: int = 44100) -> None:
    stereo = np.column_stack([left, right]).astype(np.float32)
    sf.write(str(path), stereo, sr, subtype="PCM_16")


def test_audible_stems_solo_overrides_mute():
    names = ["vocals", "drums", "bass"]
    muted = {"vocals": True, "drums": False, "bass": False}
    soloed = {"vocals": True, "drums": False, "bass": False}
    assert audible_stems(names, muted=muted, soloed=soloed) == ["vocals"]


def test_audible_stems_mute_when_no_solo():
    names = ["vocals", "drums", "bass"]
    muted = {"vocals": True, "drums": False, "bass": False}
    soloed = {"vocals": False, "drums": False, "bass": False}
    assert audible_stems(names, muted=muted, soloed=soloed) == ["drums", "bass"]


def test_waveform_peaks(tmp_path: Path):
    t = np.linspace(0, 1, 44100, endpoint=False)
    mono = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    path = tmp_path / "tone.wav"
    sf.write(str(path), mono, 44100)
    peaks = waveform_peaks(path, num_points=50)
    assert len(peaks) == 50
    assert float(peaks.max()) > 0.0


def test_mix_stems_to_wav(tmp_path: Path):
    sr = 44100
    t = np.linspace(0, 0.5, sr // 2, endpoint=False)
    left = 0.3 * np.sin(2 * np.pi * 220 * t)
    right = 0.2 * np.sin(2 * np.pi * 330 * t)
    p1 = tmp_path / "a.wav"
    p2 = tmp_path / "b.wav"
    _write_stereo_wav(p1, left, left, sr)
    _write_stereo_wav(p2, right, right, sr)
    out = tmp_path / "mix.wav"
    mix_stems_to_wav({"a": p1, "b": p2}, ["a", "b"], out)
    data, out_sr = sf.read(str(out))
    assert out_sr == sr
    assert len(data) > 0


def test_dual_guitar_splits_distinct_stereo(tmp_path: Path):
    sr = 44100
    n = sr * 2
    t = np.linspace(0, 2, n, endpoint=False)
    left = np.sin(2 * np.pi * 300 * t)
    right = np.sin(2 * np.pi * 900 * t)
    guitar = tmp_path / "guitar.wav"
    _write_stereo_wav(guitar, left, right, sr)

    diag = analyze_dual_guitar_candidate(guitar)
    assert diag.split is True

    stems, out_diag = split_dual_guitar_stem(guitar, tmp_path)
    assert out_diag.split is True
    assert "guitar1" in stems and "guitar2" in stems

    g1, _ = sf.read(str(stems["guitar1"]))
    g2, _ = sf.read(str(stems["guitar2"]))
    assert not np.allclose(g1, g2)


def test_dual_guitar_rejects_identical_channels(tmp_path: Path):
    sr = 44100
    n = sr * 2
    t = np.linspace(0, 2, n, endpoint=False)
    mono = np.sin(2 * np.pi * 440 * t)
    guitar = tmp_path / "guitar.wav"
    _write_stereo_wav(guitar, mono, mono, sr)

    diag = analyze_dual_guitar_candidate(guitar)
    assert diag.split is False
    stems, _ = split_dual_guitar_stem(guitar, tmp_path)
    assert stems == {}
