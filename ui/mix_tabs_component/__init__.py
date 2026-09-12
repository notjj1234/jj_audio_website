"""Streamlit custom component: Moises-style Home | mix tabs | + strip."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any

import streamlit.components.v1 as components

_BUILD_DIR = Path(__file__).resolve().parent / "frontend" / "build"
_ASSET_REF_RE = re.compile(r"""(?:src|href)=["'](\./assets/[^"']+)["']""")


def mix_tabs_build_is_complete(build_dir: Path | None = None) -> bool:
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
    return mix_tabs_build_is_complete()


if mix_tabs_build_is_complete():
    _mix_tabs = components.declare_component("mix_tabs", path=str(_BUILD_DIR))
elif getattr(sys, "frozen", False):
    _mix_tabs = None
else:
    _dev_port = int(os.environ.get("VITE_MIX_TABS_PORT", "3003"))
    _mix_tabs = components.declare_component(
        "mix_tabs", url=f"http://localhost:{_dev_port}"
    )


def mix_tabs(
    *,
    tabs: list[dict[str, Any]],
    home_label: str = "Home",
    home_active: bool = True,
    show_plus: bool = True,
    key: str | None = None,
) -> dict[str, Any] | None:
    """
    Render Moises-style top chrome: Home | mix tabs | +.

    ``tabs`` items: ``{id, title, active?, busy?, progress?}``.
    ``busy`` / ``progress`` (0–1) paint an in-tab loading bar while a draft
    slot is separating.
    Returns ``{action: "home"|"focus"|"close"|"plus", id?, seq}`` or None.
    """
    if _mix_tabs is None:
        raise RuntimeError(
            "Mix tabs frontend is missing from this install. "
            "Rebuild ui/mix_tabs_component/frontend (make mix-tabs-build)."
        )
    return _mix_tabs(
        homeLabel=home_label,
        homeActive=bool(home_active),
        showPlus=bool(show_plus),
        tabs=tabs,
        key=key,
        default=None,
    )
