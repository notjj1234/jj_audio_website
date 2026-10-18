"""Smoke tests for the Moises-style mix tabs Streamlit component."""

from __future__ import annotations

import inspect
from pathlib import Path


def test_mix_tabs_build_present():
    from ui.mix_tabs_component import mix_tabs_build_is_complete

    build = (
        Path(__file__).resolve().parents[1]
        / "ui"
        / "mix_tabs_component"
        / "frontend"
        / "build"
    )
    assert mix_tabs_build_is_complete(build), (
        "Mix tabs frontend is incomplete. Run make mix-tabs-build "
        "(or npm run build in ui/mix_tabs_component/frontend)"
    )


def test_mix_tabs_import():
    from ui.mix_tabs_component import component_build_available, mix_tabs

    assert component_build_available()
    assert callable(mix_tabs)
    params = inspect.signature(mix_tabs).parameters
    assert "tabs" in params
    assert "home_label" in params
    assert "home_active" in params
    assert "show_plus" in params


def test_mix_tabs_source_has_moises_chrome():
    main = (
        Path(__file__).resolve().parents[1]
        / "ui"
        / "mix_tabs_component"
        / "frontend"
        / "src"
        / "main.ts"
    ).read_text(encoding="utf-8")
    assert 'action: "home"' in main or 'report("home")' in main
    assert 'report("plus")' in main
    assert 'report("focus"' in main
    assert 'report("close"' in main
    assert 'title="Close tab"' in main
    assert "Close tab (Delete)" not in main
    assert "seq:" in main or "seq =" in main
    assert "mix-tab-bar" in main or "Home" in main
    assert "tab-progress" in main
    assert "aria-busy" in main
    assert "bindTabStripWheel" in main
    assert "scrollLeft" in main
    assert "bindTabStripKeys" in main
    assert '"ArrowRight"' in main and '"ArrowLeft"' in main
    assert "updateOverflowFades" in main
    assert "M7 3h8l5 5v13" in main
    assert "M8 12h8M12 8v8" not in main
    style = (
        Path(__file__).resolve().parents[1]
        / "ui"
        / "mix_tabs_component"
        / "frontend"
        / "src"
        / "style.css"
    ).read_text(encoding="utf-8")
    assert "tab-progress" in style
    assert "mt-indeterminate" in style
    assert ".mix-tab-wrap.fade-right::after" in style
    assert ":focus-visible" in style
    close_css = style[style.find(".mix-tab .close {") :]
    close_rule = close_css[: close_css.find("}")]
    # Design constraint: close target at least 20x20, 28x28 preferred.
    assert "width: 28px" in close_rule and "height: 28px" in close_rule


def _frontend_src(name: str) -> str:
    return (
        Path(__file__).resolve().parents[1]
        / "ui"
        / "mix_tabs_component"
        / "frontend"
        / "src"
        / name
    ).read_text(encoding="utf-8")


def test_mix_tabs_source_has_reorder_and_no_toolbar_actions():
    main = _frontend_src("main.ts")
    # No duplicate / close-others / close-right toolbar (removed by preference).
    assert "data-tab-action" not in main
    assert "tab-actions" not in main
    assert 'aria-label="Close ${title}"' in main or "`Close ${title}`" in main
    # Drag reorder: only mix tabs drag, Home never does, a bad drop cancels.
    assert 'role="tab" draggable="true"' in main
    assert main.count('draggable="true"') == 1
    assert "bindTabStripDrag" in main
    assert 'report("reorder", id, to)' in main
    assert "ev.preventDefault();\n    if (ev.dataTransfer) ev.dataTransfer.dropEffect" in main
    # Keyboard alternative to drag.
    assert "ev.shiftKey" in main and 'ev.key === "ArrowLeft"' in main
    assert "Home is not a mix tab and never moves" in main
    assert '"role", "status"' in main and '"aria-live", "polite"' in main
    # The payload carries the target slot.
    assert "to?: number" in main and "payload.to = to" in main


