# AGENTS.md

Rules for agents in this repo. **This file is only what you would get wrong by guessing.**
Elsewhere: `PROJECT_TREE.md` = "change X → start here" (read it first, before searching);
`PLANNING.md` = how to plan; `DESKTOP.md` = installer/tester runbook; `DEPLOY.md` = hosted ops.

## Two products, one shared engine

- **Desktop** (local): Streamlit `ui/` behind `packaging/launcher.py`. Audio Isolation
  (separate/mix), YouTube to MP3 (save file only), Tab PDF. No Docker. Isolate jobs are
  **serial** — one at a time, 8–16 GB RAM (`ui/isolate_jobs.py`).
- **Website** (hosted): FastAPI `backend/` + React `web/` + Caddy; jobs via
  Postgres/Redis/MinIO + arq worker (`docker-compose.yml`). **Streamlit is not in this
  stack** — `Dockerfile` copies only `src/`, `backend/`, `scripts/`.
- **Shared**: `src/audio_to_tab/` (import as `audio_to_tab`). Engine changes can break
  either product; test both affected surfaces.

### The two "Lites" are different products — never unify
- Desktop **Interface Lite** = Streamlit chrome (`ui_mode` sidebar) that auto-profiles
  speed/device (`audio_to_tab.hardware.lite_auto_choice`) and the guitar engine
  (`ui/isolate_state.py` `resolve_lite_guitar_engine`); Pro exposes every control.
- Hosted processing mode **`lite`** = "Lite / low RAM" in `backend/capabilities.py`,
  hard-capped by API quota (60 s). Not the same thing (`docs/ui-issues.md` I-609).
- Desktop Lite must **not** silently clamp audio length; hosted `lite` **does**
  (`docs/issues.md` I-500).
- YouTube to MP3 is download-only and never affects speed/device; Pro only widens the
  export-format list and help copy.

## Python

- **3.10–3.12 only** (Basic Pitch needs <3.13). `.python-version` = 3.11.
- Dev/test venv `.venv311`; desktop freeze uses a separate `.venv-desktop*`.
- `make install` → `pip install -e ".[dev,eval,demucs,roformer,separator]"` (+ CPU torch
  on Linux). The **desktop** freeze install is a different profile — `README.md`.
- `make` delegates to `scripts/dev.sh` / `scripts/dev.ps1`; edit those, not the Makefile,
  when adding a target.

## Commands

`make <target>` (POSIX) or `.\scripts\dev.ps1 <target>` (Windows). `make help` lists all.

| What | Command |
|---|---|
| test | `make test` → `pytest tests/ -q` (809 tests) |
| one test / file | `python -m pytest tests/test_metronome.py -q` · `::test_name` · `-k expr` |
| lint | `ruff check src/audio_to_tab` |
| backend | `make backend` (uvicorn `:8000`) |
| SPA dev | `make web` (Vite `:5173`, proxies `/v1` → `:8000`) |
| SPA test / build | `cd web && npm test` (vitest) · `make web-build` (build **+** vitest) |
| Streamlit | `make ui` (local demo only) |
| prewarm / fixtures | `make preflight` · `make tester` · `make fixtures` |

- `PYTHONPATH` is `src:.`, exported by the Makefile; `tests/conftest.py` also injects
  `src/` + repo root, so bare `pytest` works.
- **Lint covers `src/audio_to_tab` only** — not `ui/`, `backend/`, `web/`. ruff pinned
  `==0.16.5` (matches `.venv311`). `E501` ignored (100 cols advisory);
  `BLE001`/`S110`/`S112`/`RUF001-003` ignored project-wide.
- **No typecheck gate anywhere.** `web/tsconfig.json` is `strict` with
  `noUnusedLocals`/`noUnusedParameters`, but `vite build` never runs `tsc` and CI never
  does either. Run `cd web && npx tsc --noEmit` yourself before calling TS work done.
- **CI (`.github/workflows/ci.yml`, every push/PR) runs only pytest + ruff.** It does not
  run `npm test`, does not typecheck, does not build the desktop frontends.

## Committed frontend builds — edit source, rebuild, commit

Three Streamlit iframe components ship **hashed Vite output committed to git** so
installer testers need no Node. Never hand-edit `frontend/build/`.

| Component | Source | Rebuild |
|---|---|---|
| `ui/stem_mixer_component/frontend/` — live mixer (`main.ts`, `metronomeClicks.ts`) | `frontend/src/` | `make mixer-build` |
| `ui/region_picker_component/frontend/` — wavesurfer region picker | `frontend/src/` | `make region-picker-build` |
| `ui/mix_tabs_component/frontend/` — Moises-style Home\|mix\|+ strip | `frontend/src/` | `make mix-tabs-build` |

- **pytest enforces this.** `tests/test_stem_mixer_component.py`,
  `test_region_picker_component.py`, `test_mix_tabs_component.py` each assert the
  committed build is complete. Edit `src/` and forget the rebuild → red tests.
  `desktop-release.yml` also fails the release if the mixer build is missing.
- These three have **no test script** (no vitest). Only `web/` does.

## Invariants — do not "fix" these

- **MPS only at ≥12 GB RAM** (`MPS_MIN_RAM_GB`, `src/audio_to_tab/hardware.py`; pinned by
  `tests/test_hardware.py::test_mac_mps_gated_behind_12gb_ram`). Below that,
  unified-memory OOM/swap is worse than CPU. Do not raise
  `PYTORCH_MPS_HIGH_WATERMARK_RATIO` to "fix" an 8 GB Mac.
