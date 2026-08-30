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
    SUPPORTED_MODELS,
    IsolateConfig,
    separate_stems,
)
from audio_to_tab.lead_rhythm import LeadRhythmThresholds
from audio_to_tab.roformer import (
    ROFORMER_INSTALL_HINT,
    ROFORMER_MODELS,
    is_roformer_backend_available,
)
from audio_to_tab.scnet import (
    SCNET_INSTALL_HINT,
    SCNET_MODELS,
    is_scnet_available,
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
            "piano quality is limited), htdemucs / htdemucs_ft (4 stems), "
            "bs_roformer_sw (opt-in 6-stem BS-RoFormer-SW), "
            "melband_roformer_guitar (opt-in 2-stem guitar specialist), "
            "guitar_scnet (opt-in 4-stem SCNet, guitar from its other stem). "
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
        help="Demucs model or opt-in RoFormer engine (default: htdemucs_6s)",
    )
    parser.add_argument(
        "--quality",
        choices=["fast", "balanced", "high", "extreme"],
        default="fast",
        help="Quality preset (affects shifts/overlap; higher = much slower)",
    )
    parser.add_argument(
        "--device",
        choices=["cpu", "cuda"],
        default="cpu",
        help="Demucs device: cpu or cuda",
    )
    parser.add_argument(
        "--max-duration",
        type=float,
        default=0.0,
        help="Length in seconds of the section to process (0 = through end of file, default)",
    )
    parser.add_argument(
        "--start",
        type=float,
        default=0.0,
        help="Start offset in seconds before processing (default: 0)",
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
            "Deprecated alias for --lead-rhythm-mode best_effort (always emit Lead/Rhythm "
            "even when confidence gates fail)."
        ),
    )
    parser.add_argument(
        "--lead-rhythm-mode",
        choices=["confident", "best_effort"],
        default="confident",
        help=(
            "Lead/Rhythm emit policy (default: confident). confident skips low-confidence "
            "splits; best_effort always writes lead_guitar/rhythm_guitar when possible."
        ),
    )
    parser.add_argument(
        "--guitar-checkpoint",
        default=None,
        help="Optional stage-1 checkpoint id (htdemucs_6s only): htdemucs_6s_guitar_ft",
    )
    parser.add_argument(
        "--two-pass",
        action="store_true",
        help=(
            "Opt-in: run 4-stem htdemucs first, then htdemucs_6s on the leftover mix. "
            "About 2× slower. Ignored unless --model htdemucs_6s."
        ),
    )
    parser.add_argument(
        "--guitar-refine",
        action="store_true",
        help=(
            "Opt-in: second-pass MelBand guitar specialist (becruily) on the guitar "
            "stem. Requires pip install -e \".[separator]\". Skipped if unavailable."
        ),
    )
    parser.add_argument(
        "--low-end-restore-db",
        type=float,
        default=0.0,
        help=(
            "Opt-in guitar-stem 60–200 Hz boost in dB (0 = off). "
            "Does not enable the bass-bleed high-pass."
        ),
    )
    parser.add_argument(
        "--sub-bass-debleed",
        action="store_true",
        help=(
            "Opt-in: subtract scaled bass/drum energy below ~150 Hz from the guitar stem "
            "(default off)."
        ),
    )
    parser.add_argument(
        "--bleed-gate",
        action="store_true",
        help=(
            "Opt-in: competitive spectral scrub of bass/cymbal flutter on the guitar "
            "stem after separation (default off)."
        ),
    )
    parser.add_argument(
        "--adaptive-fold-gain",
        action="store_true",
        help=(
            "Opt-in: search the Other→Guitar fold mix gain instead of the fixed 0.5 "
            "(default off)."
        ),
    )
    parser.add_argument(
        "--guitar-ensemble",
        action="store_true",
        help=(
            "Opt-in: also run BS-RoFormer-SW on top of the primary Demucs run and "
            "per-band blend the two guitar stems (requires the [roformer] extra; "
            "much slower; default off)."
        ),
    )
    parser.add_argument(
        "--low-end-recovery",
        action="store_true",
        help=(
            "Opt-in dense-mix recovery: enables --sub-bass-debleed and, unless "
            "--low-end-restore-db is set, applies a 3 dB harmonic restore."
        ),
    )
    parser.add_argument(
        "--fold-other-mode",
        choices=["full", "best_effort", "band_limited"],
        default="best_effort",
        help=(
            "How to fold leftover Other into Guitar (default: best_effort = skip "
            "piano-like Other, else mix the guitar band only). full = legacy mix-all."
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

    if args.model in ROFORMER_MODELS:
        if not is_roformer_backend_available():
            raise SystemExit(f"RoFormer backend is not installed. {ROFORMER_INSTALL_HINT}")
    elif args.model in SCNET_MODELS:
        if not is_scnet_available():
            raise SystemExit(f"SCNet backend is not installed. {SCNET_INSTALL_HINT}")
    elif not is_demucs_available():
        raise SystemExit(f"Demucs is not installed. {DEMUCS_INSTALL_HINT}")

    max_dur = None if args.max_duration <= 0 else args.max_duration
    start_sec = max(0.0, float(args.start))
    thr = LeadRhythmThresholds.from_env()
    if args.lr_separability_floor is not None:
        thr = replace(thr, separability_floor=args.lr_separability_floor)
    if args.lr_role_margin_min is not None:
        thr = replace(thr, role_margin_min=args.lr_role_margin_min)
    if args.lr_allow_spectral_emit:
        thr = replace(thr, allow_spectral_emit=True)

    has_thr_override = (
        args.lr_separability_floor is not None
        or args.lr_role_margin_min is not None
        or args.lr_allow_spectral_emit
    )
    sub_bass_debleed = bool(args.sub_bass_debleed or args.low_end_recovery)
    low_end_restore_db = float(args.low_end_restore_db or 0.0)
    if args.low_end_recovery and low_end_restore_db < 1e-6:
        low_end_restore_db = 3.0
    config = IsolateConfig(
        model=args.model,
        quality=args.quality,
        device=args.device,
        start_sec=start_sec,
        max_duration_sec=max_dur,
        two_stems=args.two_stems,
        lead_rhythm=bool(args.lead_rhythm or args.dual_guitar),
        dual_guitar=bool(args.dual_guitar),
        lead_rhythm_mode=(
            "best_effort"
            if (args.lead_rhythm or args.dual_guitar)
            else args.lead_rhythm_mode
        ),
        guitar_checkpoint=args.guitar_checkpoint,
        two_pass=bool(args.two_pass),
        guitar_refine=bool(args.guitar_refine),
        fold_other_mode=args.fold_other_mode,
        lead_rhythm_thresholds=thr if has_thr_override else None,
        low_end_restore_db=low_end_restore_db,
        sub_bass_debleed=sub_bass_debleed,
        bleed_gate=bool(args.bleed_gate),
        adaptive_fold_gain=bool(args.adaptive_fold_gain),
        guitar_ensemble=bool(args.guitar_ensemble),
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
