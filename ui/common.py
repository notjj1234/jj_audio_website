"""Shared helpers for Streamlit pages."""

from __future__ import annotations

import json
import logging
import os
import shutil
import sys
import time
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from audio_to_tab.edition import desktop_edition, edition_display_label, edition_product_name


def _resolve_data_dir() -> Path:
    override = os.environ.get("AUDIO_TOOLS_DATA_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return _REPO_ROOT / "data" / "ui_runs"


DATA_DIR = _resolve_data_dir()
_META_FILENAME = "meta.json"

# Streamlit ``type=`` for uploaders. Include the ``audio`` shortcut (→ ``audio/*``)
# so OS/native pickers (incl. pywebview on macOS) grey out non-audio files; keep
# explicit MIME + extensions aligned with backend/limits.py.
AUDIO_UPLOAD_TYPES: list[str] = [
    "audio",
    "audio/mpeg",
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/flac",
    "audio/x-flac",
    "audio/mp4",
    "audio/x-m4a",
    "audio/m4a",
    ".mp3",
    ".wav",
    ".flac",
    ".m4a",
]


def ensure_src_path() -> None:
    if str(_SRC) not in sys.path:
        sys.path.insert(0, str(_SRC))


def desktop_app_version() -> str:
    """Version testers see (installer, Apps & Features, in-app). Not the website package version."""
    ensure_src_path()
    try:
        from audio_to_tab import __version__

        return str(__version__)
    except Exception:
        logger.warning("Could not determine app version from audio_to_tab.__version__")
        return "unknown"


def desktop_demo_blurb(version: str | None = None, edition: str | None = None) -> str:
    """Sidebar / About copy: local demo, nothing hosted to scrape."""
    ver = version or desktop_app_version()
    label = edition_display_label(edition if edition is not None else desktop_edition())
    return f"Demo {ver} ({label}) — processing stays on this PC. No account."


def _safe_upload_name(name: str | None) -> str:
    base = Path(name or "").name.replace("\x00", "").strip()
    if not base or base in {".", ".."}:
        raise ValueError("Invalid upload filename")
    return base


def save_upload(uploaded_file) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    run_dir = DATA_DIR / str(uuid.uuid4())
    run_dir.mkdir(parents=True, exist_ok=True)
    dest = run_dir / _safe_upload_name(getattr(uploaded_file, "name", None))
    dest.write_bytes(uploaded_file.getvalue())
    return dest


def run_output_dir() -> Path:
    out = DATA_DIR / str(uuid.uuid4())
    out.mkdir(parents=True, exist_ok=True)
    return out


def write_run_metadata(
    run_dir: Path,
    *,
    page: str,
    title: str,
    artifacts: dict[str, str],
    owner: str | None = None,
    source_kind: str | None = None,
    source_fingerprint: str | None = None,
    config: dict | None = None,
) -> None:
    """
    Persist small metadata alongside a run's artifacts so it can be listed as "Recent".

    ``page`` identifies which page produced the run (e.g. "tab_pdf" / "isolate").
    ``owner`` is an optional browser-scoped id used to keep recent lists private.
    ``config`` (optional) is stored as-is under a ``"config"`` key so a re-separate
    run can default its settings from the parent run even after an app restart.
    When ``config`` is None the key is omitted entirely.
    """
    meta = {
        "page": page,
        "title": title,
        "created_at": time.time(),
        "artifacts": {k: str(v) for k, v in artifacts.items()},
    }
    if owner is not None:
        meta["owner"] = owner
    if source_kind is not None:
        meta["source_kind"] = source_kind
    if source_fingerprint is not None:
        meta["source_fingerprint"] = source_fingerprint
    if config is not None:
        meta["config"] = config
    Path(run_dir).mkdir(parents=True, exist_ok=True)
    (Path(run_dir) / _META_FILENAME).write_text(json.dumps(meta), encoding="utf-8")


def list_recent_runs(
    page: str,
    limit: int = 10,
    *,
    owner: str | None = None,
) -> list[dict]:
    """Return metadata (plus ``run_dir``) for a page's most recent runs, newest first."""
    if not DATA_DIR.is_dir():
        return []
    runs: list[dict] = []
    for run_dir in DATA_DIR.iterdir():
        meta_path = run_dir / _META_FILENAME
        if not meta_path.is_file():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if meta.get("page") != page:
            continue
        if owner is not None and meta.get("owner") != owner:
            continue
        meta["run_dir"] = str(run_dir)
        runs.append(meta)
    runs.sort(key=lambda m: m.get("created_at", 0), reverse=True)
    return runs[:limit]


def delete_run(run_dir: str | Path) -> bool:
    """
    Delete a UI run directory and its artifacts.

    Only paths that resolve to a direct child of ``DATA_DIR`` are removed.
    Returns True if the directory was deleted (or already absent).
    """
    path = Path(run_dir).resolve()
    data_root = DATA_DIR.resolve()
    try:
        path.relative_to(data_root)
    except ValueError:
        return False
    if path == data_root or path.parent != data_root:
        return False
    if not path.exists():
        return True
    if not path.is_dir():
        return False
    shutil.rmtree(path)
    return not path.exists()
