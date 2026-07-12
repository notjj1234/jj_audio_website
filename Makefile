.PHONY: install install-demucs fixtures test eval backend ui pipeline help

PYTHON ?= $(if $(wildcard .venv311/bin/python),.venv311/bin/python,python3.12)
export PYTHONPATH := src:.

help:
	@echo "Targets:"
	@echo "  make install          - Install Python dependencies"
	@echo "  make install-demucs   - Install Demucs + PyTorch"
	@echo "  make fixtures         - Generate eval MIDI fixtures"
	@echo "  make test             - Run pytest"
	@echo "  make eval             - Run transcription eval harness"
	@echo "  make ui               - Start Streamlit web UI"
	@echo "  make backend          - Start FastAPI server (API only)"
	@echo "  make pipeline         - Example CLI (needs audio file)"

install:
	$(PYTHON) -m venv .venv311 || true
	. .venv311/bin/activate && pip install -e ".[dev,eval,demucs]"

install-demucs:
	$(PYTHON) -m pip install -r requirements-demucs.txt

fixtures:
	$(PYTHON) eval/generate_fixtures.py

test:
	$(PYTHON) -m pytest tests/ -q

eval: fixtures
	$(PYTHON) eval/score_transcription.py -o eval/results.json

backend:
	$(PYTHON) -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

ui:
	$(PYTHON) -m streamlit run ui/app.py --server.port 8501

pipeline:
	@echo "Usage: audio-pipeline --audio song.wav --output ./output --no-separate"
