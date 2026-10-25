"""Bar chart built from an analysis result. No audio access."""

from __future__ import annotations

from dataclasses import dataclass

from audio_to_tab.analysis import AnalysisResult, LyricLine, Section

_METERS = (2, 3, 4, 6)


@dataclass(frozen=True)
class ChartCell:
    beat: int
    start: float
    end: float
    chord: str | None


@dataclass(frozen=True)
class ChartBar:
    index: int
    start: float
    end: float
    meter: int
    cells: tuple[ChartCell, ...]


@dataclass(frozen=True)
class ChartDocument:
    title: str
    key: str
    bpm: float
    time_signature: str
    bars: tuple[ChartBar, ...]
    sections: tuple[Section, ...]
    lyrics: tuple[LyricLine, ...]

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "key": self.key,
            "bpm": self.bpm,
            "time_signature": self.time_signature,
            "bars": [
                {
                    "index": bar.index,
                    "start": bar.start,
                    "end": bar.end,
                    "meter": bar.meter,
                    "cells": [
                        {
                            "beat": cell.beat,
                            "start": cell.start,
                            "end": cell.end,
                            "chord": cell.chord,
                        }
                        for cell in bar.cells
                    ],
                }
                for bar in self.bars
            ],
            "sections": [
                {
                    "start": section.start,
                    "end": section.end,
                    "label": section.label,
                    "confidence": section.confidence,
                }
                for section in self.sections
            ],
            "lyrics": [
                {
                    "start": line.start,
                    "end": line.end,
                    "text": line.text,
                    "words": [
                        {"start": word.start, "end": word.end, "text": word.text}
                        for word in line.words
                    ],
                }
                for line in self.lyrics
            ],
        }


def _meter(result: AnalysisResult) -> int:
    meter = int(result.beats_per_measure or 4)
    return meter if meter in _METERS else 4


def _beat_times(result: AnalysisResult) -> list[float]:
    duration = float(result.duration_sec or 0.0)
    times = sorted(
        {
            float(beat)
            for beat in result.beats
            if isinstance(beat, (int, float)) and 0.0 <= float(beat) < max(duration, float(beat)) + 1e-6
        }
    )
    if duration > 0:
        times = [beat for beat in times if beat <= duration + 1e-6]
    return times


def _bars_from_beats(times: list[float], meter: int, duration: float) -> list[tuple[float, float, list[tuple[float, float]]]]:
    if meter < 1 or len(times) < meter:
        return []
    complete = (len(times) // meter) * meter
    bars: list[tuple[float, float, list[tuple[float, float]]]] = []
    for offset in range(0, complete, meter):
        group = times[offset : offset + meter]
        spans: list[tuple[float, float]] = []
        for index, start in enumerate(group):
            if index + 1 < len(group):
                end = group[index + 1]
            elif offset + meter < len(times):
                end = times[offset + meter]
            else:
                end = duration if duration > start else start
            if end <= start:
                end = start + 1e-3
            spans.append((start, end))
        bars.append((spans[0][0], spans[-1][1], spans))
    return bars


def _symbol_at(chords: tuple, when: float) -> str | None:
    for chord in chords:
        if float(chord.start) - 1e-6 <= when < float(chord.end) - 1e-9:
            symbol = str(chord.symbol)
            if symbol.upper() == "N":
                return None
            return symbol
    return None


def _snap_section(section: Section, bar_starts: list[float]) -> Section:
    if not bar_starts:
        return section
    at_or_before = [start for start in bar_starts if start <= float(section.start) + 1e-6]
    start = at_or_before[-1] if at_or_before else bar_starts[0]
    return Section(
        start=float(start),
        end=float(section.end),
        label=section.label,
        confidence=float(section.confidence),
    )


def build_chart(result: AnalysisResult, *, title: str = "") -> ChartDocument:
    """One cell per beat. A chord is written only on the beat where it changes."""
    meter = _meter(result)
    duration = float(result.duration_sec or 0.0)
    grouped = _bars_from_beats(_beat_times(result), meter, duration)
    bars: list[ChartBar] = []
    previous: str | None = None
    for index, (start, end, spans) in enumerate(grouped):
        cells: list[ChartCell] = []
        for beat_index, (cell_start, cell_end) in enumerate(spans):
            symbol = _symbol_at(result.chords, cell_start)
            show: str | None = None
            if symbol and symbol != previous:
                show = symbol
            previous = None if symbol is None else symbol
            cells.append(ChartCell(beat=beat_index + 1, start=cell_start, end=cell_end, chord=show))
        bars.append(ChartBar(index=index, start=start, end=end, meter=meter, cells=tuple(cells)))
    bar_starts = [bar.start for bar in bars]
    sections = tuple(_snap_section(section, bar_starts) for section in result.sections)
    bpm = float(result.bpm or 0.0)
    return ChartDocument(
        title=title,
        key="" if result.key is None else str(result.key),
        bpm=bpm,
        time_signature=f"{meter}/4",
        bars=tuple(bars),
        sections=sections,
        lyrics=tuple(result.lyrics),
    )


__all__ = ["ChartBar", "ChartCell", "ChartDocument", "build_chart"]
