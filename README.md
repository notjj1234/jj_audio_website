# Audio to Tab PDF

Convert MP3/WAV files or YouTube links into **draft** guitar tablature PDFs using free/open-source tools.

> **Quality expectation:** Best on solo acoustic guitar. Output is a starting sketch, not a finished transcription.

## Pipeline

```
Audio / YouTube → [Demucs guitar stem] → Basic Pitch → MIDI cleanup → Fret assignment → PDF
```

## Requirements

- Python 3.10–3.12 (3.11 recommended; Basic Pitch does not support 3.13)
- ffmpeg (`brew install ffmpeg` / `apt install ffmpeg`)
- Optional: fluidsynth (for eval fixture WAV synthesis)

## Quick start

```bash
# Install (includes Demucs + PyTorch for stem separation; first run ~2GB download)
make install

# Launch web UI
make ui
# Opens http://localhost:8501
```

For solo guitar uploads, turn off **Separate guitar stem (Demucs)** in the UI for faster processing. For full songs, leave it on (default when Demucs is installed).

If you installed before Demucs was bundled, run `make install-demucs` once to add it to an existing venv.

Demucs stem separation also requires **FFmpeg with shared libraries** (the default Homebrew/conda builds work; Windows users need a "shared" FFmpeg build, not essentials-only).

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
# OpenAPI: http://localhost:8000/docs
```

| Endpoint | Description |
|----------|-------------|
| `POST /v1/uploads/audio` | Upload MP3/WAV |
| `POST /v1/jobs` | Start pipeline job |
| `GET /v1/jobs/{id}` | Poll status |
| `WS /v1/jobs/{id}/ws` | Live progress |
| `GET /v1/artifacts/{id}/pdf` | Download PDF |

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
