"""Desktop launcher: native window over a local Streamlit server (dev or PyInstaller freeze)."""

from __future__ import annotations

import inspect
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

APP_NAME = "AudioTools"
WINDOW_TITLE = "Audio Tools"
DEFAULT_PORT = 8501
PORT_FALLBACKS = (8501, 8502, 8503, 8504, 8505)
LOCK_FILENAME = "launcher.lock"
# Frozen first-start imports Torch/Streamlit; 90s is tight on Windows HDD / Intel Mac.
HEALTH_TIMEOUT_SEC = 180.0
HEALTH_POLL_SEC = 0.3
SERVER_STOP_TIMEOUT_SEC = 10.0
WINDOW_SIZE = (1280, 860)
WINDOW_MIN_SIZE = (960, 640)

# Streamlit installs signal handlers, which only work on a main thread, so the
# server runs in a child copy of this process while the parent owns the window.
SERVER_ROLE_ENV = "AUDIO_TOOLS_SERVER_ROLE"
SERVER_PORT_ENV = "AUDIO_TOOLS_SERVER_PORT"

# Native open-panel filter when HTML accept MIME types fail to map (common on macOS).
_AUDIO_OPEN_EXTENSIONS = (
    "mp3",
    "wav",
    "flac",
    "m4a",
    "mpeg",
    "mp4",
    "aac",
    "ogg",
    "aiff",
    "aif",
)

