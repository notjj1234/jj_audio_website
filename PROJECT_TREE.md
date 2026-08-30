# CONTEXT_TREE

## How to use this file

Agents: read this before searching the repo. Pick a path from the table, then open that file.
Humans: map of where desktop vs website vs shared engine live.
How to run: `DESKTOP.md` (local Streamlit / installer) or `DEPLOY.md` (hosted compose). Not this file.
If a path is not listed, it was not on disk when this was written.

## Two products

Both products import `src/audio_to_tab/` (isolate, YouTube ingest, tab PDF pipeline). They do **not** share UI or job runners.

1. **Desktop (local only)** — Streamlit `ui/app.py` behind `packaging/launcher.py`. Serial isolate jobs in-process (`ui/isolate_jobs.py`). No Docker. Testers: `DESKTOP.md`.
2. **Website (hosted)** — FastAPI `backend/` + React `web/` + Caddy. Jobs via Postgres/Redis/MinIO + arq worker (`docker-compose.yml`). Streamlit is **not** in that stack. Operators: `DEPLOY.md`.

Shared: isolate engine, mixer math (`src/audio_to_tab/mixer.py`), ingest, tab pipeline.
Not shared: Streamlit pages vs React pages; desktop disk queue vs API `JobManager`; desktop iframe mixer vs website Web Audio mixer.

## Guitar isolation status (important context)

The engine now supports several guitar isolation backends, all opt-in behind optional extras
(`[demucs]`, `[roformer]`, `[separator]`) and SHA256-pinned urllib downloads (no `huggingface_hub`):

- **HTDemucs-6s** (stock) and **htdemucs-6s-guitar-ft** in-process (`separate.py`).
- **BS-RoFormer-SW** (6-stem) and **MelBand-RoFormer Guitar** specialist (`roformer.py`).
- Post-processing: **fold-other**, **bass-bleed diagnostics + opt-in HPF mitigation**,
  **low-end recovery** (subtractive sub-bass de-bleed + harmonic low-end restore),
  **guitar pre-refine vs refined variants**, **lead/rhythm split** (not default).

The **Tab PDF path (`pipeline.py`) and the Isolate path (`isolate.py`)** are both wired for these;
the desktop UI (`tab_pdf.py`, `isolate.py`) and the website/API (`backend/contracts.py`,
`main.py`, `jobs/runner.py`) expose them. See `docs/guitar_improvement_prompt.md` for the
background on the low-E / masking problem this addresses.

## If you need to change X, start here

| Job | Start here |
|-----|------------|
| Isolation UI (desktop) | `ui/pages/isolate.py` (page), `ui/isolate_state.py` (presets/progress), `ui/app.py` (router) |
| Guitar fix-up post-separation (desktop Mixer tab) | `ui/guitar_fixup.py` (low-end recovery, pre/refined switch), `ui/pages/isolate.py` |
| Isolation UI (website) | `web/src/pages/IsolatePage.tsx`, `web/src/api.ts`, isolate routes in `backend/main.py` |
| Guitar stem engine | `src/audio_to_tab/isolate.py` (`IsolateConfig`, `separate_stems`, fold, bass-bleed, low-end recovery, pre/refined), `src/audio_to_tab/separate.py` (Demucs CLI / guitar-ft), `src/audio_to_tab/roformer.py` (BS-RoFormer-SW / MelBand guitar) |
| Live mixer (desktop iframe) | Edit `ui/stem_mixer_component/frontend/src/main.ts` + `style.css`, then `make mixer-build`. Loader: `ui/stem_mixer_component/__init__.py`. Preview encode: `ui/media.py` |
| Live mixer (website) | `web/src/mixer/engine.ts`, `web/src/components/StemMixer.tsx` |
| YouTube ingest | `src/audio_to_tab/ingest.py` (shared). Surfaces: `ui/pages/isolate.py`, `ui/pages/tab_pdf.py`. Tests: `tests/test_ingest.py` |
| Isolate job queue (desktop) | `ui/isolate_jobs.py` (serial worker, status on disk), queue UI in `ui/pages/isolate.py`. Notifications: `ui/desktop_notify.py`. Export/download: `ui/desktop_export.py` |
| Isolate jobs (API/worker) | `backend/jobs/manager.py`, `backend/jobs/runner.py` (`separate_stems`), `backend/worker.py`, `POST /v1/isolate/jobs` in `backend/main.py`. Single-flight: `backend/jobs/single_flight.py` |
| Tab PDF | Engine: `src/audio_to_tab/pipeline.py` (includes model/refine/debleed/restore options), `transcribe.py`, `tab_generate.py`, `pdf_render.py`. Desktop: `ui/pages/tab_pdf.py`. Website: `web/src/pages/TabPage.tsx` + tab job in `backend/jobs/runner.py` |
| Desktop packaging / launcher | `packaging/launcher.py`, `packaging/audio_tools.spec`, freeze helpers in `src/audio_to_tab/edition.py`. Runbook: `DESKTOP.md`. CI: `.github/workflows/desktop-release.yml` |
| Tests for isolation / guitar | `tests/test_isolate.py`, `tests/test_isolate_jobs.py`, `tests/test_isolate_state.py`, `tests/test_guitar_ft_weights.py`, `tests/test_guitar_backups.py`, `tests/test_guitar_fixup.py`, `tests/test_pipeline_guitar.py`, `tests/test_ingest.py`, `tests/test_mixer.py`, `tests/test_stem_mixer_component.py` |

