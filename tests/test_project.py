"""Tests for the mutable per-run project manifest (project.json)."""

from __future__ import annotations

import json
from pathlib import Path

from audio_to_tab.analysis import AnalysisResult, ChordEvent, Section, save_analysis
from ui.project import (
    PROJECT_FILENAME,
    SCHEMA_VERSION,
    default_project,
    load_analysis_for_run,
    load_project,
    load_tab_for_run,
    save_project,
    seed_mixer,
    update_from_mixer,
)


def _write_meta(run_dir: Path, *, title: str = "Song", fingerprint: str = "abc123") -> None:
    (run_dir / "meta.json").write_text(
        json.dumps({"title": title, "source_fingerprint": fingerprint}),
        encoding="utf-8",
    )


def test_default_project_has_every_player_field():
    project = default_project(title="Song", source_fingerprint="abc")
    assert project["schema_version"] == SCHEMA_VERSION
    assert project["title"] == "Song"
    assert project["source_fingerprint"] == "abc"
    assert project["mixer"] == {
        "volumesDb": {},
        "pan": {},
        "muted": {},
        "soloed": {},
        "masterVolumeDb": 0.0,
    }
    assert project["practice"] == {
        "rate": 1.0,
        "semitones": 0,
        "loop": None,
        "countInBars": 0,
    }
    assert project["analysis"] == "analysis.json"
    assert project["tab"] == "tab/tab.json"


def test_save_and_load_round_trip(tmp_path: Path):
    _write_meta(tmp_path, title="Waltz", fingerprint="fp-1")
    project = default_project(title="Waltz", source_fingerprint="fp-1")
    project["mixer"] = {
        "volumesDb": {"guitar": -3.5},
        "pan": {"guitar": -30},
        "muted": {"metronome": True},
        "soloed": {"guitar": True},
        "masterVolumeDb": -2.0,
    }
    project["practice"] = {
        "rate": 0.8,
        "semitones": -2,
        "loop": {"start": 12.0, "end": 20.5},
        "countInBars": 2,
    }

    assert save_project(tmp_path, project) is True
    loaded, warning = load_project(tmp_path)

    assert warning is None
    assert loaded["title"] == "Waltz"
    assert loaded["source_fingerprint"] == "fp-1"
    assert loaded["mixer"]["volumesDb"] == {"guitar": -3.5}
    assert loaded["mixer"]["pan"] == {"guitar": -30}
    assert loaded["mixer"]["muted"] == {"metronome": True}
    assert loaded["mixer"]["soloed"] == {"guitar": True}
    assert loaded["mixer"]["masterVolumeDb"] == -2.0
    assert loaded["practice"] == {
        "rate": 0.8,
        "semitones": -2,
        "loop": {"start": 12.0, "end": 20.5},
        "countInBars": 2,
    }


def test_missing_project_uses_meta_defaults(tmp_path: Path):
    _write_meta(tmp_path, title="Quiet Song", fingerprint="fp-2")
    project, warning = load_project(tmp_path)
    assert warning is None
    assert project["title"] == "Quiet Song"
    assert project["source_fingerprint"] == "fp-2"
    assert project["mixer"]["volumesDb"] == {}
    assert project["practice"]["loop"] is None
    assert not (tmp_path / PROJECT_FILENAME).exists()


def test_corrupt_project_warns_and_returns_defaults(tmp_path: Path):
    _write_meta(tmp_path)
    (tmp_path / PROJECT_FILENAME).write_text("{not json", encoding="utf-8")
    project, warning = load_project(tmp_path)
    assert warning is not None
    assert "unreadable" in warning
    assert project["schema_version"] == SCHEMA_VERSION
    assert project["title"] == "Song"


def test_non_object_project_warns_and_returns_defaults(tmp_path: Path):
    (tmp_path / PROJECT_FILENAME).write_text("[]", encoding="utf-8")
    project, warning = load_project(tmp_path)
    assert warning is not None
    assert "not an object" in warning
    assert project["mixer"]["masterVolumeDb"] == 0.0


