"""Tests for stem mixer helpers and legacy dual-guitar heuristic."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from audio_to_tab.isolate import analyze_dual_guitar_candidate, split_dual_guitar_stem
from audio_to_tab.mixer import (
    DB_MIN,
    audible_stems,
    db_to_linear,
    effective_linear_gains,
    mix_stems_to_wav,
    waveform_peaks,
)


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


def test_db_to_linear_edges():
    assert db_to_linear(DB_MIN) == 0.0
    assert db_to_linear(DB_MIN - 10) == 0.0
    assert db_to_linear(0.0) == pytest.approx(1.0)
    assert db_to_linear(6.0) == pytest.approx(10 ** (6.0 / 20.0))
    assert db_to_linear(-6.0) == pytest.approx(10 ** (-6.0 / 20.0))


def test_effective_linear_gains_solo_overrides_mute():
    names = ["vocals", "drums", "bass"]
    muted = {"vocals": True, "drums": False, "bass": False}
    soloed = {"vocals": True, "drums": False, "bass": False}
    gains = effective_linear_gains(names, muted=muted, soloed=soloed, volume_db={})
    assert gains["vocals"] == pytest.approx(1.0)
    assert gains["drums"] == 0.0
    assert gains["bass"] == 0.0


def test_effective_linear_gains_multi_solo():
    names = ["vocals", "drums", "bass"]
    muted = {"vocals": False, "drums": False, "bass": False}
    soloed = {"vocals": True, "drums": True, "bass": False}
    gains = effective_linear_gains(
        names, muted=muted, soloed=soloed, volume_db={"vocals": -6.0, "drums": 0.0}
    )
    assert gains["vocals"] == pytest.approx(db_to_linear(-6.0))
    assert gains["drums"] == pytest.approx(1.0)
    assert gains["bass"] == 0.0


def test_effective_linear_gains_all_muted():
    names = ["vocals", "drums"]
    muted = {"vocals": True, "drums": True}
    soloed = {"vocals": False, "drums": False}
    gains = effective_linear_gains(names, muted=muted, soloed=soloed)
    assert gains == {"vocals": 0.0, "drums": 0.0}


def test_effective_linear_gains_master_volume_scales():
    names = ["vocals", "drums"]
    muted = {"vocals": False, "drums": False}
    soloed = {"vocals": False, "drums": False}
    gains = effective_linear_gains(
        names,
        muted=muted,
        soloed=soloed,
        volume_db={"vocals": 0.0, "drums": -6.0},
        master_volume_db=-6.0,
    )
    assert gains["vocals"] == pytest.approx(db_to_linear(-6.0))
    assert gains["drums"] == pytest.approx(db_to_linear(-6.0) * db_to_linear(-6.0))


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


def test_mix_stems_to_wav_with_gains(tmp_path: Path):
    sr = 44100
    t = np.linspace(0, 0.25, sr // 4, endpoint=False)
    tone = 0.5 * np.sin(2 * np.pi * 440 * t)
    p1 = tmp_path / "a.wav"
    p2 = tmp_path / "b.wav"
    _write_stereo_wav(p1, tone, tone, sr)
    _write_stereo_wav(p2, tone, tone, sr)
    out = tmp_path / "mix.wav"
    mix_stems_to_wav({"a": p1, "b": p2}, output_path=out, gains={"a": 1.0, "b": 0.0})
    data, _ = sf.read(str(out), always_2d=True)
    assert float(np.max(np.abs(data))) > 0.1


def test_mix_stems_to_wav_all_silent(tmp_path: Path):
    sr = 44100
    t = np.linspace(0, 0.25, sr // 4, endpoint=False)
    tone = 0.5 * np.sin(2 * np.pi * 440 * t)
    p1 = tmp_path / "a.wav"
    _write_stereo_wav(p1, tone, tone, sr)
    out = tmp_path / "silent.wav"
    mix_stems_to_wav({"a": p1}, output_path=out, gains={"a": 0.0})
    data, out_sr = sf.read(str(out), always_2d=True)
    assert out_sr == sr
    assert len(data) == len(t)
    assert float(np.max(np.abs(data))) == pytest.approx(0.0, abs=1e-3)


def test_mix_stems_true_peak_ceiling(tmp_path: Path):
    """Hot solo mix is limited to ~−1 dBTP (TRUE_PEAK_CEILING), not full-scale."""
    from audio_to_tab.mixer import TRUE_PEAK_CEILING, apply_true_peak_ceiling

    hot = np.full((1000, 2), 2.0, dtype=np.float32)
    limited = apply_true_peak_ceiling(hot)
    peak = float(np.max(np.abs(limited)))
    assert peak == pytest.approx(TRUE_PEAK_CEILING, rel=1e-4)

    sr = 44100
    t = np.linspace(0, 0.2, sr // 5, endpoint=False)
    tone = 1.5 * np.sin(2 * np.pi * 440 * t)  # hotter than full scale
    p1 = tmp_path / "hot.wav"
    _write_stereo_wav(p1, tone, tone, sr)
    out = tmp_path / "limited.wav"
    mix_stems_to_wav({"a": p1}, output_path=out, gains={"a": 1.0})
    data, _ = sf.read(str(out), always_2d=True)
    # PCM_16 write + ceiling → peak at or under ceiling (int16 quantize).
    assert float(np.max(np.abs(data))) <= TRUE_PEAK_CEILING + 0.02
    assert float(np.max(np.abs(data))) > 0.5


def test_mix_stems_sample_rate_mismatch(tmp_path: Path):
    t = np.linspace(0, 0.1, 4410, endpoint=False)
    tone = 0.2 * np.sin(2 * np.pi * 200 * t)
    p1 = tmp_path / "a.wav"
    p2 = tmp_path / "b.wav"
    _write_stereo_wav(p1, tone, tone, 44100)
    _write_stereo_wav(p2, tone[:2205], tone[:2205], 22050)
    with pytest.raises(ValueError, match="Sample rate mismatch"):
        mix_stems_to_wav({"a": p1, "b": p2}, ["a", "b"], tmp_path / "out.wav")


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

    with pytest.warns(DeprecationWarning, match="split_dual_guitar_stem is deprecated"):
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
    with pytest.warns(DeprecationWarning, match="split_dual_guitar_stem is deprecated"):
        stems, _ = split_dual_guitar_stem(guitar, tmp_path)
    assert stems == {}
