# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onedir spec for Audio Tools (Streamlit + Demucs, local only)."""

from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

SPECDIR = Path(SPECPATH).resolve()
ROOT = SPECDIR.parent
if sys.platform == "darwin":
    ICON = SPECDIR / "icon.icns"
else:
    ICON = SPECDIR / "icon.ico"

block_cipher = None

datas = []
binaries = []
hiddenimports = []

collect_packages = [
    "streamlit",
    "streamlit_local_storage",
    "demucs",
    "torch",
    "torchaudio",
    "torchcodec",
    "basic_pitch",
    "librosa",
    "soundfile",
    "sklearn",
    "scipy",
    "pretty_midi",
    "reportlab",
    "altair",
    "pyarrow",
    # pywebview renders the UI in a native window instead of a browser tab.
    "webview",
]
if sys.platform == "darwin":
    # WKWebView bindings; pyobjc loads its framework submodules dynamically.
    collect_packages += ["objc", "AppKit", "Foundation", "WebKit", "Quartz"]

for pkg in collect_packages:
    try:
        pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
        datas += pkg_datas
        binaries += pkg_binaries
        hiddenimports += pkg_hidden
    except Exception:
        # Optional / may not always resolve the same way across platforms
        hiddenimports += collect_submodules(pkg)
        try:
            datas += collect_data_files(pkg)
        except Exception:
            pass

# App sources: ui/ + src/audio_to_tab + .streamlit only. Never pack website
# (web/), hosted API (backend/), docker-compose, or secrets (.env, *.pem).
# Skip node_modules so a local mixer `npm install` cannot bloat the freeze.
_mixer_build = ROOT / "ui" / "stem_mixer_component" / "frontend" / "build"
_mixer_index = _mixer_build / "index.html"
_mixer_asset_re = re.compile(r"""(?:src|href)=["'](\./assets/[^"']+)["']""")
_mixer_ok = _mixer_index.is_file()
if _mixer_ok:
    _mixer_html = _mixer_index.read_text(encoding="utf-8")
    _mixer_refs = _mixer_asset_re.findall(_mixer_html)
    _mixer_ok = bool(_mixer_refs) and all((_mixer_build / ref[2:]).is_file() for ref in _mixer_refs)
if not _mixer_ok:
    raise SystemExit(
        "Mixer frontend is incomplete (need index.html plus its ./assets JS/CSS). "
        "Run: make mixer-build "
        "(or npm install && npm run build in ui/stem_mixer_component/frontend)"
    )

_ui_root = ROOT / "ui"
for _path in _ui_root.rglob("*"):
    if not _path.is_file():
        continue
    _parts = set(_path.parts)
    if "node_modules" in _parts or "__pycache__" in _parts:
        continue
    _rel = _path.relative_to(_ui_root)
    _dest_dir = "ui" if _rel.parent == Path(".") else str(Path("ui") / _rel.parent)
    datas.append((str(_path), _dest_dir))

datas += [
    (str(ROOT / "src" / "audio_to_tab"), "audio_to_tab"),
    (str(ROOT / ".streamlit"), ".streamlit"),
]

# Bundled ffmpeg (run packaging/bundle_ffmpeg.py first)
ffmpeg_current = SPECDIR / "ffmpeg" / "current"
if ffmpeg_current.is_dir():
    datas += [(str(ffmpeg_current), "ffmpeg")]

# Replace Streamlit's default favicon so the tab shows our art before set_page_config.
datas = [
    item
    for item in datas
    if not (
        isinstance(item, (list, tuple))
        and len(item) >= 1
        and str(item[0]).replace("\\", "/").endswith("streamlit/static/favicon.png")
    )
]
# Window icon for launcher._webview_icon(). WinForms needs ICO (System.Drawing.Icon
# raises on PNG and kills the thread that shows the form); Cocoa reads PNG.
_window_icon = SPECDIR / ("icon.ico" if sys.platform.startswith("win") else "icon.png")
if _window_icon.is_file():
    datas.append((str(_window_icon), "packaging"))

def _desktop_edition() -> str:
    raw = os.environ.get("AUDIO_TOOLS_EDITION", "cpu").strip().lower()
    if raw in {"cuda", "nvidia", "gpu"}:
        return "cuda"
    return "cpu"


_EDITION = _desktop_edition()
_edition_dir = Path(tempfile.mkdtemp(prefix="audiotools_edition_"))
_edition_file = _edition_dir / "edition.txt"
_edition_file.write_text(_EDITION + "\n", encoding="utf-8")
datas.append((str(_edition_file), "packaging"))

_icon_png = ROOT / "packaging" / "icon.png"
if _icon_png.is_file():
    _fav_dir = Path(tempfile.mkdtemp(prefix="audiotools_favicon_"))
    _fav = _fav_dir / "favicon.png"
    shutil.copy2(_icon_png, _fav)
    datas.append((str(_fav), "streamlit/static"))

