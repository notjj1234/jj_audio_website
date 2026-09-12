"""Streamlit entrypoint — multipage router."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import streamlit as st

logger = logging.getLogger(__name__)

from ui.common import (
    DATA_DIR,
    desktop_app_version,
    desktop_demo_blurb,
    desktop_edition,
    edition_product_name,
    should_show_global_loading,
)
from ui.isolate_state import (
    ISOLATE_UI_STATE_FILENAME,
    UI_MODE_KEY,
    UI_MODES,
    load_ui_mode,
    write_ui_mode,
)
from ui.satoshi_font import satoshi_font_face_css

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
    "<style>\n"
    + satoshi_font_face_css()
    + """
  /* Bundled Satoshi from ui/fonts/ — no CDN. Keeps brand type on-device with
     "processing stays on this computer" (offline-safe; no font phone-home). */
  /* Satoshi on text only — never on Material Icons. A blanket [class*="st-"]
     override made Streamlit ligatures (upload, arrow_right, keyboard_double_*)
     render as overlapping plain text instead of icons. */
  html, body, .stApp,
  [data-testid="stAppViewContainer"],
  [data-testid="stSidebar"],
  [data-testid="stMarkdownContainer"],
  [data-testid="stCaptionContainer"],
  [data-testid="stWidgetLabel"],
  [data-testid="stCheckbox"],
  [data-testid="stRadio"],
  [data-testid="stTextInput"],
  [data-testid="stNumberInput"],
  [data-testid="stTextArea"],
  [data-testid="stSelectbox"],
  [data-testid="stMultiSelect"],
  [data-testid="stFileUploader"],
  [data-testid="stExpander"],
  [data-testid="stTabs"],
  [data-testid="stButton"],
  [data-testid="stDownloadButton"],
  [data-testid="stSlider"],
  [data-testid="stMetric"],
  [data-testid="stAlert"],
  [data-testid="stToolbar"],
  [data-testid="stHeader"],
  [data-testid="stBottomBlockContainer"],
  section.main,
  button, input, textarea, select, label, p, h1, h2, h3, h4, h5, h6, li, span {
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

  /* Sidebar resize drag used to paint a blue text selection across nav +
     Interface + demo caption. Disable selection on the whole sidebar. */
  [data-testid="stSidebar"],
  [data-testid="stSidebar"] * {
    -webkit-user-select: none !important;
    user-select: none !important;
    -webkit-touch-callout: none !important;
  }
  [data-testid="stSidebar"] ::selection {
    background: transparent !important;
    color: inherit !important;
  }
  /* Suppress the click ring, keep the keyboard one: outlining :focus-visible too
     left Tab-key users with no visible caret anywhere in the nav. */
  [data-testid="stSidebarNav"] a:focus:not(:focus-visible),
  [data-testid="stSidebarNav"] li:focus:not(:focus-visible) {
    outline: none !important;
    box-shadow: none !important;
  }
  [data-testid="stSidebarNav"] a:focus-visible,
  [data-testid="stSidebarNav"] li:focus-visible {
    outline: 2px solid var(--primary-color, #ff4b4b) !important;
    outline-offset: 2px !important;
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

  /* Hide leftover heading permalinks (chain-link). Section help uses help= tooltips. */
  [data-testid="stHeaderActionElements"] a[href^="#"],
  [data-testid="stMarkdownContainer"] a[href^="#"].headerlink {
    display: none !important;
  }

  /* Mixer iframe: full hit target for Play/Pause (not just the border) */
  [data-testid="stCustomComponentV1"] {
    pointer-events: auto !important;
    position: relative !important;
    z-index: 60 !important;
  }
  iframe[title*="stem_mixer"],
  iframe[title*="Stem mixer"],
  iframe[title*="stem_mixer_component"] {
    pointer-events: auto !important;
    position: relative !important;
    z-index: 60 !important;
    min-height: 280px !important;
  }

  /* Isolate status strip: stay at top of the scrolling main pane when present.
     Outer slot is always mounted (idle is empty). Min-height only on the
     running inner block so 1s progress ticks do not shove the New-tab form. */
  .st-key-isolate_status_strip,
  div[class*="st-key-isolate_status_strip"] {
    position: sticky;
    top: 0;
    z-index: 20;
    background: var(--background-color, inherit);
  }
  .st-key-isolate_status_running,
  div[class*="st-key-isolate_status_running"] {
    min-height: 6.5rem;
  }

  /* Moises Home|mix|+ strip: always visible while scrolling Isolate */
  .st-key-isolate_mix_tabs_strip,
  div[class*="st-key-isolate_mix_tabs_strip"] {
    position: sticky !important;
    top: 0 !important;
    z-index: 85 !important;
    background: var(--background-color, inherit) !important;
    padding-top: 0.15rem;
    padding-bottom: 0.2rem;
    margin-bottom: 0.15rem;
  }
  /* Streamlit can leave leftover custom-component iframes when keys change. */
  .st-key-isolate_mix_tabs_strip [data-testid="stCustomComponentV1"]:not(:last-of-type),
  div[class*="st-key-isolate_mix_tabs_strip"] [data-testid="stCustomComponentV1"]:not(:last-of-type),
  .st-key-isolate_region_picker [data-testid="stCustomComponentV1"]:not(:last-of-type),
  div[class*="st-key-isolate_region_picker"] [data-testid="stCustomComponentV1"]:not(:last-of-type) {
    display: none !important;
    height: 0 !important;
    max-height: 0 !important;
    overflow: hidden !important;
    pointer-events: none !important;
  }
  .st-key-isolate_mix_tabs_strip [data-testid="stCustomComponentV1"] iframe,
  div[class*="st-key-isolate_mix_tabs_strip"] iframe {
    min-height: 0 !important;
    height: 48px !important;
    max-height: 52px !important;
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

  /* New-tab outcome/stem tiles: icon stacked above label (same for presets + custom) */
  [class*="st-key-isolate_outcome_pick_"] button,
  [class*="st-key-isolate_stem_pick_"] button {
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
    justify-content: center !important;
    text-align: center !important;
    gap: 0.35rem !important;
  }
  [class*="st-key-isolate_outcome_pick_"] button {
    white-space: pre-line !important;
    min-height: 7rem !important;
    line-height: 1.35 !important;
    padding: 0.75rem 0.85rem !important;
    overflow-wrap: normal !important;
    word-break: normal !important;
  }
  [class*="st-key-isolate_outcome_pick_"] button p,
  [class*="st-key-isolate_stem_pick_"] button p {
    white-space: pre-line !important;
    text-align: center !important;
    width: 100%;
    overflow-wrap: normal !important;
    word-break: normal !important;
  }
  [class*="st-key-isolate_stem_pick_"] button {
    min-height: 4.1rem !important;
    padding: 0.55rem 0.45rem !important;
  }
  /* Override Streamlit’s “image ≈ font height” cap; keep icon above text */
  [class*="st-key-isolate_outcome_pick_"] button img,
  [class*="st-key-isolate_stem_pick_"] button img,
  [class*="st-key-isolate_outcome_pick_"] button p img,
  [class*="st-key-isolate_stem_pick_"] button p img,
  [class*="st-key-isolate_outcome_pick_"] button span img,
  [class*="st-key-isolate_stem_pick_"] button span img {
    width: 1.9rem !important;
    height: 1.9rem !important;
    max-width: none !important;
    max-height: none !important;
    vertical-align: middle !important;
    flex-shrink: 0;
    object-fit: contain;
    display: block !important;
    margin-left: auto !important;
    margin-right: auto !important;
    margin-top: 0 !important;
    margin-bottom: 0.15rem !important;
  }
  [class*="st-key-isolate_outcome_pick_"] button img,
  [class*="st-key-isolate_outcome_pick_"] button p img,
  [class*="st-key-isolate_outcome_pick_"] button span img {
    width: 2.35rem !important;
    height: 2.35rem !important;
    margin-bottom: 0.25rem !important;
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
<script>
(function () {
  if (window.__attSidebarSelectGuard) return;
  window.__attSidebarSelectGuard = true;
  function clearSidebarSelection() {
    var sel = window.getSelection && window.getSelection();
    if (!sel || sel.rangeCount === 0 || sel.isCollapsed) return;
    var node = sel.anchorNode;
    var el = node && (node.nodeType === 1 ? node : node.parentElement);
    if (el && el.closest && el.closest('[data-testid="stSidebar"]')) {
      sel.removeAllRanges();
    }
  }
  document.addEventListener("selectionchange", clearSidebarSelection);
  document.addEventListener("mouseup", clearSidebarSelection);
})();
</script>
"""
)

# Full-page loading overlay for one-shot cross-page nav only. Decided here before
# pg.run() so the swap paints immediately. Uses a self-contained overlay root (not
# .stApp::before) so idle runs can unmount/clear it — in-memory worker flags
# alone used to leave the overlay stuck on Mixer after success. Running jobs are
# NOT an input: the app stays usable during separation, so the status strip on the
# isolate page owns that state instead of a window-wide scrim.
def _loading_overlay_html(label: str) -> str:
    safe = (
        label.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    return f"""
<style>
  @keyframes audiotools-dim-in {{
    from {{ opacity: 0; }}
    to {{ opacity: 1; }}
  }}
  @keyframes audiotools-circle-spin {{
    from {{ transform: rotate(0deg); }}
    to {{ transform: rotate(360deg); }}
  }}
  .audiotools-global-loading-root {{
    position: fixed;
    inset: 0;
    z-index: 9990;
    pointer-events: auto !important;
    display: flex;
    align-items: center;
    justify-content: center;
  }}
  .audiotools-global-loading-root .audiotools-dim {{
    position: absolute;
    inset: 0;
    background: rgba(0, 0, 0, 0.35);
    backdrop-filter: blur(2px);
    -webkit-backdrop-filter: blur(2px);
    opacity: 0;
    animation: audiotools-dim-in 0.2s ease both;
    animation-delay: 0.2s;
  }}
  .audiotools-global-loading-root .audiotools-global-loading {{
    position: relative;
    z-index: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.85rem;
    opacity: 0;
    animation: audiotools-dim-in 0.2s ease both;
    animation-delay: 0.2s;
  }}
  .audiotools-global-loading-root .audiotools-spinner {{
    width: 64px;
    height: 64px;
    border-radius: 50%;
    border: 6px solid var(--text-color, rgba(255, 255, 255, 0.9));
    border-top-color: transparent;
    animation: audiotools-circle-spin 0.9s linear infinite;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.35);
  }}
  .audiotools-global-loading-root .audiotools-loading-label {{
    color: var(--text-color, rgba(255, 255, 255, 0.95));
    font-size: 0.95rem;
    font-weight: 600;
    letter-spacing: 0.02em;
    text-shadow: 0 1px 4px rgba(0, 0, 0, 0.45);
  }}
</style>
<div class="audiotools-global-loading-root" aria-live="polite" aria-busy="true">
  <div class="audiotools-dim" aria-hidden="true"></div>
  <div class="audiotools-global-loading">
    <div class="audiotools-spinner" aria-hidden="true"></div>
    <div class="audiotools-loading-label">{safe}</div>
  </div>
</div>
"""


_LOADING_OVERLAY_CLEAR_HTML = """
<style>
  .audiotools-global-loading-root { display: none !important; }
  .stApp::before, .stApp::after { content: none !important; display: none !important; }
</style>
"""

_nav_requested = bool(st.session_state.pop("_nav_loading", False))
if should_show_global_loading(nav_requested=_nav_requested):
    st.html(_loading_overlay_html("Loading…"))
else:
    st.html(_LOADING_OVERLAY_CLEAR_HTML)

_ui_state_path = DATA_DIR / ISOLATE_UI_STATE_FILENAME


def _persist_mode() -> None:
    write_ui_mode(_ui_state_path, st.session_state.get(UI_MODE_KEY))


# Lite auto-profiles speed/device/guitar from RAM/GPU; Pro exposes every control.
# Same shared engine either way. Seeded from disk before the radio instantiates
# so a returning user keeps their Lite/Pro choice.
load_ui_mode(st.session_state, _ui_state_path)
st.sidebar.radio(
    "Interface",
    options=list(UI_MODES),
    key=UI_MODE_KEY,
    horizontal=True,
    on_change=_persist_mode,
    help=(
        "Lite picks speed and device for this computer and shows what it detected. "
        "Pro adds engine, performance and diagnostic controls. Switching is safe "
        "and keeps your current work."
    ),
)
st.sidebar.caption(_DEMO_BLURB)

_pages = Path(__file__).parent / "pages"
_nav = [
    st.Page(str(_pages / "isolate.py"), title="Audio Isolation", default=True),
    # Always listed. The page itself carries the unfinished-product warning —
    # hiding it in Lite made the sidebar look broken when users switched modes.
    st.Page(str(_pages / "tab_pdf.py"), title="Tab PDF (demo)"),
]
pg = st.navigation(_nav)
pg.run()
