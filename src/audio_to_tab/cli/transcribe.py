"""CLI: audio file → MIDI via Basic Pitch."""

from __future__ import annotations

import argparse
from pathlib import Path

from audio_to_tab.transcribe import transcribe_audio


def main() -> None:
    parser = argparse.ArgumentParser(description="Transcribe audio to MIDI using Basic Pitch")
    parser.add_argument("input", type=Path, help="Input MP3/WAV/FLAC file")
    parser.add_argument("output", type=Path, nargs="?", help="Output MIDI path (default: input.mid)")
    parser.add_argument("--onset-threshold", type=float, default=0.5)
    parser.add_argument("--frame-threshold", type=float, default=0.3)
    args = parser.parse_args()

    out = args.output or args.input.with_suffix(".mid")
    path = transcribe_audio(
        args.input,
        out,
        onset_threshold=args.onset_threshold,
        frame_threshold=args.frame_threshold,
    )
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
