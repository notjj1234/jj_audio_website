"""Serialization and measure spans for tab documents used by the practice player."""

from __future__ import annotations

import json

import pytest

from audio_to_tab.tab_generate import (
    TabDocument,
    TabEvent,
    TabNote,
    tab_document_from_dict,
    tab_document_to_dict,
    tab_measure_spans,
)


def _doc() -> TabDocument:
    return TabDocument(
        events=[
            TabEvent(
                start=0.0,
                notes=[
                    TabNote(start=0.0, end=0.5, string=0, fret=3, pitch=55),
                    TabNote(start=0.0, end=0.5, string=1, fret=2, pitch=50),
                ],
            ),
            TabEvent(
                start=2.0,
                notes=[TabNote(start=2.0, end=2.5, string=2, fret=0, pitch=43)],
            ),
        ],
        tuning_names=("E", "A", "D", "G", "B", "e"),
        tempo_bpm=120.0,
        tempo_confidence="low",
        beats_per_measure=4,
    )


def test_tab_document_round_trip():
    doc = _doc()

    data = tab_document_to_dict(doc)
    restored = tab_document_from_dict(data)

    assert restored == doc
    assert json.loads(json.dumps(data)) == data


def test_tab_document_from_dict_defaults_missing_fields():
    data = {
        "events": [
            {
                "start": 0.0,
                "notes": [{"start": 0.0, "end": 0.5, "string": 0, "fret": 3, "pitch": 55}],
            }
        ]
    }

    doc = tab_document_from_dict(data)

    assert doc.tempo_bpm == 120.0
    assert doc.tempo_confidence == "high"
    assert doc.beats_per_measure == 4
    assert doc.tuning_names[0] == "E"


def test_tab_document_from_dict_skips_malformed_notes():
    data = {
        "events": [
            {
                "start": 0.0,
                "notes": [
                    {"start": 0.0, "end": 0.5, "string": 0, "fret": 3, "pitch": 55},
                    {"start": 0.0, "end": 0.5, "string": 0, "fret": 3},
                    {"start": 0.0, "end": 0.5, "string": 99, "fret": 3, "pitch": 55},
                ],
            }
        ]
    }

    doc = tab_document_from_dict(data)

    assert len(doc.events) == 1
    assert len(doc.events[0].notes) == 1


def test_measure_spans_cover_song_and_are_contiguous():
    doc = _doc()
    doc.events.append(
        TabEvent(
            start=4.2,
            notes=[TabNote(start=4.2, end=4.6, string=3, fret=5, pitch=48)],
        )
    )

    spans = tab_measure_spans(doc)

    assert len(spans) >= 3
    assert spans[0]["start"] == pytest.approx(0.0)
    assert spans[-1]["end"] >= 4.6
    for previous, current in zip(spans, spans[1:]):
        assert current["start"] == pytest.approx(previous["end"])
    assert all(span["end"] > span["start"] for span in spans)
    assert all("|" in span["text"] for span in spans)


def test_measure_text_is_local_to_the_measure():
    doc = _doc()
    doc.events.append(
        TabEvent(
            start=4.2,
            notes=[TabNote(start=4.2, end=4.6, string=3, fret=5, pitch=48)],
        )
    )

    spans = tab_measure_spans(doc)

    assert "3" in spans[0]["text"]
    assert "5" not in spans[0]["text"]
    assert "5" in spans[2]["text"]


def test_empty_document_has_no_spans():
    assert tab_measure_spans(TabDocument(events=[])) == []
