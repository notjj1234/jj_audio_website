"""CPU vs NVIDIA CUDA desktop edition helpers."""

from __future__ import annotations

from pathlib import Path

from audio_to_tab.edition import (
    CPU_APPID,
    CUDA_APPID,
    desktop_edition,
    edition_app_name,
    edition_display_label,
    edition_window_title,
    normalize_edition,
    read_edition_file,
)


def test_normalize_edition_defaults_to_cpu():
    assert normalize_edition(None) == "cpu"
    assert normalize_edition("") == "cpu"
    assert normalize_edition("CPU") == "cpu"
    assert normalize_edition("cuda") == "cuda"
    assert normalize_edition("NVIDIA") == "cuda"
    assert normalize_edition("gpu") == "cuda"


def test_desktop_edition_env(monkeypatch):
    monkeypatch.delenv("AUDIO_TOOLS_EDITION", raising=False)
    assert desktop_edition(frozen=False) == "cpu"
    monkeypatch.setenv("AUDIO_TOOLS_EDITION", "cuda")
    assert desktop_edition(frozen=False) == "cuda"


def test_desktop_edition_reads_bundle_file(tmp_path, monkeypatch):
    monkeypatch.delenv("AUDIO_TOOLS_EDITION", raising=False)
    packaging = tmp_path / "packaging"
    packaging.mkdir()
    (packaging / "edition.txt").write_text("cuda\n", encoding="utf-8")
    assert read_edition_file(tmp_path) == "cuda"
    assert desktop_edition(bundle=tmp_path, frozen=True) == "cuda"


def test_edition_identities_split_on_windows():
    assert edition_app_name("cpu", platform="win32") == "AudioTools"
    assert edition_app_name("cuda", platform="win32") == "AudioToolsNVIDIA"
    assert edition_app_name("cuda", platform="darwin") == "AudioTools"
    assert edition_window_title("cpu") == "Audio Tools (CPU)"
    assert edition_window_title("cuda") == "Audio Tools (NVIDIA)"
    assert edition_display_label("cpu") == "CPU"
    assert edition_display_label("cuda") == "NVIDIA CUDA"


def test_appids_are_distinct():
    assert CPU_APPID == "{A7C3E8F1-4B2D-4E9A-9C1F-8D6B5A2E0F73}"
    assert CUDA_APPID == "{C4E91A2B-7D83-4F16-9B50-2A8E6C3D1F47}"
    assert CPU_APPID != CUDA_APPID
    iss = (Path(__file__).resolve().parents[1] / "packaging" / "AudioTools.iss").read_text(
        encoding="utf-8"
    )
    assert CPU_APPID.strip("{}") in iss
    assert CUDA_APPID.strip("{}") in iss
