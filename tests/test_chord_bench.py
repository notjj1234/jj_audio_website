"""The chord bench scorer runs on a short synthetic clip and writes every key."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

REPO = Path(__file__).resolve().parents[1]
SCORER = REPO / "docs" / "chord-recognition" / "bench" / "score_chords.py"
KEYS = (
    "root",
    "majmin",
    "sevenths",
    "mirex",
    "wrong_quality_right_root",
    "segs_per_bar",
    "share_events_under_one_beat",
    "median_event_sec",
    "meter_correct",
    "git_sha",
    "librosa_version",
)


def test_scorer_writes_every_key(tmp_path: Path):
    audio = tmp_path / "audio"
    annotations = tmp_path / "annotations"
    audio.mkdir()
    annotations.mkdir()
    sr = 22050
    duration = 10.0
    times = np.arange(int(sr * duration), dtype=np.float64) / sr
    tone = 0.2 * np.sin(2 * np.pi * 261.63 * times)
    tone += 0.15 * np.sin(2 * np.pi * 329.63 * times)
    tone += 0.12 * np.sin(2 * np.pi * 392.00 * times)
    sf.write(audio / "clip.wav", tone.astype(np.float32), sr)
    (annotations / "clip.lab").write_text("0.000\t10.000\tC:maj\n", encoding="utf-8")
    out = tmp_path / "scores.json"

    run = subprocess.run(
        [sys.executable, str(SCORER), "--audio", str(audio), "--annotations", str(annotations), "--out", str(out)],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )

    assert run.returncode == 0, run.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    for key in KEYS:
        assert key in payload
    assert payload["librosa_version"]
    assert payload["tracks"]
