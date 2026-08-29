"""Guitar-ft weight pin and BagOfModels remap (no network, no 330 MB checkpoint)."""

from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from audio_to_tab.separate import (
    GUITAR_FT_SHA256,
    download_guitar_ft_weights,
    guitar_ft_weights_sha256,
    remap_guitar_ft_state_dict,
    verify_guitar_ft_weights,
)


def test_remap_guitar_ft_state_dict_prefixes_inner_keys():
    inner = {
        "encoder.weight": 1,
        "decoder.bias": 2,
        "lstm.weight": 3,
    }
    wrapper = {f"models.0.{key}" for key in inner}
    remapped = remap_guitar_ft_state_dict(inner, wrapper)
    assert remapped == {
        "models.0.encoder.weight": 1,
        "models.0.decoder.bias": 2,
        "models.0.lstm.weight": 3,
    }


def test_remap_guitar_ft_state_dict_keeps_already_wrapped_keys():
    wrapped = {
        "models.0.encoder.weight": 1,
        "models.0.decoder.bias": 2,
        "models.0.lstm.weight": 3,
    }
    wrapper = set(wrapped)
    assert remap_guitar_ft_state_dict(wrapped, wrapper) == wrapped


def test_remap_guitar_ft_state_dict_empty_passthrough():
    assert remap_guitar_ft_state_dict({}, {"models.0.x": True}) == {}


def test_verify_guitar_ft_weights_accepts_pinned_hash(tmp_path: Path, monkeypatch):
    blob = tmp_path / "guitar_htdemucs_6s.pt"
    blob.write_bytes(b"fake-guitar-ft-bytes")
    digest = guitar_ft_weights_sha256(blob)
    monkeypatch.setattr("audio_to_tab.separate.GUITAR_FT_SHA256", digest)
    assert verify_guitar_ft_weights(blob) == blob
    assert blob.exists()


def test_verify_guitar_ft_weights_deletes_on_hash_mismatch(tmp_path: Path):
    blob = tmp_path / "guitar_htdemucs_6s.pt"
    blob.write_bytes(b"not-the-real-checkpoint")
    with pytest.raises(RuntimeError, match="hash mismatch"):
        verify_guitar_ft_weights(blob)
    assert not blob.exists()


def test_download_guitar_ft_weights_uses_valid_cache(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("TORCH_HOME", str(tmp_path))
    cache = tmp_path / "checkpoints"
    cache.mkdir()
    blob = cache / "guitar_htdemucs_6s.pt"
    blob.write_bytes(b"cached-ok")
    digest = guitar_ft_weights_sha256(blob)
    monkeypatch.setattr("audio_to_tab.separate.GUITAR_FT_SHA256", digest)
    with patch("audio_to_tab.separate.urllib.request.urlopen") as urlopen:
        path = download_guitar_ft_weights()
    urlopen.assert_not_called()
    assert path == blob


def test_download_guitar_ft_weights_redownloads_corrupt_cache(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("TORCH_HOME", str(tmp_path))
    cache = tmp_path / "checkpoints"
    cache.mkdir()
    blob = cache / "guitar_htdemucs_6s.pt"
    blob.write_bytes(b"corrupt-cache")
    good = b"repaired-checkpoint"
    digest = hashlib.sha256(good).hexdigest()
    monkeypatch.setattr("audio_to_tab.separate.GUITAR_FT_SHA256", digest)
    fake_resp = MagicMock()
    fake_resp.read.return_value = good
    fake_resp.__enter__.return_value = fake_resp
    fake_resp.__exit__.return_value = False
    with patch("audio_to_tab.separate.urllib.request.urlopen", return_value=fake_resp):
        path = download_guitar_ft_weights()
    assert path.read_bytes() == good


def test_download_guitar_ft_weights_rejects_bad_download(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("TORCH_HOME", str(tmp_path))
    fake_resp = MagicMock()
    fake_resp.read.return_value = b"corrupt-checkpoint"
    fake_resp.__enter__.return_value = fake_resp
    fake_resp.__exit__.return_value = False
    with patch("audio_to_tab.separate.urllib.request.urlopen", return_value=fake_resp):
        with pytest.raises(RuntimeError, match="hash mismatch"):
            download_guitar_ft_weights()
    assert not (tmp_path / "checkpoints" / "guitar_htdemucs_6s.pt").exists()


def test_pinned_sha256_matches_huggingface_blob():
    assert GUITAR_FT_SHA256 == "4fde369e41582ba5c2759b6ab926a44af467c64d4566bf914374ab267b19260e"


def test_guitar_ft_stays_opt_in_until_listen_pass():
    page = Path(__file__).resolve().parents[1] / "ui" / "pages" / "isolate.py"
    source = page.read_text(encoding="utf-8")
    assert 'key="isolate_guitar_ft"' in source
    assert "Use guitar-focused Demucs weights (experimental)" in source
    assert "scientific/research" in source
    assert "~330 MB" in source
    # Invert this checkbox only after eval/lead_rhythm 3-clip listen beats stock.
    assert "Use stock Meta 6s weights" not in source
    assert 'key="isolate_two_pass"' in source
    assert "Two-pass guitar isolation (experimental)" in source
