"""Lyrics spike: faster-whisper small on the reference songs, word timestamps on.

    .venv311/bin/python docs/plans/moises-parity/_work/spikes/lyrics_spike.py \
        "/path/song.mp3" ["/path/instrumental.mp3"]

Reads the pinned model from ~/.cache/audio_to_tab/analysis/faster-whisper-small.
Writes JSON next to /tmp for inspection; prints a compact report.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

MODEL_DIR = Path.home() / ".cache" / "audio_to_tab" / "analysis" / "faster-whisper-small"


def main(argv: list[str]) -> int:
    paths = [Path(p) for p in argv[1:]]
    if not paths:
        print("usage: lyrics_spike.py <audio> [audio...]")
        return 2
    assert MODEL_DIR.is_dir(), f"missing model dir: {MODEL_DIR}"

    from faster_whisper import WhisperModel

    t0 = time.perf_counter()
    model = WhisperModel(str(MODEL_DIR), device="cpu", compute_type="int8")
    print(f"model loaded in {time.perf_counter() - t0:.1f}s")

    results = []
    for path in paths:
        assert path.is_file(), f"missing {path}"
        started = time.perf_counter()
        segments, info = model.transcribe(
            str(path),
            word_timestamps=True,
            vad_filter=True,
            beam_size=5,
        )
        rows = []
        word_count = 0
        bad_words = 0
        for seg in segments:
            words = []
            for word in seg.words or []:
                word_count += 1
                if word.end < word.start or word.start < 0:
                    bad_words += 1
                words.append(
                    {
                        "start": round(float(word.start), 2),
                        "end": round(float(word.end), 2),
                        "text": word.word,
                        "prob": round(float(word.probability), 3),
                    }
                )
            rows.append(
                {
                    "start": round(float(seg.start), 2),
                    "end": round(float(seg.end), 2),
                    "text": seg.text.strip(),
                    "words": words,
                }
            )
        elapsed = time.perf_counter() - started
        duration = float(getattr(info, "duration", 0.0) or 0.0)
        result = {
            "path": str(path),
            "language": getattr(info, "language", None),
            "language_probability": round(float(getattr(info, "language_probability", 0.0) or 0.0), 3),
            "duration_sec": round(duration, 1),
            "elapsed_sec": round(elapsed, 1),
            "realtime_factor": round(duration / max(elapsed, 1e-9), 1),
            "segments": rows,
            "word_count": word_count,
            "bad_word_timestamps": bad_words,
        }
        results.append(result)

        print("=" * 70)
        print(path.name)
        print(
            f"  lang={result['language']} p={result['language_probability']} "
            f"duration={duration:.1f}s elapsed={elapsed:.1f}s RTF={result['realtime_factor']}x "
            f"words={word_count} bad={bad_words}"
        )
        for row in rows[:12]:
            preview = " ".join(w["text"].strip() for w in row["words"])[:100]
            print(f"  {row['start']:7.2f}-{row['end']:7.2f}  {preview}")

    out = Path("/tmp/att-lyrics-spike.json")
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
