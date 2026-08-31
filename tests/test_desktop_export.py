"""Tests for desktop save-to-folder / open-folder helpers."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from ui.desktop_export import (
    EXPORT_FORMATS,
    choose_export_dir,
    convert_audio,
    copy_mix_to_folder,
    copy_tracks_to_folder,
    default_export_dir,
    export_mix_to_folder,
    export_song_dir,
    export_tracks_to_folder,
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


def _is_windows() -> bool:
    import sys

    return sys.platform.startswith("win")


def test_convert_audio_wav_passthrough_copies(tmp_path: Path):
    src = tmp_path / "in.wav"
    src.write_bytes(b"wavdata")
    dest = tmp_path / "out.wav"
    convert_audio(src, dest, "wav")
    assert dest.read_bytes() == b"wavdata"


def test_convert_audio_mp3_uses_libmp3lame(tmp_path: Path, monkeypatch):
    calls: list[list[str]] = []
    src = tmp_path / "in.wav"
    src.write_bytes(b"x")
    dest = tmp_path / "out.mp3"

    class FakeWhich:
        @staticmethod
        def which(name, *a, **k):
            return str(tmp_path / "ffmpeg") if name == "ffmpeg" else None

    fake = tmp_path / ("ffmpeg.exe" if _is_windows() else "ffmpeg")
    fake.write_text(":", encoding="utf-8")
    monkeypatch.setattr("ui.desktop_export.shutil.which", FakeWhich.which)

    def fake_run(cmd, **_k):
        calls.append(list(cmd))
        # Simulate ffmpeg producing the output file
        dest = tmp_path / "out.mp3"
        dest.write_bytes(b"mp3")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("ui.desktop_export.subprocess.run", fake_run)

    out = convert_audio(src, dest, "mp3")
    assert out == dest
    assert calls, "ffmpeg should be invoked for mp3"
    assert "libmp3lame" in calls[0]
    assert "-b:a" in calls[0] and "192k" in calls[0]


def test_export_tracks_to_folder_uses_format_extension(tmp_path: Path, monkeypatch):
    vocals = tmp_path / "vocals.wav"
    vocals.write_bytes(b"v")
    dest = tmp_path / "out"
    # wav passthrough path — no ffmpeg needed
    out = export_tracks_to_folder({"vocals": vocals}, dest, "Song", "wav")
    assert (out / "Song_vocals.wav").read_bytes() == b"v"


def test_export_tracks_to_folder_mp3_extension(tmp_path: Path, monkeypatch):
    vocals = tmp_path / "vocals.wav"
    vocals.write_bytes(b"v")
    dest = tmp_path / "out"
    fake = tmp_path / ("ffmpeg.exe" if _is_windows() else "ffmpeg")
    fake.write_text(":", encoding="utf-8")
    monkeypatch.setattr(
        "ui.desktop_export.shutil.which", lambda name, *a, **k: str(fake) if name == "ffmpeg" else None
    )

    def fake_run(cmd, **_k):
        # Simulate ffmpeg writing the requested output file
        for arg in cmd:
            if arg.endswith(".mp3"):
                path = Path(arg)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"mp3")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("ui.desktop_export.subprocess.run", fake_run)

    out = export_tracks_to_folder({"vocals": vocals}, dest, "Song", "mp3")
    assert (out / "Song_vocals.mp3").is_file()


def test_export_mix_to_folder_wav(tmp_path: Path):
    mix = tmp_path / "mix.wav"
    mix.write_bytes(b"mix")
    dest = export_mix_to_folder(mix, tmp_path / "out", "Song_current_mix.wav", "wav")
    assert dest.name.endswith(".wav")
    assert dest.read_bytes() == b"mix"


def test_export_formats_include_expected_set():
    for fmt in ("wav", "mp3", "flac", "ogg", "opus", "m4a"):
        assert fmt in EXPORT_FORMATS
