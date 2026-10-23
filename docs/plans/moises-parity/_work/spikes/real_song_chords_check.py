"""Real-song check for Task 3: chords via the product module (not the spike)."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from audio_to_tab.analysis import build_beat_grid
from audio_to_tab.chords import detect_chords

PROFILE = Path("/tmp/att-song-profile-v2.json")


def main() -> int:
    for profile in json.loads(PROFILE.read_text(encoding="utf-8")):
        path = Path(profile["path"])
        grid = build_beat_grid(path, None, duration_sec=profile["duration_sec"])
        events = detect_chords(path, beats=grid.beats, bpm=grid.bpm)
        counts = Counter(event.symbol for event in events)
        print(path.name)
        print(f"  grid bpm={grid.bpm} beats={len(grid.beats)} | events={len(events)}")
        print(f"  top: {counts.most_common(8)}")
        print(
            "  first: "
            + ", ".join(f"{event.start:.1f}-{event.end:.1f}:{event.symbol}" for event in events[:12])
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
