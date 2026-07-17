#!/usr/bin/env bash
# Cross-platform-friendly runner for macOS/Linux (no `make` required).
# Usage: ./scripts/dev.sh install | ui | backend | test | eval | eval-lead-rhythm | fixtures | install-demucs | help
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VENV="${ROOT}/.venv311"
export PYTHONPATH="src:."

host_python() {
  local c
  for c in python3.11 python3.12 python3.10; do
    if command -v "$c" >/dev/null 2>&1; then
      if "$c" -c 'import sys; raise SystemExit(0 if (3,10)<=sys.version_info[:2]<(3,13) else 1)'; then
        echo "$c"
        return 0
      fi
    fi
  done
  if command -v python3 >/dev/null 2>&1; then
    if python3 -c 'import sys; raise SystemExit(0 if (3,10)<=sys.version_info[:2]<(3,13) else 1)'; then
      echo "python3"
      return 0
    fi
  fi
  echo "Need Python 3.10–3.12 (3.11 recommended)." >&2
  echo "On macOS: brew install python@3.11 ffmpeg" >&2
  return 1
}

venv_python() {
  if [[ -x "${VENV}/bin/python" ]]; then
    echo "${VENV}/bin/python"
  else
    host_python
  fi
}

cmd="${1:-help}"
shift || true

case "$cmd" in
  help|-h|--help)
    cat <<'EOF'
Targets:
  ./scripts/dev.sh install          Create .venv311 and install dependencies
  ./scripts/dev.sh install-demucs   Install Demucs + PyTorch into the venv
  ./scripts/dev.sh fixtures         Generate eval MIDI fixtures
  ./scripts/dev.sh test             Run pytest
  ./scripts/dev.sh eval             Run transcription eval harness
  ./scripts/dev.sh eval-lead-rhythm Score Lead/Rhythm vs local manifest
  ./scripts/dev.sh ui               Start Streamlit web UI (http://localhost:8501)
  ./scripts/dev.sh backend          Start FastAPI server (http://localhost:8000)
  ./scripts/dev.sh mixer-build      Build live stem mixer frontend (Node 18+)
EOF
    ;;
  mixer-build)
    (cd ui/stem_mixer_component/frontend && npm install && npm run build)
    echo "Stem mixer frontend built."
    ;;
  install)
    PY="$(host_python)"
    echo "Creating ${VENV} with ${PY}..."
    "$PY" -m venv "$VENV"
    "${VENV}/bin/python" -m pip install -U pip
    "${VENV}/bin/python" -m pip install -e ".[dev,eval,demucs]"
    echo "Done. Run: ./scripts/dev.sh ui"
    ;;
  install-demucs)
    "$(venv_python)" -m pip install -r requirements-demucs.txt
    ;;
  fixtures)
    "$(venv_python)" eval/generate_fixtures.py
    ;;
  test)
    "$(venv_python)" -m pytest tests/ -q
    ;;
  eval)
    "$(venv_python)" eval/generate_fixtures.py
    "$(venv_python)" eval/score_transcription.py -o eval/results.json
    ;;
  eval-lead-rhythm)
    "$(venv_python)" eval/lead_rhythm/score_lead_rhythm.py
    ;;
  backend)
    "$(venv_python)" -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
    ;;
  ui)
    "$(venv_python)" -m streamlit run ui/app.py --server.port 8501
    ;;
  *)
    echo "Unknown target: $cmd (try: ./scripts/dev.sh help)" >&2
    exit 1
    ;;
esac
