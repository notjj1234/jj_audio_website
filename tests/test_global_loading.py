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
