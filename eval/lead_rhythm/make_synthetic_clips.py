#!/usr/bin/env python3
"""Generate synthetic Lead/Rhythm eval clips under eval/lead_rhythm/clips/ (gitignored).

Does not download audio. Useful for smoke-scoring the post-process and for the
mild-pan binary-pass case documented in README.md / RESEARCH.md.

  export PYTHONPATH=src:.
  python eval/lead_rhythm/make_synthetic_clips.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import soundfile as sf

SR = 44100
DUR = 2.0


def _write_stereo(path: Path, left: np.ndarray, right: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stereo = np.column_stack([left, right]).astype(np.float32)
    sf.write(str(path), stereo, SR, subtype="PCM_16")


def _write_mono_as_stereo(path: Path, mono: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stereo = np.column_stack([mono, mono]).astype(np.float32)
    sf.write(str(path), stereo, SR, subtype="PCM_16")


def hard_pan(clips: Path) -> dict:
    t = np.linspace(0, DUR, int(SR * DUR), endpoint=False)
    lead = np.sin(2 * np.pi * 659.25 * t)  # E5
    rhythm = np.sin(2 * np.pi * 146.83 * t)  # D3
    guitar = clips / "hard_pan_example" / "guitar.wav"
    _write_stereo(guitar, lead, rhythm)
    _write_mono_as_stereo(guitar.parent / "gt_lead.wav", lead)
    _write_mono_as_stereo(guitar.parent / "gt_rhythm.wav", rhythm)
    return {
        "id": "hard_pan_example",
        "path": "hard_pan_example/guitar.wav",
        "gt_parts": 2,
        "gt_lead": "left",
        "mix_type": "hard_pan",
        "gt_lead_wav": "hard_pan_example/gt_lead.wav",
        "gt_rhythm_wav": "hard_pan_example/gt_rhythm.wav",
    }


def mild_pan(clips: Path) -> dict:
    """55/45 pan of distinct lead/rhythm tones (corr ~0.98) — binary-pass case."""
    t = np.linspace(0, DUR, int(SR * DUR), endpoint=False)
    lead = np.sin(2 * np.pi * 659.25 * t)
    rhythm = np.sin(2 * np.pi * 146.83 * t)
    left = 0.55 * lead + 0.45 * rhythm
    right = 0.45 * lead + 0.55 * rhythm
    guitar = clips / "mild_pan_example" / "guitar.wav"
    _write_stereo(guitar, left, right)
    _write_mono_as_stereo(guitar.parent / "gt_lead.wav", lead)
    _write_mono_as_stereo(guitar.parent / "gt_rhythm.wav", rhythm)
    return {
        "id": "mild_pan_example",
        "path": "mild_pan_example/guitar.wav",
        "gt_parts": 2,
        "gt_lead": "a",
        "mix_type": "mild_pan",
        "gt_lead_wav": "mild_pan_example/gt_lead.wav",
        "gt_rhythm_wav": "mild_pan_example/gt_rhythm.wav",
    }


def mono_single(clips: Path) -> dict:
    t = np.linspace(0, DUR, int(SR * DUR), endpoint=False)
    mono = np.sin(2 * np.pi * 440.0 * t)
    guitar = clips / "mono_single" / "guitar.wav"
    _write_stereo(guitar, mono, mono)
    return {
        "id": "mono_single",
        "path": "mono_single/guitar.wav",
        "gt_parts": 1,
        "gt_lead": None,
        "mix_type": "mono_single",
    }


def centered_overlap(clips: Path) -> dict:
    """Same-register-ish overlap, L≡R — not a pass gate for trained separators."""
    t = np.linspace(0, DUR, int(SR * DUR), endpoint=False)
    a = np.sin(2 * np.pi * 330.0 * t)
    b = np.sin(2 * np.pi * 349.0 * t)
    mix = 0.5 * a + 0.5 * b
    guitar = clips / "centered_overlap" / "guitar.wav"
    _write_stereo(guitar, mix, mix)
    return {
        "id": "centered_overlap",
        "path": "centered_overlap/guitar.wav",
        "gt_parts": 2,
        "gt_lead": None,
        "mix_type": "centered_overlap",
    }


def double_track_wide(clips: Path) -> dict:
    t = np.linspace(0, DUR, int(SR * DUR), endpoint=False)
    rng = np.random.RandomState(0)
    take = np.sin(2 * np.pi * 220.3 * t) + 0.02 * rng.randn(len(t))
    left = 0.55 * take
    right = 0.45 * take
    guitar = clips / "double_track_wide" / "guitar.wav"
    _write_stereo(guitar, left, right)
    return {
        "id": "double_track_wide",
        "path": "double_track_wide/guitar.wav",
        "gt_parts": 1,
        "gt_lead": None,
        "mix_type": "double_track",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--clips-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "clips",
    )
    parser.add_argument(
        "--write-manifest",
        type=Path,
        default=None,
        help="Optional path to write a ready-to-run manifest.json",
    )
    args = parser.parse_args()
    clips = args.clips_dir
    clips.mkdir(parents=True, exist_ok=True)

    entries = [
        hard_pan(clips),
        mild_pan(clips),
        mono_single(clips),
        centered_overlap(clips),
        double_track_wide(clips),
    ]
    print(f"Wrote {len(entries)} clip trees under {clips}")
    if args.write_manifest is not None:
        import json

        args.write_manifest.write_text(
            json.dumps({"clips": entries}, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote {args.write_manifest}")


if __name__ == "__main__":
    main()
