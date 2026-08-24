"""Tests for isolate media helpers (preview / cleanup)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

from ui.media import (
    PREVIEW_DURATION_THRESHOLD_SEC,
    cleanup_mix_artifacts,
    ensure_mixer_audio_paths,
    should_use_previews,
)


def _write_tone(path: Path, seconds: float, sr: int = 44100) -> None:
    n = int(sr * seconds)
    t = np.linspace(0, seconds, n, endpoint=False)
    tone = (0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    stereo = np.column_stack([tone, tone])
    sf.write(str(path), stereo, sr, subtype="PCM_16")


def test_cleanup_mix_artifacts(tmp_path: Path):
    (tmp_path / "_heard_mix_abc.wav").write_bytes(b"x")
    (tmp_path / "_heard_mix_def.wav").write_bytes(b"y")
    (tmp_path / "current_mix.wav").write_bytes(b"z")
    (tmp_path / "vocals.wav").write_bytes(b"keep")
    cleanup_mix_artifacts(tmp_path)
    assert not (tmp_path / "_heard_mix_abc.wav").exists()
    assert not (tmp_path / "_heard_mix_def.wav").exists()
    assert not (tmp_path / "current_mix.wav").exists()
    assert (tmp_path / "vocals.wav").exists()


def test_should_use_previews_short(tmp_path: Path):
    p = tmp_path / "a.wav"
    _write_tone(p, 5.0)
    assert should_use_previews({"a": p}) is False


def test_should_use_previews_long(tmp_path: Path):
    p = tmp_path / "a.wav"
    _write_tone(p, PREVIEW_DURATION_THRESHOLD_SEC + 5.0)
    assert should_use_previews({"a": p}) is True


def test_ensure_mixer_audio_paths_short_uses_original(tmp_path: Path):
    p = tmp_path / "vocals.wav"
    _write_tone(p, 2.0)
    out = ensure_mixer_audio_paths({"vocals": p})
    assert out["vocals"] == p
