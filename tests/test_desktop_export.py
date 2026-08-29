"""Tests for desktop save-to-folder / open-folder helpers."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from ui.desktop_export import (
    choose_export_dir,
    copy_mix_to_folder,
    copy_tracks_to_folder,
    default_export_dir,
    export_song_dir,
    open_path_in_os,
    sanitize_export_name,
)


def test_sanitize_export_name_strips_unsafe_chars():
    assert "/" not in sanitize_export_name("a/b:c*")
    assert sanitize_export_name("") == "stems"


def test_copy_tracks_to_folder(tmp_path: Path):
    vocals = tmp_path / "vocals.wav"
    drums = tmp_path / "drums.wav"
    vocals.write_bytes(b"v")
    drums.write_bytes(b"d")
    dest = export_song_dir(tmp_path / "Downloads", "Party Song")
    out = copy_tracks_to_folder({"vocals": vocals, "drums": drums}, dest, "Party Song")
    assert (out / "Party Song_vocals.wav").read_bytes() == b"v"
    assert (out / "Party Song_drums.wav").read_bytes() == b"d"


def test_copy_mix_to_folder(tmp_path: Path):
    mix = tmp_path / "current_mix.wav"
    mix.write_bytes(b"mix")
    dest = copy_mix_to_folder(mix, tmp_path / "out", "Song_current_mix.wav")
    assert dest.is_file()
    assert dest.read_bytes() == b"mix"


def test_open_path_in_os_uses_open_on_macos(tmp_path: Path, monkeypatch):
    folder = tmp_path / "exports"
    folder.mkdir()
    seen: list[list[str]] = []

    def fake_run(cmd, **_kwargs):
        seen.append(list(cmd))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    assert open_path_in_os(folder, platform="darwin", runner=fake_run) is True
    assert seen[0][:2] == ["open", str(folder)]


def test_open_path_in_os_missing_returns_false(tmp_path: Path):
    assert open_path_in_os(tmp_path / "nope", platform="darwin", runner=lambda *_a, **_k: None) is False


def test_choose_export_dir_parses_osascript(tmp_path: Path):
    picked = tmp_path / "chosen"
    picked.mkdir()

    def fake_run(cmd, **_kwargs):
        assert cmd[0] == "osascript"
        return SimpleNamespace(returncode=0, stdout=str(picked) + "/\n", stderr="")

    out = choose_export_dir(platform="darwin", runner=fake_run)
    assert out == picked


def test_choose_export_dir_cancel_returns_none():
    def fake_run(_cmd, **_kwargs):
        return SimpleNamespace(returncode=1, stdout="", stderr="User canceled.")

    assert choose_export_dir(platform="darwin", runner=fake_run) is None


def test_default_export_dir_is_home_or_downloads():
    dest = default_export_dir()
    assert dest == Path.home() / "Downloads" or dest == Path.home()
