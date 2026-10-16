"""Empty / near-empty MIDI must abort Tab PDF before junk PDFs."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pretty_midi
import pytest

from audio_to_tab.pipeline import (
    EMPTY_TRANSCRIPTION_MESSAGE,
    EmptyTranscriptionError,
    MIN_USABLE_TAB_NOTES,
    PipelineConfig,
    _require_usable_transcription,
    count_midi_notes,
    run_pipeline,
)


def _write_midi(path: Path, note_count: int) -> None:
    pm = pretty_midi.PrettyMIDI()
    guitar = pretty_midi.Instrument(program=25)
    for i in range(note_count):
        t0 = float(i) * 0.25
        guitar.notes.append(pretty_midi.Note(90, 64 + (i % 5), t0, t0 + 0.2))
    pm.instruments.append(guitar)
    pm.write(str(path))


def test_count_midi_notes_and_min_usable_constant(tmp_path: Path):
    mid = tmp_path / "n.mid"
    _write_midi(mid, 2)
    assert count_midi_notes(mid) == 2
    assert MIN_USABLE_TAB_NOTES == 3


def test_require_usable_transcription_raises_when_near_empty(tmp_path: Path):
    mid = tmp_path / "emptyish.mid"
    _write_midi(mid, 2)
    with pytest.raises(EmptyTranscriptionError, match="Too few notes"):
        _require_usable_transcription(mid)


def test_require_usable_transcription_passes_at_threshold(tmp_path: Path):
    mid = tmp_path / "ok.mid"
    _write_midi(mid, 3)
    _require_usable_transcription(mid)


def test_run_pipeline_aborts_before_pdf_on_empty_midi(tmp_path: Path, monkeypatch):
    audio = tmp_path / "in.wav"
    audio.write_bytes(b"RIFF....")
    out = tmp_path / "out"
    out.mkdir()

    def fake_normalize(src, dest):
        Path(dest).write_bytes(b"wav")
        return Path(dest)

    def fake_transcribe(audio_path, midi_path, **kwargs):
        _write_midi(Path(midi_path), 0)

    tempo_mock = MagicMock()
    tempo_mock.bpm = 120.0
    tempo_mock.confidence = 0.5

    monkeypatch.setattr("audio_to_tab.pipeline.normalize_audio", fake_normalize)
    monkeypatch.setattr("audio_to_tab.pipeline.transcribe_audio", fake_transcribe)
    monkeypatch.setattr(
        "audio_to_tab.pipeline.resolve_tempo",
        lambda **kw: (_ for _ in ()).throw(AssertionError("tempo must not run")),
    )
    monkeypatch.setattr(
        "audio_to_tab.pipeline.midi_to_tab",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("tab must not run")),
    )
    monkeypatch.setattr(
        "audio_to_tab.pipeline.render_structured_tab_pdf",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("pdf must not run")),
    )

    with pytest.raises(EmptyTranscriptionError) as excinfo:
        run_pipeline(
            audio_path=audio,
            output_dir=out,
            config=PipelineConfig(separate_stems=False),
        )
    assert str(excinfo.value) == EMPTY_TRANSCRIPTION_MESSAGE
    assert not (out / "transcription.pdf").exists()
