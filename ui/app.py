"""Streamlit entrypoint — multipage router."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

from ui.common import (
    desktop_app_version,
    desktop_demo_blurb,
    desktop_edition,
    edition_product_name,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# Allow `from ui.common import ...` when Streamlit runs from repo root
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _page_icon() -> str | None:
    """Resolve guitar art for the browser tab. Never fall back to an emoji."""
    candidates = [Path(__file__).resolve().parent / "icon.png"]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        root = Path(meipass)
        candidates.extend(
            (
                root / "ui" / "icon.png",
                root / "icon.png",
            )
        )
    candidates.append(_REPO_ROOT / "packaging" / "icon.png")
    for path in candidates:
        try:
            if path.is_file():
                return str(path)
        except OSError:
            continue
    return None


_icon = _page_icon()
_APP_VERSION = desktop_app_version()
_EDITION = desktop_edition()
_PRODUCT = edition_product_name(_EDITION)
_DEMO_BLURB = desktop_demo_blurb(_APP_VERSION, _EDITION)
_MENU_ITEMS = {
    "Get help": None,
    "Report a bug": None,
    "About": (
        f"# {_PRODUCT} {_APP_VERSION}\n\n"
        "Demo. Processing stays on this computer. No account."
    ),
}
_page_config: dict[str, object] = {
    "page_title": f"{_PRODUCT} {_APP_VERSION}",
    "layout": "wide",
    "menu_items": _MENU_ITEMS,
}
if _icon:
    _page_config["page_icon"] = _icon
try:
    st.set_page_config(**_page_config)
except Exception:
    try:
        st.set_page_config(page_title=f"{_PRODUCT} {_APP_VERSION}", layout="wide")
    except Exception:
        pass

# Belt-and-braces with client.toolbarMode="viewer": the settings menu (theme) stays,
# the Deploy button and Streamlit footer do not.
st.markdown(
    """
    <style>
      [data-testid="stAppDeployButton"] { display: none !important; }
      .stAppDeployButton { display: none !important; }
      footer { visibility: hidden; height: 0; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.sidebar.caption(_DEMO_BLURB)

_pages = Path(__file__).parent / "pages"
pg = st.navigation(
    [
        st.Page(str(_pages / "isolate.py"), title="Audio Isolation", default=True),
        st.Page(str(_pages / "tab_pdf.py"), title="Tab PDF (demo)"),
    ]
)
pg.run()
