"""CLI: MIDI → ASCII tab."""

from __future__ import annotations

import argparse
from pathlib import Path

from audio_to_tab.tab_generate import midi_to_tab, tab_to_ascii


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert MIDI to ASCII guitar tab")
    parser.add_argument("input", type=Path, help="Input MIDI file")
    parser.add_argument("output", type=Path, nargs="?", help="Output .tab path")
    args = parser.parse_args()

    out = args.output or args.input.with_suffix(".tab")
    doc = midi_to_tab(str(args.input))
    out.write_text(tab_to_ascii(doc), encoding="utf-8")
    print(f"Wrote {out} ({len(doc.events)} events)")


if __name__ == "__main__":
    main()
