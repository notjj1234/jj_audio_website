"""Smoke tests for the live stem mixer Streamlit component packaging."""

from __future__ import annotations

from pathlib import Path


def test_stem_mixer_build_present():
    build = (
        Path(__file__).resolve().parents[1]
        / "ui"
        / "stem_mixer_component"
        / "frontend"
        / "build"
        / "index.html"
    )
    assert build.is_file(), "Run scripts/dev.ps1 mixer-build (or npm run build in frontend/)"


def test_stem_mixer_import():
    from ui.stem_mixer_component import component_build_available, stem_mixer

    assert component_build_available()
    assert callable(stem_mixer)
