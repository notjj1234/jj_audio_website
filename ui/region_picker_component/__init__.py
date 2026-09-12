"""Streamlit custom component: waveform region picker (wavesurfer.js)."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any

import streamlit.components.v1 as components

_BUILD_DIR = Path(__file__).resolve().parent / "frontend" / "build"
_ASSET_REF_RE = re.compile(r"""(?:src|href)=["'](\./assets/[^"']+)["']""")


def region_picker_build_is_complete(build_dir: Path | None = None) -> bool:
    """True when index.html and every ./assets/ file it references exist."""
    root = Path(build_dir) if build_dir is not None else _BUILD_DIR
    index = root / "index.html"
    if not index.is_file():
        return False
    try:
        html = index.read_text(encoding="utf-8")
    except OSError:
        return False
    refs = _ASSET_REF_RE.findall(html)
    if not refs:
        return False
    return all((root / ref[2:]).is_file() for ref in refs)


def component_build_available() -> bool:
    return region_picker_build_is_complete()


if region_picker_build_is_complete():
    _region_picker = components.declare_component("region_picker", path=str(_BUILD_DIR))
elif getattr(sys, "frozen", False):
    _region_picker = None
else:
    _dev_port = int(os.environ.get("VITE_REGION_PICKER_PORT", "3002"))
    _region_picker = components.declare_component(
        "region_picker", url=f"http://localhost:{_dev_port}"
    )


def region_picker(
    *,
    audio_url: str,
    start_sec: float = 0.0,
    end_sec: float = 30.0,
    min_length_sec: float = 5.0,
    duration_sec: float | None = None,
    max_hint_sec: float | None = None,
    key: str | None = None,
) -> dict[str, Any] | None:
    """
    Render a waveform with one draggable in/out region.

    Returns ``{startSec, endSec}`` after the user finishes dragging, or None
    before the first report.
    """
    if _region_picker is None:
        raise RuntimeError(
            "Region picker frontend is missing from this install. "
            "Rebuild ui/region_picker_component/frontend (make region-picker-build)."
        )
    return _region_picker(
        audioUrl=audio_url,
        startSec=float(start_sec),
        endSec=float(end_sec),
        minLengthSec=float(min_length_sec),
        durationSec=None if duration_sec is None else float(duration_sec),
        maxHintSec=None if max_hint_sec is None else float(max_hint_sec),
        key=key,
        default=None,
    )
