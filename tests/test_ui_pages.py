"""Page-logic unit tests for the Streamlit pages (pure helpers, not st.*).

The pages are guarded by ``if __name__ == "__main__"`` so a bare import
(resolved via ``ui.ensure_src_path()``) executes only definitions — Streamlit
runs the same file with ``__name__ == "__main__"`` and the page body still
renders (see streamlit.navigation.page.Page.run). Only import-safe helpers are
exercised here; anything that touches ``st.*`` or the fs-heavy engine is out of
scope for I-098.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def isolate_page():
    from ui.pages import isolate

    return isolate


@pytest.fixture(scope="module")
def tab_pdf_page():
    from ui.pages import tab_pdf

    return tab_pdf


@pytest.fixture(scope="module")
def app_module():
    import ui.app as app

    return app


def test_isolate_page_imports_without_running_main(isolate_page) -> None:
    assert callable(isolate_page.main)


def test_tab_pdf_page_imports_without_running_main(tab_pdf_page) -> None:
    assert callable(tab_pdf_page.main)


def test_app_page_icon_points_at_existing_file(app_module) -> None:
    icon = app_module._page_icon()
    if icon:
        assert Path(icon).is_file()


def test_artifact_fingerprint_is_order_independent(isolate_page) -> None:
    a = {"guitar": Path("x/g.wav"), "vocals": Path("x/v.wav")}
    b = {"vocals": Path("x/v.wav"), "guitar": Path("x/g.wav")}
    fa = isolate_page._artifact_fingerprint(a)
    assert fa == isolate_page._artifact_fingerprint(b)
    assert len(fa) == 16
    assert fa.isalnum()
    changed = {"guitar": Path("y/g.wav"), "vocals": Path("x/v.wav")}
    assert fa != isolate_page._artifact_fingerprint(changed)


def test_selection_fingerprint_aliases_artifact_fingerprint(isolate_page) -> None:
    stems = {"guitar": Path("a/g.wav"), "bass": Path("a/b.wav")}
    assert isolate_page._selection_fingerprint(stems) == isolate_page._artifact_fingerprint(stems)


def test_stem_paths_from_artifacts_filters_diagnostics_and_non_wav(isolate_page, tmp_path) -> None:
    guitar = tmp_path / "guitar.wav"
    vocals = tmp_path / "vocals.wav"
    midi = tmp_path / "out.mid"
    for p in (guitar, vocals, midi):
        p.write_bytes(b"\x00")
    artifacts = {
        "guitar": str(guitar),
        "vocals": str(vocals),
        "out_midi": str(midi),
        "stem_presence_diagnostics": str(tmp_path / "sp.json"),
        "bass_bleed_diagnostics": str(tmp_path / "bb.json"),
        "guitar_split_diagnostics": str(tmp_path / "gs.json"),
    }
    result = isolate_page._stem_paths_from_artifacts(artifacts)
    assert set(result) == {"guitar", "vocals"}
    assert all(p.suffix == ".wav" for p in result.values())


def test_load_guitar_split_diagnostics_returns_dict_or_empty(isolate_page, tmp_path) -> None:
    assert isolate_page._load_guitar_split_diagnostics({}) == {}
    good = tmp_path / "gs.json"
    good.write_text(json.dumps({"lead_present": True}), encoding="utf-8")
    assert isolate_page._load_guitar_split_diagnostics({"guitar_split_diagnostics": str(good)}) == {
        "lead_present": True
    }


def test_mixer_export_fingerprint_is_deterministic_and_sensitive(isolate_page) -> None:
    args = (["guitar", "bass"], {"guitar": -3.0, "bass": -6.0}, {}, {}, 0.0)
    f1 = isolate_page._mixer_export_fingerprint(*args)
    assert f1 == isolate_page._mixer_export_fingerprint(*args)
    louder = isolate_page._mixer_export_fingerprint(
        ["guitar", "bass"], {"guitar": 0.0, "bass": -6.0}, {}, {}, 0.0
    )
    assert f1 != louder


def test_speed_preset_labels_resolve(isolate_page) -> None:
    for preset_id in isolate_page.SPEED_PRESETS:
        label = isolate_page._speed_preset_radio_label(preset_id)
        assert isinstance(label, str) and label
    with pytest.raises(KeyError):
        isolate_page._speed_preset_radio_label("not-a-preset")


def test_stem_hints_cover_key_stems(isolate_page) -> None:
    assert {"piano", "guitar"} <= set(isolate_page.STEM_HINTS)