def test_mix_tabs_style_keeps_one_row_and_a_visible_drop_mark():
    style = _frontend_src("style.css")
    # The host pins the iframe to 48px (ui/app.py), so the strip must not wrap.
    assert "flex-wrap: nowrap" in style
    assert ".tab-action" not in style
    assert ".tab-actions" not in style
    assert ".mix-tab.drop-before" in style and ".mix-tab.drop-after" in style
    assert ".mix-tab.dragging" in style
    assert ".sr-only" in style


def test_isolate_page_handles_every_mix_tab_action():
    page = (
        Path(__file__).resolve().parents[1] / "ui" / "pages" / "isolate.py"
    ).read_text(encoding="utf-8")
    strip = page[
        page.find("def _render_moises_tab_strip") : page.find("def _render_busy_tab_close_prompt")
    ]
    for needle in (
        'elif action == "reorder" and tab_id:',
        "move_open_mix_tab(",
    ):
        assert needle in strip, needle
    assert 'action == "duplicate"' not in strip
    assert "close_others" not in strip
    assert "close_right" not in strip
    # Reorder re-renders only the strip fragment, so the page does not jump.
    reorder_at = strip.find('elif action == "reorder"')
    reorder_end = strip.find("@st.fragment", reorder_at)
    reorder = strip[reorder_at:reorder_end]
    assert "_rerun_preserve_scroll()" in reorder
    assert "_rerun_scroll_top()" not in reorder
    assert "st.rerun()" not in strip
    # Closing from the strip never deletes a run from disk.
    assert "delete_library_run" not in strip
    assert "MIX_TAB_NOTICE_KEY" in page[page.find("def main") :]


def test_mix_tabs_strip_is_sticky_in_app_css():
    app = (
        Path(__file__).resolve().parents[1] / "ui" / "app.py"
    ).read_text(encoding="utf-8")
    assert "isolate_sticky_chrome" in app
    assert "isolate_mix_tabs_strip" in app
    assert "position: sticky" in app
    assert (
        '[data-testid="stLayoutWrapper"]:has(.st-key-isolate_sticky_chrome)'
        in app
    )
    assert (
        '[data-testid="stElementContainer"]:has(.st-key-isolate_sticky_chrome)'
        in app
    )
    assert (
        '[data-testid="stVerticalBlockBorderWrapper"]:has(.st-key-isolate_sticky_chrome)'
        in app
    )
    assert ":not(:last-of-type)" in app
    assert "isolate_region_picker" in app
    page = (
        Path(__file__).resolve().parents[1] / "ui" / "pages" / "isolate.py"
    ).read_text(encoding="utf-8")
    assert 'key="isolate_sticky_chrome"' in page
    assert 'key="isolate_mix_tabs_strip"' in page
    assert 'key="isolate_moises_tabs"' in page
    assert "_mix_tabs_nonce" not in page
    assert 'key="isolate_region_picker"' in page
    main = page[page.find("def main") :]
    chrome = main[main.find('key="isolate_sticky_chrome"') : main.find("_poll_running_jobs()")]
    assert "_mix_tab_strip_fragment" in chrome
    assert 'key="isolate_refresh"' in chrome
    assert "_queue_header_fragment()" in chrome
    assert "[6, 1.35, 1.2]" in chrome
    assert 'st.title("Audio Isolation"' not in chrome
    assert main.find('st.title("Audio Isolation"') < main.find('key="isolate_sticky_chrome"')
    assert main.find('st.title("Audio Isolation"') < main.find("_mix_tab_strip_fragment")
    assert main.find("_mix_tab_strip_fragment") < main.find("_queue_header_fragment()")
    assert main.find("_queue_header_fragment()") < main.find('key="isolate_refresh"')
    assert main.find("_mix_tab_strip_fragment") < main.find("_poll_running_jobs()")
    tab_frag = page[
        page.find("def _mix_tab_strip_fragment") : page.find("def _render_busy_tab_close_prompt")
    ]
    assert "_render_moises_tab_strip(" in tab_frag
