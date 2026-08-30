"""Opt-in SCNet guitar isolation backend (Phase 3): constants, load, dispatch."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

import audio_to_tab.scnet as scnet
from audio_to_tab import isolate, pipeline, separate

SR = 44100


def _tone_wav(path: Path, freq: float, amp: float = 0.2, seconds: float = 0.1) -> Path:
    t = np.arange(int(SR * seconds), dtype=np.float64) / SR
    y = (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(path), np.column_stack([y, y]), SR, subtype="PCM_16")
    return path


def test_scnet_constants():
    assert scnet.SCNET_MODEL_ID == "guitar_scnet"
    assert scnet.SCNET_MODELS == ("guitar_scnet",)
    # Checkpoint source order; guitar content lives in the "other" stem.
    assert scnet.SCNET_SOURCES == ("drums", "bass", "other", "vocals")
    assert scnet.SCNET_GUITAR_FROM_STEM == "other"
    assert scnet.SCNET_SAMPLE_RATE == 44100
    assert len(scnet.SCNET_CKPT_SHA256) == 64
    assert all(c in "0123456789abcdef" for c in scnet.SCNET_CKPT_SHA256)
    assert scnet.SCNET_CKPT_URL.endswith(f"/{scnet.SCNET_CKPT_NAME}")
    # MSST musdb18 inference settings.
    assert scnet.SCNET_CHUNK_SIZE == 44100 * 11
    assert scnet.SCNET_STEP == scnet.SCNET_CHUNK_SIZE // scnet.SCNET_NUM_OVERLAP
    assert scnet.SCNET_FADE_SIZE == scnet.SCNET_CHUNK_SIZE // 10


def test_scnet_module_has_no_top_level_torch():
    import sys

    assert not hasattr(scnet, "torch"), "scnet must not import torch at module top"
    assert "torch" not in sys.modules or not hasattr(
        sys.modules.get("audio_to_tab.scnet", None), "torch"
    )


def test_scnet_availability_follows_torch(monkeypatch):
    real_find_spec = importlib.util.find_spec

    def fake_find_spec(name, package=None):
        if name == "torch":
            return None
        return real_find_spec(name, package)

    monkeypatch.setattr(importlib.util, "find_spec", fake_find_spec)
    assert scnet.is_scnet_available() is False
    monkeypatch.undo()
    assert scnet.is_scnet_available() is True


def test_download_scnet_weights_pins_url_and_sha256(tmp_path, monkeypatch):
    recorded: dict[str, object] = {}

    def fake_download(url: str, dest: Path, sha256: str) -> None:
        recorded["url"] = url
        recorded["dest"] = dest
        recorded["sha256"] = sha256
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"fake")

    monkeypatch.setattr(scnet, "separator_cache_dir", lambda: tmp_path)
    monkeypatch.setattr(scnet, "download_sha256_file", fake_download)

    out = scnet.download_scnet_weights(force=True)
    assert out.name == scnet.SCNET_CKPT_NAME
    assert out.parent.name == scnet.SCNET_MODEL_ID
    assert recorded["url"] == scnet.SCNET_CKPT_URL
    assert recorded["sha256"] == scnet.SCNET_CKPT_SHA256
    assert recorded["dest"] == out


def test_msst_normalize_matches_msst_roundtrip():
    rng = np.random.default_rng(3)
    mix = (rng.standard_normal((2, 500)) * 0.3 - 0.2).astype(np.float32)
    normed, (mean, std) = scnet._msst_normalize(mix)
    assert mean == pytest.approx(float(mix.mean(0).mean()), abs=1e-6)
    assert std == pytest.approx(float(mix.mean(0).std()), abs=1e-6)
    assert np.isclose(normed.mean(), 0.0, atol=1e-6)
    # MSST normalizes each channel by the whole-track mono mean/std, so the
    # mono mix of the normalized signal is ~N(0,1).
    mono_normed = normed.mean(0)
    assert np.isclose(mono_normed.mean(), 0.0, atol=1e-6)
    assert np.isclose(mono_normed.std(), 1.0, atol=1e-6)
    restored = normed * std + mean
    assert np.allclose(restored, mix, atol=1e-5)


def test_msst_normalize_passthrough_when_silent():
    mix = np.zeros((2, 200), dtype=np.float32)
    normed, (mean, std) = scnet._msst_normalize(mix)
    assert mean == pytest.approx(0.0)
    assert std == pytest.approx(0.0)
    assert np.array_equal(normed, mix)


def test_scnet_architecture_output_shape():
    torch = pytest.importorskip("torch")
    model = scnet._scnet_architecture_module()
    model.eval()
    assert model.sources == list(scnet.SCNET_SOURCES)
    n_params = sum(p.numel() for p in model.parameters())
    assert 10_000_000 <= n_params <= 11_000_000
    x = torch.randn(1, 2, 44100)
    with torch.inference_mode():
        y = model(x)
    assert tuple(y.shape) == (1, 4, 2, 44100)
    assert bool(torch.isfinite(y).all())


def test_load_scnet_model_strict(tmp_path):
    torch = pytest.importorskip("torch")
    model = scnet._scnet_architecture_module()
    ckpt = tmp_path / "weights.ckpt"
    torch.save(model.state_dict(), str(ckpt))

    loaded = scnet.load_scnet_model(ckpt, "cpu")
    assert sum(p.numel() for p in loaded.parameters()) == sum(
        p.numel() for p in model.parameters()
    )
    assert loaded.training is False

    # Wrapper-dict checkpoints (state / state_dict / model_state_dict) work too.
    wrapped = tmp_path / "wrapped.ckpt"
    torch.save({"model_state_dict": model.state_dict()}, str(wrapped))
    scnet.load_scnet_model(wrapped, "cpu")

    # A corrupted key must fail loudly (strict load, no silent fallback).
    bad = model.state_dict()
    key = next(iter(bad))
    bad[key] = torch.zeros(bad[key].numel() - 1)
    broken = tmp_path / "broken.ckpt"
    torch.save(bad, str(broken))
    with pytest.raises(RuntimeError):
        scnet.load_scnet_model(broken, "cpu")


def test_run_scnet_model_writes_four_stems_and_no_other(tmp_path, monkeypatch):
    torch = pytest.importorskip("torch")

    class StubModel:
        def eval(self):
            return self

        def __call__(self, x):
            return torch.zeros(
                (x.shape[0], len(scnet.SCNET_SOURCES), 2, x.shape[2]),
                dtype=torch.float32,
            )

    wav = _tone_wav(tmp_path / "clip.wav", 220.0, seconds=0.3)
    monkeypatch.setattr(scnet, "is_scnet_available", lambda: True)
    monkeypatch.setattr(scnet, "download_scnet_weights", lambda: tmp_path / "stub.ckpt")
    monkeypatch.setattr(scnet, "load_scnet_model", lambda ckpt, dev: StubModel())

    stems = scnet.run_scnet_model(wav, tmp_path / "separation")
    assert set(stems) == {"drums", "bass", "guitar", "vocals"}

    track_dir = tmp_path / "separation" / scnet.SCNET_MODEL_ID / "clip"
    for name, path in stems.items():
        assert path == track_dir / f"{name}.wav"
        assert path.is_file()
        data, sr = sf.read(str(path), always_2d=True)
        assert sr == 44100
        assert data.shape == (int(0.3 * 44100), 2)
    assert not (track_dir / "other.wav").exists()


def test_isolate_registers_scnet_model():
    assert scnet.SCNET_MODEL_ID in isolate.SUPPORTED_MODELS
    assert scnet.SCNET_MODEL_ID not in isolate.DEMUCS_MODELS
    assert scnet.SCNET_MODEL_ID not in isolate.GUITAR_PRODUCING_MODELS


def test_isolate_config_scnet_constraints():
    cfg = isolate.IsolateConfig(
        model="guitar_scnet",
        two_pass=True,
        two_stems=False,
        guitar_refine=True,
        guitar_ensemble=True,
        fold_other_mode="best_effort",
    )
    assert cfg.model == "guitar_scnet"
    assert cfg.two_pass is False
    assert cfg.guitar_refine is False
    assert cfg.guitar_ensemble is False
    assert cfg.fold_other_mode == "best_effort"


def test_isolate_timeout_multiplier_scnet():
    assert isolate.isolate_timeout_multiplier(model="guitar_scnet") == 2
    # Raw multiplier does not know two_pass gets auto-disabled for non-default models.
    assert isolate.isolate_timeout_multiplier(model="guitar_scnet", two_pass=True) == 3


def test_separate_guitar_stem_scnet_requires_runtime(tmp_path, monkeypatch):
    wav = _tone_wav(tmp_path / "clip.wav", 200.0, seconds=0.1)
    # separate_guitar_stem re-imports is_scnet_available from scnet at call time.
    monkeypatch.setattr(scnet, "is_scnet_available", lambda: False)
    with pytest.raises(RuntimeError, match="SCNet"):
        separate.separate_guitar_stem(wav, tmp_path / "stem.wav", model="guitar_scnet")


def test_pipeline_progress_label_scnet():
    from audio_to_tab.pipeline import PipelineConfig

    cfg = PipelineConfig(model="guitar_scnet")
    assert pipeline._separate_progress_label(cfg) == "Isolating guitar stem with SCNet"