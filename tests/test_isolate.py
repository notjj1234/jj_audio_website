"""Tests for multi-stem isolation (Demucs mocked)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from audio_to_tab.isolate import IsolateConfig, SUPPORTED_MODELS, separate_stems


def test_supported_models():
    assert "htdemucs_6s" in SUPPORTED_MODELS
    assert "htdemucs" in SUPPORTED_MODELS
    assert "htdemucs_ft" in SUPPORTED_MODELS


def test_separate_stems_requires_demucs(tmp_path: Path):
    audio = tmp_path / "in.wav"
    audio.write_bytes(b"RIFF")
    with patch("audio_to_tab.isolate.is_demucs_available", return_value=False):
        with pytest.raises(RuntimeError, match="Demucs"):
            separate_stems(audio, tmp_path / "out")


def test_separate_stems_rejects_unknown_model(tmp_path: Path):
    audio = tmp_path / "in.wav"
    audio.write_bytes(b"RIFF")
    with patch("audio_to_tab.isolate.is_demucs_available", return_value=True):
        with pytest.raises(ValueError, match="Unsupported model"):
            separate_stems(audio, tmp_path / "out", IsolateConfig(model="not_a_model"))


def test_separate_stems_collects_wavs(tmp_path: Path):
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"fake-wav")
    out_dir = tmp_path / "stems"

    def fake_normalize(src, dest=None):
        dest = Path(dest) if dest else tmp_path / "norm.wav"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"norm")
        return dest

    def fake_run(cmd, capture_output=True, text=True):
        # Demucs output layout: -o <dir> → <dir>/<model>/<track>/*.wav
        assert "-m" in cmd and "demucs" in cmd
        assert "-n" in cmd and "htdemucs_6s" in cmd
        out_flag = cmd.index("-o")
        demucs_out = Path(cmd[out_flag + 1])
        track_dir = demucs_out / "htdemucs_6s" / "normalized"
        track_dir.mkdir(parents=True, exist_ok=True)
        for name in ("vocals", "drums", "bass", "other", "guitar", "piano"):
            (track_dir / f"{name}.wav").write_bytes(b"stem-" + name.encode())
        return MagicMock(returncode=0, stderr="", stdout="")

    with (
        patch("audio_to_tab.isolate.is_demucs_available", return_value=True),
        patch("audio_to_tab.isolate.normalize_audio", side_effect=fake_normalize),
        patch("audio_to_tab.isolate._trim_audio", side_effect=lambda p, _: p),
        patch("audio_to_tab.isolate.subprocess.run", side_effect=fake_run),
    ):
        artifacts = separate_stems(
            audio,
            out_dir,
            IsolateConfig(model="htdemucs_6s", quality="fast", max_duration_sec=15),
        )

    assert set(artifacts) == {"vocals", "drums", "bass", "other", "guitar", "piano"}
    for path in artifacts.values():
        assert path.exists()
        assert path.parent == out_dir


def test_separate_stems_passes_two_stems_flag(tmp_path: Path):
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"fake-wav")
    seen: list[list[str]] = []

    def fake_normalize(src, dest=None):
        dest = Path(dest) if dest else tmp_path / "norm.wav"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"norm")
        return dest

    def fake_run(cmd, capture_output=True, text=True):
        seen.append(cmd)
        out_flag = cmd.index("-o")
        demucs_out = Path(cmd[out_flag + 1])
        track_dir = demucs_out / "htdemucs" / "normalized"
        track_dir.mkdir(parents=True, exist_ok=True)
        (track_dir / "vocals.wav").write_bytes(b"v")
        (track_dir / "no_vocals.wav").write_bytes(b"nv")
        return MagicMock(returncode=0, stderr="", stdout="")

    with (
        patch("audio_to_tab.isolate.is_demucs_available", return_value=True),
        patch("audio_to_tab.isolate.normalize_audio", side_effect=fake_normalize),
        patch("audio_to_tab.isolate._trim_audio", side_effect=lambda p, _: p),
        patch("audio_to_tab.isolate.subprocess.run", side_effect=fake_run),
    ):
        artifacts = separate_stems(
            audio,
            tmp_path / "out",
            IsolateConfig(model="htdemucs", two_stems="vocals", max_duration_sec=None),
        )

    assert "--two-stems" in seen[0]
    assert "vocals" in seen[0]
    assert set(artifacts) == {"vocals", "no_vocals"}


def test_separate_stems_dual_guitar_when_heuristic_passes(tmp_path: Path):
    import numpy as np
    import soundfile as sf

    audio = tmp_path / "song.wav"
    audio.write_bytes(b"fake-wav")
    out_dir = tmp_path / "stems"

    def fake_normalize(src, dest=None):
        dest = Path(dest) if dest else tmp_path / "norm.wav"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"norm")
        return dest

    def fake_run(cmd, capture_output=True, text=True):
        out_flag = cmd.index("-o")
        demucs_out = Path(cmd[out_flag + 1])
        track_dir = demucs_out / "htdemucs_6s" / "normalized"
        track_dir.mkdir(parents=True, exist_ok=True)
        for name in ("vocals", "drums", "bass", "other", "piano"):
            (track_dir / f"{name}.wav").write_bytes(b"stem-" + name.encode())
        sr = 44100
        n = sr
        t = np.linspace(0, 1, n, endpoint=False)
        stereo = np.column_stack([np.sin(2 * np.pi * 200 * t), np.sin(2 * np.pi * 800 * t)])
        sf.write(str(track_dir / "guitar.wav"), stereo.astype(np.float32), sr)
        return MagicMock(returncode=0, stderr="", stdout="")

    with (
        patch("audio_to_tab.isolate.is_demucs_available", return_value=True),
        patch("audio_to_tab.isolate.normalize_audio", side_effect=fake_normalize),
        patch("audio_to_tab.isolate._trim_audio", side_effect=lambda p, _: p),
        patch("audio_to_tab.isolate.subprocess.run", side_effect=fake_run),
    ):
        artifacts = separate_stems(
            audio,
            out_dir,
            IsolateConfig(model="htdemucs_6s", dual_guitar=True, max_duration_sec=15),
        )

    assert "guitar" in artifacts
    assert "guitar1" in artifacts
    assert "guitar2" in artifacts
    g1 = artifacts["guitar1"].read_bytes()
    g2 = artifacts["guitar2"].read_bytes()
    assert g1 != g2
