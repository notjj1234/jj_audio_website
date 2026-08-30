"""Tests for desktop/local packaging helpers (no PyInstaller run)."""

from __future__ import annotations

import importlib.util
import os
import sys
import threading
import time
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import ui.common as common
from audio_to_tab.separate import run_demucs


def test_resolve_data_dir_default(monkeypatch):
    monkeypatch.delenv("AUDIO_TOOLS_DATA_DIR", raising=False)
    resolved = common._resolve_data_dir()
    assert resolved.name == "ui_runs"
    assert resolved.parent.name == "data"


def test_resolve_data_dir_override(tmp_path, monkeypatch):
    target = tmp_path / "custom_runs"
    monkeypatch.setenv("AUDIO_TOOLS_DATA_DIR", str(target))
    assert common._resolve_data_dir() == target.resolve()


def test_audio_upload_types_include_audio_shortcut_and_extensions():
    types = common.AUDIO_UPLOAD_TYPES
    assert "audio" in types
    assert ".mp3" in types
    assert ".wav" in types
    assert ".flac" in types
    assert ".m4a" in types
    assert any(t.startswith("audio/") for t in types)


def test_run_demucs_subprocess_when_not_frozen(monkeypatch):
    if hasattr(sys, "frozen"):
        monkeypatch.delattr(sys, "frozen")
    seen: list[list[str]] = []

    def fake_run(cmd, capture_output=True, text=True, **_kwargs):
        seen.append(list(cmd))
        return MagicMock(returncode=0, stderr="", stdout="")

    with patch("audio_to_tab.separate.run_process", side_effect=fake_run):
        run_demucs(["-n", "htdemucs_6s", "-d", "cpu", "song.wav"])

    assert len(seen) == 1
    assert "-m" in seen[0] and "demucs" in seen[0]
    assert "htdemucs_6s" in seen[0]


