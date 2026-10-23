"""Contract tests for the versioned analysis JSON."""

from __future__ import annotations

import json

import pytest

from audio_to_tab.analysis import (
    SCHEMA_VERSION,
    AnalysisResult,
    ChordEvent,
    LyricLine,
    LyricWord,
    Section,
    analysis_cache_key,
    build_beat_grid,
    load_analysis,
    save_analysis,
)
from audio_to_tab.tempo import TempoEstimate


def _full_result() -> AnalysisResult:
    return AnalysisResult(
        source_fingerprint="sha256:abc",
        duration_sec=120.0,
        bpm=92.5,
        bpm_confidence="high",
        key="E",
        key_confidence="medium",
        beats=(0.5, 1.0, 1.5),
        downbeats=(0.5,),
        beats_per_measure=4,
        chords=(
            ChordEvent(start=0.5, end=1.5, symbol="E", confidence=0.82),
            ChordEvent(start=1.5, end=3.0, symbol="A", confidence=0.71),
        ),
        sections=(
            Section(start=0.0, end=30.0, label="Intro", confidence=0.6),
            Section(start=30.0, end=90.0, label="Verse", confidence=0.55),
        ),
        lyrics=(
            LyricLine(
                start=10.0,
                end=12.0,
                text="hello world",
                words=(
                    LyricWord(start=10.0, end=10.5, text="hello"),
                    LyricWord(start=10.6, end=11.2, text="world"),
                ),
            ),
        ),
        lyrics_language="en",
        models={"chords": "viterbi-1", "lyrics": "fw-small-1"},
        warnings=("chord labels are a draft",),
        created_at=123.0,
    )


def test_round_trip(tmp_path):
    path = tmp_path / "analysis.json"
    result = _full_result()

    saved = save_analysis(path, result)
    loaded = load_analysis(path)

    assert saved == path
    assert loaded == result
    assert loaded is not None
    assert loaded.lyrics[0].words[0].text == "hello"


def test_missing_file_returns_none(tmp_path):
    assert load_analysis(tmp_path / "missing.json") is None


def test_unknown_schema_version_returns_none(tmp_path, caplog):
    path = tmp_path / "analysis.json"
    path.write_text(json.dumps({"schema_version": 999}), encoding="utf-8")

    with caplog.at_level("WARNING"):
        assert load_analysis(path) is None
    assert "schema" in caplog.text.lower()


def test_invalid_json_returns_none(tmp_path):
    path = tmp_path / "analysis.json"
    path.write_text("{not json", encoding="utf-8")
    assert load_analysis(path) is None


def test_minimal_payload_gets_defaults(tmp_path):
    path = tmp_path / "analysis.json"
    path.write_text(json.dumps({"schema_version": SCHEMA_VERSION}), encoding="utf-8")

    result = load_analysis(path)

    assert result is not None
    assert result.duration_sec == 0.0
    assert result.beats == ()
    assert result.chords == ()
    assert result.beats_per_measure == 4
    assert result.models == {}


def test_malformed_events_are_dropped_individually(tmp_path):
    path = tmp_path / "analysis.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "duration_sec": 10.0,
                "chords": [
                    {"start": 0.0, "end": 1.0, "symbol": "C", "confidence": 0.9},
                    {"start": 1.0, "end": 2.0, "confidence": 0.8},
                    {"start": 3.0, "end": 2.0, "symbol": "G", "confidence": 0.5},
                    {"start": "x", "end": 2.0, "symbol": "A", "confidence": 0.5},
                ],
                "sections": [
                    {"start": 0.0, "end": 5.0, "label": "Intro", "confidence": 0.6},
                    {"start": 5.0, "end": 4.0, "label": "Broken", "confidence": 0.6},
                ],
                "lyrics": [
                    {
                        "start": 0.0,
                        "end": 1.0,
                        "text": "ok",
                        "words": [
                            {"start": 0.0, "end": 0.5, "text": "ok"},
                            {"start": 2.0, "end": 1.0, "text": "bad"},
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    result = load_analysis(path)

    assert result is not None
    assert [c.symbol for c in result.chords] == ["C"]
    assert [s.label for s in result.sections] == ["Intro"]
    assert [w.text for w in result.lyrics[0].words] == ["ok"]


def test_events_are_sorted(tmp_path):
    path = tmp_path / "analysis.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "chords": [
                    {"start": 2.0, "end": 3.0, "symbol": "G", "confidence": 0.9},
                    {"start": 0.0, "end": 1.0, "symbol": "C", "confidence": 0.9},
                ],
                "sections": [
                    {"start": 10.0, "end": 20.0, "label": "Chorus", "confidence": 0.9},
                    {"start": 0.0, "end": 10.0, "label": "Verse", "confidence": 0.9},
                ],
            }
        ),
        encoding="utf-8",
    )

    result = load_analysis(path)

    assert result is not None
    assert [c.symbol for c in result.chords] == ["C", "G"]
    assert [s.label for s in result.sections] == ["Verse", "Chorus"]


