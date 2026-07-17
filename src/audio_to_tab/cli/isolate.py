"""CLI: multi-stem audio isolation via Demucs."""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from dataclasses import replace
from pathlib import Path

from audio_to_tab.isolate import (
    DEMUCS_INSTALL_HINT,
    IsolateConfig,
    SUPPORTED_MODELS,
    separate_stems,
)
from audio_to_tab.lead_rhythm import LeadRhythmThresholds
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
        default=0.0,
        help="Max seconds to process (0 = full file, default)",
    )
    parser.add_argument(
        "--two-stems",
        default=None,
        help="Optional karaoke-style split, e.g. vocals (produces that stem + no_<stem>)",
    )
    parser.add_argument(
        "--lead-rhythm",
        action="store_true",
        help=(
            "Deprecated and ignored: the Lead/Rhythm split of the Demucs guitar "
            "stem (htdemucs_6s) is now attempted automatically whenever a guitar "
            "stem is produced. Emits lead_guitar/rhythm_guitar only when "
            "confidence is high; otherwise keeps combined guitar and writes "
            "diagnostics."
        ),
    )
    parser.add_argument(
        "--dual-guitar",
        action="store_true",
        help="Deprecated and ignored alias for --lead-rhythm (split is now automatic)",
    )
    parser.add_argument(
        "--lr-separability-floor",
        type=float,
        default=None,
        help="Eval/CLI override: spatial separability floor (or ATT_LR_SEPARABILITY_FLOOR)",
    )
    parser.add_argument(
        "--lr-role-margin-min",
        type=float,
        default=None,
        help="Eval/CLI override: role confidence margin (or ATT_LR_ROLE_MARGIN_MIN)",
    )
    parser.add_argument(
        "--lr-allow-spectral-emit",
        action="store_true",
        help="Eval only: allow HPSS spectral candidates to emit Lead/Rhythm (off by default)",
    )
    args = parser.parse_args()

    if args.dual_guitar:
        warnings.warn(
            "--dual-guitar is deprecated; use --lead-rhythm",
            DeprecationWarning,
            stacklevel=1,
        )
        print(
            "Warning: --dual-guitar is deprecated; use --lead-rhythm",
            file=sys.stderr,
        )

    if not is_demucs_available():
        raise SystemExit(f"Demucs is not installed. {DEMUCS_INSTALL_HINT}")

    max_dur = None if args.max_duration <= 0 else args.max_duration
    thr = LeadRhythmThresholds.from_env()
    if args.lr_separability_floor is not None:
        thr = replace(thr, separability_floor=args.lr_separability_floor)
    if args.lr_role_margin_min is not None:
        thr = replace(thr, role_margin_min=args.lr_role_margin_min)
    if args.lr_allow_spectral_emit:
        thr = replace(thr, allow_spectral_emit=True)

    config = IsolateConfig(
        model=args.model,
        quality=args.quality,
        device=args.device,
        max_duration_sec=max_dur,
        two_stems=args.two_stems,
        lead_rhythm=bool(args.lead_rhythm or args.dual_guitar),
        dual_guitar=bool(args.dual_guitar),
        lead_rhythm_thresholds=thr if (args.lead_rhythm or args.dual_guitar) else None,
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

    diag_path = artifacts.get("guitar_split_diagnostics")
    if diag_path and Path(diag_path).exists():
        data = json.loads(Path(diag_path).read_text(encoding="utf-8"))
        parts = [
            f"outcome={data.get('outcome')}",
            f"method={data.get('method')}",
        ]
        if data.get("separability_score") is not None:
            parts.append(f"separability={data['separability_score']:.3f}")
        if data.get("role_confidence") is not None:
            parts.append(f"role_confidence={data['role_confidence']:.3f}")
        print(f"\nLead/Rhythm: {', '.join(parts)} — {data.get('reason')}")


if __name__ == "__main__":
    main()
