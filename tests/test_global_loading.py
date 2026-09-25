"""Tests for the desktop global loading overlay gate.

The overlay is a window-wide scrim, so it may only appear when the window really
is unusable. That is true for exactly one moment: a cross-page navigation, for a
single rerun. Everything else — running jobs, tab switches, widget reruns — keeps
the app interactive and is reported in place.
"""

from __future__ import annotations

from ui.common import should_show_global_loading


def test_overlay_shows_for_cross_page_navigation() -> None:
    assert should_show_global_loading(nav_requested=True) is True


def test_overlay_hidden_when_nothing_is_navigating() -> None:
    assert should_show_global_loading(nav_requested=False) is False


def test_running_job_does_not_dim_the_window() -> None:
    """A separation runs in the background and the app stays clickable.

    Dimming the whole window here advertises a freeze that is not happening;
    the isolate status strip reports job state instead.
    """
    assert should_show_global_loading(nav_requested=False) is False


def test_tab_change_alone_does_not_dim_the_window() -> None:
    """New/Mixer/Queue switches are not navigation and are not overlay inputs."""
    assert should_show_global_loading(nav_requested=False) is False


def test_lite_pro_switch_dims_the_window_with_a_gear() -> None:
    """Switching Interface blocks the window until that rerun finishes."""
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "ui" / "app.py").read_text(
        encoding="utf-8"
    )
    persist = source[source.find("def _persist_mode") : source.find("st.sidebar.radio")]
    assert '["_ui_mode_switching"] = True' in persist
    assert "audiotools-mode-switch" in source
    assert "audiotools-gear" in source
    assert "html:has(.audiotools-mode-switch) body *" in source
    assert "pointer-events: none !important" in source
    # st.html strips <script>, so dismissal must be server-side, not JS.
    overlay = source[source.find("_MODE_SWITCH_HTML = ") :]
    overlay = overlay[: overlay.find('"""', overlay.find('"""') + 3)]
    assert "<script" not in overlay
    run_at = source.find("try:\n    pg.run()")
    assert source.find("_mode_switch_slot.html(_MODE_SWITCH_HTML)") < run_at
    assert run_at < source.find("_mode_switch_slot.empty()")
    assert "finally:" in source[run_at : source.find("_mode_switch_slot.empty()")]


def test_enqueue_does_not_request_nav_overlay() -> None:
    """Separate / Add to queue must not raise the window-wide nav scrim."""
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1] / "ui" / "pages" / "isolate.py"
    ).read_text(encoding="utf-8")
    enqueue = source[
        source.find("def _enqueue_confirmed_job") : source.find("def _library_status_row")
    ]
    assert "_request_loading_overlay()" not in enqueue
    assert '["_nav_loading"]' not in enqueue
    carry = source[
        source.find("Make a tab PDF from this") : source.find("def _render_file_ready_banner")
    ]
    assert "_request_loading_overlay()" in carry
