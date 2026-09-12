#!/usr/bin/env bash
# Cross-platform-friendly runner for macOS/Linux (no `make` required).
# Usage: ./scripts/dev.sh install | ui | tester | preflight | backend | test | ...
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
  echo "On Linux: install python3.11 (or 3.10/3.12) + ffmpeg" >&2
  return 1
}

venv_python() {
  if [[ -x "${VENV}/bin/python" ]]; then
    echo "${VENV}/bin/python"
  else
    host_python
  fi
}

ffmpeg_hint() {
  if [[ "$(uname -s)" == "Darwin" ]]; then
    echo "Install ffmpeg: brew install ffmpeg"
  else
    echo "Install ffmpeg: sudo apt install ffmpeg   (or your distro equivalent)"
  fi
}

preflight() {
  local py
  py="$(host_python)"
  echo "Python OK: $py ($("$py" -c 'import sys; print(sys.version.split()[0])'))"

  if ! command -v ffmpeg >/dev/null 2>&1; then
    echo "ffmpeg not found on PATH." >&2
    ffmpeg_hint >&2
    return 1
  fi
  echo "ffmpeg OK: $(command -v ffmpeg)"

  # Best-effort RAM / disk hints (do not fail).
  if [[ "$(uname -s)" == "Darwin" ]]; then
    local mem_bytes
    mem_bytes="$(sysctl -n hw.memsize 2>/dev/null || echo 0)"
    if [[ "$mem_bytes" =~ ^[0-9]+$ ]] && (( mem_bytes > 0 )); then
      local mem_gb=$(( mem_bytes / 1024 / 1024 / 1024 ))
      echo "RAM: ~${mem_gb} GB (16 GB preferred; 8 GB min + short clips + fast quality)"
      if (( mem_gb < 8 )); then
        echo "Warning: under 8 GB RAM — use ≤90 s clips and Quality fast." >&2
      elif (( mem_gb < 16 )); then
        echo "Warning: under 16 GB RAM — prefer short clips and Quality fast." >&2
      fi
    fi
  elif [[ -r /proc/meminfo ]]; then
    local mem_kb
    mem_kb="$(awk '/MemTotal:/ {print $2}' /proc/meminfo)"
    if [[ "$mem_kb" =~ ^[0-9]+$ ]]; then
      local mem_gb=$(( mem_kb / 1024 / 1024 ))
      echo "RAM: ~${mem_gb} GB (16 GB preferred; 8 GB min + short clips + fast quality)"
      if (( mem_gb < 8 )); then
        echo "Warning: under 8 GB RAM — use ≤90 s clips and Quality fast." >&2
      elif (( mem_gb < 16 )); then
        echo "Warning: under 16 GB RAM — prefer short clips and Quality fast." >&2
      fi
    fi
  fi

  local free_kb
  free_kb="$(df -k "$ROOT" 2>/dev/null | awk 'NR==2 {print $4}')"
  if [[ "$free_kb" =~ ^[0-9]+$ ]]; then
    local free_gb=$(( free_kb / 1024 / 1024 ))
    echo "Free disk (project volume): ~${free_gb} GB (need ~5 GB for venv + models)"
    if (( free_gb < 5 )); then
      echo "Warning: less than ~5 GB free disk." >&2
    fi
  fi
  echo "Preflight OK."
}

install_torch_cpu_if_needed() {
  # macOS uses default PyPI wheels (MPS/CPU). Windows/Linux: prefer CPU index.
  local py="$1"
  local os
  os="$(uname -s)"
  if [[ "$os" == "Linux" ]]; then
    echo "Installing PyTorch CPU wheels…"
    "$py" -m pip install --upgrade torch torchaudio --index-url https://download.pytorch.org/whl/cpu
  fi
}

install_tester_deps() {
  local py
  py="$(host_python)"
  echo "Creating ${VENV} with ${py}..."
  "$py" -m venv "$VENV"
  "${VENV}/bin/python" -m pip install -U pip
  install_torch_cpu_if_needed "${VENV}/bin/python"
  "${VENV}/bin/python" -m pip install -e ".[demucs,roformer,separator]"
  echo "Done. Run: ./scripts/dev.sh ui   (or ./scripts/dev.sh tester)"
}

run_ui() {
  local py
  if [[ ! -x "${VENV}/bin/python" ]]; then
    echo "Run ./scripts/dev.sh install (or tester) first" >&2
    exit 1
  fi
  py="${VENV}/bin/python"
  echo "Starting UI at http://127.0.0.1:8501"
  export CI=1
  # Empty line satisfies Streamlit's one-time email prompt when stdin is not a TTY.
  printf '\n' | "$py" -m streamlit run ui/app.py \
    --server.address=127.0.0.1 \
    --server.port=8501 \
    --server.headless=false \
    --browser.gatherUsageStats=false
}

cmd="${1:-help}"
shift || true

case "$cmd" in
  help|-h|--help)
    cat <<'EOF'
Targets:
  ./scripts/dev.sh preflight        Check Python 3.10–3.12, ffmpeg, RAM/disk hints
  ./scripts/dev.sh tester           Preflight + install (if needed) + prewarm + UI
  ./scripts/dev.sh install          Create .venv311 and install contributor deps
  ./scripts/dev.sh install-demucs   Install Demucs + PyTorch into the venv
  ./scripts/dev.sh fixtures         Generate eval MIDI fixtures
  ./scripts/dev.sh test             Run pytest
  ./scripts/dev.sh eval             Run transcription eval harness
  ./scripts/dev.sh eval-lead-rhythm Score Lead/Rhythm vs local manifest
  ./scripts/dev.sh ui               Start Streamlit UI (http://127.0.0.1:8501)
  ./scripts/dev.sh backend          Start FastAPI server (http://localhost:8000)
  ./scripts/dev.sh mixer-build      Build live stem mixer frontend (Node 18+)
  ./scripts/dev.sh region-picker-build  Build waveform region picker frontend (Node 18+)
  ./scripts/dev.sh mix-tabs-build       Build Moises-style mix tab strip (Node 18+)
EOF
    ;;
  preflight)
    preflight
    ;;
  tester)
    preflight
    if [[ ! -x "${VENV}/bin/python" ]]; then
      install_tester_deps
    fi
    echo "Prewarming models (first run may download weights)…"
    "$(venv_python)" scripts/prewarm.py || true
    run_ui
    ;;
  mixer-build)
    (cd ui/stem_mixer_component/frontend && npm install && npm run build)
    echo "Stem mixer frontend built."
    ;;
  region-picker-build)
    (cd ui/region_picker_component/frontend && npm install && npm run build)
    echo "Region picker frontend built."
    ;;
  mix-tabs-build)
    (cd ui/mix_tabs_component/frontend && npm install && npm run build)
    echo "Mix tabs frontend built."
    ;;
  install)
    PY="$(host_python)"
    echo "Creating ${VENV} with ${PY}..."
    "$PY" -m venv "$VENV"
    "${VENV}/bin/python" -m pip install -U pip
    install_torch_cpu_if_needed "${VENV}/bin/python"
    "${VENV}/bin/python" -m pip install -e ".[dev,eval,demucs,roformer,separator]"
    echo "Done. Run: ./scripts/dev.sh ui   (or ./scripts/dev.sh tester)"
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
    run_ui
    ;;
  *)
    echo "Unknown target: $cmd (try: ./scripts/dev.sh help)" >&2
    exit 1
    ;;
esac
