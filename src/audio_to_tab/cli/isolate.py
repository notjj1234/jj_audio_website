"""CLI: multi-stem audio isolation via Demucs."""

from __future__ import annotations

import argparse
from pathlib import Path

from audio_to_tab.isolate import (
    DEMUCS_INSTALL_HINT,
    IsolateConfig,
    SUPPORTED_MODELS,
    separate_stems,
)
from audio_to_tab.separate import is_demucs_available


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Separate an audio file into instrument stems (Demucs). "
            "CPU separation is slow — expect roughly track length or longer; "
            "higher quality presets multiply runtime."
        ),
        epilog=(
            "Models: htdemucs_6s (6 stems: drums/bass/other/vocals/guitar/piano; "
            "piano quality is limited), htdemucs / htdemucs_ft (4 stems). "
            f"{DEMUCS_INSTALL_HINT}"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--audio", "-a", type=Path, required=True, help="Local audio file")
    parser.add_argument("--output", "-o", type=Path, default=Path("./output/stems"), help="Output directory")
    parser.add_argument(
        "--model",
        "-n",
        choices=list(SUPPORTED_MODELS),
        default="htdemucs_6s",
        help="Demucs model (default: htdemucs_6s)",
    )
    parser.add_argument(
        "--quality",
        choices=["fast", "balanced", "high", "extreme"],
        default="balanced",
        help="Quality preset (affects shifts/overlap; higher = much slower)",
    )
    parser.add_argument("--device", default="cpu", help="Demucs device: cpu or cuda")
    parser.add_argument(
        "--max-duration",
        type=float,
        default=90.0,
        help="Max seconds to process (0 = full file)",
    )
    parser.add_argument(
        "--two-stems",
        default=None,
        help="Optional karaoke-style split, e.g. vocals (produces that stem + no_<stem>)",
    )
    parser.add_argument(
        "--dual-guitar",
        action="store_true",
        help="Experimental: split guitar stem into guitar1/guitar2 via stereo heuristic (htdemucs_6s)",
    )
    args = parser.parse_args()

    if not is_demucs_available():
        raise SystemExit(f"Demucs is not installed. {DEMUCS_INSTALL_HINT}")

    max_dur = None if args.max_duration <= 0 else args.max_duration
    config = IsolateConfig(
        model=args.model,
        quality=args.quality,
        device=args.device,
        max_duration_sec=max_dur,
        two_stems=args.two_stems,
        dual_guitar=args.dual_guitar,
    )

    def progress(stage: str, msg: str) -> None:
        print(f"[{stage}] {msg}")

    artifacts = separate_stems(
        audio_path=args.audio,
        output_dir=args.output,
        config=config,
        on_progress=progress,
    )
    print("\nStems:")
    for name, path in sorted(artifacts.items()):
        print(f"  {name}: {path}")


if __name__ == "__main__":
    main()
