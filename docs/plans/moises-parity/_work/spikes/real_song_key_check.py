"""Real-song check for Task 2: key from chords, BPM/grid from the metronome contract."""

from __future__ import annotations

import json
from pathlib import Path

from audio_to_tab.analysis import ChordEvent, build_beat_grid
from audio_to_tab.key import estimate_key

PROFILE = Path("/tmp/att-song-profile-v2.json")


def main() -> int:
    if not PROFILE.is_file():
        print(f"missing {PROFILE}; run song_profile.py first")
        return 1
    for profile in json.loads(PROFILE.read_text(encoding="utf-8")):
        path = Path(profile["path"])
        chords = tuple(ChordEvent(a, b, symbol, confidence) for a, b, symbol, confidence in profile["chord_runs"])
        key, confidence = estimate_key(
            path,
            bpm=profile["tempo_bpm"],
            beats=tuple(),
            chords=chords,
        )
        grid = build_beat_grid(path, None, duration_sec=profile["duration_sec"])
        print(path.name)
        print(f"  key={key} ({confidence})")
        print(
            f"  bpm={grid.bpm} ({grid.bpm_confidence}) "
            f"beats={len(grid.beats)} downbeats={len(grid.downbeats)}"
        )
        print(f"  warnings={grid.warnings}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
