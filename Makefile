.PHONY: install install-demucs install-roformer fixtures test eval eval-lead-rhythm eval-lead-rhythm-synth backend ui pipeline mixer-build help _check_python preflight tester desktop-bundle-ffmpeg desktop-build desktop-app desktop-pkg desktop-dmg

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
	@echo "  make preflight        - Check Python 3.10–3.12, ffmpeg, RAM/disk hints"
	@echo "  make tester           - Preflight + install (if needed) + prewarm + UI"
	@echo "  make install          - Create .venv311 and install dependencies"
	@echo "  make install-demucs   - Install Demucs + PyTorch into the venv"
	@echo "  make install-roformer - Optional BS-RoFormer-SW extra (guitar quality)"
	@echo "  make fixtures         - Generate eval MIDI fixtures"
	@echo "  make test             - Run pytest"
	@echo "  make eval             - Run transcription eval harness"
	@echo "  make eval-lead-rhythm - Score Lead/Rhythm vs local manifest (clips gitignored)"
	@echo "  make eval-lead-rhythm-synth - Generate synthetic clips + score (smoke)"
	@echo "  make ui               - Start Streamlit demo UI (local only)"
	@echo "  make backend          - Start FastAPI server"
	@echo "  make web              - Start Vite SPA (dev, proxies API)"
	@echo "  make web-build        - Production build of web/"
	@echo "  make pipeline         - Example CLI (needs audio file)"
	@echo "  make mixer-build      - Build Streamlit stem mixer frontend (Node 18+)"
	@echo "  make desktop-bundle-ffmpeg - Download platform ffmpeg into packaging/ffmpeg/current"
	@echo "  make desktop-build    - PyInstaller onedir (needs .venv-desktop + bundled ffmpeg)"
	@echo "  make desktop-app      - Wrap dist/AudioTools into dist/AudioTools.app (macOS)"
	@echo "  make desktop-pkg      - Build .pkg installer in ~/Downloads (macOS; preferred)"
	@echo "  make desktop-dmg      - Build .dmg in ~/Downloads (macOS; maintainer fallback)"
	@echo ""
	@echo "Without make: ./scripts/dev.sh <target>  |  Windows: .\\scripts\\dev.ps1 <target>"

_check_python:
	@if [ -z "$(HOST_PYTHON)" ]; then \
		echo "No Python found. On macOS: brew install python@3.11"; \
		exit 1; \
	fi
	@$(HOST_PYTHON) -c 'import sys; v=sys.version_info[:2]; assert (3,10)<=v<(3,13), f"Need Python 3.10–3.12, found {sys.version}. On macOS: brew install python@3.11"'

preflight:
	./scripts/dev.sh preflight

tester:
	./scripts/dev.sh tester

install: _check_python
	@echo "Creating $(VENV) with $(HOST_PYTHON)..."
	$(HOST_PYTHON) -m venv $(VENV)
	$(VENV_PYTHON) -m pip install -U pip
	@if [ "$$(uname -s)" = "Linux" ]; then \
		$(VENV_PYTHON) -m pip install --upgrade torch torchaudio --index-url https://download.pytorch.org/whl/cpu; \
	fi
	$(VENV_PYTHON) -m pip install -e ".[dev,eval,demucs,roformer,separator]"
	@echo "Done. Run: make ui   (or make tester / ./scripts/dev.sh tester)"

install-demucs:
	$(PYTHON) -m pip install -r requirements-demucs.txt

install-roformer:
	$(PYTHON) -m pip install -e ".[roformer,separator]"

fixtures:
	$(PYTHON) eval/generate_fixtures.py

test:
	$(PYTHON) -m pytest tests/ -q

eval: fixtures
	$(PYTHON) eval/score_transcription.py -o eval/results.json

eval-lead-rhythm:
	$(PYTHON) eval/lead_rhythm/score_lead_rhythm.py

eval-lead-rhythm-synth:
	$(PYTHON) eval/lead_rhythm/make_synthetic_clips.py --write-manifest eval/lead_rhythm/manifest.json
	$(PYTHON) eval/lead_rhythm/score_lead_rhythm.py --no-basic-pitch --emit-mode confident --note "synthetic smoke (confident emit)"

backend:
	$(PYTHON) -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

ui:
	@test -x $(VENV_PYTHON) || (echo "Run make install (or make tester) first"; exit 1)
	$(VENV_PYTHON) -m streamlit run ui/app.py \
		--server.address=127.0.0.1 \
		--server.port=8501 \
		--server.headless=false \
		--browser.gatherUsageStats=false

web:
	cd web && npm install && npm run dev

web-build:
	cd web && npm install && npm run build && npm test

mixer-build:
	cd ui/stem_mixer_component/frontend && npm install && npm run build

region-picker-build:
	cd ui/region_picker_component/frontend && npm install && npm run build

mix-tabs-build:
	cd ui/mix_tabs_component/frontend && npm install && npm run build

# Desktop freeze (macOS maintainer path). Windows: see README.md PowerShell block.
DESKTOP_PYTHON := $(firstword \
	$(wildcard .venv-desktop/bin/python) \
	$(wildcard .venv-desktop/Scripts/python.exe) \
)

desktop-bundle-ffmpeg:
	@test -n "$(DESKTOP_PYTHON)" || (echo "Create .venv-desktop first (see README desktop build)"; exit 1)
	$(DESKTOP_PYTHON) packaging/bundle_ffmpeg.py

desktop-build:
	@test -n "$(DESKTOP_PYTHON)" || (echo "Create .venv-desktop first (see README desktop build)"; exit 1)
	@test -d packaging/ffmpeg/current || (echo "Run make desktop-bundle-ffmpeg first"; exit 1)
	$(DESKTOP_PYTHON) -m PyInstaller packaging/audio_tools.spec --noconfirm --clean

desktop-app:
	@test "$$(uname -s)" = "Darwin" || (echo "desktop-app is macOS only"; exit 1)
	chmod +x packaging/make_app.sh
	./packaging/make_app.sh

desktop-pkg:
	@test "$$(uname -s)" = "Darwin" || (echo "desktop-pkg is macOS only"; exit 1)
	chmod +x packaging/make_pkg.sh
	./packaging/make_pkg.sh

desktop-dmg:
	@test "$$(uname -s)" = "Darwin" || (echo "desktop-dmg is macOS only"; exit 1)
	chmod +x packaging/make_dmg.sh
	./packaging/make_dmg.sh

pipeline:
	@echo "Usage: audio-pipeline --audio song.wav --output ./output --no-separate"
