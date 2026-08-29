"""Score stage-1 guitar stems (stock vs guitar-ft vs two-pass).

Does not run Demucs. Point it at output dirs from ``audio-isolate``:

  audio-isolate --audio CLIP --output ./eval/lead_rhythm/out_stock \\
    --model htdemucs_6s --quality fast
  audio-isolate --audio CLIP --output ./eval/lead_rhythm/out_gft \\
    --model htdemucs_6s --quality fast --guitar-checkpoint htdemucs_6s_guitar_ft
  audio-isolate --audio CLIP --output ./eval/lead_rhythm/out_two_pass \\
    --model htdemucs_6s --quality fast --two-pass

Clips stay gitignored. Optional manifest field ``gt_guitar_wav`` enables SI-SDR
and high-end preservation vs ground truth. Do not publish author MoisesDB SDR.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from audio_to_tab.isolate import analyze_guitar_stem_quality  # noqa: E402


def _score_dir(label: str, out_dir: Path, gt_guitar: Path | None) -> dict[str, Any]:
    guitar = out_dir / "guitar.wav"
    competing = {
        name: out_dir / f"{name}.wav"
        for name in ("bass", "piano", "drums", "vocals")
        if (out_dir / f"{name}.wav").is_file()
    }
    diag = analyze_guitar_stem_quality(
        guitar,
        competing_stems=competing or None,
        reference_path=gt_guitar,
    )
    row = {"label": label, "dir": str(out_dir), **diag.to_dict()}
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description="Score stage-1 guitar stems across output dirs")
    parser.add_argument(
        "--dirs",
        nargs="+",
        metavar="LABEL=DIR",
        required=True,
        help="Pairs like stock=./out_stock guitar_ft=./out_gft two_pass=./out_two_pass",
    )
    parser.add_argument("--gt-guitar", type=Path, default=None, help="Optional guitar ground-truth WAV")
    parser.add_argument("--note", default="", help="Free-text listening notes")
    args = parser.parse_args()

    rows: list[dict[str, Any]] = []
    for item in args.dirs:
        if "=" not in item:
            raise SystemExit(f"Expected LABEL=DIR, got {item!r}")
        label, raw = item.split("=", 1)
        rows.append(_score_dir(label, Path(raw).expanduser().resolve(), args.gt_guitar))

    print(json.dumps({"note": args.note, "results": rows}, indent=2))
    if len(rows) >= 2 and rows[0].get("si_sdr") is not None:
        best = max(rows, key=lambda r: (r.get("si_sdr") is not None, r.get("si_sdr") or float("-inf")))
        print(f"\nHighest SI-SDR: {best['label']} ({best['si_sdr']:.2f} dB)")


if __name__ == "__main__":
    main()
