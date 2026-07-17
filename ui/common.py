"""Shared helpers for Streamlit pages."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

DATA_DIR = _REPO_ROOT / "data" / "ui_runs"


def ensure_src_path() -> None:
    if str(_SRC) not in sys.path:
        sys.path.insert(0, str(_SRC))


def save_upload(uploaded_file) -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    run_dir = DATA_DIR / str(uuid.uuid4())
    run_dir.mkdir(parents=True, exist_ok=True)
    dest = run_dir / uploaded_file.name
    dest.write_bytes(uploaded_file.getvalue())
    return dest


def run_output_dir() -> Path:
    out = DATA_DIR / str(uuid.uuid4())
    out.mkdir(parents=True, exist_ok=True)
    return out
