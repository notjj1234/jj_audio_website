"""Streamlit entrypoint — multipage router."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import streamlit as st

logger = logging.getLogger(__name__)

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
    except Exception as exc:
        logger.warning("Could not set Streamlit page config: %s", exc)

# Belt-and-braces with client.toolbarMode="viewer": the settings menu (theme) stays,
# the Deploy button and Streamlit footer do not.
# Also: nav user-select (resize highlight), gear instead of running-person,
# no app fade while RUNNING, mixer iframe hit-testing.
# st.html (not st.markdown) — indented HTML in markdown is parsed as a code block.
st.html(
    """
<link href="https://fonts.cdnfonts.com/css/satoshi" rel="stylesheet" />
<style>
  /* Satoshi on text only — never on Material Icons. A blanket [class*="st-"]
     override made Streamlit ligatures (upload, arrow_right, keyboard_double_*)
     render as overlapping plain text instead of icons. */
  html, body,
  [data-testid="stAppViewContainer"],
  [data-testid="stSidebar"],
  [data-testid="stMarkdownContainer"],
  [data-testid="stCaptionContainer"],
  [data-testid="stWidgetLabel"],
  [data-testid="stCheckbox"],
  [data-testid="stRadio"],
  [data-testid="stTextInput"],
  [data-testid="stFileUploader"],
  [data-testid="stExpander"],
  [data-testid="stTabs"],
  [data-testid="stButton"],
  section.main {
    font-family: "Satoshi", system-ui, sans-serif !important;
  }
  .material-icons,
  .material-icons-outlined,
  .material-icons-round,
  .material-icons-sharp,
  .material-icons-two-tone,
  .material-symbols-outlined,
  .material-symbols-rounded,
  .material-symbols-sharp,
  [data-testid="stIconMaterial"],
  [data-testid="stExpanderIcon"],
  [data-testid="stIcon"] {
    font-family: "Material Symbols Rounded", "Material Symbols Outlined",
      "Material Icons", "Material Icons Outlined" !important;
    font-style: normal !important;
    font-weight: normal !important;
    letter-spacing: normal !important;
    text-transform: none !important;
    white-space: nowrap !important;
    word-wrap: normal !important;
    direction: ltr !important;
    -webkit-font-feature-settings: "liga" !important;
    font-feature-settings: "liga" !important;
    -webkit-font-smoothing: antialiased !important;
  }
  [data-testid="stAppDeployButton"] { display: none !important; }
  .stAppDeployButton { display: none !important; }
  footer { visibility: hidden; height: 0; }

  /* Streamlit hides the sidebar collapse chevron until hover (visibility:hidden).
     Keep it always visible so desktop users do not have to hunt for it. */
  [data-testid="stSidebarCollapseButton"] {
    visibility: visible !important;
  }
  [data-testid="stSidebarCollapseButton"] button,
  [data-testid="stExpandSidebarButton"] button {
    opacity: 1 !important;
    color: var(--text-color, inherit) !important;
  }

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

  /* Always hide Streamlit's built-in corner status widget / running stick-men.
     A single centered circle is the one and only loading indicator. */
  [data-testid="stStatusWidget"],
  [data-testid="stStatusWidgetRunningManIcon"],
  [data-testid="stStatusWidgetRunningIcon"],
  [data-testid="stStatusWidgetNewYearsIcon"] {
    display: none !important;
  }

  /* Streamlit 1.55+ stale-element fade (real click/rerun dim, not .stApp):
     suppress it so ordinary interactions never flash. The intentional
     full-page loading overlay is gated separately by the pages. */
  [data-testid="stElementContainer"][data-stale="true"],
  .stElementContainer[data-stale="true"],
  [data-stale="true"] {
    opacity: 1 !important;
    filter: none !important;
    transition: none !important;
    animation: none !important;
  }

  /* Never let any running mask steal mixer clicks */
  div[data-testid="stDecoration"],
  .stApp > .element-container:has(+ iframe),
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

  /* YouTube search dialog: blur + dim the page behind the centered modal */
  [data-testid="stDialog"] {
    backdrop-filter: blur(6px) !important;
    -webkit-backdrop-filter: blur(6px) !important;
    background-color: rgba(15, 23, 42, 0.42) !important;
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

  /* Tighter Isolate/Tab page type: fewer stacked captions */
  section.main h1 {
    padding-top: 0.25rem;
    margin-bottom: 0.45rem;
  }
  section.main [data-testid="stCaptionContainer"] {
    margin-top: 0.15rem;
    margin-bottom: 0.15rem;
  }
  /* New / Mixer / Queue: large, distinguishable, visible across both themes */
  section.main [data-testid="stTabs"] {
    gap: 0.4rem;
  }
  section.main [data-testid="stTabs"] button {
    font-weight: 700 !important;
    font-size: 1.4rem !important;
    line-height: 1.3 !important;
    min-height: 52px !important;
    padding: 0.8rem 1.6rem !important;
    border-radius: 10px !important;
    color: var(--secondary-text-color, inherit) !important;
    background: var(--secondary-background-color, transparent) !important;
    border: 1px solid var(--border-color, rgba(128, 128, 128, 0.35)) !important;
    margin: 0.15rem 0 !important;
  }
  section.main [data-testid="stTabs"] button:hover {
    color: var(--text-color, inherit) !important;
  }
  section.main [data-testid="stTabs"] button[aria-selected="true"] {
    color: var(--text-color, inherit) !important;
    background: var(--primary-color, inherit) !important;
    border-color: var(--primary-color, inherit) !important;
    box-shadow: 0 0 0 1px var(--primary-color) inset;
  }
  section.main [data-testid="stTabs"] [data-baseweb="tab-highlight"],
  section.main [data-testid="stTabs"] [data-baseweb="tab-border"] {
    height: 3px !important;
    opacity: 0;
  }
</style>
"""
)

# Full-page loading overlay. Injected only while a separation job is running,
# a New/Mixer/Queue tab is switched, or a page is switched — a flag the pages
# set in session_state each run. The overlay is pure CSS (offline-safe), never
# steals clicks, and fades in after a short delay so fast reruns don't flash.
_LOADING_OVERLAY_CSS = """
<style>
  @keyframes audiotools-dim-in {
    from { opacity: 0; }
    to { opacity: 1; }
  }
  @keyframes audiotools-circle-spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
  .stApp::before {
    content: "";
    position: fixed;
    inset: 0;
    z-index: 9990;
    pointer-events: none !important;
    background: rgba(0, 0, 0, 0.35);
    backdrop-filter: blur(2px);
    -webkit-backdrop-filter: blur(2px);
    opacity: 0;
    animation: audiotools-dim-in 0.2s ease both;
    animation-delay: 0.2s;
  }
  .stApp::after {
    content: "";
    position: fixed;
    top: 50%;
    left: 50%;
    z-index: 9991;
    width: 64px;
    height: 64px;
    margin: -32px 0 0 -32px;
    pointer-events: none !important;
    border-radius: 50%;
    border: 6px solid var(--text-color, rgba(255, 255, 255, 0.9));
    border-top-color: transparent;
    opacity: 0;
    animation:
      audiotools-circle-spin 0.9s linear infinite,
      audiotools-dim-in 0.2s ease both;
    animation-delay: 0s, 0.2s;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.35);
  }
</style>
"""

if st.session_state.get("_show_global_loading", False):
    st.html(_LOADING_OVERLAY_CSS)

st.sidebar.caption(_DEMO_BLURB)

_pages = Path(__file__).parent / "pages"
pg = st.navigation(
    [
        st.Page(str(_pages / "isolate.py"), title="Audio Isolation", default=True),
        st.Page(str(_pages / "tab_pdf.py"), title="Tab PDF (demo)"),
    ]
)
pg.run()
