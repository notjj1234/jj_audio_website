# Audio Tools (Tab PDF + Isolation)

**Production website:** FastAPI + Vite SPA behind Caddy (Postgres, Redis/arq workers, MinIO). See [`DEPLOY.md`](DEPLOY.md) and `docker compose up`.

**Local demo UI:** Streamlit (`make ui`) — Tab PDF + Isolation for development only; **not** included in production compose.

Production flows:

1. **Audio → Guitar Tab PDF** — convert MP3/WAV into **draft** guitar tablature PDFs (YouTube off by default on public hosts).
2. **Audio Isolation** — Demucs multi-stem split with live Web Audio mixer in the SPA.

> **Tab quality expectation:** Best on solo acoustic guitar. Output is a starting sketch, not a finished transcription.

## Pipeline (Tab PDF)

```
Audio / YouTube → [Demucs guitar stem] → Basic Pitch → MIDI cleanup → Fret assignment → PDF
```

## Audio Isolation

Standalone stem separation (does not run transcription). Uses the same Demucs install as the tab pipeline.

| Model | Stems |
|-------|--------|
| `htdemucs_6s` (default) | drums, bass, other, vocals, guitar, piano |
| `htdemucs` / `htdemucs_ft` | drums, bass, other, vocals |

**Caveats:** CPU separation is slow (~track length or longer; higher quality presets multiply time). On `htdemucs_6s`, piano often has bleeding/artifacts. First run downloads model weights (large).

```bash
# CLI
export PYTHONPATH=src
audio-isolate --audio song.wav --output ./output/stems --model htdemucs_6s --quality fast --lead-rhythm

# Or via module if console script not installed
python -m audio_to_tab.cli.isolate --audio song.wav --output ./output/stems
```

In the web UI (`make ui`), open **Audio Isolation** from the sidebar. After separation:

- Use the **live mixer** to play all stems in sync, with per-stem volume (−60…+24 dB), mute, and solo — changes apply instantly without re-running Demucs or resetting the playhead.
- Download individual stems or a ZIP of originals.
- **Prepare current mix download** exports a server-side mix using the current mixer levels.

Optional **Lead / Rhythm split** (`htdemucs_6s` only, `--lead-rhythm` / UI checkbox): after Demucs, try to emit `lead_guitar` / `rhythm_guitar` when a spatial (preferred) or register (STFT band) candidate looks separable **and** role confidence is high. HPSS spectral pairs are diagnostics-only (no emit) unless explicitly enabled for eval. Otherwise the combined `guitar` stem is kept and `guitar_split_diagnostics.json` explains why. Quality presets affect Demucs only; the Lead/Rhythm post-process does not. This is not a guarantee for centered overlapping guitars. (`--dual-guitar` remains a deprecated alias.)

Eval: local multitrack scoring via `make eval-lead-rhythm` (see [`eval/lead_rhythm/README.md`](eval/lead_rhythm/README.md)).

Long tracks may use downsampled preview audio in the browser mixer (originals still used for downloads).

Contributor note: the live mixer is a Streamlit custom component. Built assets live under `ui/stem_mixer_component/frontend/build/`. To rebuild after editing the frontend: `.\scripts\dev.ps1 mixer-build` or `./scripts/dev.sh mixer-build` (requires Node 18+).

## Requirements

- Python 3.10–3.12 (3.11 recommended; Basic Pitch does not support 3.13)
- ffmpeg (`brew install ffmpeg` / `apt install ffmpeg`)
- Optional: fluidsynth (for eval fixture WAV synthesis)

## Quick start (Windows)

```powershell
# One-time: Python 3.11 from https://www.python.org/downloads/ (not 3.13)
# One-time: FFmpeg full/shared build on PATH, e.g.  winget install Gyan.FFmpeg

# Install app deps (includes Demucs + PyTorch; first run ~2GB download)
.\scripts\dev.ps1 install

# Local Streamlit demo (not production)
.\scripts\dev.ps1 ui
# Opens http://localhost:8501

# Production-shaped stack (requires Docker + ATT_SECRET_KEY)
# copy .env.example → .env, then:
# docker compose up -d --build
```