Lead/rhythm split (`src/audio_to_tab/lead_rhythm.py`) exists; it is **not** the default isolate path.

## Tree

### Root files

- `Makefile` — install, tester, pytest, Streamlit UI, compose-adjacent web/backend targets, mixer-build, desktop pkg.
- `pyproject.toml` — package `audio-to-tab-pdf`, Python `>=3.10,<3.13` (3.10–3.12), extras `dev` / `eval` / `demucs` / `roformer` / `separator` / `desktop`.
- `requirements.txt` — desktop-only dev pins (Streamlit, yt-dlp, onnxruntime, eval/dev extras; hosted backend deps live in `pyproject.toml` `[project.dependencies]`).
- `requirements-demucs.txt` — Demucs + torch on top of `requirements.txt`.
- `Dockerfile` — API/worker image (ffmpeg, `src/`, `backend/`, prewarm script).
- `Dockerfile.web` — SPA build + Caddy.
- `docker-compose.yml` — hosted stack: Caddy, API, worker, Postgres, Redis, MinIO.
- `docker-compose.lite.yml` — single API, sqlite, local disk (no worker/Postgres/Redis/MinIO).
- `Caddyfile` — TLS; `/v1/*` → api:8000; SPA from `/srv`.
- `README.md` — project overview.
- `DESKTOP.md` — local tester / installer runbook.
- `DEPLOY.md` — compose production runbook.
- `LICENSE` — MIT.
- `.env.example` — hosted env template (copy to `.env`; do not commit `.env`).
- `.env.lite.example` — lite compose env template.
- `.python-version` — `3.11`.
- `.gitattributes` — LF normalization.
- `.gitignore` — venvs, `.env`, wavs, internal docs (`CONTEXT_TREE.md`, `docs/oracle-free-memory-spike.md`).
- `PROJECT_TREE.md` — this file (tracked).
- `docs/` — `guitar_improvement_prompt.md` (low-end/masking fix background + Cursor prompt).

### `src/`

Shared engine. Import as `audio_to_tab`.

