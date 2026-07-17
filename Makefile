.PHONY: install install-demucs fixtures test eval eval-lead-rhythm backend ui pipeline mixer-build help _check_python

VENV := .venv311
VENV_PYTHON := $(VENV)/bin/python

# Prefer project venv; else 3.11 → 3.12 → 3.10 (Basic Pitch needs <3.13)
PYTHON ?= $(firstword \
	$(wildcard $(VENV_PYTHON)) \
	$(shell command -v python3.11 2>/dev/null) \
	$(shell command -v python3.12 2>/dev/null) \
	$(shell command -v python3.10 2>/dev/null) \
	$(shell command -v python3 2>/dev/null) \
)

# Always bootstrap the venv from a host interpreter (not an existing venv)
HOST_PYTHON := $(firstword \
	$(shell command -v python3.11 2>/dev/null) \
	$(shell command -v python3.12 2>/dev/null) \
	$(shell command -v python3.10 2>/dev/null) \
	$(shell command -v python3 2>/dev/null) \
)

export PYTHONPATH := src:.

help:
	@echo "Targets:"
	@echo "  make install          - Create .venv311 and install dependencies"
	@echo "  make install-demucs   - Install Demucs + PyTorch into the venv"
	@echo "  make fixtures         - Generate eval MIDI fixtures"
	@echo "  make test             - Run pytest"
	@echo "  make eval             - Run transcription eval harness"
	@echo "  make eval-lead-rhythm - Score Lead/Rhythm vs local manifest (clips gitignored)"
	@echo "  make ui               - Start Streamlit web UI"
	@echo "  make backend          - Start FastAPI server (API only)"
	@echo "  make pipeline         - Example CLI (needs audio file)"
	@echo "  make mixer-build      - Build live stem mixer frontend (Node 18+)"
	@echo ""
	@echo "Without make: ./scripts/dev.sh <target>  |  Windows: .\\scripts\\dev.ps1 <target>"

_check_python:
	@if [ -z "$(HOST_PYTHON)" ]; then \
		echo "No Python found. On macOS: brew install python@3.11"; \
		exit 1; \
	fi
	@$(HOST_PYTHON) -c 'import sys; v=sys.version_info[:2]; assert (3,10)<=v<(3,13), f"Need Python 3.10–3.12, found {sys.version}. On macOS: brew install python@3.11"'

install: _check_python
	@echo "Creating $(VENV) with $(HOST_PYTHON)..."
	$(HOST_PYTHON) -m venv $(VENV)
	$(VENV_PYTHON) -m pip install -U pip
	$(VENV_PYTHON) -m pip install -e ".[dev,eval,demucs]"
	@echo "Done. Run: make ui   (or ./scripts/dev.sh ui)"

install-demucs:
	$(PYTHON) -m pip install -r requirements-demucs.txt

fixtures:
	$(PYTHON) eval/generate_fixtures.py

test:
	$(PYTHON) -m pytest tests/ -q

eval: fixtures
	$(PYTHON) eval/score_transcription.py -o eval/results.json

eval-lead-rhythm:
	$(PYTHON) eval/lead_rhythm/score_lead_rhythm.py

backend:
	$(PYTHON) -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

ui:
	@test -x $(VENV_PYTHON) || (echo "Run make install first"; exit 1)
	$(VENV_PYTHON) -m streamlit run ui/app.py --server.port 8501

mixer-build:
	cd ui/stem_mixer_component/frontend && npm install && npm run build

pipeline:
	@echo "Usage: audio-pipeline --audio song.wav --output ./output --no-separate"
