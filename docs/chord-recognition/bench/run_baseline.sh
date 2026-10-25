#!/bin/sh
# Phase 0 snapshot. Re-running after the detector changes overwrites baseline.json
# with the new numbers; the committed/checked snapshot is the pre-change run.
set -eu
ROOT="$(CDPATH= cd -- "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
PY="$ROOT/.venv311/bin/python"
"$PY" "$ROOT/docs/chord-recognition/bench/score_chords.py" \
  --baseline \
  --out "$ROOT/docs/chord-recognition/bench/baseline.json"