def test_run_demucs_inprocess_when_frozen(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    called: list[list[str]] = []

    def fake_main(opts=None):
        called.append(list(opts or []))

    with patch("demucs.separate.main", side_effect=fake_main):
        with patch("audio_to_tab.separate.run_process") as sub_run:
            run_demucs(["-n", "htdemucs_6s", "-d", "cpu", "song.wav"])
            sub_run.assert_not_called()

    assert called == [["-n", "htdemucs_6s", "-d", "cpu", "song.wav"]]


def test_run_demucs_frozen_nonzero_exit(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    def boom(opts=None):
        raise SystemExit(2)

    with patch("demucs.separate.main", side_effect=boom):
        with pytest.raises(RuntimeError, match="exit code 2"):
            run_demucs(["-n", "htdemucs_6s", "song.wav"])


def test_safe_upload_name_strips_path_components():
    assert common._safe_upload_name("../../evil.wav") == "evil.wav"
    assert common._safe_upload_name("ok song.mp3") == "ok song.mp3"
    with pytest.raises(ValueError):
        common._safe_upload_name("..")
    with pytest.raises(ValueError):
        common._safe_upload_name("")


def test_save_upload_stays_inside_run_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "DATA_DIR", tmp_path)

    class FakeUpload:
        name = "../../evil.wav"

        def getvalue(self) -> bytes:
            return b"RIFF"

    dest = common.save_upload(FakeUpload())
    assert dest.name == "evil.wav"
    assert dest.parent.parent == tmp_path.resolve()
    assert dest.read_bytes() == b"RIFF"


def test_youtube_url_allowlist():
    from audio_to_tab.ingest import is_youtube_url

    assert is_youtube_url("https://www.youtube.com/watch?v=abc")
    assert is_youtube_url("https://youtu.be/abc")
    assert not is_youtube_url("https://example.com/watch?v=abc")
    assert not is_youtube_url("https://youtube.com.evil.test/watch")
    assert not is_youtube_url("file:///tmp/x")


def test_download_youtube_rejects_non_youtube(tmp_path):
    from audio_to_tab.ingest import download_youtube_audio

    with pytest.raises(ValueError, match="Only YouTube"):
        download_youtube_audio("https://example.com/a.wav", tmp_path)


def test_transcribe_does_not_import_basic_pitch_at_module_level():
    import importlib
    import sys as _sys

    saved = {k: _sys.modules[k] for k in list(_sys.modules) if k.startswith("basic_pitch")}
    for key in list(saved):
        _sys.modules.pop(key, None)
    try:
        import audio_to_tab.transcribe as transcribe

        importlib.reload(transcribe)
        assert "basic_pitch" not in _sys.modules
        assert "basic_pitch.inference" not in _sys.modules
    finally:
        for key, mod in saved.items():
            _sys.modules[key] = mod


def test_app_py_has_no_emoji_page_icon():
    from pathlib import Path

    text = (Path(__file__).resolve().parents[1] / "ui" / "app.py").read_text(encoding="utf-8")
    assert "🎸" not in text
    assert "_page_icon" in text


LAUNCHER_PATH = Path(__file__).resolve().parents[1] / "packaging" / "launcher.py"


def _load_launcher():
    """Load packaging/launcher.py as a module; it is not an installed package."""
    spec = importlib.util.spec_from_file_location("audiotools_launcher", LAUNCHER_PATH)
    assert spec and spec.loader
    launcher = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(launcher)
    return launcher


def test_patch_webview_audio_open_dialogs_forces_audio_extensions(monkeypatch):
    launcher = _load_launcher()

    class FakeFileDialog:
        OPEN = 10
        SAVE = 20

    captured: dict[str, object] = {}

    class FakeBrowserView:
        def create_file_dialog(
            self,
            dialog_type,
            directory,
            allow_multiple,
            save_filename,
            file_filter,
            main_thread=False,
        ):
            captured["dialog_type"] = dialog_type
            captured["file_filter"] = file_filter
            return ("/tmp/song.mp3",)

    cocoa = types.ModuleType("webview.platforms.cocoa")
    cocoa.BrowserView = FakeBrowserView
    platforms = types.ModuleType("webview.platforms")
    platforms.cocoa = cocoa
    webview_mod = types.ModuleType("webview")
    webview_mod.FileDialog = FakeFileDialog
    webview_mod.platforms = platforms

    monkeypatch.setitem(sys.modules, "webview", webview_mod)
    monkeypatch.setitem(sys.modules, "webview.platforms", platforms)
    monkeypatch.setitem(sys.modules, "webview.platforms.cocoa", cocoa)

    launcher._patch_webview_audio_open_dialogs()
    view = FakeBrowserView()
    view.create_file_dialog(FakeFileDialog.OPEN, "", False, "", None)
    assert captured["dialog_type"] == FakeFileDialog.OPEN
    assert captured["file_filter"][0][0] == "Audio"
    assert "mp3" in captured["file_filter"][0][1]
    assert "wav" in captured["file_filter"][0][1]

    view.create_file_dialog(FakeFileDialog.SAVE, "", False, "out.wav", None)
    assert captured["file_filter"] is None


class FakeServer:
    """Stand-in for the Streamlit child process."""

    def __init__(self) -> None:
        self.pid = 4242
        self.returncode: int | None = None
        self.terminated = False
        self.killed = False

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = 0

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9

    def wait(self, timeout=None) -> int:
        if self.returncode is None:
            self.returncode = 0
        return self.returncode


class FakeShown:
    def __init__(self, already: bool = True) -> None:
        self._event = threading.Event()
        if already:
            self._event.set()

    def wait(self, timeout=None) -> bool:
        return self._event.wait(timeout)

    def is_set(self) -> bool:
        return self._event.is_set()

    def set(self) -> None:
        self._event.set()


class FakeWindow:
    def __init__(self, shown: bool = True) -> None:
        self.loaded: list[str] = []
        self.destroyed = False
        self.events = types.SimpleNamespace(shown=FakeShown(shown))

    def load_url(self, url: str) -> None:
        self.loaded.append(url)

    def destroy(self) -> None:
        self.destroyed = True


def _install_fake_webview(monkeypatch, window):
    """Replace pywebview so tests never need a display."""
    module = types.ModuleType("webview")
    module.settings = {"ALLOW_DOWNLOADS": False}
    calls: dict[str, list] = {"create": [], "start": []}
    module._start_hold_sec = 0.0

    def create_window(title, url=None, html=None, **kwargs):
        kwargs = dict(kwargs)
        if url is not None:
            kwargs["url"] = url
        if html is not None:
            kwargs["html"] = html
        calls["create"].append((title, kwargs))
        return window

    # start() runs the boot callback, then returns as if the user closed the window.
    def start(func=None, private_mode=True, storage_path=None, icon=None, gui=None, **_kwargs):
        calls["start"].append(
            {
                "private_mode": private_mode,
                "storage_path": storage_path,
                "icon": icon,
                "gui": gui,
            }
        )
        if func is not None:
            func()
        hold = float(getattr(module, "_start_hold_sec", 0.0) or 0.0)
        if hold > 0:
            time.sleep(hold)

    module.create_window = create_window
    module.start = start
    monkeypatch.setitem(sys.modules, "webview", module)
    return module, calls


def test_launcher_health_and_lock(tmp_path, monkeypatch):
    launcher = _load_launcher()

    monkeypatch.setattr(launcher, "_user_data_root", lambda: tmp_path)
    launcher._write_lock(8501)
    data = launcher._read_lock()
    assert data is not None
    assert data["port"] == 8501
    assert data["pid"] == os.getpid()
    launcher._clear_lock_if_ours()
    assert launcher._read_lock() is None
    assert launcher._pid_alive(os.getpid()) is True
    assert launcher._pid_alive(999_999_999) is False


def test_launcher_never_binds_all_interfaces():
    assert "0.0.0.0" not in LAUNCHER_PATH.read_text(encoding="utf-8")


def test_server_command_reruns_this_launcher():
    launcher = _load_launcher()

    assert launcher._server_command() == [sys.executable, str(LAUNCHER_PATH)]


def test_server_role_passes_loopback_flags_to_streamlit(tmp_path, monkeypatch):
    launcher = _load_launcher()
    monkeypatch.setattr(launcher, "_user_data_root", lambda: tmp_path)

    import streamlit.web as streamlit_web

    captured: dict[str, list[str]] = {}

    def fake_main():
        captured["argv"] = list(sys.argv)
        return 0

    monkeypatch.setattr(streamlit_web, "cli", types.SimpleNamespace(main=fake_main), raising=False)

    assert launcher.run_streamlit_server(tmp_path, 8502) == 0
    argv = captured["argv"]
    assert argv[:3] == ["streamlit", "run", str(tmp_path / "ui" / "app.py")]
    assert "--server.address=127.0.0.1" in argv
    assert "--server.port=8502" in argv
    assert "--server.enableXsrfProtection=true" in argv
    assert "--client.toolbarMode=viewer" in argv
    assert "--server.fileWatcherType=none" in argv
    assert "--server.runOnSave=false" in argv


def test_dev_reload_enables_streamlit_watch_when_unfrozen(tmp_path, monkeypatch):
    launcher = _load_launcher()
    monkeypatch.setenv("AUDIO_TOOLS_DEV", "1")
    argv = launcher._streamlit_server_argv(tmp_path, 8501)
    assert "--server.fileWatcherType=auto" in argv
    assert "--server.runOnSave=true" in argv
    assert "--client.toolbarMode=viewer" in argv


def test_dev_reload_ignored_when_frozen(tmp_path, monkeypatch):
    launcher = _load_launcher()
    monkeypatch.setenv("AUDIO_TOOLS_DEV", "1")
    monkeypatch.setattr(launcher, "_is_frozen", lambda: True)
    argv = launcher._streamlit_server_argv(tmp_path, 8501)
    assert "--server.fileWatcherType=none" in argv
    assert "--server.runOnSave=false" in argv


def test_main_dispatches_to_server_role(tmp_path, monkeypatch):
    launcher = _load_launcher()
    monkeypatch.setattr(launcher, "_user_data_root", lambda: tmp_path)
    monkeypatch.setattr(launcher, "configure_environment", lambda bundle: tmp_path)
    monkeypatch.setattr(os, "chdir", lambda path: None)
    monkeypatch.setattr(launcher, "run_streamlit_server", lambda workdir, port: 100 + port)
    monkeypatch.setattr(launcher, "run_desktop_app", lambda workdir: 7)

    monkeypatch.setenv("AUDIO_TOOLS_SERVER_ROLE", "1")
    monkeypatch.setenv("AUDIO_TOOLS_SERVER_PORT", "8503")
    assert launcher.main() == 8603

    monkeypatch.delenv("AUDIO_TOOLS_SERVER_ROLE")
    assert launcher.main() == 7


def test_native_window_creates_with_url_after_health(tmp_path, monkeypatch):
    launcher = _load_launcher()
    monkeypatch.delenv("AUDIO_TOOLS_EDITION", raising=False)
    monkeypatch.setattr(launcher, "_user_data_root", lambda: tmp_path)
    monkeypatch.setattr(launcher, "HEALTH_POLL_SEC", 0.0)
    monkeypatch.setattr(launcher, "_webview2_available", lambda: True)
    window = FakeWindow()
    module, calls = _install_fake_webview(monkeypatch, window)

    polls = {"count": 0}

    def health_ok(port):
        polls["count"] += 1
        return polls["count"] >= 3

    monkeypatch.setattr(launcher, "_health_ok", health_ok)
    monkeypatch.setattr(launcher, "_windows_activate_pid", lambda pid: True)
    monkeypatch.setattr(launcher, "_windows_activate_window", lambda title: True)

    rc = launcher._run_native_window("http://127.0.0.1:8501", 8501, FakeServer())

    assert rc == 0
    assert polls["count"] == 3
    # First navigation is the Streamlit URL on the GUI thread — not splash + load_url.
    assert window.loaded == []
    assert calls["create"][0][0] == launcher.window_title()
    assert calls["create"][0][1].get("url") == "http://127.0.0.1:8501"
    assert "html" not in calls["create"][0][1]
    assert calls["start"][0]["private_mode"] is False
    # st.download_button and st.file_uploader are dead without these.
    assert module.settings["ALLOW_DOWNLOADS"] is True


def test_native_window_reports_a_server_that_never_gets_healthy(tmp_path, monkeypatch):
    launcher = _load_launcher()
    monkeypatch.setattr(launcher, "_user_data_root", lambda: tmp_path)
    monkeypatch.setattr(launcher, "HEALTH_POLL_SEC", 0.0)
    monkeypatch.setattr(launcher, "HEALTH_TIMEOUT_SEC", 0.05)
    monkeypatch.setattr(launcher, "_health_ok", lambda port: False)
    errors: list[str] = []
    monkeypatch.setattr(launcher, "_show_error", errors.append)
    window = FakeWindow()
    _install_fake_webview(monkeypatch, window)

    rc = launcher._run_native_window("http://127.0.0.1:8501", 8501, FakeServer())

    assert rc == 1
    assert window.loaded == []
    assert window.destroyed is False
    assert errors and "could not start" in errors[0]


def test_window_that_never_appears_reports_instead_of_opening_a_browser(tmp_path, monkeypatch):
    launcher = _load_launcher()
    monkeypatch.setattr(launcher, "_user_data_root", lambda: tmp_path)
    monkeypatch.setattr(launcher.sys, "platform", "win32")
    monkeypatch.setattr(launcher, "_webview2_available", lambda: True)
    monkeypatch.setattr(launcher, "_health_ok", lambda port: True)
    monkeypatch.setattr(launcher, "SHOWN_TIMEOUT_SEC", 0.05)
    monkeypatch.setattr(launcher, "_windows_window_handles", lambda pid: [])
    monkeypatch.setattr(launcher, "_windows_activate_pid", lambda pid: False)
    errors: list[str] = []
    monkeypatch.setattr(launcher, "_show_error", errors.append)

    def no_browser(*args, **kwargs):
        raise AssertionError("the Windows app must never fall back to a browser")

    monkeypatch.setattr(launcher, "_open_browser", no_browser)
    monkeypatch.setattr(launcher, "_run_in_browser", no_browser)
    window = FakeWindow(shown=False)
    module, _calls = _install_fake_webview(monkeypatch, window)
    module._start_hold_sec = 0.2

    rc = launcher._run_native_window("http://127.0.0.1:8501", 8501, FakeServer())

    assert rc == 1
    assert errors and "could not open its window" in errors[0]
    assert "launcher.log" in errors[0]


def test_browser_fallback_is_off_for_windows_and_macos(monkeypatch):
    launcher = _load_launcher()
    monkeypatch.delenv(launcher.BROWSER_FALLBACK_ENV, raising=False)

    monkeypatch.setattr(launcher.sys, "platform", "win32")
    assert launcher._browser_fallback_allowed() is False
    monkeypatch.setattr(launcher.sys, "platform", "darwin")
    assert launcher._browser_fallback_allowed() is False
    monkeypatch.setattr(launcher.sys, "platform", "linux")
    assert launcher._browser_fallback_allowed() is True

    # Explicit opt-in stays available for headless debugging.
    monkeypatch.setattr(launcher.sys, "platform", "win32")
    monkeypatch.setenv(launcher.BROWSER_FALLBACK_ENV, "1")
    assert launcher._browser_fallback_allowed() is True


def test_windows_window_icon_must_be_an_ico(tmp_path, monkeypatch):
    """System.Drawing.Icon throws on PNG, killing the thread that shows the form."""
    launcher = _load_launcher()
    monkeypatch.setattr(launcher, "_user_data_root", lambda: tmp_path)
    bundle = tmp_path / "bundle" / "packaging"
    bundle.mkdir(parents=True)
    (bundle / "icon.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (bundle / "icon.ico").write_bytes(b"\x00\x00\x01\x00rest")
    monkeypatch.setattr(launcher, "_bundle_root", lambda: tmp_path / "bundle")

    monkeypatch.setattr(launcher.sys, "platform", "win32")
    assert launcher._webview_icon() == str(bundle / "icon.ico")

    monkeypatch.setattr(launcher.sys, "platform", "darwin")
    assert launcher._webview_icon() == str(bundle / "icon.png")


def test_windows_icon_skips_a_png_named_ico(tmp_path, monkeypatch):
    launcher = _load_launcher()
    monkeypatch.setattr(launcher, "_user_data_root", lambda: tmp_path)
    bundle = tmp_path / "bundle" / "packaging"
    bundle.mkdir(parents=True)
    disguised = bundle / "icon.ico"
    disguised.write_bytes(b"\x89PNG\r\n\x1a\n")
    monkeypatch.setattr(launcher, "_bundle_root", lambda: tmp_path / "bundle")
    monkeypatch.setattr(launcher.sys, "platform", "win32")

    assert launcher._is_windows_icon(disguised) is False
    assert launcher._webview_icon() != str(disguised)


def test_optional_webview2_runtimes_skip_missing_arm64_and_x86():
    """pywebview raises FileNotFoundError('Cannot find win-arm64') without this."""
    launcher = _load_launcher()

    def original(dll_name: str) -> str:
        if dll_name in ("win-arm64", "win-x86"):
            raise FileNotFoundError(f"Cannot find {dll_name}")
        return f"/runtimes/{dll_name}/native"

    webview_module = types.SimpleNamespace(util=types.SimpleNamespace(interop_dll_path=original))
    launcher._patch_pywebview_optional_runtimes(webview_module)
    patched = webview_module.util.interop_dll_path

    assert patched("win-arm64") == ""
    assert patched("win-x64") == "/runtimes/win-x64/native"
    assert patched("win-x86") == ""


def test_optional_webview2_runtimes_still_raise_for_required_dlls():
    launcher = _load_launcher()

    def original(dll_name: str) -> str:
        raise FileNotFoundError(f"Cannot find {dll_name}")

    webview_module = types.SimpleNamespace(util=types.SimpleNamespace(interop_dll_path=original))
    launcher._patch_pywebview_optional_runtimes(webview_module)

    with pytest.raises(FileNotFoundError, match="Cannot find WebView2Loader.dll"):
        webview_module.util.interop_dll_path("WebView2Loader.dll")
    assert webview_module.util.interop_dll_path("win-arm64") == ""


def test_start_webview_omits_icon_on_windows_and_forces_edge(tmp_path, monkeypatch):
    """WinForms Icon(path) on the STA thread is how a PNG used to hang start()."""
    launcher = _load_launcher()
    monkeypatch.setattr(launcher, "_user_data_root", lambda: tmp_path)
    monkeypatch.setattr(launcher.sys, "platform", "win32")
    icon = tmp_path / "icon.ico"
    icon.write_bytes(b"\x00\x00\x01\x00rest")
    monkeypatch.setattr(launcher, "_webview_icon", lambda: str(icon))
    module, calls = _install_fake_webview(monkeypatch, FakeWindow())

    launcher._start_webview(module)

    started = calls["start"][0]
    assert started["icon"] is None
    assert started["gui"] == "edgechromium"
    assert started["private_mode"] is False
    assert started["storage_path"] == str(tmp_path / "webview")


def test_start_webview_passes_png_icon_on_macos(tmp_path, monkeypatch):
    launcher = _load_launcher()
    monkeypatch.setattr(launcher, "_user_data_root", lambda: tmp_path)
    monkeypatch.setattr(launcher.sys, "platform", "darwin")
    icon = tmp_path / "icon.png"
    icon.write_bytes(b"\x89PNG\r\n\x1a\n")
    monkeypatch.setattr(launcher, "_webview_icon", lambda: str(icon))
    module, calls = _install_fake_webview(monkeypatch, FakeWindow())

    launcher._start_webview(module)

    started = calls["start"][0]
    assert started["icon"] == str(icon)
    assert started["gui"] is None


def test_webview_storage_uses_a_sidecar_folder_when_the_profile_is_locked(tmp_path, monkeypatch):
    launcher = _load_launcher()
    monkeypatch.setattr(launcher, "_user_data_root", lambda: tmp_path)
    locked = tmp_path / "webview" / "EBWebView"
    locked.mkdir(parents=True)
    (locked / "lockfile").write_bytes(b"held")
    monkeypatch.setattr(launcher, "_webview_profile_locked", lambda folder: folder == tmp_path / "webview")

    path = launcher._webview_storage_dir()
    assert path == tmp_path / f"webview-{os.getpid()}"
    assert path.is_dir()


def test_spec_drops_unused_payload_and_keeps_webview2_x64():
    spec = (Path(__file__).resolve().parents[1] / "packaging" / "audio_tools.spec").read_text(
        encoding="utf-8"
    )
    assert '"tensorflow"' in spec
    assert "webview.platforms.android" in spec
    assert "ffplay" in spec
    assert "_is_duplicate_ffmpeg_dll" in spec
    assert "win-arm64" in spec
    assert "win-x86" in spec
    assert "win-x64/native/WebView2Loader.dll" in spec
    assert "Mixer frontend is incomplete" in spec
    assert "./assets/" in spec
    # Demucs CPU/CUDA stack stays collected.
    assert '"torch"' in spec
    assert '"demucs"' in spec
    assert '"backend"' in spec
    assert '"web"' in spec
    assert "_is_sensitive_shipped" in spec
    assert ".env" in spec
    assert "docker-compose" in spec
    assert ".pem" in spec
    assert "version=_windows_exe_version()" in spec
    assert "edition.txt" in spec
    assert "AUDIO_TOOLS_EDITION" in spec
    assert '(str(ROOT / "web")' not in spec
    assert '(str(ROOT / "backend")' not in spec


def test_real_windows_icon_asset_is_a_valid_ico():
    launcher = _load_launcher()
    icon = LAUNCHER_PATH.parent / "icon.ico"
    assert icon.is_file()
    assert launcher._is_windows_icon(icon) is True


def test_spawn_server_ties_the_child_lifetime_to_this_process(tmp_path, monkeypatch):
    launcher = _load_launcher()
    monkeypatch.setattr(launcher, "_user_data_root", lambda: tmp_path)
    server = FakeServer()
    monkeypatch.setattr(launcher.subprocess, "Popen", lambda *a, **k: server)
    tied: list[int] = []
    monkeypatch.setattr(launcher, "_kill_child_with_parent", lambda pid: tied.append(pid) or True)

    assert launcher._spawn_server(tmp_path, 8501) is server
    assert tied == [server.pid]


def test_closing_the_window_stops_the_server_and_clears_the_lock(tmp_path, monkeypatch):
    launcher = _load_launcher()
    monkeypatch.setattr(launcher, "_user_data_root", lambda: tmp_path)
    monkeypatch.setattr(launcher, "_existing_instance", lambda: None)
    monkeypatch.setattr(launcher, "_pick_port", lambda: 8501)
    monkeypatch.setattr(launcher, "_health_ok", lambda port: True)
    monkeypatch.setattr(launcher, "_webview2_available", lambda: True)
    monkeypatch.setattr(launcher, "_windows_activate_pid", lambda pid: True)
    monkeypatch.setattr(launcher, "_windows_activate_window", lambda title: True)
    _install_fake_webview(monkeypatch, FakeWindow())

    server = FakeServer()
    spawned: list[tuple] = []

    def spawn(workdir, port):
        spawned.append((workdir, port))
        return server

    monkeypatch.setattr(launcher, "_spawn_server", spawn)

    assert launcher.run_desktop_app(tmp_path) == 0
    assert spawned == [(tmp_path, 8501)]
    assert server.terminated is True
    assert launcher._read_lock() is None


def test_second_launch_focuses_instead_of_starting_another_server(tmp_path, monkeypatch):
    launcher = _load_launcher()
    monkeypatch.setattr(launcher, "_user_data_root", lambda: tmp_path)
    launcher._write_lock(8501)  # a live lock: our own pid
    monkeypatch.setattr(launcher, "_health_ok", lambda port: True)

    focused: list[int] = []

    def focus(pid):
        focused.append(pid)
        return True

    monkeypatch.setattr(launcher, "_focus_existing_instance", focus)

    def unreachable(*args, **kwargs):
        raise AssertionError("a second instance must not start a server or a window")

    monkeypatch.setattr(launcher, "_spawn_server", unreachable)
    monkeypatch.setattr(launcher, "_run_native_window", unreachable)

    assert launcher.run_desktop_app(tmp_path) == 0
    assert focused == [os.getpid()]
    # The running instance still owns the lock.
    assert launcher._read_lock() == {"pid": os.getpid(), "port": 8501}


def test_unfocusable_windows_instance_is_reclaimed_not_sent_to_a_browser(tmp_path, monkeypatch):
    """An orphaned server with no window gets ended so a real window can start."""
    launcher = _load_launcher()
    monkeypatch.setattr(launcher, "_user_data_root", lambda: tmp_path)
    monkeypatch.setattr(launcher.sys, "platform", "win32")
    monkeypatch.delenv(launcher.BROWSER_FALLBACK_ENV, raising=False)
    launcher._write_lock(8501)
    monkeypatch.setattr(launcher, "_health_ok", lambda port: True)
    monkeypatch.setattr(launcher, "_focus_existing_instance", lambda pid: False)
    monkeypatch.setattr(launcher, "_pick_port", lambda: 8502)

    def no_browser(*args, **kwargs):
        raise AssertionError("the Windows app must never fall back to a browser")

    monkeypatch.setattr(launcher, "_open_browser", no_browser)
    reclaimed: list[int] = []
    monkeypatch.setattr(launcher, "_reclaim_orphan", lambda pid: reclaimed.append(pid) or True)

    server = FakeServer()
    spawned: list[tuple] = []
    monkeypatch.setattr(
        launcher, "_spawn_server", lambda workdir, port: spawned.append((workdir, port)) or server
    )
    monkeypatch.setattr(launcher, "_run_native_window", lambda url, port, srv: 0)

    assert launcher.run_desktop_app(tmp_path) == 0
    assert reclaimed == [os.getpid()]
    assert spawned == [(tmp_path, 8502)]


def test_unfocusable_instance_opens_browser_only_when_opted_in(tmp_path, monkeypatch):
    launcher = _load_launcher()
    monkeypatch.setattr(launcher, "_user_data_root", lambda: tmp_path)
    monkeypatch.setenv(launcher.BROWSER_FALLBACK_ENV, "1")
    launcher._write_lock(8501)
    monkeypatch.setattr(launcher, "_health_ok", lambda port: True)
    monkeypatch.setattr(launcher, "_focus_existing_instance", lambda pid: False)
    opened: list[str] = []
    notices: list[tuple[str, bool]] = []
    monkeypatch.setattr(launcher, "_open_browser", opened.append)
    monkeypatch.setattr(
        launcher,
        "_show_dialog",
        lambda message, error=True: notices.append((message, error)),
    )

    def unreachable(*args, **kwargs):
        raise AssertionError("a second instance must not start a server")

    monkeypatch.setattr(launcher, "_spawn_server", unreachable)

    assert launcher.run_desktop_app(tmp_path) == 0
    assert opened == ["http://127.0.0.1:8501"]
    assert notices and notices[0][1] is False
    assert "browser" in notices[0][0].lower()
    # Lock still owned by the original instance.
    assert launcher._read_lock() == {"pid": os.getpid(), "port": 8501}


def test_unfocusable_second_launch_clears_lock_when_unhealthy(tmp_path, monkeypatch):
    launcher = _load_launcher()
    monkeypatch.setattr(launcher, "_user_data_root", lambda: tmp_path)
    launcher._write_lock(8501)
    # First call (inside _existing_instance): healthy so we take the existing path.
    # Later calls (after focus fail): unhealthy so we clear and restart.
    health_calls = {"n": 0}

    def health(port):
        health_calls["n"] += 1
        return health_calls["n"] == 1

    monkeypatch.setattr(launcher, "_health_ok", health)
    monkeypatch.setattr(launcher, "_focus_existing_instance", lambda pid: False)
    monkeypatch.setattr(launcher, "_show_dialog", lambda *a, **k: None)
    monkeypatch.setattr(launcher, "_pick_port", lambda: 8502)
    monkeypatch.setattr(launcher, "_reclaim_orphan", lambda pid: True)

    server = FakeServer()
    spawned: list[tuple] = []

    def spawn(workdir, port):
        spawned.append((workdir, port))
        return server

    monkeypatch.setattr(launcher, "_spawn_server", spawn)
    monkeypatch.setattr(launcher, "_run_native_window", lambda url, port, srv: 0)
    monkeypatch.setattr(launcher, "_pid_alive", lambda pid: True)

    assert launcher.run_desktop_app(tmp_path) == 0
    assert spawned == [(tmp_path, 8502)]


def test_existing_instance_clears_stale_lock_after_health_timeout(tmp_path, monkeypatch):
    launcher = _load_launcher()
    monkeypatch.setattr(launcher, "_user_data_root", lambda: tmp_path)
    launcher._write_lock(8501)
    monkeypatch.setattr(launcher, "_pid_alive", lambda pid: True)
    monkeypatch.setattr(launcher, "_health_ok", lambda port: False)
    monkeypatch.setattr(launcher, "HEALTH_POLL_SEC", 0.0)
    monkeypatch.setattr(launcher, "HEALTH_TIMEOUT_SEC", 0.05)

    assert launcher._existing_instance() is None
    assert launcher._read_lock() is None


def test_webview2_preflight_missing_asks_for_the_runtime_without_a_browser(tmp_path, monkeypatch):
    launcher = _load_launcher()
    monkeypatch.setattr(launcher, "_user_data_root", lambda: tmp_path)
    monkeypatch.setattr(launcher.sys, "platform", "win32")
    monkeypatch.delenv(launcher.BROWSER_FALLBACK_ENV, raising=False)
    monkeypatch.setattr(launcher, "_webview2_available", lambda: False)
    dialogs: list[str] = []
    monkeypatch.setattr(launcher, "_show_dialog", lambda message, error=True: dialogs.append(message))

    def no_browser(*args, **kwargs):
        raise AssertionError("the Windows app must never fall back to a browser")

    monkeypatch.setattr(launcher, "_run_in_browser", no_browser)

    rc = launcher._run_native_window("http://127.0.0.1:8501", 8501, FakeServer())
    assert rc == 1
    assert dialogs and "WebView2" in dialogs[0]
    assert "browser" not in dialogs[0].lower()


def test_pick_port_skips_a_port_that_is_in_use(monkeypatch):
    launcher = _load_launcher()
    taken = {launcher.PORT_FALLBACKS[0]}
    monkeypatch.setattr(launcher, "_port_free", lambda port: port not in taken)

    assert launcher._pick_port() == launcher.PORT_FALLBACKS[1]

    monkeypatch.setattr(launcher, "_port_free", lambda port: False)
    assert launcher._pick_port() is None


def test_ffmpeg_dir_candidates_include_bin_and_lib(tmp_path, monkeypatch):
    launcher = _load_launcher()
    bundle = tmp_path / "meipass"
    monkeypatch.setattr(sys, "executable", str(tmp_path / "AudioTools"))
    dirs = launcher._ffmpeg_dir_candidates(bundle)
    assert bundle / "ffmpeg" in dirs
    assert bundle / "ffmpeg" / "bin" in dirs
    assert bundle / "ffmpeg" / "lib" in dirs


def test_ffmpeg_dir_candidates_macos_app_frameworks(tmp_path, monkeypatch):
    launcher = _load_launcher()
    app = tmp_path / "AudioTools.app" / "Contents"
    macos = app / "MacOS"
    macos.mkdir(parents=True)
    exe = macos / "AudioTools"
    exe.write_text("", encoding="utf-8")
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.setattr(launcher.sys, "platform", "darwin")
    bundle = app / "Frameworks"
    dirs = launcher._ffmpeg_dir_candidates(bundle)
    assert bundle / "ffmpeg" / "bin" in dirs
    assert app / "Frameworks" / "ffmpeg" / "bin" in dirs


def test_configure_environment_puts_bundled_ffmpeg_on_path(tmp_path, monkeypatch):
    launcher = _load_launcher()
    bundle = tmp_path / "bundle"
    ffmpeg_bin = bundle / "ffmpeg" / "bin"
    ffmpeg_bin.mkdir(parents=True)
    (ffmpeg_bin / "ffmpeg").write_text("", encoding="utf-8")
    (bundle / "ui").mkdir()
    (bundle / "ui" / "app.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(launcher, "_user_data_root", lambda: tmp_path / "data")
    monkeypatch.setattr(launcher, "_user_cache_root", lambda: tmp_path / "cache")
    monkeypatch.delenv("PATH", raising=False)
    monkeypatch.setenv("PATH", "/usr/bin")

    workdir = launcher.configure_environment(bundle)

    assert workdir == bundle
    path = os.environ["PATH"]
    assert str(ffmpeg_bin) in path


BUNDLE_FFMPEG_PATH = Path(__file__).resolve().parents[1] / "packaging" / "bundle_ffmpeg.py"


def _load_bundle_ffmpeg():
    spec = importlib.util.spec_from_file_location("audiotools_bundle_ffmpeg", BUNDLE_FFMPEG_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_bundle_ffmpeg_platform_key_normalizes(monkeypatch):
    bf = _load_bundle_ffmpeg()

    monkeypatch.setattr(bf.platform, "system", lambda: "Windows")
    monkeypatch.setattr(bf.platform, "machine", lambda: "AMD64")
    assert bf._platform_key() == ("Windows", "AMD64")

    monkeypatch.setattr(bf.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(bf.platform, "machine", lambda: "arm64")
    assert bf._platform_key() == ("Darwin", "arm64")

    monkeypatch.setattr(bf.platform, "machine", lambda: "x86_64")
    assert bf._platform_key() == ("Darwin", "x86_64")


def test_native_window_windows_webview_failure_hints_webview2(tmp_path, monkeypatch):
    launcher = _load_launcher()
    monkeypatch.setattr(launcher, "_user_data_root", lambda: tmp_path)
    monkeypatch.setattr(launcher.sys, "platform", "win32")
    monkeypatch.delenv(launcher.BROWSER_FALLBACK_ENV, raising=False)
    monkeypatch.setattr(launcher, "_webview2_available", lambda: True)
    monkeypatch.setattr(launcher, "_health_ok", lambda port: True)
    dialogs: list[str] = []
    monkeypatch.setattr(launcher, "_show_dialog", lambda message, error=True: dialogs.append(message))

    def no_browser(*args, **kwargs):
        raise AssertionError("the Windows app must never fall back to a browser")

    monkeypatch.setattr(launcher, "_run_in_browser", no_browser)

    import types

    module = types.ModuleType("webview")
    module.settings = {}

    def boom(*args, **kwargs):
        raise RuntimeError("WebView2 / clr init failed")

    module.create_window = boom
    monkeypatch.setitem(sys.modules, "webview", module)

    rc = launcher._run_native_window("http://127.0.0.1:8501", 8501, FakeServer())
    assert rc == 1
    assert dialogs and "WebView2" in dialogs[0]


def test_desktop_app_version_is_0_1_1_not_website_package(monkeypatch):
    from audio_to_tab import __version__

    monkeypatch.delenv("AUDIO_TOOLS_EDITION", raising=False)
    assert __version__ == "0.1.3"
    assert common.desktop_app_version() == "0.1.3"
    pyproject = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    assert 'version = "0.1.3"' in pyproject
    blurb = common.desktop_demo_blurb()
    assert "Demo 0.1.3 (CPU)" in blurb
    assert "this PC" in blurb
    assert "github" not in blurb.lower()
    assert "ATT_SECRET" not in blurb
    cuda_blurb = common.desktop_demo_blurb("0.1.3", "cuda")
    assert "NVIDIA CUDA" in cuda_blurb


def test_inno_and_installer_script_use_versioned_filename():
    root = Path(__file__).resolve().parents[1]
    iss = (root / "packaging" / "AudioTools.iss").read_text(encoding="utf-8")
    assert "OutputBaseFilename=AudioTools-{#AppVersion}-windows-x64-{#Flavor}-setup" in iss
    assert '#define AppVersion "0.1.3"' in iss
    assert "VersionInfoVersion={#AppVersion}" in iss
    assert "VersionInfoProductVersion={#AppVersion}" in iss
    assert "{A7C3E8F1-4B2D-4E9A-9C1F-8D6B5A2E0F73}" in iss
    assert "{C4E91A2B-7D83-4F16-9B50-2A8E6C3D1F47}" in iss
    assert '{#define Flavor "cpu"}' in iss or '#define Flavor "cpu"' in iss
    assert "NvidiaAdapterPresent" in iss
    assert "ArchitecturesAllowed=x64compatible" in iss
    assert "MinVersion=10.0" in iss
    ps1 = (root / "packaging" / "make_windows_installer.ps1").read_text(encoding="utf-8")
    assert 'AppVersion = ""' in ps1
    assert "audio_to_tab import __version__" in ps1
    assert 'Flavor = "cpu"' in ps1
    assert "AudioTools-$AppVersion-windows-x64-$Flavor-setup.exe" in ps1


def test_streamlit_about_is_local_demo_without_hosted_urls():
    text = (Path(__file__).resolve().parents[1] / "ui" / "app.py").read_text(encoding="utf-8")
    assert "desktop_app_version" in text
    assert "desktop_demo_blurb" in text
    assert "processing stays on this computer" in text.lower()
    assert "github.com" not in text.lower()
    assert "ATT_SECRET" not in text
    assert '[data-testid="stDialog"]' in text
    assert "backdrop-filter: blur(6px)" in text
    assert '[data-testid="stElementContainer"][data-stale="true"]' in text
    assert '[data-stale="true"]' in text
    assert "opacity: 1 !important" in text
    assert 'section.main [data-testid="stTabs"] button' in text
    assert "font-size: 1.25rem !important" in text
    assert "min-height: 44px !important" in text
    launcher = LAUNCHER_PATH.read_text(encoding="utf-8")
    assert "def window_title()" in launcher
    assert "edition_window_title" in launcher


def test_tab_pdf_page_has_explicit_developer_playground_disclaimer():
    root = Path(__file__).resolve().parents[1]
    app = (root / "ui" / "app.py").read_text(encoding="utf-8")
    page = (root / "ui" / "pages" / "tab_pdf.py").read_text(encoding="utf-8")
    assert 'title="Tab PDF (demo)"' in app
    assert 'st.title("Tab PDF (demo)")' in page
    assert "JJs stuff" in page
    assert "barely works" in page
    assert "st.caption(" not in page.split("def main")[1].split("demucs_ok")[0]
    assert "Demo only — tabs are rough drafts" not in page


def test_cuda_edition_uses_separate_windows_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("AUDIO_TOOLS_EDITION", "cuda")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    launcher = _load_launcher()
    monkeypatch.setattr(launcher.sys, "platform", "win32")

    assert launcher.window_title() == "Audio Tools (NVIDIA) Demo"
    assert launcher.app_name() == "AudioToolsNVIDIA"
    assert launcher._user_data_root() == tmp_path / "AudioToolsNVIDIA"
    assert launcher._user_cache_root() == tmp_path / "AudioTools" / "models"


def test_cpu_edition_windows_data_dir(tmp_path, monkeypatch):
    monkeypatch.delenv("AUDIO_TOOLS_EDITION", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    launcher = _load_launcher()
    monkeypatch.setattr(launcher.sys, "platform", "win32")

    assert launcher.window_title() == "Audio Tools (CPU) Demo"
    assert launcher.app_name() == "AudioTools"
    assert launcher._user_data_root() == tmp_path / "AudioTools"
    assert launcher._user_cache_root() == tmp_path / "AudioTools" / "models"

