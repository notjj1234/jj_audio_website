"""Tests for best-effort OS notifications."""

from __future__ import annotations

from types import SimpleNamespace

from ui.desktop_notify import (
    escape_applescript,
    escape_powershell_single,
    notify,
)


def test_escape_applescript_quotes_and_backslashes():
    assert '\\"' in escape_applescript('He said "hi"')
    assert "\\\\" in escape_applescript("a\\b")
    assert "\n" not in escape_applescript("line1\nline2")


def test_escape_powershell_single_quotes():
    assert "''" in escape_powershell_single("It's done")
    assert "\n" not in escape_powershell_single("a\nb")


def test_notify_macos_uses_osascript_and_escapes(monkeypatch):
    seen: list[list[str]] = []

    def fake_run(cmd, **_kwargs):
        seen.append(list(cmd))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    assert notify(
        'Title "X"',
        'Body "Y"',
        platform="darwin",
        runner=fake_run,
    )
    assert seen[0][0] == "osascript"
    script = seen[0][2]
    assert "display notification" in script
    assert escape_applescript('Body "Y"') in script
    assert escape_applescript('Title "X"') in script


def test_notify_windows_uses_powershell_balloon():
    seen: list[list[str]] = []

    def fake_run(cmd, **_kwargs):
        seen.append(list(cmd))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    assert notify("It's ready", "Track 'A' done", platform="win32", runner=fake_run)
    assert seen[0][0] == "powershell"
    script = seen[0][-1]
    assert "ShowBalloonTip" in script
    assert "It's ready".replace("'", "''") in script
    assert "Track ''A'' done" in script


def test_notify_linux_uses_notify_send():
    seen: list[list[str]] = []

    def fake_run(cmd, **_kwargs):
        seen.append(list(cmd))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    assert notify("Audio Isolation", "Separated: Song", platform="linux", runner=fake_run)
    assert seen[0] == ["notify-send", "Audio Isolation", "Separated: Song"]


def test_notify_swallows_errors():
    def boom(*_a, **_k):
        raise OSError("no notifier")

    assert notify("t", "b", platform="darwin", runner=boom) is False
