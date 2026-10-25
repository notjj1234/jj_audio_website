"""ChordPro-ish text export. A chord sits in brackets immediately before its lyric."""

from __future__ import annotations

from pathlib import Path

from audio_to_tab.chart import ChartDocument


def _lyric_on_bar(document: ChartDocument, start: float, end: float) -> str:
    lines = []
    for line in document.lyrics:
        if start - 1e-6 <= float(line.start) < end - 1e-9:
            text = str(line.text).strip()
            if text:
                lines.append(text)
    return " ".join(lines)


def chart_to_text(document: ChartDocument) -> str:
    header = [
        f"{{title: {document.title}}}" if document.title else "{title: }",
        f"{{key: {document.key}}}",
        f"{{time: {document.time_signature}}}",
        f"{{tempo: {document.bpm:g}}}",
    ]
    body: list[str] = []
    for bar in document.bars:
        chunks: list[str] = []
        lyric = _lyric_on_bar(document, bar.start, bar.end)
        lyric_used = False
        for cell in bar.cells:
            if cell.chord:
                token = f"[{cell.chord}]"
                if lyric and not lyric_used:
                    token = f"{token}{lyric}"
                    lyric_used = True
                chunks.append(token)
            else:
                chunks.append(".")
        if lyric and not lyric_used:
            chunks.append(lyric)
        body.append(" ".join(chunks))
    if not body and document.lyrics:
        body.append(document.lyrics[0].text)
    return "\n".join([*header, *body]) + "\n"


def write_chart_text(document: ChartDocument, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(chart_to_text(document), encoding="utf-8")
    return path


__all__ = ["chart_to_text", "write_chart_text"]
