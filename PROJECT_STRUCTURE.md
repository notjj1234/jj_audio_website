# Project structure

> Context file for Cursor agents. Read this first for orientation. Do not treat as a task list.

Audio-to-guitar-tab and stem-isolation app: FastAPI + React SPA in production (full Compose or lite/Oracle), plus a Streamlit device-local UI (primary $0 tester path), sharing a core Python pipeline. Desktop packages via PyInstaller wrap Streamlit.

## Tree

```
/
├── README.md                            # Project overview, tester path, CLI, and local dev instructions
├── DESKTOP.md                           # Device-local tester + desktop installer runbook
├── DEPLOY.md                            # Production Docker Compose deploy runbook and env checklist
├── WEBSITE_PREP_GUIDE.txt               # Checklist for putting the FastAPI+SPA site online
├── PROJECT_STRUCTURE.md                 # This orientation file for Cursor agents
├── pyproject.toml                       # Python package metadata, dependencies, CLI entrypoints, Ruff config
├── requirements.txt                     # Pinned core Python dependencies for pip installs
├── requirements-demucs.txt              # Extra Demucs, PyTorch, torchcodec dependency layer
├── Makefile                             # Dev targets: preflight, tester, web-build, mixer-build, ui, backend, test
├── docker-compose.yml                   # Production stack: Caddy, API, worker, Postgres, Redis, MinIO
├── docker-compose.lite.yml              # Lite stack: Caddy + single API, sqlite, local disk
├── Dockerfile                           # Python 3.11 API/worker image with ffmpeg and Demucs
├── Dockerfile.web                       # Multi-stage Vite SPA build plus Caddy reverse proxy image
├── Caddyfile                            # TLS, SPA static serving, and /v1 API reverse proxy rules
├── .env.example                         # Sample production environment variables for Docker Compose
├── .env.lite.example                    # Sample env for lite/Oracle Compose (sqlite, single-flight)
├── .gitignore                           # Ignore rules for venvs, data, output, node_modules, secrets
├── .gitattributes                       # Git line-ending normalization policy
├── .python-version                      # Pins recommended local Python version (3.11)
├── docs/                                # Operational notes and capacity-spike results
│   └── oracle-free-memory-spike.md      # Demucs peak-RAM measurements vs Oracle Free 12 GB
├── .github/                             # CI workflows and Dependabot
│   ├── dependabot.yml                   # Weekly Dependabot PRs for pip and web npm
│   └── workflows/
│       └── desktop-release.yml          # Unsigned Win zip / Mac pkg via PyInstaller (tag desktop-v*)
├── packaging/                           # Desktop freeze (PyInstaller); not used by Streamlit tester path
│   ├── launcher.py                      # Starts Streamlit on 127.0.0.1; sets user cache/data + ffmpeg PATH
│   ├── audio_tools.spec                 # PyInstaller onedir spec (Streamlit + Demucs; skips backend/web)
│   ├── bundle_ffmpeg.py                 # Downloads platform ffmpeg shared build at build time
│   ├── generate_icons.sh                # Regenerates favicon and desktop icons from icon.png
│   ├── make_app.sh                      # Builds dist/AudioTools.app from PyInstaller onedir
│   ├── make_pkg.sh                      # Builds macOS .pkg installer (preferred end-user path)
│   ├── make_dmg.sh                      # Builds macOS DMG (maintainer fallback)
│   ├── pkg_scripts/postinstall          # Clears quarantine after pkg install
│   ├── Install AudioTools.command       # DMG helper: copy to Applications + eject
│   ├── icon.png                         # 1024×1024 master icon for app, SPA, and Streamlit
│   ├── icon.icns                        # macOS .icns app icon derived from icon.png
│   └── icon.ico                         # Windows .ico app icon derived from icon.png
├── .streamlit/                          # Local Streamlit server config and credentials
│   ├── config.toml                      # Streamlit headless server settings, disables usage stats
│   └── credentials.toml                 # Local Streamlit credentials placeholder for demo UI
├── .vscode/                             # Shared editor settings and tasks
│   ├── settings.json                    # VS Code Python interpreter and src analysis path settings
│   └── tasks.json                       # VS Code tasks wrapping install, ui, backend dev commands
├── .cursor/                             # Cursor agent skill definitions for this repo
│   └── skills/
│       ├── SKILL.md                     # Cursor "prompt-master" skill for prompt engineering tasks
│       └── .gitkeep                     # Keeps the skills directory tracked in git
├── backend/                             # FastAPI production API, auth, jobs, storage
│   ├── __init__.py                      # Package marker for Audio Tools FastAPI backend
│   ├── main.py                          # FastAPI app: routes, auth, uploads, jobs, WebSocket progress
│   ├── config.py                        # Env-driven backend configuration and settings model
│   ├── contracts.py                     # Pydantic API request/response schemas and enums
│   ├── capabilities.py                  # Host hardware probe and processing-mode resolution
│   ├── auth.py                          # JWT auth, password hashing, FastAPI user dependencies
│   ├── models.py                        # SQLAlchemy ORM models for users, jobs, artifacts
│   ├── db.py                            # SQLAlchemy engine, session factory, DB init
│   ├── storage.py                       # Local filesystem and S3/MinIO object storage adapters
│   ├── events.py                        # In-process and Redis job progress event fan-out
│   ├── limits.py                        # Upload size, MIME, and filename validation helpers
│   ├── worker.py                        # arq worker entrypoint for durable background jobs
│   └── jobs/                            # Background job orchestration
│       ├── __init__.py                  # Jobs subpackage marker
│       ├── manager.py                   # Durable job manager backed by DB and object storage
│       ├── runner.py                    # Executes tab pipeline and isolation jobs asynchronously
│       └── single_flight.py             # One-job-at-a-time gate for lite/RAM-limited hosts
├── src/                                 # Core audio_to_tab Python library and CLI
│   └── audio_to_tab/
│       ├── __init__.py                  # Package marker for audio-to-guitar-tab PDF pipeline
│       ├── pipeline.py                  # End-to-end audio to tab PDF orchestration
│       ├── ingest.py                    # Audio ingestion, normalization, YouTube download helpers
│       ├── separate.py                  # Demucs stem separation (subprocess or in-process when frozen)
│       ├── isolate.py                   # Standalone multi-stem Demucs isolation with diagnostics
│       ├── lead_rhythm.py               # Splits Demucs guitar stem into lead and rhythm tracks
│       ├── transcribe.py                # Audio transcription via Spotify Basic Pitch
│       ├── midi_cleanup.py              # Filters and cleans MIDI notes after pitch detection
│       ├── tab_generate.py              # MIDI to ASCII guitar tab via playability-aware fret assignment
│       ├── rhythm.py                    # Beat-grid quantization for tab timing events
│       ├── tempo.py                     # Tempo estimation from audio, MIDI, or override
│       ├── tuning.py                    # Guitar tuning constants and fretboard position utilities
│       ├── pdf_render.py                # Renders ASCII/structured tab documents to PDF via ReportLab
│       ├── mixer.py                     # Stem mixing, gain, and waveform helpers for isolation UI
│       └── cli/                         # Console entry points for each pipeline step
│           ├── __init__.py              # CLI subpackage marker
│           ├── pipeline.py              # CLI: full audio/YouTube to tab PDF pipeline
│           ├── transcribe.py            # CLI: audio file to MIDI via Basic Pitch
│           ├── mid2tab.py               # CLI: MIDI to ASCII guitar tab conversion
│           ├── tab2pdf.py               # CLI: ASCII tab or MIDI to PDF rendering
│           └── isolate.py               # CLI: multi-stem audio isolation via Demucs
├── ui/                                  # Streamlit local UI (device-local product path; not in prod compose)
│   ├── __init__.py                      # Streamlit UI package marker
│   ├── app.py                           # Streamlit multipage router entrypoint
│   ├── common.py                        # Shared upload handling, run directories, metadata helpers
│   ├── media.py                         # Preview encoding, media URLs, mix artifact cleanup
│   ├── isolate_state.py                 # Pure helpers for isolate presets, stages, progress state
│   ├── icon.png                         # Streamlit favicon copied from packaging/icon.png
│   ├── pages/                           # Streamlit page modules
│   │   ├── __init__.py                  # Pages package marker
│   │   ├── isolate.py                   # Audio Isolation page: upload, separate stems, live mixer
│   │   └── tab_pdf.py                   # Audio to Guitar Tab PDF page wrapping pipeline
│   └── stem_mixer_component/            # Custom Streamlit component: browser stem mixer
│       ├── __init__.py                  # Declares stem_mixer component; loads build or dev server
│       └── frontend/                    # Vite TypeScript project for the mixer frontend
│           ├── package.json             # npm manifest: scripts, streamlit-component-lib, Vite
│           ├── package-lock.json        # Locked dependency versions for reproducible installs
│           ├── vite.config.ts           # Vite config: build to build/, dev server port 3001
│           ├── tsconfig.json            # TypeScript compiler options for the mixer frontend
│           ├── index.html               # Dev HTML shell loading main TS entry module
│           ├── build/                   # Skipped (noise) — generated production mixer bundle
│           ├── node_modules/            # Skipped (noise) — installed JS dependencies
│           └── src/
│               ├── main.ts              # Mixer engine, playback, controls, Streamlit state sync
│               ├── style.css            # Mixer layout, stem cards, waveform, transport styling
│               └── vite-env.d.ts        # Vite client type reference for TypeScript tooling
├── web/                                 # Production React/Vite SPA
│   ├── package.json                     # npm manifest for React SPA "audio-tools-web"
│   ├── package-lock.json                # Locked dependency versions for the SPA
│   ├── tsconfig.json                    # TypeScript compiler options for the Vite app
│   ├── vite.config.ts                   # Vite dev server, API proxy to :8000, Vitest config
│   ├── vercel.json                      # Vercel SPA build output and HTML5 routing rewrites
│   ├── netlify.toml                     # Netlify SPA publish dir and fallback redirects
│   ├── .env.example                     # Optional VITE_API_BASE_URL for split SPA/API hosting
│   ├── index.html                       # SPA HTML shell loading the React entrypoint
│   ├── public/                          # Static favicon and PWA icon assets
│   │   ├── favicon.ico                  # Classic browser tab favicon
│   │   ├── favicon-32x32.png            # 32px PNG favicon
│   │   ├── apple-touch-icon.png         # iOS home-screen / Apple touch icon
│   │   └── icon-512.png                 # 512px PWA / Android icon
│   ├── dist/                            # Skipped (noise) — generated SPA production build
│   ├── node_modules/                    # Skipped (noise) — installed JS dependencies
│   └── src/
│       ├── main.tsx                     # React DOM mount and router bootstrap
│       ├── App.tsx                      # Auth shell, navigation, and routes for tab/isolate
│       ├── auth.tsx                     # JWT login context provider and session state
│       ├── api.ts                       # Typed HTTP client for backend jobs, uploads, auth
│       ├── styles.css                   # Global CSS styling for the production app
│       ├── vite-env.d.ts                # Vite/TypeScript ambient type declarations
│       ├── pages/
│       │   ├── LoginPage.tsx            # Email/password login form for API access
│       │   ├── TabPage.tsx              # Upload audio and poll tab PDF job progress
│       │   └── IsolatePage.tsx          # Upload audio, run isolation job, show live mixer
│       ├── components/
│       │   ├── JobProgress.tsx          # Displays job status, stage label, progress messages
│       │   ├── ProcessingModeSelect.tsx # Dropdown for auto/fast/balanced/GPU/lite processing modes
│       │   └── StemMixer.tsx            # React wrapper around Web Audio mixer engine
│       └── mixer/
│           ├── engine.ts                # Web Audio stem mixer: volume, mute, solo logic
│           └── engine.test.ts           # Vitest unit tests for mixer gain/audible-stem helpers
├── tests/                               # Pytest suite for API, pipeline, UI, and mixer logic
│   ├── conftest.py                      # Adds repo src/ and root to Python import path
│   ├── backend_test_utils.py            # Reconfigures backend settings for isolated tests
│   ├── test_api.py                      # FastAPI smoke tests for health, upload, isolation jobs
│   ├── test_capabilities.py             # Host capability probe and processing-mode resolution tests
│   ├── test_web_security.py             # Auth, upload limits, CORS, job persistence security tests
│   ├── test_single_flight.py            # One-job-at-a-time lite-host gate tests
│   ├── test_tab.py                      # Tab generation, tempo, MIDI cleanup, PDF render tests
│   ├── test_isolate.py                  # Demucs-mocked multi-stem isolation and diagnostics tests
│   ├── test_isolate_state.py            # Isolate page upload, progress, preset helper tests
│   ├── test_desktop_paths.py            # AUDIO_TOOLS_DATA_DIR + frozen Demucs path unit tests
│   ├── test_mixer.py                    # Stem mixer gain, audible-stem, dB conversion tests
│   ├── test_lead_rhythm.py              # Lead vs rhythm guitar post-process tests
│   ├── test_media.py                    # Isolate UI preview encoding and cleanup tests
│   ├── test_ui_common.py                # Streamlit run listing and safe deletion helper tests
│   └── test_stem_mixer_component.py     # Smoke tests for Streamlit stem mixer build/import
├── eval/                                # Transcription and lead/rhythm evaluation harnesses
│   ├── __init__.py                      # Empty eval package marker
│   ├── generate_fixtures.py             # Generates synthetic MIDI/WAV evaluation fixtures
│   ├── score_transcription.py           # Scores Basic Pitch output against fixture MIDI via mir_eval
│   ├── fixtures/                        # Synthetic MIDI/WAV fixtures for transcription eval
│   │   ├── manifest.json                # Catalog of transcription eval fixtures with metadata
│   │   ├── solo_melody.mid              # Monophonic melody MIDI eval fixture
│   │   ├── solo_melody.wav              # Monophonic melody WAV eval fixture
│   │   ├── arpeggio.mid                 # Fingerpicked arpeggio MIDI eval fixture
│   │   ├── arpeggio.wav                 # Fingerpicked arpeggio WAV eval fixture
│   │   ├── chords.mid                   # Polyphonic chords MIDI eval fixture
│   │   ├── chords.wav                   # Polyphonic chords WAV eval fixture
│   │   └── test_tone.wav                # [uncertain] extra WAV in fixtures; not in manifest
│   └── lead_rhythm/                     # Lead/rhythm guitar-split evaluation
│       ├── __init__.py                  # Lead/rhythm eval package marker
│       ├── score_lead_rhythm.py         # Scores lead/rhythm splits against multitrack manifest
│       ├── README.md                    # Checklist and instructions for the eval workflow
│       ├── RESULTS.md                   # Recorded lead/rhythm eval scoring results
│       └── manifest.example.json        # Example clip manifest schema for scoring harness
├── scripts/                             # Cross-platform development helper scripts
│   ├── dev.sh                           # macOS/Linux: install, preflight, tester, ui, backend, test, eval
│   ├── dev.ps1                          # Windows PowerShell equivalent of Makefile/dev.sh targets
│   ├── prewarm.py                       # Best-effort Basic Pitch and Demucs model prewarm script
│   └── oracle_free_memory_spike.py      # Measures Demucs peak RSS; writes Oracle Free spike doc
├── data/                                # Runtime data root: uploads, jobs, UI runs (gitignored contents)
│   ├── jobs/                            # Backend job working directories (empty placeholder)
│   ├── uploads/                         # Uploaded source audio files (empty placeholder)
│   ├── ui_runs/                         # Per-run folders (by UUID) of Streamlit isolate/tab output
│   ├── verify_no_separate/              # Local verification tab output without separation step
│   └── verify_run/                      # Local verification tab pipeline output
└── output/                              # Runtime CLI/pipeline output directory (gitignored contents)
    └── pipeline_test/                   # Example CLI pipeline output (MIDI, tab, PDF)
```

