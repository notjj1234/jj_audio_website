"""CLI: ASCII tab or MIDI → PDF."""

from __future__ import annotations

import argparse
from pathlib import Path

from audio_to_tab.pdf_render import render_structured_tab_pdf, render_tab_pdf
from audio_to_tab.tab_generate import midi_to_tab, tab_to_ascii


def main() -> None:
    parser = argparse.ArgumentParser(description="Render guitar tab to PDF")
    parser.add_argument("input", type=Path, help="Input .tab or .mid file")
    parser.add_argument("output", type=Path, nargs="?", help="Output PDF path")
    parser.add_argument("--title", default="Guitar Tab")
    args = parser.parse_args()

    out = args.output or args.input.with_suffix(".pdf")

    if args.input.suffix.lower() == ".mid":
        doc = midi_to_tab(str(args.input))
        render_structured_tab_pdf(doc, str(out), title=args.title)
    else:
        tab_text = args.input.read_text(encoding="utf-8")
        render_tab_pdf(tab_text, str(out), title=args.title)

    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
