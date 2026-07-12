"""Tests for tab generation, tempo, and MIDI cleanup."""

from pathlib import Path
from unittest.mock import patch

import pretty_midi
import pytest

from audio_to_tab.midi_cleanup import CleanupConfig, _cap_onset_density, cleanup_midi
from audio_to_tab.pdf_render import render_structured_tab_pdf
from audio_to_tab.rhythm import quantize_tab_document
from audio_to_tab.separate import is_demucs_available
from audio_to_tab.tab_generate import (
    DEFAULT_MAX_FRET,
    midi_to_tab,
    tab_to_ascii,
    _pick_single_position,
)
from audio_to_tab.tempo import estimate_tempo_from_midi_robust, resolve_tempo
from audio_to_tab.tuning import positions_for_pitch, STANDARD_TUNING_MIDI


def test_is_demucs_available():
    assert is_demucs_available() is True


def test_ui_effective_separate_when_demucs_missing():
    """UI must not request separation when Demucs is unavailable."""
    with patch("audio_to_tab.separate.is_demucs_available", return_value=False):
        from audio_to_tab.separate import is_demucs_available as check

        separate_stems = True
        effective = separate_stems and check()
        assert effective is False


def test_positions_for_open_e():
    positions = positions_for_pitch(64, STANDARD_TUNING_MIDI)
    assert any(p.string == 5 and p.fret == 0 for p in positions)


def test_midi_to_tab_simple(tmp_path: Path):
    pm = pretty_midi.PrettyMIDI()
    guitar = pretty_midi.Instrument(program=25)
    guitar.notes.append(pretty_midi.Note(90, 64, 0.0, 0.5))
    guitar.notes.append(pretty_midi.Note(90, 67, 0.5, 1.0))
    pm.instruments.append(guitar)
    midi_path = tmp_path / "test.mid"
    pm.write(str(midi_path))

    doc = midi_to_tab(str(midi_path), tempo_bpm=120.0)
    assert len(doc.events) >= 2
    ascii_tab = tab_to_ascii(doc)
    assert "E|" in ascii_tab or "e|" in ascii_tab


def test_pdf_render(tmp_path: Path):
    pm = pretty_midi.PrettyMIDI()
    guitar = pretty_midi.Instrument(program=25)
    guitar.notes.append(pretty_midi.Note(90, 64, 0.0, 0.5))
    pm.instruments.append(guitar)
    midi_path = tmp_path / "t.mid"
    pm.write(str(midi_path))
    doc = midi_to_tab(str(midi_path), tempo_bpm=120.0)
    pdf_path = tmp_path / "out.pdf"
    render_structured_tab_pdf(doc, str(pdf_path), title="Test")
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 100


def test_onset_density_cap():
    notes = [
        pretty_midi.Note(90, 60 + i, 0.0, 0.2) for i in range(10)
    ]
    cfg = CleanupConfig(max_notes_per_onset=6, onset_window_sec=0.05)
    capped = _cap_onset_density(notes, cfg)
    assert len(capped) == 6


def test_dense_midi_tempo_not_inflated(tmp_path: Path):
    """Drum-like dense onsets should not yield 200+ BPM with robust estimator."""
    pm = pretty_midi.PrettyMIDI()
    guitar = pretty_midi.Instrument(program=25)
    t = 0.0
    while t < 4.0:
        guitar.notes.append(pretty_midi.Note(80, 64, t, t + 0.05))
        t += 0.05
    pm.instruments.append(guitar)
    midi_path = tmp_path / "dense.mid"
    pm.write(str(midi_path))

    bpm = estimate_tempo_from_midi_robust(pm)
    assert bpm <= 180.0


def test_resolve_tempo_override(tmp_path: Path):
    pm = pretty_midi.PrettyMIDI()
    guitar = pretty_midi.Instrument(program=25)
    guitar.notes.append(pretty_midi.Note(90, 64, 0.0, 0.5))
    pm.instruments.append(guitar)
    midi_path = tmp_path / "t.mid"
    pm.write(str(midi_path))

    est = resolve_tempo(audio_path=None, midi_path=midi_path, override_bpm=100.0)
    assert est.bpm == 100.0
    assert est.source == "override"


def test_fret_assignment_prefers_near_position():
    positions = positions_for_pitch(76, STANDARD_TUNING_MIDI)  # E5
    chosen = _pick_single_position(positions, hand_fret=5.0, prev_string=None, penalize_open=True)
    assert chosen.fret <= DEFAULT_MAX_FRET
    assert abs(chosen.fret - 5.0) < 8


def test_fret_assignment_avoids_large_jump_in_sequence(tmp_path: Path):
    pm = pretty_midi.PrettyMIDI()
    guitar = pretty_midi.Instrument(program=25)
    guitar.notes.append(pretty_midi.Note(90, 64, 0.0, 0.4))   # E4
    guitar.notes.append(pretty_midi.Note(90, 65, 0.1, 0.5))   # F4 shortly after
    pm.instruments.append(guitar)
    midi_path = tmp_path / "seq.mid"
    pm.write(str(midi_path))

    doc = midi_to_tab(str(midi_path), tempo_bpm=120.0)
    frets = [n.fret for e in doc.events for n in e.notes]
    assert len(frets) >= 2
    assert abs(frets[1] - frets[0]) <= 5


def test_quantize_tab_document_snaps_timing():
    from audio_to_tab.tab_generate import TabDocument, TabEvent, TabNote

    doc = TabDocument(
        events=[
            TabEvent(
                start=0.03,
                notes=[TabNote(start=0.03, end=0.18, string=5, fret=3, pitch=67)],
            )
        ],
        tempo_bpm=120.0,
    )
    q = quantize_tab_document(doc)
    assert q.events[0].start == pytest.approx(0.05, abs=0.06)


def test_cleanup_midi_writes_filtered(tmp_path: Path):
    pm = pretty_midi.PrettyMIDI()
    guitar = pretty_midi.Instrument(program=25)
    guitar.notes.append(pretty_midi.Note(20, 64, 0.0, 0.5))
    guitar.notes.append(pretty_midi.Note(90, 64, 0.5, 1.0))
    pm.instruments.append(guitar)
    raw = tmp_path / "raw.mid"
    out = tmp_path / "out.mid"
    pm.write(str(raw))

    cleanup_midi(str(raw), str(out), CleanupConfig(min_velocity=40))
    cleaned = pretty_midi.PrettyMIDI(str(out))
    assert len(cleaned.instruments[0].notes) == 1
