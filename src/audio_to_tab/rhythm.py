"""Beat-grid quantization for tab events."""

from __future__ import annotations

from audio_to_tab.tab_generate import TabDocument, TabEvent, TabNote


def sec_per_sixteenth(tempo_bpm: float, beats_per_measure: int = 4) -> float:
    """Duration of one 16th note in seconds."""
    return 60.0 / tempo_bpm / 4.0


def quantize_time(t: float, grid_sec: float) -> float:
    if grid_sec <= 0:
        return t
    return round(t / grid_sec) * grid_sec


def quantize_tab_document(
    doc: TabDocument,
    *,
    beats_per_measure: int = 4,
    subdivisions_per_beat: int = 4,
) -> TabDocument:
    """Snap event starts and note ends to a 16th-note grid at doc.tempo_bpm."""
    grid_sec = 60.0 / doc.tempo_bpm / subdivisions_per_beat
    min_duration = grid_sec

    new_events: list[TabEvent] = []
    for event in doc.events:
        q_start = quantize_time(event.start, grid_sec)
        new_notes: list[TabNote] = []
        for note in event.notes:
            q_end = quantize_time(note.end, grid_sec)
            q_end = max(q_start + min_duration, q_end)
            new_notes.append(
                TabNote(
                    start=q_start,
                    end=q_end,
                    string=note.string,
                    fret=note.fret,
                    pitch=note.pitch,
                )
            )
        new_events.append(TabEvent(start=q_start, notes=new_notes))

    return TabDocument(
        events=new_events,
        tuning_names=doc.tuning_names,
        tempo_bpm=doc.tempo_bpm,
        tempo_confidence=doc.tempo_confidence,
        beats_per_measure=beats_per_measure,
    )