In **Cursor**: `Ctrl+Shift+P` → **Tasks: Run Task** → **ui** (Streamlit demo).

If PowerShell blocks the script: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

## Quick start (macOS / Linux)

```bash
# One-time OS deps (macOS)
xcode-select --install          # provides `make` (skip if already installed)
brew install python@3.11 ffmpeg

# Install app deps (includes Demucs + PyTorch; first run ~2GB download)
make install
# If `make` is unavailable:  chmod +x scripts/dev.sh && ./scripts/dev.sh install

# Launch web UI
make ui
# Or: ./scripts/dev.sh ui
# Opens http://localhost:8501
```

For solo guitar uploads, turn off **Separate guitar stem (Demucs)** in the UI for faster processing. For full songs, leave it on (default when Demucs is installed).

If you installed before Demucs was bundled, run `make install-demucs` / `.\scripts\dev.ps1 install-demucs` / `./scripts/dev.sh install-demucs` once to add it to an existing venv.

Demucs stem separation also requires **FFmpeg with shared libraries** (Homebrew/conda defaults work; on Windows use a "full/shared" build such as Gyan.FFmpeg, not essentials-only).

```bash
# Generate test fixtures
make fixtures

# Run unit tests
make test

# Transcribe a local file (skip Demucs for solo guitar)
pip install -e .
export PYTHONPATH=src
audio-pipeline --audio song.wav --output ./output --no-separate

# Or step-by-step
audio-transcribe song.wav song.mid
audio-mid2tab song.mid song.tab
audio-tab2pdf song.mid song.pdf
```

## Production website

```bash
cp .env.example .env   # set ATT_SECRET_KEY and admin password
docker compose up -d --build
# https://localhost  → SPA login, Tab PDF, Isolate
```

Details, RAM guidance, and backup notes: [`DEPLOY.md`](DEPLOY.md). Readiness status: [`WEB_READINESS.md`](WEB_READINESS.md).

SPA source: [`web/`](web/) (`npm install && npm run dev` proxies to `make backend`).

## Backend API

```bash
make backend
# Windows: .\scripts\dev.ps1 backend
# OpenAPI: http://localhost:8000/docs
```

In development, `ATT_REQUIRE_AUTH` defaults to `false` (bootstrap admin used). Production compose sets auth on.

| Endpoint | Description |
|----------|-------------|
| `POST /v1/auth/login` | JWT access + HTTP-only refresh cookie |
| `POST /v1/uploads/audio` | Upload audio (size/MIME limited; auth in prod) |
| `POST /v1/jobs` | Start tab pipeline job |
| `POST /v1/isolate/jobs` | Start isolation job (`quality` default `fast`) |
| `GET /v1/jobs/{id}` | Poll status (mobile fallback) |
| `POST /v1/jobs/{id}/cancel` | Request cancel |
| `WS /v1/jobs/{id}/ws` | Live progress (`?access_token=` when auth on) |
| `GET /v1/artifacts/{id}/{kind}/signed` | Short-lived signed download |

Jobs persist in Postgres (SQLite locally); workers process via Redis/arq when `ATT_USE_WORKER=true`.

## Demucs (full mixes)

Requires `torchcodec` (installed with `make install-demucs`) and FFmpeg shared libraries on your system.

```bash
make install-demucs
audio-pipeline --audio full_mix.mp3 --output ./output --quality fast
```

## YouTube

```bash
audio-pipeline --url "https://www.youtube.com/watch?v=..." --output ./output
```

**Disclaimer:** Downloading YouTube audio may violate YouTube Terms of Service. You are responsible for ensuring you have rights to transcribe the material.

## Evaluation

```bash
make eval
```

Scores transcription F1 against synthetic fixtures when fluidsynth WAVs are available.

## Known limitations

- Chord voicings and articulations (bends, slides, HOs) are not detected
- Standard tuning only in v1
- Full mixes need Demucs; processing is slow on CPU
- Ghost notes may appear in output

## License

MIT
