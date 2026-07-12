"""CLI: full audio → tab PDF pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path

from audio_to_tab.pipeline import YOUTUBE_DISCLAIMER, PipelineConfig, run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert audio or YouTube URL to guitar tab PDF",
        epilog=YOUTUBE_DISCLAIMER,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--audio", "-a", type=Path, help="Local MP3/WAV file")
    input_group.add_argument("--url", "-u", type=str, help="YouTube URL")

    parser.add_argument("--output", "-o", type=Path, default=Path("./output"), help="Output directory")
    parser.add_argument("--no-separate", action="store_true", help="Skip Demucs stem separation (solo guitar)")
    parser.add_argument("--quality", choices=["fast", "balanced", "high", "extreme"], default="balanced")
    parser.add_argument("--device", default="cpu", help="Demucs device: cpu or cuda")
    parser.add_argument("--max-duration", type=float, default=90.0, help="Max seconds to process")
    parser.add_argument("--title", default="Guitar Tab")
    parser.add_argument("--tempo", type=float, default=None, help="Override detected tempo (BPM)")
    parser.add_argument("--onset-threshold", type=float, default=0.5)
    parser.add_argument("--frame-threshold", type=float, default=0.3)
    parser.add_argument("--no-mix-aware", action="store_true", help="Disable stricter mix-aware note filters")
    parser.add_argument("--min-velocity", type=int, default=40)
    parser.add_argument("--min-duration", type=float, default=0.05, help="Min note duration in seconds")
    args = parser.parse_args()

    if args.url:
        print(f"Note: {YOUTUBE_DISCLAIMER}\n")

    config = PipelineConfig(
        separate_stems=not args.no_separate,
        demucs_quality=args.quality,
        demucs_device=args.device,
        onset_threshold=args.onset_threshold,
        frame_threshold=args.frame_threshold,
        max_duration_sec=args.max_duration,
        title=args.title,
        tempo_bpm_override=args.tempo,
        mix_aware_filtering=not args.no_mix_aware,
        min_velocity=args.min_velocity,
        min_duration_sec=args.min_duration,
    )

    def progress(stage: str, msg: str) -> None:
        print(f"[{stage}] {msg}")

    artifacts = run_pipeline(
        audio_path=args.audio,
        youtube_url=args.url,
        output_dir=args.output,
        config=config,
        on_progress=progress,
    )
    print("\nArtifacts:")
    for kind, path in artifacts.items():
        print(f"  {kind}: {path}")


if __name__ == "__main__":
    main()