- `audio_to_tab/__init__.py` — package marker.
- `audio_to_tab/isolate.py` — Demucs/RoFormer multi-stem isolate, region trim, `--segment` clamp, fold-other, presence / bass-bleed / guitar-stem-quality diagnostics, opt-in bass-bleed HPF mitigation, low-end recovery (`apply_guitar_low_end_recovery`, `apply_low_end_restore`, `LowEndRecoveryDiagnostics`), guitar pre-refine vs refined variants (`GUITAR_PREREFINE_NAME` / `GUITAR_REFINED_NAME`, `switch_guitar_stem_variant`), melband refine, checkpoint/resume.
- `audio_to_tab/separate.py` — Demucs subprocess / frozen in-process; `separate_guitar_stem` (model/guitar-ft/roformer/refine/debleed/restore); guitar-ft weights download + SHA256 verify (`run_demucs_guitar_ft_inprocess`).
- `audio_to_tab/roformer.py` — BS-RoFormer-SW (6-stem) + MelBand-RoFormer Guitar specialist; urllib + SHA256 downloads; bs-roformer-infer / audio-separator backends; `run_guitar_refine` (residual-aware).
- `audio_to_tab/ingest.py` — file normalize + YouTube download (`yt-dlp`).
- `audio_to_tab/mixer.py` — stem mix / waveform helpers used by desktop downloads.
- `audio_to_tab/hardware.py` — RAM/GPU probe; desktop speed recommendations.
- `audio_to_tab/edition.py` — Windows CPU vs NVIDIA freeze flavor.
- `audio_to_tab/lead_rhythm.py` — opt-in lead/rhythm split on the guitar stem (not product default).
- `audio_to_tab/pipeline.py` — audio → tab PDF end-to-end (`PipelineConfig` incl. model, guitar_checkpoint, guitar_refine, demucs_segment/jobs, fold_other_mode, low_end_restore_db, sub_bass_debleed).
- `audio_to_tab/transcribe.py` — Basic Pitch audio → MIDI.
- `audio_to_tab/tab_generate.py` — MIDI → ASCII tab.
- `audio_to_tab/pdf_render.py` — ASCII/MIDI → PDF (ReportLab).
- `audio_to_tab/tempo.py` — tempo from audio/MIDI.
- `audio_to_tab/rhythm.py` — beat-grid quantize for tab events.
- `audio_to_tab/midi_cleanup.py` — post-pitch MIDI cleanup.
- `audio_to_tab/tuning.py` — fretboard / tuning helpers.
- `audio_to_tab/subprocess_util.py` — subprocess kwargs for desktop/CLI.
- `audio_to_tab/cli/isolate.py` — CLI isolate (Demucs/RoFormer, `--guitar-checkpoint`, `--guitar-refine`, `--fold-other-mode`, `--sub-bass-debleed`, `--low-end-restore-db`, `--low-end-recovery`, `--two-pass`, integrations with lead/rhythm thresholds).
- `audio_to_tab/cli/pipeline.py` — CLI full pipeline.
- `audio_to_tab/cli/transcribe.py` — CLI transcribe.
- `audio_to_tab/cli/tab2pdf.py` — CLI tab/MIDI → PDF.
- `audio_to_tab/cli/mid2tab.py` — CLI MIDI → ASCII tab.

### `ui/`

Desktop Streamlit only.

- `app.py` — multipage router (Isolate, Tab PDF); window title / Demo suffix.
- `pages/isolate.py` — Audio Isolation page (upload, YouTube, queue, mixer, downloads, fold/refine/low-end options, pre-refined vs refined toggle).
- `pages/tab_pdf.py` — Tab PDF page (model selector: htdemucs_6s / BS-RoFormer-SW, guitar refine, guitar-ft checkpoint, low-end restore, sub-bass de-bleed).
- `guitar_fixup.py` — post-separation guitar stem fix-up for the Mixer tab (low-end recovery, pre/refined switch, diagnostics).
- `isolate_jobs.py` — serial Demucs worker; job status JSON under app data dir.
- `isolate_state.py` — presets, custom stems, progress stages, guitar track selection / normalization (pure helpers).
- `desktop_export.py` — save isolate downloads to a chosen folder + reveal in OS file manager.
- `desktop_notify.py` — best-effort OS notifications for isolate job completion (no extra pip deps).
- `common.py` — run listing, uploads, data dir, edition labels.
- `media.py` — Streamlit media URLs, preview encode, mix cleanup.
- `icon.png` — window / tab icon.
- `stem_mixer_component/__init__.py` — iframe component; serves `frontend/build/`.
- `stem_mixer_component/frontend/src/main.ts` — live mixer (Web Audio) source.
- `stem_mixer_component/frontend/src/style.css` — mixer styles.
- `stem_mixer_component/frontend/package.json`, `vite.config.ts`, `tsconfig.json`, `index.html` — Vite build for the iframe.

### `web/`

