"""Smoke tests for the live stem mixer Streamlit component packaging."""

from __future__ import annotations

import inspect
from pathlib import Path


def test_stem_mixer_build_present():
    from ui.stem_mixer_component import mixer_build_is_complete

    build = (
        Path(__file__).resolve().parents[1]
        / "ui"
        / "stem_mixer_component"
        / "frontend"
        / "build"
    )
    assert mixer_build_is_complete(build), (
        "Mixer frontend is incomplete. Run scripts/dev.ps1 mixer-build "
        "(or npm run build in ui/stem_mixer_component/frontend)"
    )


def test_mixer_build_is_complete_rejects_html_without_assets(tmp_path):
    from ui.stem_mixer_component import mixer_build_is_complete

    (tmp_path / "index.html").write_text(
        '<script type="module" src="./assets/index-missing.js"></script>',
        encoding="utf-8",
    )
    assert mixer_build_is_complete(tmp_path) is False


def test_stem_mixer_import():
    from ui.stem_mixer_component import component_build_available, stem_mixer

    assert component_build_available()
    assert callable(stem_mixer)


def test_stem_mixer_accepts_track_title():
    from ui.stem_mixer_component import stem_mixer

    params = inspect.signature(stem_mixer).parameters
    assert "track_title" in params
    assert params["track_title"].default == ""


def test_stem_mixer_accepts_master_volume():
    from ui.stem_mixer_component import stem_mixer

    params = inspect.signature(stem_mixer).parameters
    assert "initial_master_volume_db" in params
    assert params["initial_master_volume_db"].default == 0.0

