"""Score transcription output against ground-truth MIDI using mir_eval."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import mir_eval
import numpy as np
import pretty_midi

# Allow running from repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from audio_to_tab.transcribe import transcribe_audio  # noqa: E402


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _notes_from_midi(path: Path) -> tuple[np.ndarray, np.ndarray]:
    pm = pretty_midi.PrettyMIDI(str(path))
    intervals: list[list[float]] = []
    pitches_hz: list[float] = []
    for inst in pm.instruments:
        if inst.is_drum:
            continue
        for note in inst.notes:
            intervals.append([note.start, note.end])
            pitches_hz.append(float(pretty_midi.note_number_to_hz(note.pitch)))
    if not intervals:
        return np.empty((0, 2)), np.array([])
    return np.array(intervals), np.array(pitches_hz)


def score_midi_pair(ref_path: Path, est_path: Path) -> dict:
    ref_int, ref_pitch = _notes_from_midi(ref_path)
    est_int, est_pitch = _notes_from_midi(est_path)

    if len(ref_int) == 0:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0, "ref_notes": 0, "est_notes": len(est_int)}

    precision, recall, f1, _ = mir_eval.transcription.precision_recall_f1_overlap(
        ref_intervals=ref_int,
        ref_pitches=ref_pitch,
        est_intervals=est_int,
        est_pitches=est_pitch,
        offset_ratio=None,
    )
    return {
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "ref_notes": len(ref_int),
        "est_notes": len(est_int),
    }


def score_audio_transcription(wav_path: Path, ref_midi_path: Path) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        est_midi = Path(tmp) / "estimated.mid"
        transcribe_audio(wav_path, est_midi, normalize=False)
        result = score_midi_pair(ref_midi_path, est_midi)
        result["fixture_wav"] = str(wav_path)
        return result


def run_eval(fixtures_dir: Path | None = None) -> dict:
    fixtures_dir = fixtures_dir or FIXTURES_DIR
    manifest_path = fixtures_dir / "manifest.json"
    if not manifest_path.exists():
        from generate_fixtures import generate_all_fixtures

        generate_all_fixtures()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    eval_root = fixtures_dir.parent
    results: dict[str, dict] = {}

    for item in manifest:
        fid = item["id"]
        ref_midi = eval_root / item["midi"]

        # Tab round-trip test on clean MIDI (isolates tab logic)
        from audio_to_tab.tab_generate import midi_to_tab  # noqa: E402

        tab_doc = midi_to_tab(str(ref_midi))
        tab_notes = sum(len(e.notes) for e in tab_doc.events)
        tab_coverage = tab_notes / max(item["note_count"], 1)

        entry: dict = {
            "category": item["category"],
            "tab_note_coverage": round(tab_coverage, 3),
            "ref_notes": item["note_count"],
        }

        if item.get("wav"):
            wav_path = eval_root / item["wav"]
            if wav_path.exists():
                try:
                    entry["transcription"] = score_audio_transcription(wav_path, ref_midi)
                except Exception as exc:
                    entry["transcription_error"] = str(exc)
        else:
            entry["transcription"] = "skipped — no WAV (install fluidsynth)"

        results[fid] = entry

    summary = {
        "fixtures": results,
        "gate_solo_melody_f1": results.get("solo_melody", {})
        .get("transcription", {})
        .get("f1", None)
        if isinstance(results.get("solo_melody", {}).get("transcription"), dict)
        else None,
    }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate transcription against fixtures")
    parser.add_argument("--output", "-o", type=Path, default=Path("eval/results.json"))
    parser.add_argument("--fixtures", type=Path, default=FIXTURES_DIR)
    args = parser.parse_args()

    results = run_eval(args.fixtures)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(json.dumps(results, indent=2))
    print(f"\nWrote {args.output}")


if __name__ == "__main__":
    main()
