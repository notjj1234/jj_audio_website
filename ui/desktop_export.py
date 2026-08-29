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