def test_unsupported_schema_warns_and_returns_defaults(tmp_path: Path):
    (tmp_path / PROJECT_FILENAME).write_text(
        json.dumps({"schema_version": SCHEMA_VERSION + 99, "title": "Old"}),
        encoding="utf-8",
    )
    project, warning = load_project(tmp_path)
    assert warning is not None
    assert "not supported" in warning
    assert project["title"] == ""


def test_untrusted_values_are_clamped(tmp_path: Path):
    _write_meta(tmp_path)
    (tmp_path / PROJECT_FILENAME).write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "mixer": {
                    "volumesDb": {"guitar": 400, "bass": "loud"},
                    "pan": {"guitar": -400, "bass": 250},
                    "masterVolumeDb": -999,
                },
                "practice": {
                    "rate": 3.0,
                    "semitones": 99,
                    "countInBars": 9,
                    "loop": {"start": 10.0, "end": 10.2},
                },
            }
        ),
        encoding="utf-8",
    )
    project, warning = load_project(tmp_path)
    assert warning is None
    assert project["mixer"]["volumesDb"] == {"guitar": 25.0, "bass": 0.0}
    assert project["mixer"]["pan"] == {"guitar": -100, "bass": 100}
    assert project["mixer"]["masterVolumeDb"] == -25.0
    assert project["practice"]["rate"] == 1.5
    assert project["practice"]["semitones"] == 6
    assert project["practice"]["countInBars"] == 2
    assert project["practice"]["loop"] is None


def test_rate_snaps_to_component_grid(tmp_path: Path):
    _write_meta(tmp_path)
    (tmp_path / PROJECT_FILENAME).write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "practice": {"rate": 0.83},
            }
        ),
        encoding="utf-8",
    )
    project, _warning = load_project(tmp_path)
    assert project["practice"]["rate"] == 0.85


def test_save_only_writes_when_content_changes(tmp_path: Path):
    project = default_project(title="Song")
    assert save_project(tmp_path, project) is True
    path = tmp_path / PROJECT_FILENAME
    first = path.read_text(encoding="utf-8")

    assert save_project(tmp_path, project) is False
    assert path.read_text(encoding="utf-8") == first

    project["mixer"]["volumesDb"] = {"guitar": -6.0}
    assert save_project(tmp_path, project) is True
    assert path.read_text(encoding="utf-8") != first

    assert save_project(tmp_path, project, force=True) is True


def test_created_at_survives_later_saves(tmp_path: Path):
    project = default_project(title="Song")
    save_project(tmp_path, project)
    first, _warning = load_project(tmp_path)

    project["practice"]["rate"] = 0.75
    save_project(tmp_path, project)
    second, _warning = load_project(tmp_path)

    assert second["created_at"] == first["created_at"]
    assert second["updated_at"] >= first["updated_at"]
    assert second["practice"]["rate"] == 0.75


def test_update_from_mixer_copies_mixer_and_practice():
    project = default_project(title="Song")
    state = {
        "volumesDb": {"guitar": -1.25},
        "pan": {"guitar": 42.4},
        "muted": {"bass": True},
        "soloed": {"guitar": True},
        "masterVolumeDb": 3.0,
        "playbackRate": 0.75,
        "playbackSemitones": -3,
        "loop": {"start": 4.0, "end": 9.0},
        "countInBars": 1,
    }

    updated = update_from_mixer(project, state)

    assert updated is project
    assert updated["mixer"] == {
        "volumesDb": {"guitar": -1.25},
        "pan": {"guitar": 42},
        "muted": {"bass": True},
        "soloed": {"guitar": True},
        "masterVolumeDb": 3.0,
    }
    assert updated["practice"] == {
        "rate": 0.75,
        "semitones": -3,
        "loop": {"start": 4.0, "end": 9.0},
        "countInBars": 1,
    }


def test_update_from_mixer_ignores_non_dict_and_keeps_practice():
    project = default_project(title="Song")
    project["practice"]["rate"] = 0.9
    assert update_from_mixer(project, None) is project
    assert project["practice"]["rate"] == 0.9


