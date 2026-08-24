"""Download a platform ffmpeg shared build into packaging/ffmpeg/ for PyInstaller."""

from __future__ import annotations

import os
import platform
import shutil
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

OUT_ROOT = Path(__file__).resolve().parent / "ffmpeg"

# Prefer well-known static/shared builds suitable for torchcodec (shared libs).
# Versions pinned for reproducibility; bump intentionally.
FFMPEG_SOURCES = {
    # Windows x86_64 — BtbN shared GPL build (includes shared DLLs)
    ("Windows", "AMD64"): {
        "url": (
            "https://github.com/BtbN/FFmpeg-Builds/releases/download/"
            "latest/ffmpeg-master-latest-win64-gpl-shared.zip"
        ),
        "kind": "zip",
        "bin_names": ("ffmpeg.exe",),
    },
    # macOS arm64 — evermeet-style not always arm; use osxexperts / BtbN macOS when available.
    # Fallback: document that CI may use homebrew copy. Use static evermeet for x86 historically.
    ("Darwin", "arm64"): {
        "url": (
            "https://github.com/eugeneware/ffmpeg-static/releases/download/b6.0/ffmpeg-darwin-arm64.gz"
        ),
        "kind": "gz_single",
        "bin_names": ("ffmpeg",),
        "note": "static single binary; prefer brew ffmpeg shared in local maintainer builds",
    },
    ("Darwin", "x86_64"): {
        "url": (
            "https://github.com/eugeneware/ffmpeg-static/releases/download/b6.0/ffmpeg-darwin-x64.gz"
        ),
        "kind": "gz_single",
        "bin_names": ("ffmpeg",),
    },
    ("Linux", "x86_64"): {
        "url": (
            "https://github.com/BtbN/FFmpeg-Builds/releases/download/"
            "latest/ffmpeg-master-latest-linux64-gpl-shared.tar.xz"
        ),
        "kind": "tar",
        "bin_names": ("ffmpeg",),
    },
    ("Linux", "aarch64"): {
        "url": (
            "https://github.com/BtbN/FFmpeg-Builds/releases/download/"
            "latest/ffmpeg-master-latest-linuxarm64-gpl-shared.tar.xz"
        ),
        "kind": "tar",
        "bin_names": ("ffmpeg",),
    },
}


def _platform_key() -> tuple[str, str]:
    system = platform.system()
    machine = platform.machine()
    if system == "Windows":
        machine = "AMD64" if machine.lower() in ("amd64", "x86_64") else machine
    elif system == "Darwin":
        machine = "arm64" if machine == "arm64" else "x86_64"
    elif system == "Linux":
        if machine in ("x86_64", "amd64"):
            machine = "x86_64"
        elif machine in ("aarch64", "arm64"):
            machine = "aarch64"
    return system, machine


