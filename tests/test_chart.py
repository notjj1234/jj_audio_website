"""Chart document: one cell per beat, symbols only where the harmony changes."""

from __future__ import annotations

from audio_to_tab.analysis import AnalysisResult, ChordEvent, Section
from audio_to_tab.chart import build_chart


def _result(**overrides) -> AnalysisResult:
    beats = tuple(index * 0.5 for index in range(12))
    payload = {
        "duration_sec": 6.0,
        "bpm": 120.0,
        "key": "C",
        "beats": beats,
        "beats_per_measure": 4,
        "chords": (ChordEvent(0.0, 6.0, "C", 0.9),),
    }
    payload.update(overrides)
    return AnalysisResult(**payload)


def test_three_four_gives_three_cells():
    document = build_chart(_result(beats_per_measure=3, key="G"))

    assert document.time_signature == "3/4"
    assert document.bars
    assert all(len(bar.cells) == 3 for bar in document.bars)
    assert len(document.bars) == 4


def test_chord_only_on_change():
    document = build_chart(
        _result(
            duration_sec=4.0,
            beats=tuple(index * 0.5 for index in range(8)),
            chords=(
                ChordEvent(0.0, 2.0, "C", 0.9),
                ChordEvent(2.0, 4.0, "G", 0.8),
            ),
        )
    )

    symbols = [cell.chord for bar in document.bars for cell in bar.cells]
    assert symbols == ["C", None, None, None, "G", None, None, None]


def test_sections_align_to_bar_starts():
    document = build_chart(
        _result(
            sections=(Section(start=0.25, end=4.0, label="Verse", confidence=0.7),),
        )
    )

    assert document.sections[0].start == document.bars[0].start
    assert document.sections[0].label == "Verse"
