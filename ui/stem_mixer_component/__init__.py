"""Streamlit custom component: live multi-stem Web Audio mixer."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit.components.v1 as components

_BUILD_DIR = Path(__file__).parent / "frontend" / "build"


def component_build_available() -> bool:
    return _BUILD_DIR.is_dir() and (_BUILD_DIR / "index.html").exists()


if component_build_available():
    _stem_mixer = components.declare_component("stem_mixer", path=str(_BUILD_DIR))
else:
    # Dev server: npm run dev in frontend/ (port 3001)
    _stem_mixer = components.declare_component("stem_mixer", url="http://localhost:3001")


def stem_mixer(
    stems: list[dict[str, Any]],
    *,
    initial_volumes_db: dict[str, float] | None = None,
    initial_muted: dict[str, bool] | None = None,
    initial_soloed: dict[str, bool] | None = None,
    track_title: str = "",
    key: str | None = None,
) -> dict[str, Any] | None:
    """
    Render the live stem mixer.

    ``stems`` items: ``{id, label, url}`` plus optional ``downloadUrl``,
    ``downloadFilename``, ``peaks`` (waveform envelope), and ``hint`` used to
    render the per-stem "Waveform & download" dropdown.
    Returns the latest control state from the browser, e.g.
    ``{volumesDb, muted, soloed}``, or None before the first report.
    """
    return _stem_mixer(
        stems=stems,
        initialVolumesDb=initial_volumes_db or {},
        initialMuted=initial_muted or {},
        initialSoloed=initial_soloed or {},
        trackTitle=track_title,
        key=key,
        default=None,
    )
