"""Save isolate downloads to a chosen folder and reveal it in the OS file manager.

No tkinter — the frozen app excludes it. Folder picking uses osascript /
PowerShell / zenity.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from audio_to_tab.subprocess_util import subprocess_run_kwargs

_UNSAFE_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def default_export_dir() -> Path:
    downloads = Path.home() / "Downloads"
    if downloads.is_dir():
        return downloads
    return Path.home()


def sanitize_export_name(name: str) -> str:
    cleaned = _UNSAFE_NAME.sub("_", (name or "").strip()) or "stems"
    return cleaned[:80].rstrip(" .")


def export_song_dir(export_root: Path, base_name: str) -> Path:
    return Path(export_root) / sanitize_export_name(base_name)


def copy_tracks_to_folder(
    stem_paths: dict[str, Path],
    dest_dir: Path,
    base_name: str,
) -> Path:
    """Copy selected stem WAVs into ``dest_dir``. Returns the folder written."""
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    prefix = sanitize_export_name(base_name)
    for name, src in stem_paths.items():
        src_path = Path(src)
        if not src_path.is_file():
            continue
        shutil.copy2(src_path, dest_dir / f"{prefix}_{name}.wav")
    return dest_dir


def copy_mix_to_folder(mix_path: Path, dest_dir: Path, filename: str) -> Path:
    """Copy the current mix WAV into ``dest_dir``. Returns the file written."""
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / sanitize_export_name(Path(filename).stem)
    dest = dest.with_suffix(".wav")
    shutil.copy2(mix_path, dest)
    return dest


# Formats ffmpeg can encode for free (lossy/lossless). ``wav`` is a byte-for-byte
# passthrough (no re-encode); the rest go through ffmpeg with a fixed profile.
EXPORT_FORMATS = ("wav", "mp3", "flac", "ogg", "opus", "m4a")

EXPORT_FORMAT_LABELS = {
    "wav": "WAV (lossless)",
    "mp3": "MP3 (192 kbps)",
    "flac": "FLAC (lossless)",
    "ogg": "OGG (Vorbis)",
    "opus": "Opus (high quality)",
    "m4a": "M4A (AAC)",
}

_FFMPEG_PROFILES = {
    "mp3": ["-c:a", "libmp3lame", "-b:a", "192k", "-vn"],
    "flac": ["-c:a", "flac", "-vn"],
    "ogg": ["-c:a", "libvorbis", "-q:a", "4", "-vn"],
    "opus": ["-c:a", "libopus", "-b:a", "160k", "-vn"],
    "m4a": ["-c:a", "aac", "-b:a", "192k", "-vn"],
}


def _ffmpeg_path() -> str | None:
    """Resolve the ffmpeg binary (bundled in the frozen app or on PATH).

    Checks PATH first, then common PyInstaller bundle locations (_MEIPASS)
    and the dev-time repo ``packaging/ffmpeg/`` directory.
    """
    found = shutil.which("ffmpeg")
    if found:
        return found
    candidates: list[Path] = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "ffmpeg")
        candidates.append(Path(meipass) / "bin" / "ffmpeg")
    candidates.append(Path(__file__).resolve().parents[2] / "packaging" / "ffmpeg" / "ffmpeg")
    for cand in candidates:
        try:
            if cand.is_file() and os.access(cand, os.X_OK):
                return str(cand)
        except OSError:
            continue
    return None


def convert_audio(src: Path, dest: Path, fmt: str) -> Path:
    """Convert ``src`` to ``fmt`` and write to ``dest``. Returns ``dest``.

    ``wav`` is copied as-is (lossless passthrough). Other formats are encoded
    with ffmpeg using the profile in ``_FFMPEG_PROFILES``.
    """
    src = Path(src)
    dest = Path(dest)
    fmt = (fmt or "wav").lower()
    if fmt == "wav":
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        return dest
    ffmpeg = _ffmpeg_path()
    if not ffmpeg:
        raise FileNotFoundError(f"ffmpeg is required to export to {fmt}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    profile = _FFMPEG_PROFILES.get(fmt)
    if profile is None:
        raise ValueError(f"Unsupported export format: {fmt}")
    cmd = [ffmpeg, "-y", "-i", str(src), *profile, str(dest)]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False, **subprocess_run_kwargs())
    if result.returncode != 0 or not dest.exists():
        raise RuntimeError(f"ffmpeg conversion to {fmt} failed")
    return dest


def _export_dest_dir(dest_dir: Path) -> Path:
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    return dest_dir


def export_tracks_to_folder(
    stem_paths: dict[str, Path],
    dest_dir: Path,
    base_name: str,
    fmt: str = "wav",
) -> Path:
    """Convert selected stems into ``dest_dir`` as ``fmt``. Returns the folder."""
    dest_dir = _export_dest_dir(dest_dir)
    prefix = sanitize_export_name(base_name)
    for name, src in stem_paths.items():
        src_path = Path(src)
        if not src_path.is_file():
            continue
        target = dest_dir / f"{prefix}_{name}.{fmt}"
        convert_audio(src_path, target, fmt)
    return dest_dir


def export_mix_to_folder(mix_path: Path, dest_dir: Path, filename: str, fmt: str = "wav") -> Path:
    """Convert the current mix into ``dest_dir`` as ``fmt``. Returns the file."""
    dest_dir = _export_dest_dir(dest_dir)
    dest = dest_dir / sanitize_export_name(Path(filename).stem)
    dest = dest.with_suffix("." + fmt)
    convert_audio(Path(mix_path), dest, fmt)
    return dest


def open_path_in_os(
    path: Path,
    *,
    platform: str | None = None,
    runner=None,
) -> bool:
    """Open a folder (or a file's parent) in Finder / Explorer / the file manager."""
    target = Path(path)
    if target.is_file():
        target = target.parent
    if not target.exists():
        return False
    plat = platform or sys.platform
    run = runner or subprocess.run
    try:
        if plat == "darwin":
            run(["open", str(target)], check=False, capture_output=True, text=True)
        elif plat == "win32":
            if runner is None:
                os.startfile(str(target))  # type: ignore[attr-defined]
            else:
                run(["explorer", str(target)], check=False, capture_output=True, text=True)
        else:
            run(["xdg-open", str(target)], check=False, capture_output=True, text=True)
    except OSError:
        return False
    return True


def _choose_dir_command(platform: str) -> list[str] | None:
    if platform == "darwin":
        return [
            "osascript",
            "-e",
            'POSIX path of (choose folder with prompt "Choose a folder for downloads")',
        ]
    if platform == "win32":
        return [
            "powershell",
            "-NoProfile",
            "-Command",
            (
                "Add-Type -AssemblyName System.Windows.Forms; "
                "$d = New-Object System.Windows.Forms.FolderBrowserDialog; "
                "$d.Description = 'Choose a folder for downloads'; "
                "if ($d.ShowDialog() -eq 'OK') { $d.SelectedPath }"
            ),
        ]
    zenity = shutil.which("zenity")
    if zenity:
        return [zenity, "--file-selection", "--directory", "--title=Choose a folder for downloads"]
    return None


def choose_export_dir(
    *,
    platform: str | None = None,
    runner=None,
) -> Path | None:
    """Native folder picker. Returns None if the user cancels or the picker fails."""
    plat = platform or sys.platform
    cmd = _choose_dir_command(plat)
    if not cmd:
        return None
    run = runner or subprocess.run
    try:
        result = run(cmd, capture_output=True, text=True, check=False)
    except OSError:
        return None
    if getattr(result, "returncode", 1) not in (0, None):
        return None
    text = (getattr(result, "stdout", None) or "").strip().strip('"')
    if not text or text.lower().startswith("user canceled"):
        return None
    picked = Path(text).expanduser()
    if plat == "darwin":
        picked = Path(str(picked).rstrip("/"))
    return picked if picked.exists() or picked.parent.exists() else None