def test_cache_key_is_deterministic_and_sensitive():
    first = analysis_cache_key("fp", {"b": "2", "a": "1"}, {"x": 1, "y": 2})
    reordered = analysis_cache_key("fp", {"a": "1", "b": "2"}, {"y": 2, "x": 1})

    assert first == reordered
    assert len(first) == 64
    assert first != analysis_cache_key("fp2", {"a": "1", "b": "2"}, {"x": 1, "y": 2})
    assert first != analysis_cache_key("fp", {"a": "9", "b": "2"}, {"x": 1, "y": 2})
    assert first != analysis_cache_key("fp", {"a": "1", "b": "2"}, {"x": 9, "y": 2})


def test_saved_json_is_plain(tmp_path):
    path = tmp_path / "analysis.json"
    save_analysis(path, _full_result())

    data = json.loads(path.read_text(encoding="utf-8"))

    assert data["schema_version"] == SCHEMA_VERSION
    assert isinstance(data["chords"], list)
    assert isinstance(data["lyrics"][0]["words"], list)
    assert data["beats"] == [0.5, 1.0, 1.5]
    assert data["models"]["chords"] == "viterbi-1"


def test_save_creates_parent_directory(tmp_path):
    path = tmp_path / "nested" / "analysis.json"
    save_analysis(path, AnalysisResult())
    assert path.is_file()
    assert load_analysis(path) is not None


def test_invalid_cache_inputs_still_hash():
    key = analysis_cache_key("", {}, {})
    assert len(key) == 64
    assert isinstance(key, str)


def _diagnostics(**overrides):
    payload = {
        "bpm": 120.0,
        "confidence": "high",
        "click_times_1x": [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0],
        "beats_per_measure": 4,
        "downbeat_sec": 1.0,
    }
    payload.update(overrides)
    return payload


def test_beat_grid_prefers_stored_diagnostics(monkeypatch, tmp_path):
    def fail(*args, **kwargs):
        raise AssertionError("stored diagnostics must not re-track")

    monkeypatch.setattr("audio_to_tab.tempo.estimate_tempo_from_audio", fail)

    grid = build_beat_grid(
        tmp_path / "unused.wav",
        _diagnostics(),
        duration_sec=3.6,
    )

    assert grid.bpm == 120.0
    assert grid.bpm_confidence == "high"
    assert grid.beats == (0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5)
    assert grid.downbeats == (1.0, 3.0)
    assert grid.beats_per_measure == 4
    assert grid.warnings == ()
    assert list(grid.beats) == sorted(grid.beats)
    assert all(0.0 <= t <= 3.6 for t in grid.beats)


def test_beat_grid_downbeat_off_grid_is_not_invented():
    grid = build_beat_grid(None, _diagnostics(downbeat_sec=1.35), duration_sec=3.6)

    assert grid.downbeats == ()
    assert any("downbeat" in warning for warning in grid.warnings)


def test_beat_grid_missing_downbeat_is_empty():
    payload = _diagnostics()
    del payload["downbeat_sec"]

    grid = build_beat_grid(None, payload, duration_sec=3.6)

    assert grid.downbeats == ()
    assert any("downbeat" in warning for warning in grid.warnings)


def test_beat_grid_falls_back_to_single_grid(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "audio_to_tab.tempo.estimate_tempo_from_audio",
        lambda path: TempoEstimate(bpm=120.0, confidence="high", source="audio"),
    )

    grid = build_beat_grid(tmp_path / "song.wav", None, duration_sec=2.0)

    assert grid.bpm == 120.0
    assert grid.bpm_confidence == "low"
    assert grid.beats == (0.0, 0.5, 1.0, 1.5, 2.0)
    assert grid.downbeats == ()
    assert any("low confidence" in warning for warning in grid.warnings)


def test_beat_grid_fallback_without_tempo(monkeypatch, tmp_path):
    monkeypatch.setattr("audio_to_tab.tempo.estimate_tempo_from_audio", lambda path: None)

    grid = build_beat_grid(tmp_path / "song.wav", None, duration_sec=2.0)

    assert grid.bpm is None
    assert grid.beats == ()
    assert any("tempo estimation failed" in warning for warning in grid.warnings)


def test_beat_grid_malformed_diagnostics_falls_back(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "audio_to_tab.tempo.estimate_tempo_from_audio",
        lambda path: TempoEstimate(bpm=100.0, confidence="high", source="audio"),
    )

    grid = build_beat_grid(
        tmp_path / "song.wav",
        {"bpm": "x", "click_times_1x": "nope"},
        duration_sec=1.0,
    )

    assert grid.bpm == 100.0
    assert grid.beats == (0.0, 0.6)


def test_beat_grid_single_beat_falls_back(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "audio_to_tab.tempo.estimate_tempo_from_audio",
        lambda path: TempoEstimate(bpm=120.0, confidence="high", source="audio"),
    )

    grid = build_beat_grid(
        tmp_path / "song.wav",
        {"click_times_1x": [0.5], "bpm": 120.0},
        duration_sec=1.0,
    )

    assert grid.beats == (0.0, 0.5, 1.0)
    assert grid.bpm_confidence == "low"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
