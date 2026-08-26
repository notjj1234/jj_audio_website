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
_WINDOW_PRODUCT = f"{_PRODUCT} Demo" if not getattr(sys, "frozen", False) else _PRODUCT
_DEMO_BLURB = desktop_demo_blurb(_APP_VERSION, _EDITION)
_MENU_ITEMS = {
    "Get help": None,
    "Report a bug": None,
    "About": (
        f"# {_WINDOW_PRODUCT} {_APP_VERSION}\n\n"
        "Demo. Processing stays on this computer. No account."
    ),
}
_page_config: dict[str, object] = {
    "page_title": f"{_WINDOW_PRODUCT} {_APP_VERSION}",
    "layout": "wide",
    "menu_items": _MENU_ITEMS,
}
if _icon:
    _page_config["page_icon"] = _icon
try:
    st.set_page_config(**_page_config)
except Exception:
    try:
        st.set_page_config(page_title=f"{_WINDOW_PRODUCT} {_APP_VERSION}", layout="wide")
    except Exception:
        pass

# Belt-and-braces with client.toolbarMode="viewer": the settings menu (theme) stays,
# the Deploy button and Streamlit footer do not.
# Also: nav user-select (resize highlight), gear instead of running-person,
# no app fade while RUNNING, mixer iframe hit-testing.
st.markdown(
    """
    <style>
      [data-testid="stAppDeployButton"] { display: none !important; }
      .stAppDeployButton { display: none !important; }
      footer { visibility: hidden; height: 0; }

      /* Sidebar: stop resize-drag from selecting every label */
      [data-testid="stSidebar"],
      [data-testid="stSidebar"] *,
      [data-testid="stSidebarNav"],
      [data-testid="stSidebarNav"] * {
        -webkit-user-select: none !important;
        user-select: none !important;
      }
      [data-testid="stSidebar"] ::selection,
      [data-testid="stSidebarNav"] ::selection {
        background: transparent !important;
      }
      [data-testid="stSidebarNav"] a:focus,
      [data-testid="stSidebarNav"] a:focus-visible,
      [data-testid="stSidebarNav"] li:focus,
      [data-testid="stSidebarNav"] li:focus-visible {
        outline: none !important;
        box-shadow: none !important;
      }

      /* Status widget: hide running-person; show a spinning gear */
      [data-testid="stStatusWidget"] {
        display: inline-flex !important;
        align-items: center !important;
        gap: 0.35rem !important;
      }
      [data-testid="stStatusWidget"] img,
      [data-testid="stStatusWidget"] svg,
      [data-testid="stStatusWidget"] > div > img,
      [data-testid="stStatusWidget"] > div > svg {
        display: none !important;
        width: 0 !important;
        height: 0 !important;
        visibility: hidden !important;
      }
      [data-testid="stStatusWidget"]::before {
        content: "⚙";
        display: inline-block;
        font-size: 1.15rem;
        line-height: 1;
        flex-shrink: 0;
        animation: audiotools-gear-spin 1.2s linear infinite;
      }
      @keyframes audiotools-gear-spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
      }

      /* Kill whole-app fade while script is RUNNING (animation, not only opacity) */
      .stApp,
      [data-testid="stAppViewContainer"],
      [data-testid="stAppViewContainer"][data-test-script-state="running"],
      .stApp[data-test-script-state="running"],
      .stAppViewContainer,
      section.main {
        opacity: 1 !important;
        transition: none !important;
        animation: none !important;
      }

      /* Running overlay must not steal mixer clicks */
      [data-testid="stAppViewContainer"][data-test-script-state="running"]::before,
      .stApp[data-test-script-state="running"]::before,
      div[data-testid="stDecoration"],
      .stApp > .element-container:has(+ iframe) {
        pointer-events: none !important;
      }
      /* Prefer disabling any full-bleed running mask if present */
      [class*="stAppRunning"],
      [class*="app-running"],
      .stSpinnerOverlay {
        pointer-events: none !important;
      }

      /* Mixer iframe: full hit target for Play/Pause (not just the border) */
      [data-testid="stCustomComponentV1"] {
        pointer-events: auto !important;
        position: relative !important;
        z-index: 60 !important;
      }
      [data-testid="stCustomComponentV1"] iframe,
      iframe[title*="stem_mixer"],
      iframe[title*="Stem mixer"],
      iframe[title*="stem_mixer_component"] {
        pointer-events: auto !important;
        position: relative !important;
        z-index: 60 !important;
        min-height: 280px !important;
      }

      /* Isolate status strip: stay at top of the scrolling main pane when present */
      .st-key-isolate_status_strip,
      div[class*="st-key-isolate_status_strip"] {
        position: sticky;
        top: 0;
        z-index: 20;
        background: var(--background-color, inherit);
      }

      /* Refresh sits level with the Isolate title, right of the header row */
      [data-testid="stHorizontalBlock"]:has(.st-key-isolate_refresh) {
        align-items: center !important;
      }
      [data-testid="stHorizontalBlock"]:has(.st-key-isolate_refresh) [data-testid="stHeading"],
      [data-testid="stHorizontalBlock"]:has(.st-key-isolate_refresh) h1 {
        padding-top: 0 !important;
        margin-bottom: 0 !important;
      }
      [data-testid="stHorizontalBlock"]:has(.st-key-isolate_refresh) .st-key-isolate_refresh {
        display: flex;
        justify-content: flex-end;
      }

      /* Tighter Isolate/Tab page type: fewer stacked captions, quieter tabs */
      section.main h1 {
        padding-top: 0.25rem;
        margin-bottom: 0.45rem;
      }
      section.main [data-testid="stCaptionContainer"] {
        margin-top: 0.15rem;
        margin-bottom: 0.15rem;
      }
      section.main [data-testid="stTabs"] button {
        font-weight: 600;
      }
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
