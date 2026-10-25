"""Sidebar chord card is the isolation mixer only."""

from __future__ import annotations

from pathlib import Path

from ui.pages.isolate import _sidebar_chord_seed, sidebar_chord_visible

_ROOT = Path(__file__).resolve().parents[1]


def test_sidebar_chord_visible_only_for_a_mix_with_chords():
    chords = [{"symbol": "Am", "start": 0.0, "end": 2.0}]
    assert sidebar_chord_visible("mix", "/tmp/song", {"chords": chords}) is True
    assert sidebar_chord_visible("home", "/tmp/song", {"chords": chords}) is False
    assert sidebar_chord_visible("mix", None, {"chords": chords}) is False
    assert sidebar_chord_visible("mix", "/tmp/song", {"chords": []}) is False
    assert sidebar_chord_visible("mix", "/tmp/song", None) is False


def test_sidebar_chord_seed_shows_the_first_real_name():
    assert _sidebar_chord_seed({"chords": [{"symbol": "N"}, {"symbol": "A#m"}]}) == "A#m"
    assert _sidebar_chord_seed({"chords": [{"symbol": "<Am>"}]}) == "&lt;Am&gt;"
    assert _sidebar_chord_seed({"chords": []}) == ""


def test_sidebar_chord_markup_is_not_on_the_shell_or_other_pages():
    isolate = (_ROOT / "ui" / "pages" / "isolate.py").read_text(encoding="utf-8")
    app = (_ROOT / "ui" / "app.py").read_text(encoding="utf-8")
    assert '<div class="att-sidebar-chord">' not in app
    assert 'data.source !== "att-sidebar-chord"' in app
    listener = app[app.find("function svgOk") : app.find("function paintChord")]
    assert "<svg" not in listener
    assert "</svg>" not in listener
    assert '"<" + "svg"' in listener
    assert "flex-direction: column" in isolate[isolate.find("_SIDEBAR_CHORD_HTML") : isolate.find("def _render_sidebar_chord")]
    assert "168px" in isolate
    assert "Next " not in isolate[isolate.find("_SIDEBAR_CHORD_HTML") : isolate.find("def _render_sidebar_chord")]
    assert "<script>" not in isolate[isolate.find("_SIDEBAR_CHORD_HTML") : isolate.find("def _render_sidebar_chord")]
    assert "def _render_sidebar_chord" in isolate
    workspace = isolate[isolate.find("def _render_mixer_workspace") : isolate.find("\ndef main(")]
    assert "_render_sidebar_chord(" in workspace
    for name in ("home.py", "youtube_audio.py", "tab_pdf.py", "settings.py"):
        assert "att-sidebar-chord" not in (_ROOT / "ui" / "pages" / name).read_text(encoding="utf-8")