- **Desktop isolation is GPU-first** when CUDA or eligible MPS exists; memory pressure
  picks speed/quality, it no longer downgrades device to CPU. The 8 GB Mac CPU floor stays.
- **Metronome contract:** `MetronomeResult.click_times_1x` — defined in
  `audio_to_tab/metronome.py`, consumed by the desktop mixer. `rebake_metronome_artifact`
  reloads the stored grid and re-renders; it must **not** re-track. Tracking is a
  `librosa.feature.rhythm.tempo(aggregate=None)` curve → a second
  `librosa.beat.beat_track(bpm=curve)`.
- **Mixer background play:** `installWakeHooks` acts only on `visible`/`pageshow`/`focus`
  and never soft-pauses on document hide. Kept in sync between
  `ui/stem_mixer_component/frontend/src/main.ts` and `web/src/mixer/engine.ts` — change
  one, change the other. Browsers suspending Web Audio on a fully backgrounded tab is
  accepted, not a bug.
- **Mixer export is built on "Save current mix"**, not on every mute/solo/volume change
  (`docs/ui-issues.md` I-607).
- **Model weights download via SHA256-pinned `urllib`**, never `huggingface_hub`
  (`tests/test_guitar_ft_weights.py`).
- **Never reuse or renumber issue IDs.** `docs/issues.md` and `docs/ui-issues.md` reserve
  `I-072`, `I-098`, `I-104`, `I-200`–`I-252`, `I-500`–`I-510`, `I-618`, `I-600`–`I-623`
  (CI and eval scripts cite them). Append new sections; next UI ID is `I-624`.
  Many rows are `implemented-in-code` history — **read the code before treating a row as
  an open gap.**

## Desktop / packaging

- `AUDIO_TOOLS_EDITION` = `cpu` | `cuda` | `both` (aliases `nvidia`/`gpu`,
  `combined`/`cpu+cuda`/`all`); resolved by `src/audio_to_tab/edition.py` plus
  `packaging/edition.txt` inside the freeze. `desktop-release.yml` asserts `edition.txt`
  matches the env var.
- `make desktop-bundle-ffmpeg` (writes gitignored `packaging/ffmpeg/current`) is
  **required** before `make desktop-build`.
- Desktop onedir **must not** contain `backend/`, `web/`, or any `.env*` — asserted by
  `desktop-release.yml` and excluded in `packaging/audio_tools.spec`. Don't add hosted
  code to the spec.
- Releases are tag-triggered (`desktop-v*`) or `workflow_dispatch`, producing 4 **unsigned**
  artifacts (win cpu / win cuda / mac arm64 / mac x64). Version lives in
  `src/audio_to_tab/__init__.py` `__version__` — bump it there, not in the spec.

## Testing quirks

- Most tests mock torch/demucs, but `tests/test_tab.py::test_is_demucs_available` asserts a
  **real** Demucs import. A `[dev]`-only install fails — use the `make install` profile.
- YouTube integration tests skip unless `RUN_YOUTUBE_INTEGRATION=1` (public internet).
- Tests needing `eval/fixtures/*.mid` **skip** when missing — run `make fixtures` if you
  see unexpected skips rather than assuming they passed.
- macOS CI deselects `tests/test_api.py::test_upload_and_job` (basic-pitch has no
  TensorFlow wheel on Darwin). Not a bug to fix; Windows/Linux run it.
- Backend work: set `ATT_REQUIRE_AUTH=false` locally. The `starlette.testclient` →
  `httpx2` deprecation warning is pre-existing noise.

## Env / config

- All settings are `ATT_*` in `backend/config.py`. Copy `.env.example` (hosted),
  `.env.lite.example` (lite compose), or `web/.env.example` (SPA) → `.env`.
  **Never commit `.env`.**
- Demo mode: `ATT_DEMO_MODE=true` + `ATT_REQUIRE_AUTH=false` → per-tab anonymous JWT.
- CORS: exact origins in `ATT_CORS_ORIGINS`, **never `*`**. Production refuses placeholder
  `ATT_BOOTSTRAP_ADMIN_PASSWORD` and needs a strong `ATT_SECRET_KEY`.
  `ATT_ALLOW_YOUTUBE` defaults **off** (keep off on public hosts).
- `.streamlit/config.toml` sets `fileWatcherType = "none"` and `headless = true` — after
  editing `ui/`, **restart Streamlit**. That is expected, not a bug.

## Never commit / never hand-edit

- `.env`, `data/`, `output/`, wavs (except `eval/fixtures/*.wav`), model weights,
  `packaging/ffmpeg/`, `dist/`, `build/`.
- `web/dist/`, every `node_modules/`, every `*/frontend/build/assets/*` (hashed output).
- `.cursor/`, `CONTEXT_TREE.md`, `docs/oracle-free-memory-spike.md` — gitignored internal
  docs. `PROJECT_TREE.md` is the tracked canonical tree; update it when adding files.
- Streamlit gotchas: `st.expander()` takes no `help=` kwarg (use `st.caption()` inside);
  every interaction re-runs the whole script, so state handling is the app's real problem.

## Git

Do not commit, push, tag, or open a PR unless the user explicitly approves it in that
conversation.
