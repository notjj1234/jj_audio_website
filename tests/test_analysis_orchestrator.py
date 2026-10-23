"""Orchestrator tests: stage isolation, order, and graceful degradation."""

from __future__ import annotations

import json

from audio_to_tab.analysis import (
    AnalysisResult,
    BeatGrid,
    ChordEvent,
    LyricLine,
    LyricWord,
    Section,
    analysis_cache_key,
    analyze_audio,
)


def _grid() -> BeatGrid:
    return BeatGrid(
        bpm=120.0,
        bpm_confidence="high",
        beats=(0.0, 0.5, 1.0, 1.5),
        downbeats=(0.0,),
        beats_per_measure=4,
        warnings=(),
    )


def _patch_stages(monkeypatch, order: list[str]):
    def fake_grid(*args, **kwargs):
        order.append("beats")
        return _grid()

    def fake_chords(*args, **kwargs):
        order.append("chords")
        return [ChordEvent(0.0, 1.0, "C", 0.0)]

    def fake_key(*args, **kwargs):
        order.append("key")
        return "C", "high"

    def fake_sections(*args, **kwargs):
        order.append("sections")
        return [Section(0.0, 4.0, "Full song", 0.0)]

    def fake_lyrics(*args, **kwargs):
        order.append("lyrics")
        return (
            [
                LyricLine(
                    0.0,
                    1.0,
                    "hello",
                    (LyricWord(0.0, 1.0, "hello"),),
                )
            ],
            "en",
            [],
        )

    monkeypatch.setattr("audio_to_tab.analysis.build_beat_grid", fake_grid)
    monkeypatch.setattr("audio_to_tab.chords.detect_chords", fake_chords)
    monkeypatch.setattr("audio_to_tab.key.estimate_key", fake_key)
    monkeypatch.setattr("audio_to_tab.sections.detect_sections", fake_sections)
    monkeypatch.setattr("audio_to_tab.lyrics.transcribe_lyrics", fake_lyrics)


def test_stage_order_and_result(monkeypatch, tmp_path):
    order: list[str] = []
    _patch_stages(monkeypatch, order)

    result = analyze_audio(
        tmp_path / "song.wav",
        harmony_path=tmp_path / "no_vocals.wav",
        vocals_path=tmp_path / "vocals.wav",
        source_fingerprint="fp",
        duration_sec=4.0,
        include_lyrics=True,
    )

    assert order == ["beats", "chords", "key", "sections", "lyrics"]
    assert isinstance(result, AnalysisResult)
    assert result.bpm == 120.0
    assert result.key == "C"
    assert result.chords == (ChordEvent(0.0, 1.0, "C", 0.0),)
    assert result.sections == (Section(0.0, 4.0, "Full song", 0.0),)
    assert result.lyrics[0].text == "hello"
    assert result.lyrics_language == "en"
    assert result.models["chords"] == "template-viterbi-1"
    assert result.models["lyrics"] == "faster-whisper-small-int8"


def test_chord_failure_keeps_bpm_key_sections(monkeypatch, tmp_path):
    order: list[str] = []
    _patch_stages(monkeypatch, order)

    def fail(*args, **kwargs):
        raise RuntimeError("model exploded")

    monkeypatch.setattr("audio_to_tab.chords.detect_chords", fail)

    result = analyze_audio(
        tmp_path / "song.wav",
        source_fingerprint="fp",
        duration_sec=4.0,
        include_lyrics=False,
    )

    assert result.bpm == 120.0
    assert result.key == "C"
    assert result.sections
    assert result.chords == ()
    assert any("chord detection failed" in warning for warning in result.warnings)


def test_include_lyrics_false_does_not_call_lyrics(monkeypatch, tmp_path):
    order: list[str] = []
    _patch_stages(monkeypatch, order)

    def fail(*args, **kwargs):
        raise AssertionError("lyrics must not run")

    monkeypatch.setattr("audio_to_tab.lyrics.transcribe_lyrics", fail)

    result = analyze_audio(
        tmp_path / "song.wav",
        vocals_path=tmp_path / "vocals.wav",
        source_fingerprint="fp",
        duration_sec=4.0,
        include_lyrics=False,
    )

    assert "lyrics" not in order
    assert result.lyrics == ()
    assert result.models["lyrics"] == "disabled"


