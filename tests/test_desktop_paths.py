"""Tests for desktop/local packaging helpers (no PyInstaller run)."""

from __future__ import annotations

import importlib.util
import os
import sys
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

    def fake_run(cmd, capture_output=True, text=True):
        seen.append(list(cmd))
        return MagicMock(returncode=0, stderr="", stdout="")

    with patch("audio_to_tab.separate.subprocess.run", side_effect=fake_run):
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
        with patch("audio_to_tab.separate.subprocess.run") as sub_run:
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


class FakeWindow:
    def __init__(self) -> None:
        self.loaded: list[str] = []
        self.destroyed = False

    def load_url(self, url: str) -> None:
        self.loaded.append(url)

    def destroy(self) -> None:
        self.destroyed = True


def _install_fake_webview(monkeypatch, window):
    """Replace pywebview so tests never need a display."""
    module = types.ModuleType("webview")
    module.settings = {"ALLOW_DOWNLOADS": False}
    calls: dict[str, list] = {"create": [], "start": []}

    def create_window(title, **kwargs):
        calls["create"].append((title, kwargs))
        return window

    # start() runs the boot callback, then returns as if the user closed the window.
    def start(func=None, private_mode=True, storage_path=None, icon=None):
        calls["start"].append(
            {"private_mode": private_mode, "storage_path": storage_path, "icon": icon}
        )
        if func is not None:
            func()

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


def test_native_window_loads_url_only_after_health(tmp_path, monkeypatch):
    launcher = _load_launcher()
    monkeypatch.setattr(launcher, "_user_data_root", lambda: tmp_path)
    monkeypatch.setattr(launcher, "HEALTH_POLL_SEC", 0.0)
    window = FakeWindow()
    module, calls = _install_fake_webview(monkeypatch, window)

    polls = {"count": 0}

    def health_ok(port):
        polls["count"] += 1
        return polls["count"] >= 3

    monkeypatch.setattr(launcher, "_health_ok", health_ok)

    rc = launcher._run_native_window("http://127.0.0.1:8501", 8501, FakeServer())

    assert rc == 0
    assert polls["count"] == 3
    assert window.loaded == ["http://127.0.0.1:8501"]
    assert calls["create"][0][0] == "Audio Tools"
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
    assert window.destroyed is True
    assert errors and "could not start" in errors[0]


def test_closing_the_window_stops_the_server_and_clears_the_lock(tmp_path, monkeypatch):
    launcher = _load_launcher()
    monkeypatch.setattr(launcher, "_user_data_root", lambda: tmp_path)
    monkeypatch.setattr(launcher, "_existing_instance", lambda: None)
    monkeypatch.setattr(launcher, "_pick_port", lambda: 8501)
    monkeypatch.setattr(launcher, "_health_ok", lambda port: True)
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


def test_unfocusable_second_launch_still_refuses_to_start_a_server(tmp_path, monkeypatch):
    launcher = _load_launcher()
    monkeypatch.setattr(launcher, "_user_data_root", lambda: tmp_path)
    launcher._write_lock(8501)
    monkeypatch.setattr(launcher, "_health_ok", lambda port: True)
    monkeypatch.setattr(launcher, "_focus_existing_instance", lambda pid: False)
    notices: list[tuple[str, bool]] = []
    monkeypatch.setattr(
        launcher,
        "_show_dialog",
        lambda message, error=True: notices.append((message, error)),
    )

    def unreachable(*args, **kwargs):
        raise AssertionError("a second instance must not start a server")

    monkeypatch.setattr(launcher, "_spawn_server", unreachable)

    assert launcher.run_desktop_app(tmp_path) == 0
    assert notices and notices[0][1] is False
    assert "already running" in notices[0][0]


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
    dialogs: list[str] = []
    monkeypatch.setattr(launcher, "_show_dialog", lambda message, error=True: dialogs.append(message))
    monkeypatch.setattr(launcher, "_run_in_browser", lambda url, port, server: 0)

    import types

    module = types.ModuleType("webview")
    module.settings = {}

    def boom(*args, **kwargs):
        raise RuntimeError("WebView2 / clr init failed")

    module.create_window = boom
    monkeypatch.setitem(sys.modules, "webview", module)

    rc = launcher._run_native_window("http://127.0.0.1:8501", 8501, FakeServer())
    assert rc == 0
    assert dialogs and "WebView2" in dialogs[0]