def test_seed_mixer_returns_component_argument_names():
    project = default_project(title="Song")
    project["mixer"] = {
        "volumesDb": {"guitar": -2.0},
        "pan": {"guitar": -20},
        "muted": {"bass": True},
        "soloed": {"guitar": True},
        "masterVolumeDb": -1.0,
    }
    project["practice"] = {
        "rate": 0.85,
        "semitones": 2,
        "loop": {"start": 1.0, "end": 5.0},
        "countInBars": 2,
    }

    seed = seed_mixer(project)

    assert seed == {
        "initial_volumes_db": {"guitar": -2.0},
        "initial_muted": {"bass": True},
        "initial_soloed": {"guitar": True},
        "initial_pan": {"guitar": -20},
        "initial_master_volume_db": -1.0,
        "playback_rate": 0.85,
        "playback_semitones": 2,
        "initial_loop": {"start": 1.0, "end": 5.0},
        "count_in_bars": 2,
    }


def test_load_analysis_for_run_missing_is_none(tmp_path: Path):
    assert load_analysis_for_run(tmp_path) is None


def test_load_analysis_for_run_returns_json_dict(tmp_path: Path):
    result = AnalysisResult(
        duration_sec=30.0,
        bpm=92.0,
        key="G major",
        chords=(ChordEvent(start=0.0, end=4.0, symbol="G", confidence=0.0),),
        sections=(Section(start=0.0, end=30.0, label="verse", confidence=0.5),),
    )
    save_analysis(tmp_path / "analysis.json", result)

    payload = load_analysis_for_run(tmp_path)

    assert payload is not None
    assert payload["bpm"] == 92.0
    assert payload["key"] == "G major"
    assert payload["chords"][0]["symbol"] == "G"


def test_load_analysis_respects_project_path(tmp_path: Path):
    result = AnalysisResult(duration_sec=10.0, bpm=100.0)
    save_analysis(tmp_path / "custom-analysis.json", result)
    project = default_project()
    project["analysis"] = "custom-analysis.json"

    payload = load_analysis_for_run(tmp_path, project)

    assert payload is not None
    assert payload["bpm"] == 100.0


def test_load_analysis_ignores_corrupt_file(tmp_path: Path):
    (tmp_path / "analysis.json").write_text("{bad", encoding="utf-8")
    assert load_analysis_for_run(tmp_path) is None


def test_load_analysis_rejects_path_outside_run(tmp_path: Path):
    run = tmp_path / "run"
    run.mkdir()
    outside = tmp_path / "outside.json"
    save_analysis(outside, AnalysisResult(duration_sec=10.0, bpm=100.0))
    project = default_project()
    project["analysis"] = "../outside.json"
    assert load_analysis_for_run(run, project) is None


def test_load_tab_rejects_path_outside_run(tmp_path: Path):
    run = tmp_path / "run"
    run.mkdir()
    outside = tmp_path / "outside-tab.json"
    outside.write_text(json.dumps({"measures": [{"start": 0, "end": 2, "text": "x"}]}))
    project = default_project()
    project["tab"] = "../outside-tab.json"
    assert load_tab_for_run(run, project) is None


def test_load_tab_for_run_missing_or_empty_is_none(tmp_path: Path):
    assert load_tab_for_run(tmp_path) is None
    (tmp_path / "tab").mkdir()
    (tmp_path / "tab" / "tab.json").write_text("{}", encoding="utf-8")
    assert load_tab_for_run(tmp_path) is None


def test_load_tab_for_run_returns_measures_and_pdf_url(tmp_path: Path):
    (tmp_path / "tab").mkdir()
    payload = {
        "schema_version": 1,
        "document": {"title": "Song", "tuning": "standard"},
        "measures": [{"index": 1, "start": 0.0, "end": 2.0}],
    }
    (tmp_path / "tab" / "tab.json").write_text(json.dumps(payload), encoding="utf-8")

    tab = load_tab_for_run(tmp_path, pdf_url="/media/tab.pdf")

    assert tab is not None
    assert tab["document"] == {"title": "Song", "tuning": "standard"}
    assert tab["measures"] == [{"index": 1, "start": 0.0, "end": 2.0}]
    assert tab["pdfUrl"] == "/media/tab.pdf"