hiddenimports += [
    "streamlit.web.cli",
    "streamlit.runtime.scriptrunner",
    "audio_to_tab",
    "audio_to_tab.edition",
    "audio_to_tab.hardware",
    "audio_to_tab.isolate",
    "audio_to_tab.separate",
    "audio_to_tab.ingest",
    "audio_to_tab.mixer",
    "audio_to_tab.lead_rhythm",
    "audio_to_tab.pipeline",
    "ui",
    "ui.app",
    "ui.common",
    "ui.media",
    "ui.isolate_state",
    "ui.pages.isolate",
    "ui.pages.tab_pdf",
    "ui.stem_mixer_component",
    # webview.guilib imports its backend inside a function, one platform at a time.
    "webview.guilib",
    "webview.http",
    "webview.window",
    "bottle",
    "proxy_tools",
]

if sys.platform == "darwin":
    hiddenimports += ["webview.platforms.cocoa"]
elif sys.platform.startswith("win"):
    hiddenimports += [
        "webview.platforms.edgechromium",
        "webview.platforms.winforms",
        "clr",
        "clr_loader",
        "pythonnet",
    ]

excludes = [
    "backend",
    "web",
    "pytest",
    "IPython",
    "jupyter",
    "notebook",
    "tkinter",
    # Basic Pitch picks its backend at import time: with TensorFlow absent it loads
    # saved_models/icassp_2022/nmp.onnx through onnxruntime, which we do bundle.
    # This is the single largest cut in the installer (~870 MB of TF + friends).
    "tensorflow",
    "tensorflow_intel",
    "tensorflow_io_gcs_filesystem",
    "tensorboard",
    "tensorboard_data_server",
    "keras",
    "h5py",
    "grpc",
    "ml_dtypes",
    "coremltools",
    "tflite_runtime",
    # Server-side only: the desktop app talks to no database and no object store.
    "psycopg",
    "psycopg_binary",
    "boto3",
    "botocore",
    "s3transfer",
    # Build-time hook package, not importable at runtime (hyphenated module name).
    "webview.__pyinstaller",
    # Unused pywebview backends; guilib falls back past them harmlessly.
    "webview.platforms.android",
    "webview.platforms.cef",
    "webview.platforms.gtk",
    "webview.platforms.qt",
]
if sys.platform == "darwin":
    excludes += [
        "webview.platforms.edgechromium",
        "webview.platforms.mshtml",
        "webview.platforms.win32",
        "webview.platforms.winforms",
    ]
else:
    excludes += ["webview.platforms.cocoa"]

# collect_all() sweeps in every pywebview backend; excludes must win.
_excluded = set(excludes)
_excluded_prefixes = tuple(f"{name}." for name in excludes)
hiddenimports = [
    name
    for name in hiddenimports
    if name not in _excluded and not name.startswith(_excluded_prefixes)
]

