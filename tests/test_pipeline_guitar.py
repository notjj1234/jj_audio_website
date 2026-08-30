"""Tab PDF guitar backend wiring: residual refine, config defaults, low-end restore."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from audio_to_tab.isolate import (
    IsolateConfig,
    apply_guitar_low_end_recovery,
    apply_low_end_restore,
    apply_sub_bass_debleed,
)
from audio_to_tab.pipeline import PipelineConfig
from audio_to_tab.roformer import collect_named_stems
from audio_to_tab.separate import (
    GUITAR_FT_CHECKPOINT_ID,
    guitar_ft_weights_cached,
    separate_guitar_stem,
)


def test_pipeline_config_quality_backend_defaults():
    cfg = PipelineConfig()
    assert cfg.model == "htdemucs_6s"
    assert cfg.guitar_checkpoint is None
    assert cfg.guitar_refine is False
    assert cfg.demucs_segment == 8
    assert cfg.demucs_jobs == 1
    assert cfg.fold_other_mode is None
    assert cfg.max_duration_sec is None
    assert cfg.low_end_restore_db == 0.0
    assert cfg.sub_bass_debleed is False
    assert cfg.bleed_gate is False
    assert cfg.adaptive_fold_gain is False
    assert cfg.guitar_ensemble is False


def test_isolate_config_sub_bass_debleed_defaults_off():
    assert IsolateConfig().sub_bass_debleed is False
    assert IsolateConfig().low_end_restore_db == 0.0


def test_pipeline_trim_zero_or_negative_is_noop(tmp_path):
    from audio_to_tab.pipeline import _trim_audio

    src = tmp_path / "in.wav"
    src.write_bytes(b"x")
    assert _trim_audio(src, None) == src
    assert _trim_audio(src, 0.0) == src
    assert _trim_audio(src, -1.0) == src


def test_pipeline_trim_raises_on_ffmpeg_failure(tmp_path, monkeypatch):
    from unittest.mock import MagicMock

    from audio_to_tab.pipeline import _trim_audio

    src = tmp_path / "in.wav"
    src.write_bytes(b"x")

    def boom(cmd, capture_output=True, check=False, **kw):
        Path(cmd[-1]).write_bytes(b"partial")
        return MagicMock(returncode=1, stderr="kaboom", stdout="")

    monkeypatch.setattr("audio_to_tab.pipeline.shutil.which", lambda _name: "/usr/bin/ffmpeg")
    monkeypatch.setattr("subprocess.run", boom)
    with pytest.raises(RuntimeError, match="ffmpeg trim failed"):
        _trim_audio(src, 30.0)


def test_isolate_config_clamps_low_end_restore_db():
    assert IsolateConfig(low_end_restore_db=99).low_end_restore_db == 12.0
    assert IsolateConfig(low_end_restore_db=-3).low_end_restore_db == 0.0


def test_collect_named_stems_filters_to_requested_names(tmp_path: Path):
    (tmp_path / "guitar.wav").write_bytes(b"g")
    (tmp_path / "other.wav").write_bytes(b"o")
    (tmp_path / "bass.wav").write_bytes(b"b")
    nested = tmp_path / "htdemucs_6s" / "track"
    nested.mkdir(parents=True)
    (nested / "vocals.wav").write_bytes(b"v")
    found = collect_named_stems(tmp_path, ("guitar", "other"))
    assert set(found) == {"guitar", "other"}
    assert found["guitar"].name == "guitar.wav"
    assert found["other"].name == "other.wav"


def _write_stems_from_demucs_args(args: list[str]) -> None:
    root = Path(args[args.index("-o") + 1])
    dest = root / "htdemucs_6s" / "track"
    dest.mkdir(parents=True)
    (dest / "guitar.wav").write_bytes(b"guitar-bytes")
    (dest / "other.wav").write_bytes(b"other-bytes")


def test_separate_guitar_stem_passes_residual_to_refine(tmp_path: Path, monkeypatch):
    audio = tmp_path / "mix.wav"
    audio.write_bytes(b"mix")
    out = tmp_path / "guitar_stem.wav"
    captured: dict[str, object] = {}

    def fake_refine(guitar_path, output_path, *, residual_path=None, device="cpu"):
        captured["residual_path"] = residual_path
        captured["residual_exists"] = bool(residual_path and Path(residual_path).is_file())
        captured["residual_bytes"] = (
            Path(residual_path).read_bytes() if captured["residual_exists"] else None
        )
        return output_path

    monkeypatch.setattr("audio_to_tab.separate.is_demucs_available", lambda: True)
    monkeypatch.setattr("audio_to_tab.separate.run_demucs", _write_stems_from_demucs_args)
    monkeypatch.setattr("audio_to_tab.roformer.is_guitar_refine_available", lambda: True)
    monkeypatch.setattr("audio_to_tab.roformer.run_guitar_refine", fake_refine)

    result = separate_guitar_stem(audio, out, guitar_refine=True)
    assert result == out
    assert out.read_bytes() == b"guitar-bytes"
    assert captured["residual_exists"] is True
    assert captured["residual_bytes"] == b"other-bytes"


def test_separate_guitar_stem_ensemble_blends_when_requested(tmp_path: Path, monkeypatch):
    audio = tmp_path / "mix.wav"
    audio.write_bytes(b"mix")
    out = tmp_path / "guitar_stem.wav"
    captured: dict[str, object] = {}

    def fake_roformer(src, dest_dir, *, model, device="cpu"):
        (dest_dir / "guitar.wav").write_bytes(b"roformer-guitar")

    def fake_blend(primary, secondary, output_path):
        captured["primary"] = primary
        captured["secondary"] = secondary
        Path(output_path).write_bytes(Path(secondary).read_bytes())
        from audio_to_tab.isolate import EnsembleGuitarDiagnostics

        return EnsembleGuitarDiagnostics(
            attempted=True, reason=f"blended {secondary}", blended=True
        )

    monkeypatch.setattr("audio_to_tab.separate.is_demucs_available", lambda: True)
    monkeypatch.setattr("audio_to_tab.separate.run_demucs", _write_stems_from_demucs_args)
    monkeypatch.setattr("audio_to_tab.roformer.is_roformer_backend_available", lambda: True)
    monkeypatch.setattr("audio_to_tab.roformer.run_roformer_model", fake_roformer)
    monkeypatch.setattr("audio_to_tab.isolate.blend_guitar_stems", fake_blend)

    result = separate_guitar_stem(
        audio,
        out,
        model="htdemucs_6s",
        guitar_ensemble=True,
    )
    assert result == out
    assert out.read_bytes() == b"roformer-guitar"
    assert captured["secondary"].name == "guitar.wav"


def test_separate_guitar_stem_folds_other_into_guitar(tmp_path: Path, monkeypatch):
    audio = tmp_path / "mix.wav"
    audio.write_bytes(b"mix")
    out = tmp_path / "guitar_stem.wav"
    captured: dict[str, object] = {}

    def fake_fold(artifacts, *, mode, adaptive_gain=False):
        captured["guitar"] = Path(artifacts["guitar"])
        captured["other"] = Path(artifacts["other"]).read_bytes()
        captured["mode"] = mode
        captured["adaptive_gain"] = adaptive_gain
        return artifacts, None

    monkeypatch.setattr("audio_to_tab.separate.is_demucs_available", lambda: True)
    monkeypatch.setattr("audio_to_tab.separate.run_demucs", _write_stems_from_demucs_args)
    monkeypatch.setattr("audio_to_tab.isolate.apply_fold_other_into_guitar", fake_fold)

    result = separate_guitar_stem(audio, out, fold_other_mode="band_limited")
    assert result == out
    assert out.read_bytes() == b"guitar-bytes"
    assert captured["mode"] == "band_limited"
    assert captured["guitar"] == out
    assert captured["other"] == b"other-bytes"


def test_separate_guitar_stem_rejects_unknown_fold_mode(tmp_path: Path, monkeypatch):
    audio = tmp_path / "mix.wav"
    audio.write_bytes(b"mix")
    out = tmp_path / "guitar_stem.wav"
    monkeypatch.setattr("audio_to_tab.separate.is_demucs_available", lambda: True)

    with pytest.raises(ValueError, match="fold_other_mode"):
        separate_guitar_stem(audio, out, fold_other_mode="bogus")


def test_separate_guitar_stem_raises_when_guitar_ft_uncached(tmp_path: Path, monkeypatch):
    audio = tmp_path / "mix.wav"
    audio.write_bytes(b"mix")
    out = tmp_path / "guitar_stem.wav"
    called = {"ft": False, "cli": False}

    def fake_ft(*_args, **_kwargs):
        called["ft"] = True

    def fake_cli(args):
        called["cli"] = True
        _write_stems_from_demucs_args(args)

    monkeypatch.setattr("audio_to_tab.separate.is_demucs_available", lambda: True)
    monkeypatch.setattr("audio_to_tab.separate.guitar_ft_weights_cached", lambda: False)
    monkeypatch.setattr("audio_to_tab.separate.run_demucs_guitar_ft_inprocess", fake_ft)
    monkeypatch.setattr("audio_to_tab.separate.run_demucs", fake_cli)

    with pytest.raises(RuntimeError, match="not falling back to stock"):
        separate_guitar_stem(audio, out, guitar_checkpoint=GUITAR_FT_CHECKPOINT_ID)
    assert called["ft"] is False
    assert called["cli"] is False


def test_separate_guitar_stem_uses_guitar_ft_when_cached(tmp_path: Path, monkeypatch):
    audio = tmp_path / "mix.wav"
    audio.write_bytes(b"mix")
    out = tmp_path / "guitar_stem.wav"
    called = {"cli": False}

    def fake_ft(_audio, root, **_kwargs):
        dest = Path(root) / "htdemucs_6s" / "track"
        dest.mkdir(parents=True)
        (dest / "guitar.wav").write_bytes(b"ft-guitar")
        (dest / "other.wav").write_bytes(b"ft-other")

    def fake_cli(_args):
        called["cli"] = True

    monkeypatch.setattr("audio_to_tab.separate.is_demucs_available", lambda: True)
    monkeypatch.setattr("audio_to_tab.separate.guitar_ft_weights_cached", lambda: True)
    monkeypatch.setattr("audio_to_tab.separate.run_demucs_guitar_ft_inprocess", fake_ft)
    monkeypatch.setattr("audio_to_tab.separate.run_demucs", fake_cli)

    separate_guitar_stem(audio, out, guitar_checkpoint=GUITAR_FT_CHECKPOINT_ID)
    assert called["cli"] is False
    assert out.read_bytes() == b"ft-guitar"


def test_separate_guitar_stem_roformer_raises_without_backend(tmp_path: Path, monkeypatch):
    audio = tmp_path / "mix.wav"
    audio.write_bytes(b"mix")
    out = tmp_path / "guitar_stem.wav"
    called = {"roformer": False, "cli": False}

    def fake_roformer(*_args, **_kwargs):
        called["roformer"] = True

    def fake_cli(args):
        called["cli"] = True
        _write_stems_from_demucs_args(args)

    monkeypatch.setattr("audio_to_tab.roformer.is_roformer_backend_available", lambda: False)
    monkeypatch.setattr("audio_to_tab.roformer.run_roformer_model", fake_roformer)
    monkeypatch.setattr("audio_to_tab.separate.is_demucs_available", lambda: True)
    monkeypatch.setattr("audio_to_tab.separate.run_demucs", fake_cli)

    with pytest.raises(RuntimeError, match="RoFormer backend"):
        separate_guitar_stem(audio, out, model="bs_roformer_sw")
    assert called["roformer"] is False
    assert called["cli"] is False


def test_guitar_ft_weights_cached_false_when_missing(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("TORCH_HOME", str(tmp_path))
    assert guitar_ft_weights_cached() is False


def test_guitar_ft_weights_cached_true_when_hash_matches(tmp_path: Path, monkeypatch):
    from audio_to_tab.separate import guitar_ft_weights_sha256

    monkeypatch.setenv("TORCH_HOME", str(tmp_path))
    cache = tmp_path / "checkpoints"
    cache.mkdir()
    blob = cache / "guitar_htdemucs_6s.pt"
    blob.write_bytes(b"cached-ok")
    digest = guitar_ft_weights_sha256(blob)
    monkeypatch.setattr("audio_to_tab.separate.GUITAR_FT_SHA256", digest)
    assert guitar_ft_weights_cached() is True


def _write_tone(path: Path, hz: float, sr: int = 22050, seconds: float = 0.4) -> None:
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    y = (0.25 * np.sin(2 * np.pi * hz * t)).astype(np.float32)
    sf.write(str(path), y, sr)


def test_apply_low_end_restore_zero_db_is_noop(tmp_path: Path):
    wav = tmp_path / "guitar.wav"
    _write_tone(wav, 82.0)
    before = wav.read_bytes()
    diag = apply_low_end_restore(wav, boost_db=0.0)
    assert diag.attempted is False
    assert wav.read_bytes() == before
    assert diag.pre_low_band_energy_share is None


def test_apply_low_end_restore_boost_raises_low_band_share(tmp_path: Path):
    wav = tmp_path / "guitar.wav"
    # Mix a low-E fundamental with a high tone so the 60–200 Hz band is not already 100%.
    sr = 22050
    seconds = 0.5
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    y = (
        0.08 * np.sin(2 * np.pi * 82.0 * t) + 0.25 * np.sin(2 * np.pi * 2000.0 * t)
    ).astype(np.float32)
    sf.write(str(wav), y, sr)
    off = apply_low_end_restore(wav, tmp_path / "copy.wav", boost_db=0.0)
    boosted = apply_low_end_restore(wav, tmp_path / "boosted.wav", boost_db=6.0)
    assert boosted.attempted is True
    assert boosted.post_low_band_energy_share is not None
    assert boosted.pre_low_band_energy_share is not None
    assert boosted.post_low_band_energy_share > boosted.pre_low_band_energy_share
    assert off.attempted is False


def test_apply_sub_bass_debleed_reduces_low_band_share(tmp_path: Path):
    sr = 22050
    seconds = 0.5
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    guitar_tone = 0.15 * np.sin(2 * np.pi * 82.0 * t) + 0.2 * np.sin(2 * np.pi * 2000.0 * t)
    bass_tone = 0.4 * np.sin(2 * np.pi * 55.0 * t)
    bled = (guitar_tone + 0.6 * bass_tone).astype(np.float32)
    bass_only = bass_tone.astype(np.float32)
    guitar_wav = tmp_path / "guitar.wav"
    bass_wav = tmp_path / "bass.wav"
    out_wav = tmp_path / "debled.wav"
    sf.write(str(guitar_wav), bled, sr)
    sf.write(str(bass_wav), bass_only, sr)

    _, pre, post, removed = apply_sub_bass_debleed(guitar_wav, out_wav, bass_wav)
    assert pre is not None and post is not None and removed is not None
    assert post < pre
    assert removed > 0.0


def test_apply_guitar_low_end_recovery_default_off(tmp_path: Path):
    wav = tmp_path / "guitar.wav"
    _write_tone(wav, 82.0)
    diag = apply_guitar_low_end_recovery(wav)
    assert diag.attempted is False
    assert diag.sub_bass_debleed_applied is False
    assert diag.harmonic_restore_applied is False


def test_apply_guitar_low_end_recovery_debleed_writes_diagnostics(tmp_path: Path):
    sr = 22050
    seconds = 0.5
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    guitar_tone = 0.15 * np.sin(2 * np.pi * 82.0 * t) + 0.2 * np.sin(2 * np.pi * 2000.0 * t)
    bass_tone = 0.4 * np.sin(2 * np.pi * 55.0 * t)
    bled = (guitar_tone + 0.6 * bass_tone).astype(np.float32)
    bass_only = bass_tone.astype(np.float32)
    guitar_wav = tmp_path / "guitar.wav"
    bass_wav = tmp_path / "bass.wav"
    sf.write(str(guitar_wav), bled, sr)
    sf.write(str(bass_wav), bass_only, sr)

    diag = apply_guitar_low_end_recovery(
        guitar_wav,
        guitar_wav,
        bass_path=bass_wav,
        sub_bass_debleed=True,
    )
    assert diag.attempted is True
    assert diag.sub_bass_debleed_applied is True
    assert diag.pre_low_band_energy_share is not None
    assert diag.post_low_band_energy_share is not None
    assert diag.post_low_band_energy_share < diag.pre_low_band_energy_share


def test_separate_guitar_stem_applies_sub_bass_debleed(tmp_path: Path, monkeypatch):
    audio = tmp_path / "mix.wav"
    audio.write_bytes(b"mix")
    out = tmp_path / "guitar_stem.wav"
    diag_path = tmp_path / "recovery.json"

    def _write_stems_with_bass(args: list[str]) -> None:
        root = Path(args[args.index("-o") + 1])
        dest = root / "htdemucs_6s" / "track"
        dest.mkdir(parents=True)
        sr = 22050
        t = np.linspace(0, 0.2, int(sr * 0.2), endpoint=False)
        guitar = (0.2 * np.sin(2 * np.pi * 82.0 * t)).astype(np.float32)
        bass = (0.5 * np.sin(2 * np.pi * 55.0 * t)).astype(np.float32)
        sf.write(str(dest / "guitar.wav"), guitar + 0.5 * bass, sr)
        sf.write(str(dest / "bass.wav"), bass, sr)
        sf.write(str(dest / "other.wav"), np.zeros_like(guitar), sr)

    monkeypatch.setattr("audio_to_tab.separate.is_demucs_available", lambda: True)
    monkeypatch.setattr("audio_to_tab.separate.run_demucs", _write_stems_with_bass)

    separate_guitar_stem(
        audio,
        out,
        sub_bass_debleed=True,
        recovery_diagnostics_path=diag_path,
    )
    assert out.is_file()
    assert diag_path.is_file()
    data = json.loads(diag_path.read_text(encoding="utf-8"))
    assert data["attempted"] is True
    assert data["sub_bass_debleed_applied"] is True
