"""Files the desktop app may receive from the operating system.

The launcher writes one small JSON file per opened path. Isolate Home claims
those files and stages them on a new tab. MIDI is not in the list: opening a
MIDI file is not a reason to add a MIDI editor.

``OPENED_AUDIO_EXTENSIONS`` is the same set the Home file dialog already offers.
"""

from __future__ import annotations

import json
import os
import time
from collections.abc import Sequence
from pathlib import Path
from urllib.parse import unquote, urlparse
from uuid import uuid4

# Directory of claimable JSON files. The launcher sets this on the Streamlit process.
PENDING_OPEN_ENV = "AUDIO_TOOLS_PENDING_OPEN"

# No leading dot. Order is the file-dialog order.
OPENED_AUDIO_EXTENSIONS: tuple[str, ...] = (
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
    "mov",
    "webm",
    "mkv",
)

_OPENED = frozenset(OPENED_AUDIO_EXTENSIONS)
_VIDEO = frozenset({"mp4", "mov", "webm", "mkv"})


def extension_of(path: Path) -> str:
    return path.suffix.lower().lstrip(".")


def is_opened_audio(path: Path) -> bool:
    return extension_of(path) in _OPENED


def is_opened_video(path: Path) -> bool:
    return extension_of(path) in _VIDEO


def _as_path(raw: str) -> Path | None:
    text = raw.strip()
    if text.lower().startswith("file:"):
        parsed = urlparse(text)
        if parsed.scheme != "file":
            return None
        text = unquote(parsed.path)
    if not text:
        return None
    return Path(text)


def paths_from_argv(argv: Sequence[str]) -> tuple[list[Path], list[Path]]:
    """Split process arguments into files to stage and files to decline.

    Flags (``-psn_…`` on macOS) and paths that are not files are ignored.
    A real file whose extension is outside ``OPENED_AUDIO_EXTENSIONS`` is
    declined so the page can say why it did not open.
    """
    accepted: list[Path] = []
    declined: list[Path] = []
    seen: set[str] = set()
    for raw in list(argv)[1:]:
        text = str(raw or "").strip()
        if not text or text.startswith("-"):
            continue
        path = _as_path(text)
        if path is None:
            continue
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        try:
            is_file = path.is_file()
        except OSError:
            continue
        if not is_file:
            continue
        if is_opened_audio(path):
            accepted.append(path)
        else:
            declined.append(path)
    return accepted, declined


def enqueue_opened_paths(folder: Path, items: Sequence[dict]) -> None:
    """Append opened paths. Each item is ``{"path": str, "declined": bool}``."""
    if not items:
        return
    folder.mkdir(parents=True, exist_ok=True)
    stamp = time.time_ns()
    for index, item in enumerate(items):
        name = f"{stamp:020d}-{index:04d}-{uuid4().hex[:8]}.json"
        tmp = folder / f".{name}.tmp"
        dest = folder / name
        tmp.write_text(json.dumps(dict(item)), encoding="utf-8")
        tmp.replace(dest)


def claim_opened_paths(folder: Path) -> list[dict]:
    """Take every queued open, oldest first. Missing folder is an empty queue."""
    if not folder.is_dir():
        return []
    claimed: list[tuple[str, dict]] = []
    for item in sorted(folder.glob("*.json")):
        taken = item.with_name(f".{item.name}.{os.getpid()}.claimed")
        try:
            item.replace(taken)
        except OSError:
            continue
        try:
            data = json.loads(taken.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeError):
            data = None
        try:
            taken.unlink()
        except OSError:
            pass
        if isinstance(data, dict) and data.get("path"):
            claimed.append((item.name, data))
    claimed.sort(key=lambda pair: pair[0])
    return [data for _name, data in claimed]
