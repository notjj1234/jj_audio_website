"""Score Lead/Rhythm splits against a local multitrack manifest.

Clips stay gitignored under eval/lead_rhythm/clips/. See README.md.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = Path(__file__).resolve().parent / "manifest.json"
DEFAULT_OUT = Path(__file__).resolve().parent / "RESULTS.md"


@dataclass
class ClipResult:
    clip_id: str
    mix_type: str
    gt_parts: int
    gt_lead: str | None
    outcome: str
    method: str
    emitted: bool
    label_ok: bool | None
    role_confidence: float | None
    separability: float | None
    reason: str
    elapsed_sec: float


def _load_manifest(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "clips" in data:
        return list(data["clips"])
    if isinstance(data, list):
        return data
    raise ValueError("manifest must be a list or {\"clips\": [...]}")


def _resolve_path(raw: str, base: Path) -> Path:
    p = Path(raw)
    if not p.is_absolute():
        p = (base / p).resolve()
    return p


def _label_ok(gt_lead: str | None, features: dict[str, Any], assignment_hint: str | None) -> bool | None:
    """gt_lead is 'a' or 'b' meaning stream_a/stream_b was lead, or 'left'/'right' for spatial."""
    if gt_lead is None:
        return None
    # Diagnostics store score_a_lead / score_b_lead; emit writes lead from assignment.
    # We infer from which score won when present.
    if "score_a_lead" in features and "score_b_lead" in features:
        a_wins = features["score_a_lead"] >= features["score_b_lead"]
        if gt_lead in ("a", "left", "stream_a"):
            return a_wins
        if gt_lead in ("b", "right", "stream_b"):
            return not a_wins
    if assignment_hint:
        return assignment_hint == gt_lead
    return None


def score_clip(
    entry: dict[str, Any],
    *,
    clips_dir: Path,
    work_dir: Path,
    use_basic_pitch: bool,
) -> ClipResult:
    from audio_to_tab.lead_rhythm import LeadRhythmThresholds, split_lead_rhythm_guitar

    clip_id = str(entry["id"])
    audio_path = _resolve_path(entry["path"], clips_dir)
    gt_parts = int(entry.get("gt_parts", 0))
    gt_lead = entry.get("gt_lead")
    mix_type = str(entry.get("mix_type", "unknown"))

    out = work_dir / clip_id
    out.mkdir(parents=True, exist_ok=True)
    thr = LeadRhythmThresholds.from_env()

    t0 = time.perf_counter()
    if not audio_path.exists():
        return ClipResult(
            clip_id=clip_id,
            mix_type=mix_type,
            gt_parts=gt_parts,
            gt_lead=gt_lead,
            outcome="skipped",
            method="none",
            emitted=False,
            label_ok=None,
            role_confidence=None,
            separability=None,
            reason=f"missing file: {audio_path}",
            elapsed_sec=0.0,
        )

    # Prefer a pre-isolated guitar.wav next to the clip, else the path itself.
    guitar = audio_path
    sibling = audio_path.parent / "guitar.wav"
    if sibling.exists() and audio_path.name != "guitar.wav":
        guitar = sibling

    extra, diag = split_lead_rhythm_guitar(
        guitar,
        out,
        use_basic_pitch=use_basic_pitch,
        thresholds=thr,
    )
    elapsed = time.perf_counter() - t0
    emitted = "lead_guitar" in extra and "rhythm_guitar" in extra
    label_ok = None
    if emitted and diag.outcome == "lead_rhythm":
        label_ok = _label_ok(gt_lead, diag.features or {}, None)

    return ClipResult(
        clip_id=clip_id,
        mix_type=mix_type,
        gt_parts=gt_parts,
        gt_lead=gt_lead,
        outcome=diag.outcome,
        method=diag.method,
        emitted=emitted,
        label_ok=label_ok,
        role_confidence=diag.role_confidence,
        separability=diag.separability_score,
        reason=diag.reason,
        elapsed_sec=elapsed,
    )


def aggregate(results: list[ClipResult]) -> dict[str, Any]:
    emits = [r for r in results if r.emitted]
    gt2 = [r for r in results if r.gt_parts == 2]
    gt_le1 = [r for r in results if r.gt_parts <= 1]

    split_precision = (
        sum(1 for r in emits if r.gt_parts == 2) / len(emits) if emits else None
    )
    split_recall = (
        sum(1 for r in gt2 if r.emitted) / len(gt2) if gt2 else None
    )
    ambiguous_ok = (
        sum(1 for r in gt_le1 if not r.emitted) / len(gt_le1) if gt_le1 else None
    )
    labeled = [r for r in emits if r.label_ok is not None]
    label_correctness = (
        sum(1 for r in labeled if r.label_ok) / len(labeled) if labeled else None
    )

    by_mix: dict[str, dict[str, Any]] = {}
    groups: dict[str, list[ClipResult]] = defaultdict(list)
    for r in results:
        groups[r.mix_type].append(r)
    for mix, rows in groups.items():
        g2 = [x for x in rows if x.gt_parts == 2]
        by_mix[mix] = {
            "n": len(rows),
            "emit_rate": sum(1 for x in rows if x.emitted) / len(rows) if rows else 0.0,
            "recall_gt2": (
                sum(1 for x in g2 if x.emitted) / len(g2) if g2 else None
            ),
        }

    return {
        "n": len(results),
        "split_precision": split_precision,
        "split_recall": split_recall,
        "ambiguous_rate_on_gt_le1": ambiguous_ok,
        "label_correctness": label_correctness,
        "by_mix_type": by_mix,
    }


def write_results_md(
    path: Path,
    results: list[ClipResult],
    summary: dict[str, Any],
    *,
    note: str = "",
) -> None:
    lines = [
        "# Lead/Rhythm eval results",
        "",
        f"_Generated by `eval/lead_rhythm/score_lead_rhythm.py`. {note}_",
        "",
        "## Summary",
        "",
        f"- clips: **{summary['n']}**",
        f"- split precision (emit ∧ gt_parts=2): **{summary['split_precision']}**",
        f"- split recall (gt_parts=2 ∧ emit): **{summary['split_recall']}**",
        f"- ambiguous/refuse rate on gt≤1: **{summary['ambiguous_rate_on_gt_le1']}**",
        f"- label correctness (when known): **{summary['label_correctness']}**",
        "",
        "### By mix_type",
        "",
        "| mix_type | n | emit_rate | recall_gt2 |",
        "|----------|---|-----------|------------|",
    ]
    for mix, row in sorted(summary["by_mix_type"].items()):
        lines.append(
            f"| {mix} | {row['n']} | {row['emit_rate']:.3f} | {row['recall_gt2']} |"
        )
    lines.extend(
        [
            "",
            "## Per clip",
            "",
            "| id | mix_type | gt_parts | outcome | method | emitted | label_ok | sep | role | s |",
            "|----|----------|----------|---------|--------|---------|----------|-----|------|---|",
        ]
    )
    for r in results:
        lines.append(
            f"| {r.clip_id} | {r.mix_type} | {r.gt_parts} | {r.outcome} | {r.method} | "
            f"{r.emitted} | {r.label_ok} | {r.separability} | {r.role_confidence} | "
            f"{r.elapsed_sec:.2f} |"
        )
    lines.extend(["", "## Gate", "", "Do not change `SEPARABILITY_*` / `ROLE_*` without appending a row here.", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Score Lead/Rhythm splits vs manifest")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="JSON manifest (clips gitignored; example committed as manifest.example.json)",
    )
    parser.add_argument(
        "--clips-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "clips",
        help="Base directory for relative manifest paths",
    )
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "out",
        help="Per-clip output directory",
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="RESULTS.md path")
    parser.add_argument(
        "--no-basic-pitch",
        action="store_true",
        help="Use audio-stats role features (faster; for smoke)",
    )
    parser.add_argument(
        "--note",
        default="",
        help="Optional note appended to RESULTS.md header (threshold change log)",
    )
    args = parser.parse_args()

    if not args.manifest.exists():
        example = Path(__file__).resolve().parent / "manifest.example.json"
        raise SystemExit(
            f"Manifest not found: {args.manifest}\n"
            f"Copy {example} → manifest.json and add local clips under clips/."
        )

    entries = _load_manifest(args.manifest)
    args.work_dir.mkdir(parents=True, exist_ok=True)
    results = [
        score_clip(
            e,
            clips_dir=args.clips_dir,
            work_dir=args.work_dir,
            use_basic_pitch=not args.no_basic_pitch,
        )
        for e in entries
    ]
    summary = aggregate(results)
    write_results_md(args.out, results, summary, note=args.note)
    print(json.dumps(summary, indent=2))
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
