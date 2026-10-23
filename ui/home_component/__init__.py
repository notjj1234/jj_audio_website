"""Streamlit custom component: desktop Home library surface."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any

import streamlit.components.v1 as components

_BUILD_DIR = Path(__file__).resolve().parent / "frontend" / "build"
_ASSET_REF_RE = re.compile(r"""(?:src|href)=["'](\./assets/[^"']+)["']""")


def home_build_is_complete(build_dir: Path | None = None) -> bool:
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
    return home_build_is_complete()


if home_build_is_complete():
    _home = components.declare_component("audio_tools_home", path=str(_BUILD_DIR))
elif getattr(sys, "frozen", False):
    _home = None
else:
    _dev_port = int(os.environ.get("HOME_VITE_DEV_PORT", "3002"))
    _home = components.declare_component(
        "audio_tools_home",
        url=f"http://localhost:{_dev_port}",
    )


def home_library(
    props: dict[str, Any],
    *,
    key: str | None = None,
) -> dict[str, Any] | None:
    """Render the Home surface. ``props`` must already be path-free."""
    if _home is None:
        raise RuntimeError(
            "Home frontend is missing from this install. "
            "Run scripts/dev.sh home-build and restart."
        )
    return _home(
        nonce=props.get("nonce") or "",
        product=props.get("product") or "Audio Tools",
        cards=list(props.get("cards") or []),
        recents=list(props.get("recents") or []),
        rows=list(props.get("rows") or []),
        setlists=list(props.get("setlists") or []),
        activeSetlist=props.get("activeSetlist") or "",
        loading=bool(props.get("loading")),
        flash=props.get("flash"),
        key=key,
        default=None,
    )
