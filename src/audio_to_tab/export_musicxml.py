"""MusicXML 3.1 export for a chart document. Standard library only."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from audio_to_tab.chart import ChartDocument
from audio_to_tab.chord_symbols import PITCHES, parse

_KIND = {
    "maj": "major",
    "min": "minor",
    "dim": "diminished",
    "aug": "augmented",
    "sus2": "suspended-second",
    "sus4": "suspended-fourth",
    "5": "power",
    "6": "major-sixth",
    "m6": "minor-sixth",
    "7": "dominant",
    "maj7": "major-seventh",
    "m7": "minor-seventh",
    "m7b5": "half-diminished",
    "dim7": "diminished-seventh",
    "mMaj7": "major-minor",
    "maj9": "major-ninth",
    "9": "dominant-ninth",
    "7b9": "dominant-ninth",
    "add9": "major",
    "m9": "minor-ninth",
}
_FIFTHS_BY_PC = {
    0: 0,
    1: 7,
    2: 2,
    3: -3,
    4: 4,
    5: -1,
    6: 6,
    7: 1,
    8: -4,
    9: 3,
    10: -2,
    11: 5,
}


def _step_alter(name: str) -> tuple[str, int]:
    if len(name) == 2 and name[1] == "#":
        return name[0], 1
    if len(name) == 2 and name[1] == "b":
        return name[0], -1
    return name[:1] or "C", 0


def fifths_for_key(key: str | None) -> int:
    if not isinstance(key, str) or not key.strip():
        return 0
    text = key.strip()
    minor = text.endswith("m") and not text.lower().endswith("maj")
    root = text[:-1] if minor else text
    chord = parse(root)
    if chord is None:
        return 0
    pc = PITCHES.index(chord.root)
    if minor:
        pc = (pc + 3) % 12
    return int(_FIFTHS_BY_PC.get(pc, 0))


def _harmony(parent: ET.Element, symbol: str) -> None:
    chord = parse(symbol)
    if chord is None:
        return
    harmony = ET.SubElement(parent, "harmony")
    root = ET.SubElement(harmony, "root")
    step, alter = _step_alter(chord.root)
    ET.SubElement(root, "root-step").text = step
    if alter:
        ET.SubElement(root, "root-alter").text = str(alter)
    ET.SubElement(harmony, "kind").text = _KIND.get(chord.quality, "major")
    if chord.bass:
        bass = ET.SubElement(harmony, "bass")
        bass_step, bass_alter = _step_alter(chord.bass)
        ET.SubElement(bass, "bass-step").text = bass_step
        if bass_alter:
            ET.SubElement(bass, "bass-alter").text = str(bass_alter)


def _lyric_for_beat(document: ChartDocument, start: float, end: float) -> str | None:
    for line in document.lyrics:
        if start - 1e-6 <= float(line.start) < end - 1e-9:
            text = str(line.text).strip()
            return text or None
    return None


def chart_to_musicxml(document: ChartDocument) -> str:
    """score-partwise 3.1: one measure per bar, one beat per division, harmony on changes."""
    score = ET.Element("score-partwise", version="3.1")
    if document.title:
        ET.SubElement(score, "work").append(_text_el("work-title", document.title))
    part_list = ET.SubElement(score, "part-list")
    score_part = ET.SubElement(part_list, "score-part", id="P1")
    ET.SubElement(score_part, "part-name").text = "Harmony"
    part = ET.SubElement(score, "part", id="P1")
    beats, beat_type = _time(document.time_signature)
    wrote_attributes = False
    measures = document.bars or ()
    if not measures:
        measures = ()
    for bar in measures:
        measure = ET.SubElement(part, "measure", number=str(bar.index + 1))
        if not wrote_attributes:
            attributes = ET.SubElement(measure, "attributes")
            ET.SubElement(attributes, "divisions").text = "1"
            key = ET.SubElement(attributes, "key")
            ET.SubElement(key, "fifths").text = str(fifths_for_key(document.key))
            time = ET.SubElement(attributes, "time")
            ET.SubElement(time, "beats").text = str(beats)
            ET.SubElement(time, "beat-type").text = str(beat_type)
            wrote_attributes = True
        for cell in bar.cells:
            if cell.chord:
                _harmony(measure, cell.chord)
            lyric = _lyric_for_beat(document, cell.start, cell.end)
            if lyric:
                note = ET.SubElement(measure, "note")
                pitch = ET.SubElement(note, "pitch")
                ET.SubElement(pitch, "step").text = "C"
                ET.SubElement(pitch, "octave").text = "4"
                ET.SubElement(note, "duration").text = "1"
                ET.SubElement(note, "voice").text = "1"
                ET.SubElement(note, "type").text = "quarter"
                lyric_el = ET.SubElement(note, "lyric", number="1")
                ET.SubElement(lyric_el, "text").text = lyric
            else:
                note = ET.SubElement(measure, "note")
                ET.SubElement(note, "rest")
                ET.SubElement(note, "duration").text = "1"
                ET.SubElement(note, "voice").text = "1"
                ET.SubElement(note, "type").text = "quarter"
    if not measures:
        measure = ET.SubElement(part, "measure", number="1")
        attributes = ET.SubElement(measure, "attributes")
        ET.SubElement(attributes, "divisions").text = "1"
        note = ET.SubElement(measure, "note")
        ET.SubElement(note, "rest")
        ET.SubElement(note, "duration").text = "1"
    ET.indent(score, space="  ")
    return ET.tostring(score, encoding="unicode", xml_declaration=True)


def _text_el(tag: str, text: str) -> ET.Element:
    element = ET.Element(tag)
    element.text = text
    return element


def _time(signature: str) -> tuple[int, int]:
    parts = str(signature or "4/4").split("/")
    try:
        beats = int(parts[0])
        beat_type = int(parts[1]) if len(parts) > 1 else 4
    except ValueError:
        return 4, 4
    return max(1, beats), beat_type if beat_type in {2, 4, 8, 16} else 4


def write_musicxml(document: ChartDocument, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(chart_to_musicxml(document), encoding="utf-8")
    return path


__all__ = ["chart_to_musicxml", "fifths_for_key", "write_musicxml"]
