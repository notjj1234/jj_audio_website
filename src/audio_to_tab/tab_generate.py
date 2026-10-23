"""MIDI to ASCII guitar tablature via playability-aware fret assignment."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import pretty_midi

from audio_to_tab.tuning import (
    STANDARD_TUNING_MIDI,
    STANDARD_TUNING_NAMES,
    FretPosition,
    positions_for_pitch,
)


@dataclass
class TabNote:
    start: float
    end: float
    string: int
    fret: int
    pitch: int


@dataclass
class TabEvent:
    start: float
    notes: list[TabNote] = field(default_factory=list)


@dataclass
class TabDocument:
    events: list[TabEvent]
    tuning_names: tuple[str, ...] = STANDARD_TUNING_NAMES
    tempo_bpm: float = 120.0
    tempo_confidence: str = "high"
    beats_per_measure: int = 4


DEFAULT_MAX_FRET = 15
MAX_FRET_JUMP = 4
OPEN_STRING_PENALTY_THRESHOLD = 3.0
STRING_CHANGE_COST = 2.0


def _group_notes_into_events(notes: list[pretty_midi.Note], chord_threshold_sec: float = 0.03) -> list[list[pretty_midi.Note]]:
    """Group simultaneous notes into chord events."""
    if not notes:
        return []
    sorted_notes = sorted(notes, key=lambda n: (n.start, n.pitch))
    groups: list[list[pretty_midi.Note]] = [[sorted_notes[0]]]
    for note in sorted_notes[1:]:
        if abs(note.start - groups[-1][0].start) <= chord_threshold_sec:
            groups[-1].append(note)
        else:
            groups.append([note])
    return groups


def _position_cost(
    pos: FretPosition,
    hand_fret: float,
    prev_string: int | None,
    *,
    penalize_open: bool,
) -> float:
    cost = abs(pos.fret - hand_fret)
    if prev_string is not None and pos.string != prev_string:
        cost += STRING_CHANGE_COST * abs(pos.string - prev_string)
    if penalize_open and pos.fret == 0 and hand_fret > OPEN_STRING_PENALTY_THRESHOLD:
        cost += 5.0
    return cost


def _filter_playable_positions(
    positions: list[FretPosition],
    hand_fret: float,
    max_fret: int,
    max_jump: int,
    allow_large_jump: bool,
) -> list[FretPosition]:
    playable = [p for p in positions if p.fret <= max_fret]
    if not playable:
        playable = positions
    if allow_large_jump:
        return playable
    within_jump = [p for p in playable if abs(p.fret - hand_fret) <= max_jump]
    return within_jump or playable


def _pick_single_position(
    positions: list[FretPosition],
    hand_fret: float,
    prev_string: int | None,
    *,
    penalize_open: bool,
) -> FretPosition:
    """Pick fret position minimizing playability cost."""
    return min(
        positions,
        key=lambda p: _position_cost(p, hand_fret, prev_string, penalize_open=penalize_open),
    )


def _pick_chord_positions(
    pitches: list[int],
    tuning: tuple[int, ...],
    hand_fret: float,
    max_fret: int,
    max_fret_span: int = 5,
) -> list[FretPosition]:
    """Assign string/fret for a chord minimizing span and hand movement."""
    candidates_per_pitch = [
        _filter_playable_positions(
            positions_for_pitch(p, tuning, max_fret=max_fret),
            hand_fret,
            max_fret,
            MAX_FRET_JUMP,
            allow_large_jump=True,
        )
        for p in sorted(pitches)
    ]
    if not candidates_per_pitch:
        return []
    if len(candidates_per_pitch) == 1:
        return [_pick_single_position(candidates_per_pitch[0], hand_fret, None, penalize_open=True)]

    best_combo: list[FretPosition] | None = None
    best_score = float("inf")

    def search(idx: int, used_strings: set[int], combo: list[FretPosition], frets: list[int]) -> None:
        nonlocal best_combo, best_score
        if idx == len(candidates_per_pitch):
            if not frets:
                return
            span = max(frets) - min(frets)
            center = sum(frets) / len(frets)
            score = span * 10 + abs(center - hand_fret)
            if score < best_score:
                best_score = score
                best_combo = combo.copy()
            return

        for pos in candidates_per_pitch[idx]:
            if pos.string in used_strings:
                continue
            trial_frets = [*frets, pos.fret]
            if trial_frets and max(trial_frets) - min(trial_frets) > max_fret_span:
                continue
            used_strings.add(pos.string)
            combo.append(pos)
            search(idx + 1, used_strings, combo, trial_frets)
            combo.pop()
            used_strings.remove(pos.string)

    search(0, set(), [], [])
    if best_combo:
        return best_combo

    result: list[FretPosition] = []
    used: set[int] = set()
    for pitch in sorted(pitches):
        for pos in positions_for_pitch(pitch, tuning, max_fret=max_fret):
            if pos.string not in used:
                result.append(pos)
                used.add(pos.string)
                break
    return result


def midi_to_tab(
    midi_path: str,
    tuning: tuple[int, ...] = STANDARD_TUNING_MIDI,
    tempo_bpm: float | None = None,
    tempo_confidence: str = "high",
    beats_per_measure: int = 4,
    max_fret: int = DEFAULT_MAX_FRET,
) -> TabDocument:
    """Convert MIDI file to structured tab document."""
    pm = pretty_midi.PrettyMIDI(midi_path)
    notes: list[pretty_midi.Note] = []
    for inst in pm.instruments:
        if not inst.is_drum:
            notes.extend(inst.notes)

    if tempo_bpm is None:
        from audio_to_tab.tempo import estimate_tempo_from_midi_robust

        tempo_bpm = estimate_tempo_from_midi_robust(pm)
        tempo_confidence = "low"

    events: list[TabEvent] = []
    hand_fret = 5.0
    prev_string: int | None = None
    prev_start = 0.0
    sec_per_beat = 60.0 / tempo_bpm

    for group in _group_notes_into_events(notes):
        start = group[0].start
        time_gap = start - prev_start
        allow_large_jump = time_gap > sec_per_beat
        penalize_open = hand_fret > OPEN_STRING_PENALTY_THRESHOLD

        pitches = [n.pitch for n in group]
        if len(pitches) == 1:
            positions = _filter_playable_positions(
                positions_for_pitch(pitches[0], tuning, max_fret=max_fret),
                hand_fret,
                max_fret,
                MAX_FRET_JUMP,
                allow_large_jump=allow_large_jump,
            )
            if not positions:
                continue
            chosen = _pick_single_position(
                positions, hand_fret, prev_string, penalize_open=penalize_open
            )
            hand_fret = 0.7 * hand_fret + 0.3 * chosen.fret
            prev_string = chosen.string
            tab_notes = [
                TabNote(start=start, end=group[0].end, string=chosen.string, fret=chosen.fret, pitch=chosen.pitch)
            ]
        else:
            chosen_list = _pick_chord_positions(pitches, tuning, hand_fret, max_fret)
            if not chosen_list:
                continue
            frets = [c.fret for c in chosen_list]
            hand_fret = 0.7 * hand_fret + 0.3 * (sum(frets) / len(frets))
            prev_string = chosen_list[0].string if len(chosen_list) == 1 else None
            pitch_to_note = {n.pitch: n for n in group}
            tab_notes = []
            for chosen in chosen_list:
                src = pitch_to_note.get(chosen.pitch)
                end = src.end if src else start + 0.25
                tab_notes.append(
                    TabNote(start=start, end=end, string=chosen.string, fret=chosen.fret, pitch=chosen.pitch)
                )

        events.append(TabEvent(start=start, notes=tab_notes))
        prev_start = start

    return TabDocument(
        events=events,
        tempo_bpm=tempo_bpm,
        tempo_confidence=tempo_confidence,
        beats_per_measure=beats_per_measure,
    )


def tab_to_ascii(doc: TabDocument, chars_per_beat: int = 4, beats_per_measure: int | None = None) -> str:
    """Render tab document as ASCII text with note durations.

    ``chars_per_beat`` is ASCII columns per quarter-note beat (default 4 => one
    column per 16th note); the measure width follows the meter.
    """
    if not doc.events:
        return "No notes detected.\n"

    bpm = beats_per_measure if beats_per_measure is not None else doc.beats_per_measure
    chars_per_measure = chars_per_beat * bpm
    sec_per_char = 60.0 / doc.tempo_bpm / chars_per_beat
    end_time = max((n.end for e in doc.events for n in e.notes), default=1.0)
    total_chars = max(int(end_time / sec_per_char) + chars_per_beat, chars_per_measure)

    lines: list[list[str]] = [["-" for _ in range(total_chars)] for _ in range(6)]
    prefixes = [f"{name}|" for name in doc.tuning_names]

    for event in doc.events:
        for note in event.notes:
            start_col = min(int(note.start / sec_per_char), total_chars - 1)
            end_col = min(max(start_col + 1, int(note.end / sec_per_char)), total_chars)
            fret_str = str(note.fret)
            for i, ch in enumerate(fret_str):
                pos = start_col + i
                if pos < total_chars:
                    lines[note.string][pos] = ch
            hold_start = start_col + len(fret_str)
            for pos in range(hold_start, end_col):
                if pos < total_chars and lines[note.string][pos] == "-":
                    lines[note.string][pos] = "="

    tempo_label = f"{doc.tempo_bpm:.0f} BPM"
    if doc.tempo_confidence == "low":
        tempo_label += " (low confidence)"
    header = f"Tempo: {tempo_label} | Standard tuning (E A D G B e)\n"
    header += "Generated by audio-to-tab-pdf (draft transcription. Verify before performing)\n\n"
    body = "\n".join(prefixes[s] + "".join(lines[s]) for s in range(5, -1, -1))
    return header + body + "\n"


def _finite(value: Any, default: float | None = None) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def tab_document_to_dict(doc: TabDocument) -> dict[str, Any]:
    """Serialize a tab document to plain JSON-ready data (no dataclasses)."""
    return {
        "events": [
            {
                "start": float(event.start),
                "notes": [
                    {
                        "start": float(note.start),
                        "end": float(note.end),
                        "string": int(note.string),
                        "fret": int(note.fret),
                        "pitch": int(note.pitch),
                    }
                    for note in event.notes
                ],
            }
            for event in doc.events
        ],
        "tuning_names": [str(name) for name in doc.tuning_names],
        "tempo_bpm": float(doc.tempo_bpm),
        "tempo_confidence": str(doc.tempo_confidence),
        "beats_per_measure": int(doc.beats_per_measure),
    }


def tab_document_from_dict(data: Mapping[str, Any]) -> TabDocument:
    """Rebuild a tab document, dropping malformed notes instead of failing the run."""
    raw_events = data.get("events")
    events: list[TabEvent] = []
    if isinstance(raw_events, list):
        for raw_event in raw_events:
            if not isinstance(raw_event, Mapping):
                continue
            raw_notes = raw_event.get("notes")
            notes: list[TabNote] = []
            if isinstance(raw_notes, list):
                for raw_note in raw_notes:
                    if not isinstance(raw_note, Mapping):
                        continue
                    start = _finite(raw_note.get("start"))
                    end = _finite(raw_note.get("end"))
                    string = raw_note.get("string")
                    fret = raw_note.get("fret")
                    pitch = raw_note.get("pitch")
                    try:
                        string_i = int(string)  # type: ignore[arg-type]
                        fret_i = int(fret)  # type: ignore[arg-type]
                        pitch_i = int(pitch)  # type: ignore[arg-type]
                    except (TypeError, ValueError):
                        continue
                    if (
                        start is None
                        or end is None
                        or start < 0
                        or end < start
                        or not 0 <= string_i < 6
                        or fret_i < 0
                        or not 0 <= pitch_i <= 127
                    ):
                        continue
                    notes.append(
                        TabNote(
                            start=start,
                            end=end,
                            string=string_i,
                            fret=fret_i,
                            pitch=pitch_i,
                        )
                    )
            if not notes:
                continue
            notes.sort(key=lambda note: (note.start, note.string, note.fret))
            event_start = _finite(raw_event.get("start"), notes[0].start) or notes[0].start
            events.append(TabEvent(start=event_start, notes=notes))
    events.sort(key=lambda event: event.start)

    raw_tuning = data.get("tuning_names")
    if (
        isinstance(raw_tuning, (list, tuple))
        and len(raw_tuning) == 6
        and all(isinstance(name, str) and name for name in raw_tuning)
    ):
        tuning = tuple(str(name) for name in raw_tuning)
    else:
        tuning = STANDARD_TUNING_NAMES

    tempo = _finite(data.get("tempo_bpm"), 120.0) or 120.0
    if tempo <= 0:
        tempo = 120.0
    try:
        beats = int(data.get("beats_per_measure", 4))
    except (TypeError, ValueError):
        beats = 4
    beats = min(16, max(1, beats))
    confidence = str(data.get("tempo_confidence") or "high")

    return TabDocument(
        events=events,
        tuning_names=tuning,
        tempo_bpm=tempo,
        tempo_confidence=confidence,
        beats_per_measure=beats,
    )


def tab_measure_spans(doc: TabDocument) -> list[dict[str, Any]]:
    """Return one ``{start, end, text}`` row per measure for the player's bar highlight."""
    if not doc.events:
        return []
    tempo = float(doc.tempo_bpm) if doc.tempo_bpm and doc.tempo_bpm > 0 else 120.0
    beats = max(1, int(doc.beats_per_measure))
    measure_sec = 60.0 / tempo * beats
    if not math.isfinite(measure_sec) or measure_sec <= 0:
        return []
    end_time = max((note.end for event in doc.events for note in event.notes), default=0.0)
    count = max(1, math.ceil(end_time / measure_sec - 1e-9))

    spans: list[dict[str, Any]] = []
    for index in range(count):
        start = index * measure_sec
        end = (index + 1) * measure_sec
        local_events: list[TabEvent] = []
        for event in doc.events:
            local_notes: list[TabNote] = []
            for note in event.notes:
                if note.end <= start or note.start >= end:
                    continue
                local_notes.append(
                    TabNote(
                        start=max(0.0, note.start - start),
                        end=min(measure_sec, note.end - start),
                        string=note.string,
                        fret=note.fret,
                        pitch=note.pitch,
                    )
                )
            if local_notes:
                local_events.append(
                    TabEvent(
                        start=max(0.0, min(note.start for note in local_notes)),
                        notes=local_notes,
                    )
                )
        local_doc = TabDocument(
            events=local_events,
            tuning_names=doc.tuning_names,
            tempo_bpm=tempo,
            tempo_confidence=doc.tempo_confidence,
            beats_per_measure=beats,
        )
        rendered = tab_to_ascii(local_doc, beats_per_measure=beats)
        text = rendered.split("\n\n", 1)[-1].strip()
        spans.append({"start": start, "end": end, "text": text})
    return spans