SPLASH_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<style>
  html, body { height: 100%; margin: 0; }
  body {
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    gap: 18px; background: #ffffff; color: #31333f; -webkit-user-select: none;
    font-family: -apple-system, "Segoe UI", system-ui, sans-serif;
  }
  .title { font-size: 20px; font-weight: 600; }
  .hint { font-size: 13px; color: #6b6f7b; }
  .bar { width: 220px; height: 3px; border-radius: 2px; background: #e6e8ef; overflow: hidden; }
  .bar span {
    display: block; width: 40%; height: 100%; border-radius: 2px; background: #ff4b4b;
    animation: slide 1.1s ease-in-out infinite;
  }
  @keyframes slide {
    0% { transform: translateX(-100%); }
    100% { transform: translateX(250%); }
  }
</style>
</head>
<body>
  <div class="title">Starting Audio Tools</div>
  <div class="bar"><span></span></div>
  <div class="hint">Warming up the audio engine. First launch takes a few seconds.</div>
</body>
</html>
"""


def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _bundle_root() -> Path:
    if _is_frozen():
        # PyInstaller onedir: _MEIPASS is the extracted/bundled resources dir
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def _user_data_root() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    if sys.platform.startswith("win"):
        local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(local) / APP_NAME
    return Path.home() / ".local" / "share" / "audio-tools"


def _user_cache_root() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / APP_NAME
    if sys.platform.startswith("win"):
        local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(local) / APP_NAME / "models"
    return Path.home() / ".cache" / "audio-tools"


def _user_log_dir() -> Path:
    log_dir = _user_data_root() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def _log(message: str) -> None:
    try:
        with (_user_log_dir() / "launcher.log").open("a", encoding="utf-8") as log:
            log.write(message.rstrip() + "\n")
    except OSError:
        pass


def _lock_path() -> Path:
    return _user_data_root() / LOCK_FILENAME


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform.startswith("win"):
        import ctypes

        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _read_lock() -> dict | None:
    path = _lock_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    try:
        pid = int(data.get("pid", 0))
        port = int(data.get("port", 0))
    except (TypeError, ValueError):
        return None
    if pid <= 0 or port <= 0:
        return None
    return {"pid": pid, "port": port}


def _write_lock(port: int) -> None:
    path = _lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"pid": os.getpid(), "port": int(port)}
    path.write_text(json.dumps(payload), encoding="utf-8")


def _clear_lock_if_ours() -> None:
    data = _read_lock()
    if data is None or data["pid"] != os.getpid():
        return
    try:
        _lock_path().unlink()
    except OSError:
        pass


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def _health_ok(port: int) -> bool:
    url = f"http://127.0.0.1:{port}/_stcore/health"
    try:
        with urllib.request.urlopen(url, timeout=1.5) as resp:
            return 200 <= int(getattr(resp, "status", 0) or 0) < 300
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _show_dialog(message: str, *, error: bool = True) -> None:
    _log(("ERROR " if error else "INFO ") + message)
    print(message, file=sys.stderr if error else sys.stdout)
    if sys.platform == "darwin":
        escaped = message.replace("\\", "\\\\").replace('"', '\\"')
        script = (
            f'display dialog "{escaped}" with title "{WINDOW_TITLE}" '
            'buttons {"OK"} default button 1'
        )
        try:
            subprocess.run(["osascript", "-e", script], check=False, capture_output=True)
        except OSError:
            pass
        return
    if sys.platform.startswith("win"):
        try:
            import ctypes

            style = 0x10 if error else 0x40
            ctypes.windll.user32.MessageBoxW(0, message, WINDOW_TITLE, style)  # type: ignore[attr-defined]
        except Exception:
            pass


def _show_error(message: str) -> None:
    _show_dialog(message, error=True)


def _running_from_dmg() -> bool:
    if sys.platform != "darwin":
        return False
    exe = str(Path(sys.executable).resolve())
    return exe.startswith("/Volumes/")


def _pick_port() -> int | None:
    """First loopback port nothing else is listening on.

    Callers must rule out an existing instance first; a port serving a live copy
    of this app is never reusable for a *new* server because the bind would fail.
    """
    for port in PORT_FALLBACKS:
        if _port_free(port):
            return port
    return None


def _open_browser(url: str) -> None:
    try:
        if sys.platform == "darwin":
            # `open` brings the default browser forward; webbrowser.open often does not.
            completed = subprocess.run(["open", url], check=False, capture_output=True)
            if completed.returncode == 0:
                return
        webbrowser.open(url)
    except Exception:
        _log(f"Failed to open browser for {url}")


def _macos_activate_pid(pid: int) -> bool:
    """Raise another process's windows via NSRunningApplication (no extra deps)."""
    if sys.platform != "darwin":
        return False
    try:
        import ctypes

        ctypes.cdll.LoadLibrary("/System/Library/Frameworks/AppKit.framework/AppKit")
        libobjc = ctypes.cdll.LoadLibrary("/usr/lib/libobjc.A.dylib")
        libobjc.objc_getClass.restype = ctypes.c_void_p
        libobjc.objc_getClass.argtypes = [ctypes.c_char_p]
        libobjc.sel_registerName.restype = ctypes.c_void_p
        libobjc.sel_registerName.argtypes = [ctypes.c_char_p]
        send = ctypes.cast(libobjc.objc_msgSend, ctypes.c_void_p).value
        cls = libobjc.objc_getClass(b"NSRunningApplication")
        if not cls or not send:
            return False
        app_for_pid = ctypes.CFUNCTYPE(
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int
        )(send)
        app = app_for_pid(
            cls,
            libobjc.sel_registerName(b"runningApplicationWithProcessIdentifier:"),
            int(pid),
        )
        if not app:
            return False
        activate = ctypes.CFUNCTYPE(
            ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong
        )(send)
        # NSApplicationActivateAllWindows | NSApplicationActivateIgnoringOtherApps
        return bool(activate(app, libobjc.sel_registerName(b"activateWithOptions:"), 0x3))
    except Exception:
        _log("Could not activate the running Audio Tools process")
        return False


def _windows_activate_window(title: str) -> bool:
    if not sys.platform.startswith("win"):
        return False
    try:
        import ctypes

        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        hwnd = user32.FindWindowW(None, title)
        if not hwnd:
            return False
        user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        return bool(user32.SetForegroundWindow(hwnd))
    except Exception:
        _log("Could not activate the running Audio Tools window")
        return False


def _focus_existing_instance(pid: int) -> bool:
    """Bring the already-running instance's window forward. Never starts a server."""
    if sys.platform == "darwin":
        return _macos_activate_pid(pid)
    if sys.platform.startswith("win"):
        return _windows_activate_window(WINDOW_TITLE)
    return False


def _wait_until_healthy(port: int, timeout: float, is_alive=None) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _health_ok(port):
            return True
        if is_alive is not None and not is_alive():
            _log("Local server exited before it became healthy")
            return False
        time.sleep(HEALTH_POLL_SEC)
    return False


def _existing_instance() -> dict | None:
    """The pid/port of a live sibling instance, or None if we should start one."""
    data = _read_lock()
    if data is None:
        return None
    pid = data["pid"]
    port = data["port"]
    if not _pid_alive(pid):
        try:
            _lock_path().unlink()
        except OSError:
            pass
        return None
    if _health_ok(port):
        return data
    # Another copy is still starting — wait briefly for it instead of launching a second server.
    deadline = time.monotonic() + min(HEALTH_TIMEOUT_SEC, 30.0)
    while time.monotonic() < deadline:
        if _health_ok(port):
            return data
        if not _pid_alive(pid):
            try:
                _lock_path().unlink()
            except OSError:
                pass
            return None
        time.sleep(HEALTH_POLL_SEC)
    return None


def _prepend_path(directory: Path) -> None:
    if not directory.is_dir():
        return
    current = os.environ.get("PATH", "")
    prefix = str(directory)
    sep = ";" if sys.platform.startswith("win") else ":"
    parts = current.split(sep) if current else []
    if prefix not in parts:
        os.environ["PATH"] = prefix + (sep + current if current else "")


def _ffmpeg_dir_candidates(bundle: Path) -> list[Path]:
    """Locations that may contain ffmpeg / ffprobe (and Windows ffmpeg DLLs)."""
    exe_dir = Path(sys.executable).resolve().parent
    dirs = [
        bundle / "ffmpeg",
        bundle / "ffmpeg" / "bin",
        bundle / "ffmpeg" / "lib",
        exe_dir / "ffmpeg",
        exe_dir / "ffmpeg" / "bin",
        exe_dir / "ffmpeg" / "lib",
    ]
    # PyInstaller .app: executable is Contents/MacOS, datas live in Contents/Frameworks.
    if sys.platform == "darwin" and exe_dir.name == "MacOS":
        frameworks = exe_dir.parent / "Frameworks"
        dirs.extend(
            (
                frameworks / "ffmpeg",
                frameworks / "ffmpeg" / "bin",
                frameworks / "ffmpeg" / "lib",
            )
        )
    return dirs


WEBVIEW2_INSTALL_URL = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"
WEBVIEW2_HINT = (
    "Audio Tools needs the Microsoft Edge WebView2 Runtime for its window "
    "(included with Windows 11 and recent Windows 10). Install it from "
    f"{WEBVIEW2_INSTALL_URL} then try again. Opening in your browser instead."
)


def configure_environment(bundle: Path) -> Path:
    """
    Set user cache/data dirs and PATH for bundled ffmpeg.
    Returns the working directory that contains ui/app.py.
    """
    data_root = _user_data_root()
    cache_root = _user_cache_root()
    runs_dir = data_root / "runs"
    # TORCH_HOME: platform user cache for Demucs weights
    if sys.platform.startswith("win"):
        torch_home = data_root / "models"
    else:
        torch_home = cache_root / "torch"

    for path in (data_root, runs_dir, torch_home, _user_log_dir()):
        path.mkdir(parents=True, exist_ok=True)

    os.environ.setdefault("AUDIO_TOOLS_DATA_DIR", str(runs_dir))
    os.environ.setdefault("TORCH_HOME", str(torch_home))
    os.environ.setdefault("HF_HOME", str(torch_home / "huggingface"))
    os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    os.environ.setdefault("STREAMLIT_SERVER_HEADLESS", "true")
    # PyInstaller bundles lack site-packages in Streamlit's __file__ path, which
    # auto-enables global.developmentMode and rejects explicit --server.port.
    os.environ.setdefault("STREAMLIT_GLOBAL_DEVELOPMENT_MODE", "false")
    os.environ.setdefault("STREAMLIT_BROWSER_SERVER_ADDRESS", "127.0.0.1")
    os.environ.setdefault("STREAMLIT_SERVER_ADDRESS", "127.0.0.1")
    os.environ.setdefault("STREAMLIT_SERVER_FILE_WATCHER_TYPE", "none")
    os.environ.setdefault("STREAMLIT_SERVER_RUN_ON_SAVE", "false")

    for cand in _ffmpeg_dir_candidates(bundle):
        _prepend_path(cand)

    # Prefer repo root (dev) or _MEIPASS (frozen) as cwd so ui/app.py resolves
    if (bundle / "ui" / "app.py").is_file():
        return bundle
    # Dev: launcher lives in packaging/
    repo = Path(__file__).resolve().parents[1]
    if (repo / "ui" / "app.py").is_file():
        return repo
    return bundle


def _server_command() -> list[str]:
    """Re-run this launcher; frozen builds have no separate Python interpreter."""
    if _is_frozen():
        return [sys.executable]
    return [sys.executable, str(Path(__file__).resolve())]


def _spawn_server(workdir: Path, port: int) -> subprocess.Popen:
    env = os.environ.copy()
    env[SERVER_ROLE_ENV] = "1"
    env[SERVER_PORT_ENV] = str(port)
    kwargs: dict = {"cwd": str(workdir), "env": env, "stdin": subprocess.DEVNULL}
    if sys.platform.startswith("win"):
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    log_file = None
    try:
        log_file = (_user_log_dir() / "server.log").open("a", encoding="utf-8")
    except OSError:
        log_file = None
    try:
        return subprocess.Popen(
            _server_command(),
            stdout=log_file or subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
            **kwargs,
        )
    finally:
        if log_file is not None:
            log_file.close()


def _stop_server(server: subprocess.Popen | None) -> None:
    if server is None or server.poll() is not None:
        return
    _log(f"Stopping local server pid={server.pid}")
    try:
        server.terminate()
    except OSError:
        return
    try:
        server.wait(timeout=SERVER_STOP_TIMEOUT_SEC)
        return
    except subprocess.TimeoutExpired:
        _log("Server ignored terminate; killing it")
    try:
        server.kill()
        server.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        pass


def run_streamlit_server(workdir: Path, port: int) -> int:
    """Server role: hand the main thread to Streamlit (it installs signal handlers)."""
    _log(f"Server process {os.getpid()} running Streamlit on 127.0.0.1:{port}")
    from streamlit.web import cli as stcli

    sys.argv = [
        "streamlit",
        "run",
        str(workdir / "ui" / "app.py"),
        "--server.address=127.0.0.1",
        f"--server.port={port}",
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
        "--browser.serverAddress=127.0.0.1",
        "--server.fileWatcherType=none",
        "--server.runOnSave=false",
        "--server.enableCORS=true",
        "--server.enableXsrfProtection=true",
        "--client.toolbarMode=viewer",
    ]
    return int(stcli.main() or 0)


def _webview_icon() -> str | None:
    for candidate in (
        _bundle_root() / "packaging" / "icon.png",
        _bundle_root() / "ui" / "icon.png",
        Path(__file__).resolve().parent / "icon.png",
    ):
        if candidate.is_file():
            return str(candidate)
    return None


def _patch_webview_audio_open_dialogs() -> None:
    """Force native open panels to audio extensions only.

    Streamlit's ``accept`` often sends MIME types that pywebview cannot map to
    UTTypes on macOS, leaving every file selectable. This app only uploads audio,
    so OPEN dialogs always use an audio extension filter. SAVE (downloads) is
    unchanged.
    """
    try:
        from webview import FileDialog
        from webview.platforms import cocoa
    except ImportError:
        return

    browser_view = cocoa.BrowserView
    if getattr(browser_view.create_file_dialog, "_audio_tools_patched", False):
        return

    original = browser_view.create_file_dialog
    audio_filter = [["Audio", list(_AUDIO_OPEN_EXTENSIONS)]]

    def create_file_dialog(
        self,
        dialog_type,
        directory,
        allow_multiple,
        save_filename,
        file_filter,
        main_thread=False,
    ):
        use_filter = file_filter
        if dialog_type == FileDialog.OPEN:
            use_filter = audio_filter
        return original(
            self,
            dialog_type,
            directory,
            allow_multiple,
            save_filename,
            use_filter,
            main_thread=main_thread,
        )

    create_file_dialog._audio_tools_patched = True  # type: ignore[attr-defined]
    browser_view.create_file_dialog = create_file_dialog  # type: ignore[method-assign]


def _start_webview(webview, boot) -> None:
    """webview.start() must own the main thread; pass only kwargs this version knows."""
    storage = _user_data_root() / "webview"
    storage.mkdir(parents=True, exist_ok=True)
    candidates = {
        "func": boot,
        # Persist localStorage so streamlit-local-storage keeps user settings.
        "private_mode": False,
        "storage_path": str(storage),
        "icon": _webview_icon(),
    }
    allowed = set(inspect.signature(webview.start).parameters)
    webview.start(**{k: v for k, v in candidates.items() if k in allowed and v is not None})


def _run_in_browser(url: str, port: int, server: subprocess.Popen) -> int:
    """Last resort when no native window can be created (headless dev box)."""
    if not _wait_until_healthy(port, HEALTH_TIMEOUT_SEC, lambda: server.poll() is None):
        _show_error(_not_ready_message(url))
        return 1
    _open_browser(url)
    server.wait()
    return int(server.returncode or 0)


def _run_native_window(url: str, port: int, server: subprocess.Popen) -> int:
    try:
        import webview
    except ImportError:
        _log("pywebview is unavailable; falling back to the system browser")
        return _run_in_browser(url, port, server)

    # st.download_button and st.file_uploader need real download / open panels.
    webview.settings["ALLOW_DOWNLOADS"] = True
    _patch_webview_audio_open_dialogs()

    window = None
    stopping = threading.Event()
    failed = threading.Event()

    def close_window() -> None:
        if window is None:
            return
        try:
            window.destroy()
        except Exception:
            pass

    def boot() -> None:
        # pywebview runs this on a non-daemon thread, so it must return promptly.
        if not _wait_until_healthy(port, HEALTH_TIMEOUT_SEC, lambda: server.poll() is None):
            failed.set()
            _show_error(_not_ready_message(url))
            close_window()
            return
        _log(f"Health check OK; loading {url} in the native window")
        window.load_url(url)

    def watch_server() -> None:
        while not stopping.wait(0.5):
            if server.poll() is not None:
                _log(f"Server exited (rc={server.returncode}); closing the window")
                close_window()
                return

    try:
        window = webview.create_window(
            WINDOW_TITLE,
            html=SPLASH_HTML,
            width=WINDOW_SIZE[0],
            height=WINDOW_SIZE[1],
            min_size=WINDOW_MIN_SIZE,
            text_select=True,
        )
        threading.Thread(target=watch_server, name="audiotools-server-watch", daemon=True).start()
        _start_webview(webview, boot)
    except Exception as exc:
        stopping.set()
        _log(f"Native window unavailable ({exc}); falling back to the system browser")
        detail = str(exc).lower()
        if sys.platform.startswith("win") and any(
            token in detail for token in ("webview", "clr", "chromium", "edge")
        ):
            _show_dialog(WEBVIEW2_HINT, error=True)
        return _run_in_browser(url, port, server)
    finally:
        stopping.set()
    _log("Native window closed")
    return 1 if failed.is_set() else 0


def _not_ready_message(url: str) -> str:
    return (
        f"Audio Tools could not start its local UI within {int(HEALTH_TIMEOUT_SEC)}s. "
        f"Logs: {_user_log_dir() / 'launcher.log'} and "
        f"{_user_log_dir() / 'server.log'} (server URL was {url})."
    )


def run_desktop_app(workdir: Path) -> int:
    if _is_frozen() and _running_from_dmg():
        _show_error(
            "Move AudioTools to the Applications folder, then launch it from there. "
            "Do not run it from the disk image."
        )
        return 1

    existing = _existing_instance()
    if existing is not None:
        _log(f"Existing instance pid={existing['pid']} port={existing['port']}; focusing it")
        if not _focus_existing_instance(existing["pid"]):
            _show_dialog(
                "Audio Tools is already running. Switch to its window from the Dock or taskbar.",
                error=False,
            )
        return 0

    port = _pick_port()
    if port is None:
        _show_error("Ports 8501–8505 are in use by other programs. Quit them and try again.")
        return 1

    url = f"http://127.0.0.1:{port}"
    _write_lock(port)
    try:
        server = _spawn_server(workdir, port)
    except OSError as exc:
        _clear_lock_if_ours()
        _show_error(f"Audio Tools could not start its local server: {exc}")
        return 1

    _log(f"Server pid={server.pid} starting at {url} cwd={workdir}")
    try:
        return _run_native_window(url, port, server)
    finally:
        _stop_server(server)
        _clear_lock_if_ours()


def main() -> int:
    bundle = _bundle_root()
    workdir = configure_environment(bundle)
    os.chdir(workdir)

    # Ensure src/ is importable when not frozen
    src = workdir / "src"
    if src.is_dir() and str(src) not in sys.path:
        sys.path.insert(0, str(src))
    if str(workdir) not in sys.path:
        sys.path.insert(0, str(workdir))

    if os.environ.get(SERVER_ROLE_ENV) == "1":
        try:
            port = int(os.environ.get(SERVER_PORT_ENV, "") or 0)
        except ValueError:
            port = 0
        if port <= 0:
            _log(f"Server role started without a valid {SERVER_PORT_ENV}")
            return 1
        return run_streamlit_server(workdir, port)

    return run_desktop_app(workdir)


if __name__ == "__main__":
    raise SystemExit(main())
