"""Guitar tuning and fretboard utilities."""

from __future__ import annotations

from dataclasses import dataclass

STANDARD_TUNING_MIDI = (40, 45, 50, 55, 59, 64)  # E2 A2 D3 G3 B3 E4
STANDARD_TUNING_NAMES = ("E", "A", "D", "G", "B", "e")
GUITAR_PITCH_MIN = 40  # E2
GUITAR_PITCH_MAX = 88  # E6


@dataclass(frozen=True)
class FretPosition:
    string: int  # 0 = low E, 5 = high e
    fret: int
    pitch: int


def positions_for_pitch(pitch: int, tuning: tuple[int, ...] = STANDARD_TUNING_MIDI, max_fret: int = 24) -> list[FretPosition]:
    """All valid (string, fret) pairs for a MIDI pitch on a fretted instrument."""
    positions: list[FretPosition] = []
    for string_idx, open_pitch in enumerate(tuning):
        fret = pitch - open_pitch
        if 0 <= fret <= max_fret:
            positions.append(FretPosition(string=string_idx, fret=fret, pitch=pitch))
    return positions


def midi_note_name(pitch: int) -> str:
    names = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
    return f"{names[pitch % 12]}{pitch // 12 - 1}"
