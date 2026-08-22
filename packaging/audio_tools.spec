# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onedir spec for Audio Tools (Streamlit + Demucs, local only)."""

from __future__ import annotations

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

# App sources (no backend/, web/, docker). Skip node_modules so a local mixer
# `npm install` cannot bloat the frozen bundle.
_mixer_index = ROOT / "ui" / "stem_mixer_component" / "frontend" / "build" / "index.html"
if not _mixer_index.is_file():
    raise SystemExit(
        "Mixer frontend is missing. Run: make mixer-build "
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
