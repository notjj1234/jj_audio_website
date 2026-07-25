"""Pure helpers for isolate page upload/result state and separation progress."""

from __future__ import annotations

from pathlib import Path
from typing import Any

ISOLATION_STAGE_ORDER = (
    "ingest",
    "separate",
    "collect",
    "bass_bleed",
    "guitar_split",
    "presence",
    "done",
)

STAGE_WEIGHTS: dict[str, float] = {
    "ingest": 0.05,
    "separate": 0.75,
    "collect": 0.05,
    "bass_bleed": 0.05,
    "guitar_split": 0.05,
    "presence": 0.03,
    "done": 0.02,
}


def upload_fingerprint(uploaded: Any) -> str | None:
    """Fingerprint a Streamlit UploadedFile (name + size), or None if absent."""
    if uploaded is None:
        return None
    name = getattr(uploaded, "name", None)
    size = getattr(uploaded, "size", None)
    if not name:
        return None
    return f"{name}:{size}"


def sync_output_name_on_upload(
    uploaded: Any,
    *,
    last_fp: str | None,
    output_name: str,
) -> tuple[str | None, str, bool]:
    """
    When the user picks a new file, return updated fingerprint and output name.

    Returns ``(new_fp, output_name, changed)``.
    """
    fp = upload_fingerprint(uploaded)
    if fp is None or fp == last_fp:
        return fp, output_name, False
    new_name = Path(uploaded.name).stem
    return fp, new_name, True


def should_hide_stale_results(
    *,
    pending_upload_fp: str | None,
    has_artifacts: bool,
) -> bool:
    """True when a new upload is queued but prior separation results are still loaded."""
    return bool(has_artifacts and pending_upload_fp is not None)


def stage_progress_percent(stage: str, *, weights: dict[str, float] | None = None) -> float:
    """Cumulative weighted progress (0.0–1.0) through isolation stages."""
    w = weights or STAGE_WEIGHTS
    total = sum(w.get(s, 0.0) for s in ISOLATION_STAGE_ORDER)
    if total <= 0:
        return 0.0
    if stage not in ISOLATION_STAGE_ORDER:
        return 0.0
    idx = ISOLATION_STAGE_ORDER.index(stage)
    done = sum(w.get(ISOLATION_STAGE_ORDER[i], 0.0) for i in range(idx + 1))
    return min(1.0, done / total)


def format_progress_label(percent: float, message: str) -> str:
    """Human-readable progress line, e.g. ``42% — Running Demucs…``."""
    pct = int(round(percent * 100))
    return f"{pct}% — {message}"


def format_elapsed(seconds: float) -> str:
    """Format elapsed seconds as M:SS."""
    if seconds < 0:
        seconds = 0
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m}:{s:02d}"
