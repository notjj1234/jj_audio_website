"""ASCII tab to PDF rendering via ReportLab."""

from __future__ import annotations

import math
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

from audio_to_tab.tab_generate import TabDocument, tab_to_ascii

SPARSE_BAR_EVENT_THRESHOLD = 2


def render_tab_pdf(
    tab_text: str,
    output_path: str,
    *,
    title: str = "Guitar Tab",
    subtitle: str = "Draft transcription — verify before performing",
) -> str:
    """Render ASCII tab text to a readable PDF."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    c = canvas.Canvas(str(path), pagesize=letter)
    _, height = letter
    margin = 0.75 * inch
    line_height = 14
    y = height - margin

    c.setFont("Helvetica-Bold", 16)
    c.drawString(margin, y, title)
    y -= 22

    c.setFont("Helvetica", 10)
    c.setFillColorRGB(0.4, 0.4, 0.4)
    c.drawString(margin, y, subtitle)
    y -= 20
    c.setFillColorRGB(0, 0, 0)

    c.setFont("Courier", 10)
    for line in tab_text.splitlines():
        if y < margin:
            c.showPage()
            c.setFont("Courier", 10)
            y = height - margin
        c.drawString(margin, y, line[:120])
        y -= line_height

    c.save()
    return str(path)


def tab_document_to_pdf(
    doc: TabDocument,
    output_path: str,
    *,
    title: str = "Guitar Tab",
) -> str:
    """Convert TabDocument to PDF."""
    ascii_tab = tab_to_ascii(doc)
    return render_tab_pdf(ascii_tab, output_path, title=title)


def _events_in_measure(doc: TabDocument, m_start: float, m_end: float) -> list:
    return [e for e in doc.events if m_start <= e.start < m_end]


def _count_measures(end_time: float, sec_per_measure: float) -> int:
    """Measure count where a note ending exactly on a bar line adds no empty measure."""
    if sec_per_measure <= 0:
        return 1
    return max(1, math.ceil(end_time / sec_per_measure))


def render_structured_tab_pdf(
    doc: TabDocument,
    output_path: str,
    *,
    title: str = "Guitar Tab",
) -> str:
    """Render tab with drawn staff lines for cleaner PDF output."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    c = canvas.Canvas(str(path), pagesize=letter)
    _, height = letter
    margin = 0.6 * inch
    staff_gap = 11
    measure_width = 4.5 * inch
    strings = 6
    beats_per_measure = doc.beats_per_measure

    def new_page_header(page_y: float) -> float:
        c.setFont("Helvetica-Bold", 14)
        c.drawString(margin, page_y, title)
        c.setFont("Helvetica", 9)
        c.setFillColorRGB(0.45, 0.45, 0.45)
        c.drawString(margin, page_y - 16, "Draft transcription — verify before performing")
        c.setFillColorRGB(0, 0, 0)
        return page_y - 40

    y = new_page_header(height - margin)

    if not doc.events:
        c.setFont("Helvetica", 11)
        c.drawString(margin, y, "No notes detected.")
        c.save()
        return str(path)

    sec_per_measure = 60.0 / doc.tempo_bpm * beats_per_measure
    end_time = max((n.end for e in doc.events for n in e.notes), default=sec_per_measure)
    num_measures = _count_measures(end_time, sec_per_measure)
    measures_per_row = 2
    row_height = strings * staff_gap + 30

    tuning_labels = list(reversed(doc.tuning_names))

    for measure_start in range(0, num_measures, measures_per_row):
        if y < margin + row_height:
            c.showPage()
            y = new_page_header(height - margin)

        for col in range(measures_per_row):
            measure_idx = measure_start + col
            if measure_idx >= num_measures:
                break
            x0 = margin + col * (measure_width + 0.2 * inch)
            m_start = measure_idx * sec_per_measure
            m_end = m_start + sec_per_measure

            for s in range(strings):
                y_line = y - s * staff_gap
                c.line(x0, y_line, x0 + measure_width, y_line)
                c.setFont("Helvetica", 8)
                c.drawString(x0 - 14, y_line - 3, tuning_labels[s])

            measure_events = _events_in_measure(doc, m_start, m_end)
            for event in measure_events:
                rel_start = (event.start - m_start) / sec_per_measure
                x_start = x0 + rel_start * measure_width
                for note in event.notes:
                    string_from_top = 5 - note.string
                    y_note = y - string_from_top * staff_gap
                    rel_end = min((note.end - m_start) / sec_per_measure, 1.0)
                    x_end = x0 + rel_end * measure_width
                    if x_end - x_start > 6:
                        c.setLineWidth(2)
                        c.line(x_start, y_note + 2, x_end, y_note + 2)
                        c.setLineWidth(1)
                    c.setFont("Helvetica-Bold", 9)
                    c.drawCentredString(x_start, y_note + 2, str(note.fret))

            bar_label = f"Bar {measure_idx + 1}"
            if len(measure_events) <= SPARSE_BAR_EVENT_THRESHOLD:
                bar_label += " (sparse)"
                c.setFillColorRGB(0.5, 0.5, 0.5)
            c.setFont("Helvetica", 7)
            c.drawString(x0, y - strings * staff_gap - 8, bar_label)
            c.setFillColorRGB(0, 0, 0)

        y -= row_height

    tempo_footer = f"Tempo: {doc.tempo_bpm:.0f} BPM"
    if doc.tempo_confidence == "low":
        tempo_footer += " (low confidence)"
    tempo_footer += "  |  Standard tuning"
    c.setFont("Helvetica", 8)
    c.drawString(margin, margin * 0.5, tempo_footer)
    c.save()
    return str(path)
