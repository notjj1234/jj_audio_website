"""Tests for isolate media helpers (preview / cleanup)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import soundfile as sf

from ui.media import (
    PREVIEW_SAMPLE_RATE,
    cleanup_mix_artifacts,
    ensure_mixer_audio_paths,
    ensure_region_preview_wav,
    region_preview_cache_key,
    register_mixer_media,
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


def test_mixer_preview_rate_is_full_quality():
    assert PREVIEW_SAMPLE_RATE == 44100


def test_register_mixer_media_registers_both_url_sets(monkeypatch):
    from pathlib import Path

    calls: list[str] = []

    def fake_urls(paths, *, coord_prefix="isolate.mixer"):
        calls.append(coord_prefix)
        return {name: f"/media/{coord_prefix}/{name}" for name in paths}

    monkeypatch.setattr("ui.media.stem_media_urls", fake_urls)
    playback, downloads = register_mixer_media({"vocals": Path("v.wav")})
    assert playback == {"vocals": "/media/isolate.mixer/vocals"}
    assert downloads == {"vocals": "/media/isolate.download/vocals"}
    assert calls == ["isolate.mixer", "isolate.download"]


def test_ensure_mixer_audio_paths_long_uses_original(tmp_path: Path):
    p = tmp_path / "vocals.wav"
    _write_tone(p, 200.0)
    out = ensure_mixer_audio_paths({"vocals": p})
    assert out["vocals"] == p
    assert not (tmp_path / "preview").exists()


def test_ensure_mixer_audio_paths_short_uses_original(tmp_path: Path):
    p = tmp_path / "vocals.wav"
    _write_tone(p, 2.0)
    out = ensure_mixer_audio_paths({"vocals": p})
    assert out["vocals"] == p


def test_region_preview_cache_key_includes_start_and_end():
    full = region_preview_cache_key("fpabc", 0.0, None)
    clip = region_preview_cache_key("fpabc", 10.0, 30.0)
    other = region_preview_cache_key("fpabc", 12.0, 30.0)
    assert full != clip
    assert clip != other
    assert "10" in clip or "10.0" in clip


def test_ensure_region_preview_wav_full_file_returns_source(tmp_path: Path):
    src = tmp_path / "song.wav"
    src.write_bytes(b"wav")
    out = ensure_region_preview_wav(
        src,
        start_sec=0.0,
        length_sec=None,
        fingerprint="fp1",
        cache_dir=tmp_path / "cache",
    )
    assert out == src


def test_ensure_region_preview_wav_trim_uses_ss_before_input(tmp_path: Path):
    src = tmp_path / "song.wav"
    src.write_bytes(b"wav")
    cache = tmp_path / "cache"
    seen: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        seen.append(list(cmd))
        Path(cmd[-1]).write_bytes(b"trimmed")
        return MagicMock(returncode=0)

    with patch("ui.media.shutil.which", return_value="/usr/bin/ffmpeg"), patch(
        "ui.media.subprocess.run", side_effect=fake_run
    ):
        out = ensure_region_preview_wav(
            src,
            start_sec=10.0,
            length_sec=30.0,
            fingerprint="fp1",
            cache_dir=cache,
        )

    assert out.exists()
    assert out != src
    cmd = seen[0]
    ss_idx = cmd.index("-ss")
    i_idx = cmd.index("-i")
    t_idx = cmd.index("-t")
    assert ss_idx < i_idx < t_idx
    assert cmd[ss_idx + 1] == "10.0"
    assert cmd[t_idx + 1] == "30.0"