Hosted SPA (Vite + React). Dev: `make web` (proxies API).

- `index.html` — SPA shell.
- `package.json` / `vite.config.ts` / `tsconfig.json` — build; Vitest for mixer engine.
- `netlify.toml`, `vercel.json` — SPA fallback hosting.
- `.env.example` — optional `VITE_API_BASE_URL` (same-origin Caddy leaves unset).
- `public/` — favicons / apple-touch / 512 icon.
- `src/main.tsx` — React mount.
- `src/App.tsx` — routes `/isolate`, `/tab`, login.
- `src/api.ts` — REST/WebSocket client for jobs, uploads, stems.
- `src/auth.tsx` — session / JWT.
- `src/styles.css` — global styles.
- `src/pages/IsolatePage.tsx` — website isolation UI.
- `src/pages/TabPage.tsx` — website tab PDF UI.
- `src/pages/LoginPage.tsx` — login.
- `src/components/StemMixer.tsx` — website mixer UI.
- `src/components/JobProgress.tsx` — job status display.
- `src/components/ProcessingModeSelect.tsx` — auto/fast/balanced from capabilities API.
- `src/mixer/engine.ts` — Web Audio mix engine.
- `src/mixer/engine.test.ts` — mixer unit tests.

### `backend/`

Hosted API.

- `main.py` — FastAPI routes: auth, upload, isolate/tab jobs (incl. guitar model/refine/debleed/restore fields), stem/mix download, WS events.
- `config.py` — `ATT_*` settings.
- `contracts.py` — Pydantic request/response models (incl. `low_end_restore_db`, `sub_bass_debleed`, guitar model/refine fields).
- `auth.py` — JWT, bootstrap admin, demo session.
- `models.py` — SQLAlchemy User / Job / Upload.
- `db.py` — engine + sessions.
- `storage.py` — local disk or S3/MinIO.
- `events.py` — in-process / Redis job progress.
- `capabilities.py` — host processing modes for the SPA.
- `limits.py` — upload size/type checks.
- `worker.py` — arq worker entry.
- `jobs/manager.py` — persist jobs, artifacts, cancel (incl. guitar option fields).
- `jobs/runner.py` — runs `separate_stems` / `run_pipeline` (passes guitar options).
- `jobs/single_flight.py` — one heavy job at a time on small hosts.

### `packaging/`

Desktop freeze + installers. How-to: `DESKTOP.md`.

- `launcher.py` — native window over local Streamlit (dev or frozen).
- `audio_tools.spec` — PyInstaller onedir.
- `bundle_ffmpeg.py` — download ffmpeg into `packaging/ffmpeg/` (gitignored binaries).
- `macos_signing.py` — Developer ID + notarization helpers.
- `make_app.sh` — wrap onedir → `AudioTools.app`.
- `make_pkg.sh` — macOS `.pkg` (preferred installer).
- `make_dmg.sh` — macOS `.dmg` (fallback).
- `make_windows_installer.ps1` — Inno Setup CPU/CUDA Setup.exe.
- `AudioTools.iss` — Inno script.
- `Install AudioTools.command` — DMG double-click copy to `/Applications`.
- `entitlements.plist`, `pkg_component.plist` — macOS signing / pkg metadata.
- `pkg_scripts/postinstall` — launch app after `.pkg` install.
- `generate_icons.sh`, `icon.png` / `icon.icns` / `icon.ico` — app icons.

### `tests/`

