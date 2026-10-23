"""Home screen: practice entry points and analysis status."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import soundfile as sf

from audio_to_tab.analysis import AnalysisResult, ChordEvent, Section, save_analysis
from ui.pages.home import analysis_line, analysis_summary


def _analysis_result() -> AnalysisResult:
    return AnalysisResult(
        duration_sec=64.0,
        bpm=92.4,
        key="G major",
        chords=(
            ChordEvent(start=0.0, end=4.0, symbol="G", confidence=0.0),
            ChordEvent(start=4.0, end=8.0, symbol="C", confidence=0.0),
        ),
        sections=(
            Section(start=0.0, end=32.0, label="verse", confidence=0.6),
            Section(start=32.0, end=64.0, label="chorus", confidence=0.6),
        ),
    )


def test_analysis_line_formats_bpm_key_and_sections():
    summary = {"bpm": 92, "key": "G major", "section_count": 4}
    assert analysis_line(summary) == "BPM 92 · G major · 4 sections"
    assert analysis_line({"bpm": 120.5, "key": None, "section_count": 1}) == (
        "BPM 120.5 · Key — · 1 section"
    )
    assert analysis_line(None) == "Not analysed yet"
    assert analysis_line({"section_count": 0}) == "BPM — · Key — · No sections"


def test_analysis_summary_prefers_meta_and_falls_back_to_analysis_json(tmp_path: Path):
    meta_summary = {"bpm": 100, "key": "C major", "section_count": 3}
    assert analysis_summary({"analysis": meta_summary}) == meta_summary

    path = tmp_path / "analysis.json"
    save_analysis(path, _analysis_result())
    row = {"artifacts": {"analysis": str(path)}}
    summary = analysis_summary(row)
    assert summary is not None
    assert summary["bpm"] == 92.4
    assert summary["key"] == "G major"
    assert summary["section_count"] == 2
    assert summary["chord_count"] == 2


def test_analysis_summary_ignores_missing_or_corrupt_files(tmp_path: Path):
    assert analysis_summary({"artifacts": {"analysis": str(tmp_path / "nope.json")}}) is None
    bad = tmp_path / "analysis.json"
    bad.write_text("{bad", encoding="utf-8")
    assert analysis_summary({"artifacts": {"analysis": str(bad)}}) is None
    assert analysis_summary({}) is None


def test_home_source_has_learn_practice_and_analyse_actions():
    source = (
        Path(__file__).resolve().parents[1] / "ui" / "pages" / "home.py"
    ).read_text(encoding="utf-8")
    assert "Learn a song" in source
    assert '"Practice"' in source
    assert '"Analyse"' in source
    assert "analysis_line(" in source
    assert "open_practice_run(" in source
    assert "analyse_existing_run(" in source
    # The existing flows stay put.
    assert "youtube_audio.py" in source
    assert "tab_pdf.py" in source


def test_analyse_existing_run_updates_meta(tmp_path: Path, monkeypatch):
    import ui.isolate_jobs as jobs

    wav = tmp_path / "no_vocals.wav"
    sf.write(str(wav), np.zeros(1000, dtype=np.float32), 44100)
    meta = {
        "page": "isolate",
        "title": "Song",
        "source_fingerprint": "fp",
        "artifacts": {"no_vocals": str(wav)},
    }
    (tmp_path / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

    result = _analysis_result()

    def fake_stage(run_dir, artifacts, **_kwargs):
        path = save_analysis(Path(run_dir) / "analysis.json", result)
        diagnostics = Path(run_dir) / "analysis_diagnostics.json"
        diagnostics.write_text("{}", encoding="utf-8")
        return result, path, diagnostics, "draft quality"

    monkeypatch.setattr(jobs, "worker_busy", lambda: False)
    monkeypatch.setattr(jobs, "_run_analysis_stage", fake_stage)

    ok, message = jobs.analyse_existing_run(tmp_path)

    assert ok is True
    assert message.startswith("Analysis ready with warnings:")
    assert "draft quality" in message
    updated = json.loads((tmp_path / "meta.json").read_text(encoding="utf-8"))
    assert updated["analysis"]["bpm"] == 92.4
    assert updated["analysis"]["key"] == "G major"
    assert updated["analysis"]["section_count"] == 2
    assert updated["artifacts"]["analysis"].endswith("analysis.json")
    assert updated["artifacts"]["analysis_diagnostics"].endswith(
        "analysis_diagnostics.json"
    )


def test_analyse_existing_run_refuses_busy_worker(tmp_path: Path, monkeypatch):
    import ui.isolate_jobs as jobs

    monkeypatch.setattr(jobs, "worker_busy", lambda: True)
    ok, message = jobs.analyse_existing_run(tmp_path)
    assert ok is False
    assert "separation" in message


def test_analyse_existing_run_requires_meta_and_a_stem(tmp_path: Path, monkeypatch):
    import ui.isolate_jobs as jobs

    monkeypatch.setattr(jobs, "worker_busy", lambda: False)
    ok, message = jobs.analyse_existing_run(tmp_path)
    assert ok is False
    assert "meta.json" in message

    (tmp_path / "meta.json").write_text(json.dumps({"artifacts": {}}), encoding="utf-8")
    ok, message = jobs.analyse_existing_run(tmp_path)
    assert ok is False
    assert "stem" in message


def test_home_v2_is_the_default(monkeypatch):
    from ui.design_tokens import ui_v2_enabled

    monkeypatch.delenv("AUDIO_TOOLS_UI_V2", raising=False)
    assert ui_v2_enabled() is True
    monkeypatch.setenv("AUDIO_TOOLS_UI_V2", "0")
    assert ui_v2_enabled() is False


def test_home_v2_props_have_no_run_dir():
    import json

    from ui.pages.home import build_home_props

    secret = "/tmp/secret/song"
    props = build_home_props(rows=[{"run_dir": secret, "title": "x"}])
    encoded = json.dumps(props)
    assert "run_dir" not in encoded
    assert secret not in encoded
    assert props["rows"][0]["token"]
    assert props["rows"][0]["action"] == "analyse"
    assert props["cards"][0]["id"] == "learn"


def test_home_muted_token_clears_contrast():
    from ui.design_tokens import HOME_BG, HOME_TEXT_MUTED, contrast_ratio, home_flag_css

    css = home_flag_css()
    assert "width: 240px" in css
    assert "font-weight: 400" in css
    assert "font-weight: 600" not in css
    assert "att-shell-v2" in css
    assert 'stSidebar"]' in css
    assert "overflow: hidden" in css
    assert contrast_ratio(HOME_TEXT_MUTED, HOME_BG) >= 4.5
    assert contrast_ratio("#F4F7FB", HOME_BG) >= 4.5


def test_home_v2_keeps_the_legacy_path():
    source = (
        Path(__file__).resolve().parents[1] / "ui" / "pages" / "home.py"
    ).read_text(encoding="utf-8")
    assert "def _main_legacy" in source
    assert "st.title(product, anchor=False)" in source
    assert "ui_v2_enabled()" in source
    frontend = (
        Path(__file__).resolve().parents[1]
        / "ui"
        / "home_component"
        / "frontend"
        / "src"
        / "main.ts"
    ).read_text(encoding="utf-8")
    assert "run_dir" not in frontend
    assert "No songs yet." in frontend
    assert "No songs match that search." in frontend
    assert "#F6AD49" in frontend
    assert "#75EBF5" not in frontend
    assert "#E9EEF5" not in frontend

