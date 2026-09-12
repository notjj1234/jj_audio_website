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
    assert "seq:" in main or "seq =" in main
    assert "mix-tab-bar" in main or "Home" in main
    assert "tab-progress" in main
    assert "aria-busy" in main
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


def test_mix_tabs_strip_is_sticky_in_app_css():
    app = (
        Path(__file__).resolve().parents[1] / "ui" / "app.py"
    ).read_text(encoding="utf-8")
    assert "isolate_mix_tabs_strip" in app
    assert "position: sticky" in app
    assert ":not(:last-of-type)" in app
    assert "isolate_region_picker" in app
    page = (
        Path(__file__).resolve().parents[1] / "ui" / "pages" / "isolate.py"
    ).read_text(encoding="utf-8")
    assert 'key="isolate_mix_tabs_strip"' in page
    assert 'key="isolate_moises_tabs"' in page
    assert "_mix_tabs_nonce" not in page
    assert 'key="isolate_region_picker"' in page
