"""MusicXML and text export use the standard library only."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from audio_to_tab.analysis import AnalysisResult, ChordEvent, LyricLine
from audio_to_tab.chart import build_chart
from audio_to_tab.export_musicxml import chart_to_musicxml, fifths_for_key
from audio_to_tab.export_text import chart_to_text


def _document():
    result = AnalysisResult(
        duration_sec=2.0,
        bpm=120.0,
        key="C",
        beats=(0.0, 0.5, 1.0, 1.5),
        beats_per_measure=4,
        chords=(ChordEvent(0.0, 2.0, "C", 0.9, simple="C", medium="C"),),
        lyrics=(LyricLine(0.0, 0.5, "hello", ()),),
    )
    return build_chart(result, title="Demo")


def test_musicxml_structure():
    xml = chart_to_musicxml(_document())
    root = ET.fromstring(xml)

    assert root.tag == "score-partwise"
    assert root.attrib["version"] == "3.1"
    assert root.find("./part-list/score-part/part-name").text == "Harmony"
    assert root.find(".//harmony/root/root-step").text == "C"
    assert root.find(".//harmony/kind").text == "major"
    assert root.find(".//lyric/text").text == "hello"
    assert root.find(".//time/beats").text == "4"
    assert root.find(".//time/beat-type").text == "4"
    assert root.find(".//attributes/divisions").text == "1"
    assert fifths_for_key("C") == 0
    assert fifths_for_key("F") == -1
    assert fifths_for_key("Am") == 0


def test_text_export_is_readable():
    text = chart_to_text(_document())

    assert "[C]hello" in text
    assert "{key: C}" in text
    assert "{time: 4/4}" in text
