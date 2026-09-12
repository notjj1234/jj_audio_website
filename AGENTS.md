# AGENTS.md

## Two products, one shared engine

- **Desktop** (local): Streamlit `ui/`, frozen by `packaging/` (`launcher.py`, `audio_tools.spec`). Serial in-process isolate jobs. **Lite** auto-profiles speed/device/guitar from RAM/GPU (`audio_to_tab.hardware`); **Pro** exposes every control.
- **Website** (hosted): FastAPI `backend/` + React SPA `web/` + Caddy; jobs via Postgres/Redis/MinIO + arq worker (`docker-compose.yml`). **Streamlit is NOT in the hosted stack.** Hosted Auto/`lite` processing modes live in `backend/capabilities.py`.
- **Shared** engine: `src/audio_to_tab/` (isolate, mixer, ingest, tab-PDF pipeline). Import as `audio_to_tab`.

Read `PROJECT_TREE.md` first — it is the canonical "change X → start here" map. `docs/issues.md` has the project's design-decision history (CI references it by issue id).

## Python

- Requires **Python 3.10–3.12** (Basic Pitch needs <3.13); `.python-version` is 3.11.
- Dev/test venv is `.venv311`. Desktop freeze uses separate `.venv-desktop*` (see `DESKTOP.md`).
- `pip install -e ".[dev,eval,demucs,roformer,separator]"` is the dev install profile (note CPU torch comes separately — see Makefile / `scripts/dev.ps1`).

## Commands (Windows: `.\scripts\dev.ps1 <target>`; POSIX: `make <target>`)

- **test**: `.venv311\Scripts\python.exe -m pytest tests/ -q` (`dev.ps1 test` sets `PYTHONPATH=src;.`; conftest also injects `src/` + repo root).
- **lint** (ruff, pinned `==0.16.5` in CI): `ruff check src/audio_to_tab` — CI lints **only `src/`**, not `ui/`, `backend/`, or `web/`. Config in `pyproject.toml`: `E501` ignored (100 cols is advisory), `BLE001`/`S110`/`S112`/`RUF001-003` ignored project-wide.
- **backend**: `python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload`. Run tests against API with `ATT_REQUIRE_AUTH=false` for dev.
- **web**: `cd web && npm install && npm run dev` (Vite dev proxies `/v1` to the API). Tests: `npm test` (`vitest run`, e.g. `web/src/mixer/engine.test.ts`). Build: `make web-build` (also runs vitest).
- **ui**: `python -m streamlit run ui/app.py` (local demo only).
- **mixer-build**: `make mixer-build` — rebuilds the desktop iframe mixer from `ui/stem_mixer_component/frontend/src/`. The hashed output in `frontend/build/` is **committed** (so testers need no Node); never hand-edit it — change source, run this, commit.
- **region-picker-build**: `make region-picker-build` — rebuilds the desktop waveform region picker from `ui/region_picker_component/frontend/src/` (wavesurfer.js). Same commit rule as the mixer.
- **mix-tabs-build**: `make mix-tabs-build` — rebuilds the Moises-style Home|mix|+ tab strip from `ui/mix_tabs_component/frontend/src/`. Same commit rule as the mixer.

## Testing quirks

- Tests mock torch/demucs, **but a few assert a real Demucs is importable** (`test_tab.py::test_is_demucs_available`). Install with the `[dev,demucs]` + CPU-torch profile or those fail.
- YouTube integration tests skip unless `RUN_YOUTUBE_INTEGRATION=1` (they hit the public internet).
- macOS CI deselects `tests/test_api.py::test_upload_and_job` (basic-pitch/tensorflow issue); irrelevant to Windows.

## Desktop / packaging gotchas

- `$env:AUDIO_TOOLS_EDITION = "cpu" | "cuda"` selects the freeze flavor (`src/audio_to_tab/edition.py`); CI verifies `packaging/edition.txt` matches.
- `packaging/bundle_ffmpeg.py` downloads ffmpeg into `packaging/ffmpeg/` (gitignored) — required before `make desktop-build`.
- Desktop onedir **must not ship** `backend/`, `web/`, or any `.env*` — CI asserts this. Don't add hosted code to the spec.

## Env / config

- Copy `.env.example` (hosted) or `.env.lite.example` (lite docker compose) → `.env`. **Never commit `.env`.** All settings are `ATT_*` in `backend/config.py`.
- Demo mode: `ATT_DEMO_MODE=true` + `ATT_REQUIRE_AUTH=false` (anonymous per-tab JWT). CORS must be exact origins, never `*`.

## Do not commit / hand-edit

- `.env`, wavs (except `eval/fixtures/*.wav`), Demucs/torch weights, `packaging/ffmpeg/` binaries.
- `.cursor/`, `CONTEXT_TREE.md`, `docs/oracle-free-memory-spike.md` are gitignored internal docs.
- Node artifacts: `web/dist/`, all `node_modules/`, `ui/stem_mixer_component/frontend/build/assets/*` (hashed).
- Model weights (guitar-ft, RoFormer) download at runtime via **SHA256-pinned urllib** (no `huggingface_hub`); tests in `tests/test_guitar_ft_weights.py`.

Under any circumstances should you commit files to github for me. Only if i actually approve then u should.