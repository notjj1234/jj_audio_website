"""MIDI note cleanup after pitch detection."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pretty_midi

from audio_to_tab.tuning import GUITAR_PITCH_MAX, GUITAR_PITCH_MIN


@dataclass
class CleanupConfig:
    min_velocity: int = 40
    min_duration_sec: float = 0.05
    pitch_min: int = GUITAR_PITCH_MIN
    pitch_max: int = GUITAR_PITCH_MAX
    quantize_sec: float | None = 0.05  # None to skip quantization
    max_notes_per_onset: int = 6
    onset_window_sec: float = 0.05


def mix_aware_cleanup_config() -> CleanupConfig:
    """Stricter filters for full-mix / stem-separated guitar transcription."""
    return CleanupConfig(
        min_velocity=55,
        min_duration_sec=0.08,
        quantize_sec=0.05,
        max_notes_per_onset=6,
        onset_window_sec=0.05,
    )


def solo_guitar_cleanup_config() -> CleanupConfig:
    """Default filters for clean solo guitar input."""
    return CleanupConfig()


def _cap_onset_density(notes: list[pretty_midi.Note], cfg: CleanupConfig) -> list[pretty_midi.Note]:
    """Keep at most max_notes_per_onset notes per onset window (highest velocity)."""
    if not notes or cfg.max_notes_per_onset <= 0:
        return notes

    sorted_notes = sorted(notes, key=lambda n: (n.start, -n.velocity, n.pitch))
    kept: list[pretty_midi.Note] = []
    window_start = -1.0
    window_notes: list[pretty_midi.Note] = []

    def flush_window() -> None:
        nonlocal window_notes
        if not window_notes:
            return
        window_notes.sort(key=lambda n: (-n.velocity, n.pitch))
        kept.extend(window_notes[: cfg.max_notes_per_onset])
        window_notes = []

    for note in sorted_notes:
        if not window_notes or note.start - window_start <= cfg.onset_window_sec:
            if not window_notes:
                window_start = note.start
            window_notes.append(note)
        else:
            flush_window()
            window_start = note.start
            window_notes = [note]

    flush_window()
    return sorted(kept, key=lambda n: (n.start, n.pitch))


def cleanup_midi(
    midi_path: str,
    output_path: str,
    config: CleanupConfig | None = None,
) -> str:
    """Filter ghost notes and quantize timing in a MIDI file."""
    cfg = config or CleanupConfig()
    pm = pretty_midi.PrettyMIDI(midi_path)

    for instrument in pm.instruments:
        kept: list[pretty_midi.Note] = []
        for note in instrument.notes:
            if note.velocity < cfg.min_velocity:
                continue
            if note.end - note.start < cfg.min_duration_sec:
                continue
            if note.pitch < cfg.pitch_min or note.pitch > cfg.pitch_max:
                continue
            if cfg.quantize_sec:
                note.start = round(note.start / cfg.quantize_sec) * cfg.quantize_sec
                note.end = max(
                    note.start + cfg.min_duration_sec,
                    round(note.end / cfg.quantize_sec) * cfg.quantize_sec,
                )
            kept.append(note)
        instrument.notes = _cap_onset_density(kept, cfg)

    pm.write(output_path)
    return output_path


def merge_instruments_to_one(pm: pretty_midi.PrettyMIDI) -> pretty_midi.PrettyMIDI:
    """Collapse all tracks into a single guitar instrument."""
    all_notes: list[pretty_midi.Note] = []
    for inst in pm.instruments:
        if not inst.is_drum:
            all_notes.extend(inst.notes)

    merged = pretty_midi.PrettyMIDI()
    guitar = pretty_midi.Instrument(program=25, name="Guitar")
    guitar.notes = sorted(all_notes, key=lambda n: (n.start, n.pitch))
    merged.instruments.append(guitar)
    return merged


def estimate_tempo_bpm(pm: pretty_midi.PrettyMIDI) -> float:
    """Estimate tempo from MIDI; default 120 if unknown."""
    try:
        tempo = pm.estimate_tempo()
        if tempo and not np.isnan(tempo):
            return float(tempo)
    except Exception:
        pass
    return 120.0