def test_no_vocals_stem_warns_without_calling_model(monkeypatch, tmp_path):
    order: list[str] = []
    _patch_stages(monkeypatch, order)

    def fail(*args, **kwargs):
        raise AssertionError("lyrics must not run without vocals")

    monkeypatch.setattr("audio_to_tab.lyrics.transcribe_lyrics", fail)

    result = analyze_audio(
        tmp_path / "song.wav",
        source_fingerprint="fp",
        duration_sec=4.0,
        include_lyrics=True,
    )

    assert any("no vocals" in warning.lower() for warning in result.warnings)
    assert result.models["lyrics"] == "no-vocals"


def test_lyrics_warnings_are_preserved(monkeypatch, tmp_path):
    order: list[str] = []
    _patch_stages(monkeypatch, order)

    monkeypatch.setattr(
        "audio_to_tab.lyrics.transcribe_lyrics",
        lambda *args, **kwargs: ([], None, ["no lyrics detected"]),
    )

    result = analyze_audio(
        tmp_path / "song.wav",
        vocals_path=tmp_path / "vocals.wav",
        source_fingerprint="fp",
        duration_sec=4.0,
    )

    assert "no lyrics detected" in result.warnings


def test_metronome_diagnostics_are_preferred(monkeypatch, tmp_path):
    diagnostics = tmp_path / "metronome_diagnostics.json"
    diagnostics.write_text(
        json.dumps(
            {
                "bpm": 100.0,
                "confidence": "high",
                "click_times_1x": [0.0, 0.6, 1.2, 1.8],
                "beats_per_measure": 4,
                "downbeat_sec": 0.0,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "audio_to_tab.tempo.estimate_tempo_from_audio",
        lambda path: (_ for _ in ()).throw(AssertionError("re-tracked")),
    )
    monkeypatch.setattr("audio_to_tab.chords.detect_chords", lambda *a, **k: [])
    monkeypatch.setattr("audio_to_tab.key.estimate_key", lambda *a, **k: (None, "low"))
    monkeypatch.setattr(
        "audio_to_tab.sections.detect_sections",
        lambda *a, **k: [Section(0.0, 2.0, "Full song", 0.0)],
    )

    result = analyze_audio(
        tmp_path / "song.wav",
        metronome_diagnostics=diagnostics,
        source_fingerprint="fp",
        duration_sec=2.0,
        include_lyrics=False,
    )

    assert result.bpm == 100.0
    assert result.beats == (0.0, 0.6, 1.2, 1.8)
    assert result.downbeats == (0.0,)
    assert result.beats_per_measure == 4
    assert result.bpm_confidence == "high"


def test_missing_audio_does_not_raise(tmp_path):
    result = analyze_audio(
        tmp_path / "nope.wav",
        source_fingerprint="fp",
        duration_sec=12.0,
        include_lyrics=False,
    )

    assert isinstance(result, AnalysisResult)
    assert result.sections
    assert result.sections[0].label == "Full song"
    assert result.warnings


def test_progress_messages_cover_each_stage(monkeypatch, tmp_path):
    order: list[str] = []
    _patch_stages(monkeypatch, order)
    messages: list[tuple[str, str]] = []

    analyze_audio(
        tmp_path / "song.wav",
        vocals_path=tmp_path / "vocals.wav",
        source_fingerprint="fp",
        duration_sec=4.0,
        include_lyrics=True,
        progress=lambda stage, message: messages.append((stage, message)),
    )

    assert messages
    assert all(stage == "analysis" for stage, _ in messages)
    text = " ".join(message.lower() for _, message in messages)
    assert "beat" in text
    assert "chord" in text
    assert "key" in text
    assert "section" in text
    assert "lyric" in text


def test_cache_key_is_stable_for_orchestrator_models(monkeypatch, tmp_path):
    order: list[str] = []
    _patch_stages(monkeypatch, order)

    result = analyze_audio(
        tmp_path / "song.wav",
        vocals_path=tmp_path / "vocals.wav",
        source_fingerprint="fp",
        duration_sec=4.0,
    )

    first = analysis_cache_key("fp", result.models, {"include_lyrics": True})
    second = analysis_cache_key("fp", result.models, {"include_lyrics": True})
    assert first == second


def test_source_fingerprint_and_duration_are_preserved(monkeypatch, tmp_path):
    order: list[str] = []
    _patch_stages(monkeypatch, order)

    result = analyze_audio(
        tmp_path / "song.wav",
        source_fingerprint="sha256:abc",
        duration_sec=123.5,
        include_lyrics=False,
    )

    assert result.source_fingerprint == "sha256:abc"
    assert result.duration_sec == 123.5
    assert result.schema_version == 1
