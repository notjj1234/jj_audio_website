# Audio Tools (Tab PDF + Isolation)

Two Streamlit features (sidebar navigation):

1. **Audio → Guitar Tab PDF** — convert MP3/WAV or YouTube links into **draft** guitar tablature PDFs using free/open-source tools.
2. **Audio Isolation** — Moises-style multi-stem split (Demucs): download vocals, drums, bass, guitar, piano, other as WAVs.

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
audio-isolate --audio song.wav --output ./output/stems --model htdemucs_6s --quality fast --dual-guitar

# Or via module if console script not installed
python -m audio_to_tab.cli.isolate --audio song.wav --output ./output/stems
```

In the web UI (`make ui`), open **Audio Isolation** from the sidebar. After separation, use the **stem board** to preview waveforms, mute/solo stems, and play a heard mix. Optional **dual-guitar split** (experimental, `htdemucs_6s` only) attempts Guitar 1 / Guitar 2 when the guitar stem has distinct stereo content.

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

# Launch web UI
.\scripts\dev.ps1 ui
# Opens http://localhost:8501
```

In **Cursor**: `Ctrl+Shift+P` → **Tasks: Run Task** → **ui**.

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

## Backend API (optional)

For programmatic access or CI, start the FastAPI server separately:

```bash
make backend
# Windows: .\scripts\dev.ps1 backend
# OpenAPI: http://localhost:8000/docs
```

| Endpoint | Description |
|----------|-------------|
| `POST /v1/uploads/audio` | Upload MP3/WAV |
| `POST /v1/jobs` | Start tab pipeline job |
| `POST /v1/isolate/jobs` | Start multi-stem isolation job |
| `GET /v1/jobs/{id}` | Poll status (tab or isolate) |
| `WS /v1/jobs/{id}/ws` | Live progress |
| `GET /v1/artifacts/{id}/pdf` | Download tab PDF |
| `GET /v1/artifacts/{id}/{stem}` | Download isolate stem (e.g. `vocals`) or `zip` |

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
