"""Guitar-ft weight pin and BagOfModels remap (no network, no 330 MB checkpoint)."""

from __future__ import annotations

import hashlib
import os
import urllib.request
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from audio_to_tab.separate import (
    GUITAR_FT_SHA256,
    download_guitar_ft_weights,
    guitar_ft_weights_cached,
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
    fake_resp.read.side_effect = [good, b""]
    fake_resp.__enter__.return_value = fake_resp
    fake_resp.__exit__.return_value = False
    with patch("audio_to_tab.separate.urllib.request.urlopen", return_value=fake_resp):
        path = download_guitar_ft_weights()
    assert path.read_bytes() == good


def test_download_guitar_ft_weights_rejects_bad_download(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("TORCH_HOME", str(tmp_path))
    fake_resp = MagicMock()
    fake_resp.read.side_effect = [b"corrupt-checkpoint", b""]
    fake_resp.__enter__.return_value = fake_resp
    fake_resp.__exit__.return_value = False
    with patch("audio_to_tab.separate.urllib.request.urlopen", return_value=fake_resp):
        with pytest.raises(RuntimeError, match="hash mismatch"):
            download_guitar_ft_weights()
    assert not (tmp_path / "checkpoints" / "guitar_htdemucs_6s.pt").exists()


def test_download_guitar_ft_weights_sends_ua_and_streams(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("TORCH_HOME", str(tmp_path))
    good = b"chunked-good-checkpoint"
    digest = hashlib.sha256(good).hexdigest()
    monkeypatch.setattr("audio_to_tab.separate.GUITAR_FT_SHA256", digest)
    fake_resp = MagicMock()
    fake_resp.read.side_effect = [good[:5], good[5:], b""]
    fake_resp.__enter__.return_value = fake_resp
    fake_resp.__exit__.return_value = False
    with patch(
        "audio_to_tab.separate.urllib.request.urlopen", return_value=fake_resp
    ) as urlopen:
        path = download_guitar_ft_weights()
    req = urlopen.call_args.args[0]
    assert isinstance(req, urllib.request.Request)
    assert req.get_header("User-agent") == "audio-to-tab-pdf/1.0 (guitar isolation; urllib)"
    assert path.read_bytes() == good


def test_guitar_ft_weights_cached_uses_sidecar_digest(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("TORCH_HOME", str(tmp_path))
    cache = tmp_path / "checkpoints"
    cache.mkdir()
    blob = cache / "guitar_htdemucs_6s.pt"
    blob.write_bytes(b"sidecar-ok")
    digest = guitar_ft_weights_sha256(blob)
    monkeypatch.setattr("audio_to_tab.separate.GUITAR_FT_SHA256", digest)
    assert verify_guitar_ft_weights(blob) == blob
    sidecar = cache / "guitar_htdemucs_6s.pt.sha256"
    assert sidecar.read_text(encoding="utf-8").strip() == digest
    with patch("audio_to_tab.separate.guitar_ft_weights_sha256") as sha:
        assert guitar_ft_weights_cached() is True
    sha.assert_not_called()


def test_guitar_ft_weights_cached_rehashes_when_file_newer_than_sidecar(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setenv("TORCH_HOME", str(tmp_path))
    cache = tmp_path / "checkpoints"
    cache.mkdir()
    blob = cache / "guitar_htdemucs_6s.pt"
    blob.write_bytes(b"sidecar-stale")
    digest = guitar_ft_weights_sha256(blob)
    monkeypatch.setattr("audio_to_tab.separate.GUITAR_FT_SHA256", digest)
    assert verify_guitar_ft_weights(blob) == blob
    sidecar = cache / "guitar_htdemucs_6s.pt.sha256"
    future = sidecar.stat().st_mtime + 1000.0
    os.utime(blob, (future, future))
    with patch("audio_to_tab.separate.guitar_ft_weights_sha256", return_value=digest) as sha:
        assert guitar_ft_weights_cached() is True
    sha.assert_called_once()


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