- `conftest.py` — puts `src/` and repo root on `sys.path`.
- `backend_test_utils.py` — rebind backend settings without reloading ORM.
- `test_isolate.py` — isolate engine (Demucs mocked), including `--segment` clamp, fold, bass-bleed.
- `test_isolate_jobs.py` — desktop serial queue / remove / error formatting.
- `test_isolate_state.py` — presets and progress helpers; guitar track selection/normalization.
- `test_guitar_ft_weights.py` — guitar-ft weights SHA256 / download helpers.
- `test_guitar_backups.py` — guitar pre-refine vs refined variants.
- `test_guitar_fixup.py` — `ui/guitar_fixup.py` low-end recovery + variant switch.
- `test_pipeline_guitar.py` — tab pipeline guitar options (model/refine/debleed/restore).
- `test_ingest.py` — YouTube ingest (network opt-in).
- `test_mixer.py` — mix helpers.
- `test_stem_mixer_component.py` — desktop mixer build packaging.
- `test_media.py` — preview / cleanup.
- `test_ui_common.py` — run list / delete.
- `test_desktop_paths.py` — launcher paths, freeze helpers.
- `test_desktop_export.py` — `ui/desktop_export.py`.
- `test_desktop_notify.py` — `ui/desktop_notify.py`.
- `test_hardware.py` — RAM/GPU probe.
- `test_edition.py` — CPU vs CUDA edition.
- `test_macos_signing.py` — signing helpers (no codesign I/O).
- `test_api.py` — FastAPI smoke (incl. guitar option fields).
- `test_web_security.py` — auth, CORS, upload caps.
- `test_capabilities.py` — processing-mode API.
- `test_single_flight.py` — API job gate.
- `test_lead_rhythm.py` — lead/rhythm post-process.
- `test_tab.py` — tab / tempo / MIDI cleanup.
- `test_subprocess_util.py` — subprocess helpers.

### `scripts/`

- `dev.sh` — macOS/Linux: `tester`, `install`, `ui`, `backend`, `test`, … (no make required).
- `dev.ps1` — Windows equivalent.
- `prewarm.py` — pull Demucs / Basic Pitch weights (API first-request); integrates `is_roformer_backend_available`.

### `eval/`

Offline scoring. Clips/results under `eval/lead_rhythm/` are mostly gitignored.

- `generate_fixtures.py` — synthetic MIDI/WAV fixtures.
- `score_transcription.py` — mir_eval vs ground-truth MIDI.
- `fixtures/manifest.json` — fixture list; `*.mid` + allowed `*.wav` here.
- `lead_rhythm/README.md` — how to score lead/rhythm locally.
- `lead_rhythm/score_lead_rhythm.py` — scorer.
- `lead_rhythm/score_guitar_stage1.py` — scores stage-1 guitar stems across output dirs via `analyze_guitar_stem_quality` (low/mid/high share, competitor overlap, optional SI-SDR + high-end preservation).
- `lead_rhythm/make_synthetic_clips.py` — synthetic clips (output gitignored).
- `lead_rhythm/manifest.example.json` — example manifest.

### `.github/`

- `dependabot.yml` — weekly pip updates.
- `workflows/desktop-release.yml` — Windows CPU/CUDA Setup + macOS arm64/x64 `.pkg`.

### `.streamlit/`

- `config.toml` — local Streamlit (no usage stats, viewer toolbar). `credentials.toml` is gitignored.

### `docs/`

- `guitar_improvement_prompt.md` — explains the low-E / low-end masking problem and contains a Cursor Agent prompt for further guitar-isolation work. (Tracked.)
- `oracle-free-memory-spike.md` — gitignored (not in public git).

### Do not edit (generated / vendor)

One line each; do not hand-edit:

- `node_modules/`, `ui/stem_mixer_component/frontend/node_modules/`
- `.venv/`, `.venv311/`, `.venv312/`, `.venv-desktop/`, `.venv-desktop-x64/`, `.venv-*/`
- `web/dist/`
- `ui/stem_mixer_component/frontend/build/assets/*` (hashed Vite output)
- `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `audio_to_tab_pdf.egg-info/`
- `dist/`, `build/`, `.build/`, `packaging/ffmpeg/`
- `data/`, `output/` (local runs)

## Do not edit unless

- Mixer iframe **build**: `ui/stem_mixer_component/frontend/build/` is committed so testers need no Node. Change `frontend/src/` then `make mixer-build`. Do not rewrite hashed `assets/*` by hand.
- Env: copy `.env.example` / `.env.lite.example` / `web/.env.example` → `.env`. Never commit `.env`.
- Do not commit wavs (except `eval/fixtures/*.wav`), Demucs/torch weights, or `packaging/ffmpeg/` binaries.
- `CONTEXT_TREE.md` (and `docs/oracle-free-memory-spike.md`) are gitignored; `PROJECT_TREE.md` is tracked and is the canonical in-repo tree.