a = Analysis(
    [str(SPECDIR / "launcher.py")],
    pathex=[str(ROOT), str(ROOT / "src")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

def _is_build_only(dest: str) -> bool:
    """C++ headers and import libraries: needed to compile against Torch, not to run it."""
    rel = str(dest).replace("\\", "/")
    if rel.startswith("torch/include/"):
        return True
    return rel.startswith("torch/lib/") and rel.endswith(".lib")


# Root-level copies of the same DLLs already shipped under ffmpeg/bin (torchcodec
# collect_all). ffmpeg.exe needs the copies beside itself; the duplicates at the
# bundle root only slow the installer extract.
_FFMPEG_DLL_NAME = re.compile(
    r"^(avcodec|avfilter|avformat|avdevice|avutil|swscale|swresample)-\d+\.dll$",
    re.IGNORECASE,
)
_UNUSED_WEBVIEW_BACKENDS = (
    "webview/platforms/android",
    "webview/platforms/cef.py",
    "webview/platforms/gtk.py",
    "webview/platforms/qt.py",
)


def _is_unused_shipped(dest: str) -> bool:
    """Drop player binaries, link-time ffmpeg leftovers, and unused GUI backends."""
    rel = str(dest).replace("\\", "/").lstrip("/")
    name = rel.rsplit("/", 1)[-1].lower()
    if name in {"ffplay.exe", "ffplay"}:
        return True
    if rel.startswith("ffmpeg/") and name.endswith((".lib", ".dll.a", ".def", ".exp", ".h")):
        return True
    if any(rel == token or rel.startswith(token + "/") or rel.endswith(token) for token in _UNUSED_WEBVIEW_BACKENDS):
        return True
    if sys.platform.startswith("win") and rel.endswith("webview/platforms/cocoa.py"):
        return True
    if sys.platform == "darwin" and rel.endswith(
        (
            "webview/platforms/edgechromium.py",
            "webview/platforms/winforms.py",
            "webview/platforms/mshtml.py",
            "webview/platforms/win32.py",
        )
    ):
        return True
    # Keep webview/lib/runtimes/win-x64/native/WebView2Loader.dll (and the
    # Microsoft.Web.WebView2.*.dll interop assemblies). Drop the other ABIs;
    # launcher.py patches pywebview so missing win-arm64/win-x86 do not crash.
    if "webview/lib/runtimes/win-arm64/" in rel or "webview/lib/runtimes/win-x86/" in rel:
        return True
    return False


def _is_duplicate_ffmpeg_dll(dest: str) -> bool:
    rel = str(dest).replace("\\", "/").lstrip("/")
    return "/" not in rel and bool(_FFMPEG_DLL_NAME.match(rel))


def _is_sensitive_name(path: str) -> bool:
    """Secrets and compose files must never ship in the demo freeze."""
    name = Path(str(path).replace("\\", "/")).name.lower()
    if name == ".env" or name.startswith(".env."):
        return True
    if name.startswith("docker-compose") and name.endswith((".yml", ".yaml")):
        return True
    if name.startswith("credentials"):
        return True
    return name.endswith(".pem")


def _is_hosted_tree(src: str, dest: str) -> bool:
    """Drop the website (web/) and hosted API (backend/), not streamlit.web."""
    dest_n = str(dest).replace("\\", "/").lstrip("/")
    if dest_n == "web" or dest_n.startswith("web/"):
        return True
    if dest_n == "backend" or dest_n.startswith("backend/"):
        return True
    if not src:
        return False
    try:
        resolved = Path(src).resolve()
    except OSError:
        return False
    for hosted in (ROOT / "web", ROOT / "backend"):
        try:
            resolved.relative_to(hosted.resolve())
            return True
        except ValueError:
            continue
    return False


def _is_sensitive_shipped(dest: str, src: str = "") -> bool:
    return _is_sensitive_name(dest) or _is_sensitive_name(src) or _is_hosted_tree(src, dest)


def _should_drop(dest: str) -> bool:
    return _is_build_only(dest) or _is_unused_shipped(dest) or _is_duplicate_ffmpeg_dll(dest)


def _should_drop_entry(entry) -> bool:
    dest = entry[0]
    src = entry[1] if len(entry) > 1 else ""
    return _should_drop(dest) or _is_sensitive_shipped(dest, src)


a.datas = [entry for entry in a.datas if not _should_drop_entry(entry)]
a.binaries = [entry for entry in a.binaries if not _should_drop_entry(entry)]


def _desktop_app_version() -> str:
    init_py = ROOT / "src" / "audio_to_tab" / "__init__.py"
    match = re.search(
        r'^__version__\s*=\s*["\']([^"\']+)["\']',
        init_py.read_text(encoding="utf-8"),
        re.M,
    )
    return match.group(1) if match else "0.1.2"


def _version_tuple(version: str) -> tuple[int, int, int, int]:
    parts: list[int] = []
    for token in version.split("."):
        digits = "".join(ch for ch in token if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    while len(parts) < 4:
        parts.append(0)
    return (parts[0], parts[1], parts[2], parts[3])


def _windows_exe_version():
    """File properties → Details. macOS has no PE version resource."""
    if not sys.platform.startswith("win"):
        return None
    try:
        from PyInstaller.utils.win32.versioninfo import (
            FixedFileInfo,
            StringFileInfo,
            StringStruct,
            StringTable,
            VarFileInfo,
            VarStruct,
            VSVersionInfo,
        )
    except Exception:
        return None
    version = _desktop_app_version()
    product = "Audio Tools (NVIDIA)" if _EDITION == "cuda" else "Audio Tools (CPU)"
    filevers = _version_tuple(version)
    return VSVersionInfo(
        ffi=FixedFileInfo(
            filevers=filevers,
            prodvers=filevers,
            mask=0x3F,
            flags=0x0,
            OS=0x40004,
            fileType=0x1,
            subtype=0x0,
            date=(0, 0),
        ),
        kids=[
            StringFileInfo(
                [
                    StringTable(
                        "040904B0",
                        [
                            StringStruct("CompanyName", "Audio Tools"),
                            StringStruct("FileDescription", f"{product} demo"),
                            StringStruct("FileVersion", version),
                            StringStruct("InternalName", "AudioTools"),
                            StringStruct("OriginalFilename", "AudioTools.exe"),
                            StringStruct("ProductName", product),
                            StringStruct("ProductVersion", version),
                        ],
                    )
                ]
            ),
            VarFileInfo([VarStruct("Translation", [1033, 1200])]),
        ],
    )

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AudioTools",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ICON) if ICON.is_file() else None,
    version=_windows_exe_version(),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="AudioTools",
)
