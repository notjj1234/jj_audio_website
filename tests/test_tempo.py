"""Real-audio tempo regression tests (the librosa public API moved between releases)."""

from __future__ import annotations

import numpy as np
import pytest
import soundfile as sf

from audio_to_tab.metronome import tempo_curve_from_onset
from audio_to_tab.tempo import estimate_tempo_from_audio


def _click_track(path, *, bpm: float = 120.0, duration: float = 8.0, sr: int = 22050) -> None:
    y = np.zeros(int(sr * duration), dtype=np.float64)
    period = 60.0 / bpm
    rng = np.random.default_rng(0)
    burst = rng.normal(0.0, 0.5, int(sr * 0.02))
    for index in range(int(duration / period)):
        start = int(index * period * sr)
        y[start : start + burst.size] += burst
    sf.write(path, y, sr)


def test_estimate_tempo_from_real_audio(tmp_path):
    path = tmp_path / "click-120.wav"
    _click_track(path, bpm=120.0)

    estimate = estimate_tempo_from_audio(path)

    assert estimate is not None
    assert estimate.source == "audio"
    assert estimate.bpm == pytest.approx(120.0, abs=4.0)


def test_tempo_curve_uses_public_librosa_api():
    onset = np.zeros(400, dtype=np.float64)
    onset[::10] = 1.0

    curve = tempo_curve_from_onset(onset, sr=22050, hop_length=512)

    assert curve.size > 0
    assert np.all(np.isfinite(curve))
    assert np.all(curve > 0)