def _download(url: str, dest: Path) -> None:
    print(f"Downloading {url}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=300) as resp, dest.open("wb") as out:
        shutil.copyfileobj(resp, out)


def _find_ffmpeg(tree: Path) -> Path | None:
    names = {"ffmpeg", "ffmpeg.exe"}
    for path in tree.rglob("*"):
        if path.is_file() and path.name in names:
            return path
    return None


def _extract_zip(archive: Path, dest: Path) -> None:
    with zipfile.ZipFile(archive, "r") as zf:
        zf.extractall(dest)


def _extract_tar(archive: Path, dest: Path) -> None:
    with tarfile.open(archive, "r:*") as tf:
        tf.extractall(dest)


def _extract_gz_single(archive: Path, dest: Path, name: str = "ffmpeg") -> Path:
    import gzip

    dest.mkdir(parents=True, exist_ok=True)
    out = dest / name
    with gzip.open(archive, "rb") as src, out.open("wb") as dst:
        shutil.copyfileobj(src, dst)
    out.chmod(0o755)
    return out


def _copy_ffmpeg_tree(src_ffmpeg: Path, out_dir: Path) -> None:
    """Copy ffmpeg binary and sibling shared libs into out_dir."""
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # If binary is in a bin/ folder of a shared build, copy whole parent (bin + lib)
    parent = src_ffmpeg.parent
    if parent.name == "bin" and (parent.parent / "lib").is_dir():
        # Copy bin/ and lib/ (and LICENSE if present)
        for sub in ("bin", "lib"):
            src_sub = parent.parent / sub
            if src_sub.is_dir():
                shutil.copytree(src_sub, out_dir / sub)
        for lic in parent.parent.glob("LICENSE*"):
            shutil.copy2(lic, out_dir / lic.name)
        for notice in parent.parent.glob("*LGPL*"):
            shutil.copy2(notice, out_dir / notice.name)
        for notice in parent.parent.glob("*COPYING*"):
            shutil.copy2(notice, out_dir / notice.name)
    else:
        # Single binary layout
        shutil.copy2(src_ffmpeg, out_dir / src_ffmpeg.name)
        # Copy nearby DLLs/dylibs
        for pattern in ("*.dll", "*.dylib", "*.so*"):
            for lib in parent.glob(pattern):
                shutil.copy2(lib, out_dir / lib.name)
        # Write a short LGPL notice reminder
        (out_dir / "FFMPEG_LICENSE_NOTE.txt").write_text(
            "This directory may contain FFmpeg binaries subject to LGPL/GPL.\n"
            "See upstream FFmpeg license files for terms.\n",
            encoding="utf-8",
        )


def _maybe_copy_ffprobe(out_dir: Path) -> None:
    """Shared builds already ship ffprobe; static ffmpeg-only archives do not."""
    probe_name = "ffprobe.exe" if sys.platform.startswith("win") else "ffprobe"
    dest_bin = out_dir / "bin"
    dest = (dest_bin if dest_bin.is_dir() else out_dir) / probe_name
    if dest.is_file():
        return
    found = shutil.which("ffprobe")
    if not found:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(found, dest)
    try:
        dest.chmod(0o755)
    except OSError:
        pass


def _verify(out_dir: Path) -> None:
    exe = out_dir / "bin" / ("ffmpeg.exe" if sys.platform.startswith("win") else "ffmpeg")
    if not exe.is_file():
        exe = out_dir / ("ffmpeg.exe" if sys.platform.startswith("win") else "ffmpeg")
    if not exe.is_file():
        raise SystemExit(f"ffmpeg binary missing under {out_dir}")
    # Smoke: -version
    import subprocess

    env = os.environ.copy()
    bindir = exe.parent
    sep = ";" if sys.platform.startswith("win") else ":"
    env["PATH"] = str(bindir) + sep + env.get("PATH", "")
    # Shared builds often need lib/ on PATH / LD_LIBRARY_PATH
    libdir = out_dir / "lib"
    if libdir.is_dir():
        if sys.platform.startswith("linux"):
            env["LD_LIBRARY_PATH"] = str(libdir) + sep + env.get("LD_LIBRARY_PATH", "")
        elif sys.platform == "darwin":
            env["DYLD_LIBRARY_PATH"] = str(libdir) + sep + env.get("DYLD_LIBRARY_PATH", "")
        else:
            env["PATH"] = str(libdir) + sep + env["PATH"]
    result = subprocess.run([str(exe), "-version"], capture_output=True, text=True, env=env)
    if result.returncode != 0:
        raise SystemExit(f"ffmpeg -version failed: {result.stderr or result.stdout}")
    print(result.stdout.splitlines()[0] if result.stdout else "ffmpeg OK")


def main() -> int:
    key = _platform_key()
    meta = FFMPEG_SOURCES.get(key)
    if not meta:
        print(f"No ffmpeg bundle URL for {key}; copy a shared ffmpeg into {OUT_ROOT} manually.")
        return 1

    out_dir = OUT_ROOT / f"{key[0].lower()}-{key[1].lower()}"
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        archive = tmp_path / "ffmpeg_dl"
        _download(meta["url"], archive)
        extract_dir = tmp_path / "extract"
        extract_dir.mkdir()
        kind = meta["kind"]
        if kind == "zip":
            _extract_zip(archive, extract_dir)
        elif kind == "tar":
            _extract_tar(archive, extract_dir)
        elif kind == "gz_single":
            _extract_gz_single(archive, extract_dir / "bin")
        else:
            raise SystemExit(f"Unknown archive kind: {kind}")

        found = _find_ffmpeg(extract_dir)
        if not found:
            raise SystemExit("Could not find ffmpeg in downloaded archive")
        _copy_ffmpeg_tree(found, out_dir)

    _maybe_copy_ffprobe(out_dir)
    _verify(out_dir)
    # Convenience symlink/copy at packaging/ffmpeg/current for the spec
    current = OUT_ROOT / "current"
    if current.exists() or current.is_symlink():
        if current.is_dir() and not current.is_symlink():
            shutil.rmtree(current)
        else:
            current.unlink()
    shutil.copytree(out_dir, current)
    print(f"Bundled ffmpeg ready at {current}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
