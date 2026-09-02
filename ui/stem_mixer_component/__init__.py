"""Streamlit custom component: live multi-stem Web Audio mixer."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any

import streamlit.components.v1 as components

_BUILD_DIR = Path(__file__).resolve().parent / "frontend" / "build"
_ASSET_REF_RE = re.compile(r"""(?:src|href)=["'](\./assets/[^"']+)["']""")


def mixer_build_is_complete(build_dir: Path | None = None) -> bool:
    """True when index.html and every ./assets/ file it references exist.

    A leftover index.html without the Vite JS/CSS ships a blank mixer iframe
    (Streamlit: "trouble loading the stem_mixer component").
    """
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
    return mixer_build_is_complete()


if mixer_build_is_complete():
    _stem_mixer = components.declare_component("stem_mixer", path=str(_BUILD_DIR))
elif getattr(sys, "frozen", False):
    # Frozen builds must never fall back to a missing Vite dev server.
    _stem_mixer = None
else:
    # Dev server: npm run dev in frontend/ (default port 3001, override VITE_DEV_PORT).
    _dev_port = int(os.environ.get("VITE_DEV_PORT", "3001"))
    _stem_mixer = components.declare_component("stem_mixer", url=f"http://localhost:{_dev_port}")


def stem_mixer(
    stems: list[dict[str, Any]],
    *,
    initial_volumes_db: dict[str, float] | None = None,
    initial_muted: dict[str, bool] | None = None,
    initial_soloed: dict[str, bool] | None = None,
    initial_master_volume_db: float = 0.0,
    track_title: str = "",
    key: str | None = None,
) -> dict[str, Any] | None:
    """
    Render the live stem mixer.

    ``stems`` items: ``{id, label, url}`` plus optional ``downloadUrl``,
    ``downloadFilename``, ``peaks`` (waveform envelope), and ``hint``.
    Waveforms render inline on each stem card.
    Returns the latest control state from the browser, e.g.
    ``{volumesDb, muted, soloed, masterVolumeDb}``, or None before the first report.
    """
    if _stem_mixer is None:
        raise RuntimeError(
            "Live mixer frontend is missing from this install. "
            "Reinstall Audio Tools after rebuilding ui/stem_mixer_component/frontend."
        )
    return _stem_mixer(
        stems=stems,
        initialVolumesDb=initial_volumes_db or {},
        initialMuted=initial_muted or {},
        initialSoloed=initial_soloed or {},
        initialMasterVolumeDb=float(initial_master_volume_db),
        trackTitle=track_title,
        key=key,
        default=None,
    )
