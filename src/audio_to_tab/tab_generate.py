"""MIDI to ASCII guitar tablature via playability-aware fret assignment."""

from __future__ import annotations

from dataclasses import dataclass, field

import pretty_midi

from audio_to_tab.tuning import FretPosition, STANDARD_TUNING_MIDI, STANDARD_TUNING_NAMES, positions_for_pitch


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
            trial_frets = frets + [pos.fret]
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


def tab_to_ascii(doc: TabDocument, chars_per_beat: int = 16, beats_per_measure: int | None = None) -> str:
    """Render tab document as ASCII text with note durations."""
    if not doc.events:
        return "No notes detected.\n"

    bpm = beats_per_measure if beats_per_measure is not None else doc.beats_per_measure
    sec_per_char = 60.0 / doc.tempo_bpm / (chars_per_beat / bpm)
    end_time = max((n.end for e in doc.events for n in e.notes), default=1.0)
    total_chars = max(int(end_time / sec_per_char) + chars_per_beat, chars_per_beat * bpm)

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
    header += "Generated by audio-to-tab-pdf (draft transcription — verify before performing)\n\n"
    body = "\n".join(prefixes[s] + "".join(lines[s]) for s in range(5, -1, -1))
    return header + body + "\n"