## Skipped (noise)
- `.git/` — version control metadata
- `.venv/`, `.venv311/`, `.venv312/`, `.venv-desktop/` — local Python virtual environments
- `.pytest_cache/` — pytest run cache
- `.ruff_cache/` — Ruff linter cache
- `**/__pycache__/` — Python bytecode caches (src, ui, eval, tests)
- `src/audio_to_tab_pdf.egg-info/`, `audio_to_tab_pdf.egg-info/` — generated setuptools editable-install metadata
- `web/node_modules/`, `web/dist/` — SPA installed deps and generated production build
- `ui/stem_mixer_component/frontend/node_modules/` — installed mixer frontend deps
- `ui/stem_mixer_component/frontend/build/` — generated production mixer bundle (JS/CSS)
- `packaging/ffmpeg/` — downloaded ffmpeg binaries (build-time only)
- `dist/`, `build/` — PyInstaller output
- `eval/results.json` — generated transcription eval scores (`make eval`)
- `.DS_Store` files (repo root, `src/`, `ui/`, `data/`) — macOS filesystem metadata
- `data/**` per-run contents (uploads, stems, diagnostics, previews) — runtime artifacts, not source
- `output/**` per-run contents — generated pipeline artifacts, not source

## Key entry points
- `README.md` / `DESKTOP.md` / `DEPLOY.md` — tester, desktop, and production runbooks
- `backend/main.py` — production API routes; processing modes and job wiring
- `web/src/App.tsx` — production frontend layout and routing
- `src/audio_to_tab/pipeline.py` — core audio-to-tab processing workflow
- `src/audio_to_tab/isolate.py` — core instrument-separation workflow
- `ui/app.py` — local Streamlit demo entrypoint
- `packaging/launcher.py` — desktop freeze entrypoint

## How agents should use this
- Use this file for orientation before exploring.
- Prefer the paths listed here; do not assume files outside this tree exist.
- If something here conflicts with the live repo, trust the live repo.
