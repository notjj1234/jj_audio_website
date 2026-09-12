# PROJECT_TREE

## How to use this file

Agents (including Continue / local LLMs): read this before searching the repo. Pick a path from the table, then open that file.
Humans: map of where desktop vs website vs shared engine live.
How to run: `DESKTOP.md` (local Streamlit / installer) or `DEPLOY.md` (hosted compose). Not this file.
If a path is not listed, it was not on disk when this was written (see **Last verified**).

## Two products

Both products import `src/audio_to_tab/` (isolate, YouTube ingest, tab PDF pipeline). They do **not** share UI or job runners.

1. **Desktop (local only)** — Streamlit `ui/app.py` behind `packaging/launcher.py`. Serial isolate jobs in-process (`ui/isolate_jobs.py`). No Docker.
   - **Lite / Pro** here means Streamlit **interface mode** (`ui_mode` in sidebar): Lite shows goal outcome cards and auto-profiles speed/device/guitar from RAM/GPU (`audio_to_tab/hardware.py`, `prefer_roformer` gated on accelerator); Pro exposes every stem/engine/diagnostic control. Wiring: `ui/app.py`, `ui/isolate_state.py`, `ui/pages/isolate.py`. Testers: `DESKTOP.md`.
2. **Website (hosted)** — FastAPI `backend/` + React `web/` + Caddy. Jobs via Postgres/Redis/MinIO + arq worker (`docker-compose.yml`). Streamlit is **not** in that stack.
   - Hosted processing modes Auto / `lite` / fast_cpu / etc. live in `backend/capabilities.py`. **That “lite” is not desktop Interface Lite.** Operators: `DEPLOY.md`.

Shared: isolate engine, mixer math (`src/audio_to_tab/mixer.py`), ingest, tab pipeline.
Not shared: Streamlit pages vs React pages; desktop disk queue vs API `JobManager`; desktop iframe mixer vs website Web Audio mixer.

## Guitar isolation status (important context)

The engine supports several guitar isolation backends, behind optional extras
(`[demucs]`, `[roformer]`, `[separator]`, `[scnet]`) and SHA256-pinned urllib downloads (no `huggingface_hub`):

- **HTDemucs-6s** (stock) and **htdemucs-6s-guitar-ft** in-process (`separate.py`).
- **BS-RoFormer-SW** (6-stem) and **MelBand-RoFormer Guitar** specialist (`roformer.py`).
- **SCNet** (`guitar_scnet`) — optional 4-stem MUSDB18 model; guitar content is in `other` (`scnet.py`). Opt-in, not the default first-stage separator.
- Post-processing: **fold-other** (incl. adaptive fold / bleed gate / ensemble paths — see `tests/test_guitar_improvements.py`), **bass-bleed diagnostics + opt-in HPF mitigation**, **low-end recovery**, **guitar pre-refine vs refined variants**, **lead/rhythm split** (not default).

The **Tab PDF path (`pipeline.py`) and the Isolate path (`isolate.py`)** are both wired for Demucs/RoFormer/refine/debleed/restore; SCNet is isolate/CLI-facing. Desktop UI (`tab_pdf.py`, `isolate.py`) and website/API (`backend/contracts.py`, `main.py`, `jobs/runner.py`) expose the guitar option fields they support.

## If you need to change X, start here

| Job | Start here |
|-----|------------|
| Isolation UI (desktop) | `ui/pages/isolate.py` (page), `ui/isolate_state.py` (Lite outcomes / Pro stems / progress / mode helpers), `ui/app.py` (Lite↔Pro sidebar + overlay), `ui/stem_icons.py` (outcome/stem icons) |
| Desktop Lite↔Pro mode | `ui/app.py` (sidebar `UI_MODE_*`, `load_ui_mode` / `write_ui_mode`), `ui/isolate_state.py` (`is_pro_mode`, `DEFAULT_UI_MODE`), branching in `ui/pages/isolate.py` |
| Lite outcome cards | `ui/isolate_state.py` (`OUTCOME_CARDS`, `resolve_outcome_card`, `outcome_card_for_options`), icons `ui/stem_icons.py`, render in `ui/pages/isolate.py` |
| Desktop Lite hardware auto | `src/audio_to_tab/hardware.py` (`lite_auto_speed_id`, `lite_accelerator_available`, `lite_detected_caption` / `lite_using_caption`, MPS ≥12 GB). Wired in `ui/pages/isolate.py`; guitar preference via `prefer_roformer` in `ui/isolate_state.py`. Hosted Auto is separate: `backend/capabilities.py` |
| Global loading overlay | `ui/common.py` (`should_show_global_loading` — **nav-only**, not jobs), inject/clear in `ui/app.py`. Job progress stays on isolate status strip. Tests: `tests/test_global_loading.py` |
| Job retry / failed strip | `ui/isolate_jobs.py` (`requeue_job`, status JSON on disk), `ui/isolate_state.py` (`should_show_failed_job`, dismiss TTL), strip UI in `ui/pages/isolate.py` |
| Bundled Satoshi font | `ui/satoshi_font.py` + `ui/fonts/` (woff2); injected from `ui/app.py` (no CDN). Website copy: `web/public/fonts/` |
| Guitar fix-up post-separation (desktop Mixer) | `ui/guitar_fixup.py` (low-end recovery, pre/refined switch), `ui/pages/isolate.py` |
| Isolation UI (website) | `web/src/pages/IsolatePage.tsx`, `web/src/api.ts`, `web/src/trackOptions.ts`, isolate routes in `backend/main.py` |
| Guitar stem engine | `src/audio_to_tab/isolate.py` (`IsolateConfig`, `separate_stems`, fold, bass-bleed, low-end recovery, pre/refined), `src/audio_to_tab/separate.py` (Demucs / guitar-ft), `src/audio_to_tab/roformer.py`, `src/audio_to_tab/scnet.py` |
| SCNet backend | `src/audio_to_tab/scnet.py`; dispatch in `isolate.py` / CLI `cli/isolate.py`; tests `tests/test_scnet.py` |
| Live mixer (desktop iframe) | Edit `ui/stem_mixer_component/frontend/src/main.ts` + `style.css`, then `make mixer-build`. Loader: `ui/stem_mixer_component/__init__.py`. Preview encode: `ui/media.py` |
| Region picker (desktop iframe) | Edit `ui/region_picker_component/frontend/src/main.ts` + `style.css`, then `make region-picker-build`. Loader: `ui/region_picker_component/__init__.py`. Wired in `ui/pages/isolate.py` (`_render_region_controls`) |
| Mix tabs (desktop iframe) | Edit `ui/mix_tabs_component/frontend/src/main.ts` + `style.css`, then `make mix-tabs-build`. Loader: `ui/mix_tabs_component/__init__.py`. Moises-style Home\|mix\|+ strip on Isolate |
| Live mixer (website) | `web/src/mixer/engine.ts`, `web/src/components/StemMixer.tsx` |
| YouTube ingest | `src/audio_to_tab/ingest.py` (shared). Surfaces: `ui/pages/isolate.py`, `ui/pages/tab_pdf.py`. Tests: `tests/test_ingest.py` |
| Isolate job queue (desktop) | `ui/isolate_jobs.py` (serial worker, status on disk, `requeue_job`), queue UI in `ui/pages/isolate.py`. Notifications: `ui/desktop_notify.py`. Export/download: `ui/desktop_export.py` |
| Isolate jobs (API/worker) | `backend/jobs/manager.py`, `backend/jobs/runner.py` (`separate_stems`), `backend/worker.py`, `POST /v1/isolate/jobs` in `backend/main.py`. Single-flight: `backend/jobs/single_flight.py` |
| Tab PDF | Engine: `src/audio_to_tab/pipeline.py` (model/refine/debleed/restore), `transcribe.py`, `tab_generate.py`, `pdf_render.py`. Desktop: `ui/pages/tab_pdf.py`. Website: `web/src/pages/TabPage.tsx` + tab job in `backend/jobs/runner.py` |
| Desktop packaging / launcher | `packaging/launcher.py`, `packaging/audio_tools.spec`, freeze helpers in `src/audio_to_tab/edition.py`. Runbook: `DESKTOP.md`. CI: `.github/workflows/desktop-release.yml` |
| CI (pytest / ruff) | `.github/workflows/ci.yml` (push/PR). Distinct from desktop release packaging. |
| Agent / planning docs | `AGENTS.md` (agent rules), `PLANNING.md` (planning notes), `docs/issues.md` (I-xxx history), `docs/ui-issues.md` (I-600+ UI register) |
| Tests for isolation / guitar / desktop UX | `tests/test_isolate.py`, `test_isolate_jobs.py`, `test_isolate_state.py`, `test_global_loading.py`, `test_hardware.py`, `test_scnet.py`, `test_guitar_ft_weights.py`, `test_guitar_backups.py`, `test_guitar_fixup.py`, `test_guitar_improvements.py`, `test_pipeline_guitar.py`, `test_ingest.py`, `test_mixer.py`, `test_metronome.py`, `test_stem_mixer_component.py`, `test_region_picker_component.py`, `test_mix_tabs_component.py`, `test_ui_pages.py`, `test_cli_smoke.py` |

Lead/rhythm split (`src/audio_to_tab/lead_rhythm.py`) exists; it is **not** the default isolate path.

## Tree

### Root files

- `Makefile` — install, tester, pytest, Streamlit UI, compose-adjacent web/backend targets, mixer-build, region-picker-build, mix-tabs-build, desktop pkg.
- `pyproject.toml` — package `audio-to-tab-pdf`, Python `>=3.10,<3.13` (3.10–3.12), extras `dev` / `eval` / `demucs` / `roformer` / `separator` / `scnet` / `desktop`.
- `requirements.txt` — desktop-only dev pins (Streamlit, yt-dlp, onnxruntime, eval/dev extras; hosted backend deps live in `pyproject.toml` `[project.dependencies]`).
- `requirements-demucs.txt` — Demucs + torch on top of `requirements.txt`.
- `Dockerfile` — API/worker image (ffmpeg, `src/`, `backend/`, prewarm script).
- `Dockerfile.web` — SPA build + Caddy.
- `docker-compose.yml` — hosted stack: Caddy, API, worker, Postgres, Redis, MinIO.
- `docker-compose.lite.yml` — single API, sqlite, local disk (no worker/Postgres/Redis/MinIO).
- `Caddyfile` — TLS; `/v1/*` → api:8000; SPA from `/srv`.
- `README.md` — project overview.
- `AGENTS.md` — agent rules (venv, commands, what not to commit). Read with this file.
- `PLANNING.md` — planning notes; cited by `docs/issues.md`.
- `DESKTOP.md` — local tester / installer runbook.
- `DEPLOY.md` — compose production runbook.
- `LICENSE` — MIT.
- `.env.example` — hosted env template (copy to `.env`; do not commit `.env`).
- `.env.lite.example` — lite compose env template.
- `.python-version` — `3.11`.
- `.gitattributes` — LF normalization.
- `.gitignore` — venvs, `.env`, wavs, internal docs (`CONTEXT_TREE.md`, `docs/oracle-free-memory-spike.md`).
- `PROJECT_TREE.md` — this file (tracked). Canonical in-repo tree. (`CONTEXT_TREE.md` is a gitignored internal name, not present in a clean clone.)
- `docs/` — `issues.md` (I-xxx history; I-500 isolation audit); `ui-issues.md` (I-600+ UI/UX register; does not replace `issues.md`).

### `src/`

Shared engine. Import as `audio_to_tab`.

- `audio_to_tab/__init__.py` — package marker / version.
- `audio_to_tab/isolate.py` — Demucs/RoFormer/SCNet multi-stem isolate, region trim, `--segment` clamp, fold-other, presence / bass-bleed / guitar-stem-quality diagnostics, opt-in bass-bleed HPF mitigation, low-end recovery (`apply_guitar_low_end_recovery`, `apply_low_end_restore`, `LowEndRecoveryDiagnostics`), guitar pre-refine vs refined variants (`GUITAR_PREREFINE_NAME` / `GUITAR_REFINED_NAME`, `switch_guitar_stem_variant`), melband refine, checkpoint/resume. Bleed-gate / adaptive fold / ensemble covered in tests `test_guitar_improvements.py`.
- `audio_to_tab/separate.py` — Demucs subprocess / frozen in-process; `separate_guitar_stem` (model/guitar-ft/roformer/refine/debleed/restore); guitar-ft weights download + SHA256 verify (`run_demucs_guitar_ft_inprocess`).
- `audio_to_tab/roformer.py` — BS-RoFormer-SW (6-stem) + MelBand-RoFormer Guitar specialist; urllib + SHA256 downloads; bs-roformer-infer / audio-separator backends; `run_guitar_refine` (residual-aware).
- `audio_to_tab/scnet.py` — optional SCNet (`guitar_scnet`) 4-stem MUSDB18 backend; urllib + SHA256 checkpoint; `.[scnet]` extra. Not the default first-stage separator.
- `audio_to_tab/ingest.py` — file normalize + YouTube download (`yt-dlp`).
- `audio_to_tab/mixer.py` — stem mix / waveform helpers used by desktop downloads; metronome sorts last and starts muted.
- `audio_to_tab/hardware.py` — RAM/GPU/chip probe (`HostProbe.cpu_brand`, Apple Silicon label e.g. `Apple M2 Pro`); desktop speed recommendations; MPS gated at ≥12 GB; Lite helpers (`lite_accelerator_available`, `lite_auto_speed_id`, Detected/Using captions).
- `audio_to_tab/edition.py` — Windows CPU vs NVIDIA freeze flavor.
- `audio_to_tab/lead_rhythm.py` — opt-in lead/rhythm split on the guitar stem (not product default).
- `audio_to_tab/pipeline.py` — audio → tab PDF end-to-end (`PipelineConfig` incl. model, guitar_checkpoint, guitar_refine, demucs_segment/jobs, fold_other_mode, low_end_restore_db, sub_bass_debleed).
- `audio_to_tab/transcribe.py` — Basic Pitch audio → MIDI.
- `audio_to_tab/tab_generate.py` — MIDI → ASCII tab.
- `audio_to_tab/pdf_render.py` — ASCII/MIDI → PDF (ReportLab).
- `audio_to_tab/tempo.py` — tempo from audio/MIDI.
- `audio_to_tab/metronome.py` — beat-track drums/source and write a muted-by-default metronome click stem after isolate.
- `audio_to_tab/rhythm.py` — beat-grid quantize for tab events.
- `audio_to_tab/midi_cleanup.py` — post-pitch MIDI cleanup.
- `audio_to_tab/tuning.py` — fretboard / tuning helpers.
- `audio_to_tab/subprocess_util.py` — subprocess kwargs for desktop/CLI.
- `audio_to_tab/cli/__init__.py` — CLI package marker.
- `audio_to_tab/cli/isolate.py` — CLI isolate (Demucs/RoFormer/SCNet, `--guitar-checkpoint`, `--guitar-refine`, `--fold-other-mode`, `--sub-bass-debleed`, `--low-end-restore-db`, `--low-end-recovery`, `--two-pass`, lead/rhythm thresholds).
- `audio_to_tab/cli/pipeline.py` — CLI full pipeline.
- `audio_to_tab/cli/transcribe.py` — CLI transcribe.
- `audio_to_tab/cli/tab2pdf.py` — CLI tab/MIDI → PDF.
- `audio_to_tab/cli/mid2tab.py` — CLI MIDI → ASCII tab.

### `ui/`

Desktop Streamlit only.

- `__init__.py` — empty package marker.
- `app.py` — multipage router (Isolate + Tab PDF); Lite↔Pro sidebar (`UI_MODE_*`, persist to disk); nav-only global loading overlay (`should_show_global_loading`); injects Satoshi via `satoshi_font.py`.
- `pages/isolate.py` — Audio Isolation page (upload, YouTube, New/Mixer/Queue, downloads, fold/refine/low-end, pre/refined toggle). Lite: outcome cards + hardware Detected/Using + auto speed/device/guitar; Pro: Speed / Engine / This computer / stem checkboxes. Status strip owns running/failed jobs (retry, dismiss).
- `pages/tab_pdf.py` — Tab PDF demo page (model selector, guitar refine, guitar-ft, low-end restore, sub-bass de-bleed). Upload cap caption from `ui/common.py` (`max_upload_caption`).
- `guitar_fixup.py` — post-separation guitar stem fix-up for the Mixer tab (low-end recovery, pre/refined switch, diagnostics).
- `isolate_jobs.py` — serial Demucs/RoFormer worker; job status JSON under app data dir; `requeue_job`, `separation_in_progress`, `format_job_error`.
- `isolate_state.py` — Lite outcome cards, Pro track options, progress stages, UI mode helpers (`is_pro_mode`, persist settings), failed-strip TTL/dismiss, guitar selection (`prefer_roformer` for Lite CPU-only hosts).
- `stem_icons.py` — Lucide-style line-art icons for Lite/Pro stem and outcome tiles.
- `satoshi_font.py` — `@font-face` CSS for bundled Satoshi (used by `app.py`).
- `fonts/` — Satoshi `.woff2` + `satoshi.css` + `satoshi/README.txt` (local, no CDN).
- `desktop_export.py` — save isolate downloads to a chosen folder + reveal in OS file manager.
- `desktop_notify.py` — best-effort OS notifications for isolate job completion (no extra pip deps).
- `common.py` — run listing, uploads, data dir, edition labels, `max_upload_mb` / `max_upload_caption`, `should_show_global_loading` (nav-only).
- `media.py` — Streamlit media URLs, preview encode, mix cleanup.
- `icon.png` — window / tab icon.
- `stem_mixer_component/__init__.py` — iframe component; serves `frontend/build/`.
- `stem_mixer_component/frontend/src/main.ts` — live mixer (Web Audio) source.
- `stem_mixer_component/frontend/src/style.css` — mixer styles.
- `stem_mixer_component/frontend/package.json`, `vite.config.ts`, `tsconfig.json`, `index.html` — Vite build for the iframe.
- `region_picker_component/__init__.py` — waveform region iframe; serves `frontend/build/`.
- `region_picker_component/frontend/src/main.ts` — wavesurfer + Regions plugin source.
- `region_picker_component/frontend/src/style.css` — region picker styles.
- `region_picker_component/frontend/package.json`, `vite.config.ts`, `tsconfig.json`, `index.html` — Vite build.
- `mix_tabs_component/__init__.py` — Moises-style Home|mix|+ strip; serves `frontend/build/`.
- `mix_tabs_component/frontend/src/main.ts` — tab strip UI source.
- `mix_tabs_component/frontend/src/style.css` — tab strip styles.
- `mix_tabs_component/frontend/package.json`, `vite.config.ts`, `tsconfig.json`, `index.html` — Vite build.

### `web/`

Hosted SPA (Vite + React). Dev: `make web` (proxies API). Paths below are repo-rooted.

- `web/index.html` — SPA shell (may reference favicon paths not present under `web/public/`).
- `web/package.json` / `web/vite.config.ts` / `web/tsconfig.json` — build; Vitest for mixer engine.
- `web/netlify.toml`, `web/vercel.json` — SPA fallback hosting.
- `web/.env.example` — optional `VITE_API_BASE_URL` (same-origin Caddy leaves unset).
- `web/public/fonts/` — Satoshi `.woff2` + `satoshi.css` (bundled; favicon/apple-touch assets are **not** currently under `web/public/`).
- `web/src/main.tsx` — React mount.
- `web/src/App.tsx` — routes `/isolate`, `/tab`, login.
- `web/src/api.ts` — REST/WebSocket client for jobs, uploads, stems.
- `web/src/auth.tsx` — session / JWT.
- `web/src/styles.css` — global styles.
- `web/src/trackOptions.ts` — stem / track option labels shared by isolate UI.
- `web/src/vite-env.d.ts` — Vite typings.
- `web/src/pages/IsolatePage.tsx` — website isolation UI.
- `web/src/pages/TabPage.tsx` — website tab PDF UI.
- `web/src/pages/LoginPage.tsx` — login.
- `web/src/components/RegionPicker.tsx` — wavesurfer region trim for section mode.
- `web/src/components/StemMixer.tsx` — website mixer UI.
- `web/src/components/JobProgress.tsx` — job status display.
- `web/src/components/ProcessingModeSelect.tsx` — auto/fast/balanced from capabilities API.
- `web/src/components/ProcessingModeSelect.test.ts` — Vitest for processing-mode select.
- `web/src/mixer/engine.ts` — Web Audio mix engine.
- `web/src/mixer/engine.test.ts` — mixer unit tests.

### `backend/`

Hosted API.

- `__init__.py` — package marker.
- `main.py` — FastAPI routes: auth, upload, isolate/tab jobs (incl. guitar model/refine/debleed/restore fields), stem/mix download, WS events.
- `config.py` — `ATT_*` settings.
- `contracts.py` — Pydantic request/response models (incl. `low_end_restore_db`, `sub_bass_debleed`, guitar model/refine fields).
- `auth.py` — JWT, bootstrap admin, demo session.
- `models.py` — SQLAlchemy User / Job / Upload.
- `db.py` — engine + sessions.
- `storage.py` — local disk or S3/MinIO.
- `events.py` — in-process / Redis job progress.
- `capabilities.py` — hosted SPA processing modes (Auto / fast_cpu / balanced / high_gpu / lite). Distinct from desktop Streamlit Lite UI mode.
- `limits.py` — upload size/type checks.
- `worker.py` — arq worker entry.
- `jobs/__init__.py` — jobs package marker.
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
- `generate_icons.sh` — rebuild icons from source art.
- `icon.png` / `icon.icns` / `icon.ico` — app icons (present in this clone; regenerate via `generate_icons.sh` if missing).

### `tests/`

- `conftest.py` — puts `src/` and repo root on `sys.path`.
- `backend_test_utils.py` — rebind backend settings without reloading ORM.
- `test_isolate.py` — isolate engine (Demucs mocked), including `--segment` clamp, fold, bass-bleed.
- `test_isolate_jobs.py` — desktop serial queue / remove / error formatting / requeue.
- `test_isolate_state.py` — Lite outcomes, Pro stems, progress helpers, UI mode, failed-strip TTL; `prefer_roformer` guitar defaults.
- `test_global_loading.py` — nav-only overlay gate (`should_show_global_loading`).
- `test_scnet.py` — SCNet constants, availability, dispatch.
- `test_guitar_improvements.py` — spectral bleed gate, adaptive fold gain, guitar ensemble.
- `test_guitar_ft_weights.py` — guitar-ft weights SHA256 / download helpers.
- `test_guitar_backups.py` — guitar pre-refine vs refined variants.
- `test_guitar_fixup.py` — `ui/guitar_fixup.py` low-end recovery + variant switch.
- `test_pipeline_guitar.py` — tab pipeline guitar options (model/refine/debleed/restore).
- `test_cli_smoke.py` — five CLI entrypoints + `pyproject` scripts.
- `test_ui_pages.py` — Streamlit page pure helpers.
- `test_ingest.py` — YouTube ingest (network opt-in).
- `test_mixer.py` — mix helpers.
- `test_metronome.py` — beat-tracked metronome click stem.
- `test_stem_mixer_component.py` — desktop mixer build packaging.
- `test_region_picker_component.py` — desktop region picker build packaging.
- `test_mix_tabs_component.py` — desktop mix-tabs build packaging.
- `test_media.py` — preview / cleanup.
- `test_ui_common.py` — run list / delete / upload caption helpers.
- `test_desktop_paths.py` — launcher paths, freeze helpers, Streamlit about/shell assertions.
- `test_desktop_export.py` — `ui/desktop_export.py`.
- `test_desktop_notify.py` — `ui/desktop_notify.py`.
- `test_hardware.py` — RAM/GPU/chip probe, desktop recommend, Lite Detected/Using captions, MPS gate.
- `test_edition.py` — CPU vs CUDA edition.
- `test_macos_signing.py` — signing helpers (no codesign I/O).
- `test_api.py` — FastAPI smoke (incl. guitar option fields).
- `test_web_security.py` — auth, CORS, upload caps.
- `test_capabilities.py` — hosted processing-mode API (not desktop Lite UI).
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
- `workflows/ci.yml` — push/PR pytest + ruff on `src/`.
- `workflows/desktop-release.yml` — Windows CPU/CUDA Setup + macOS arm64/x64 `.pkg`.

### `.streamlit/`

- `config.toml` — local Streamlit: `gatherUsageStats = false`, `toolbarMode = "viewer"`, `headless = true`, `address = "127.0.0.1"`, `fileWatcherType = "none"`, `runOnSave = false`, `maxUploadSize = 500`, CORS + XSRF on. `credentials.toml` is gitignored.

### `docs/`

- `issues.md` — canonical I-xxx design-decision / issue history (CI and `PLANNING.md` cite it). Includes reserved historical IDs and the 2026-09-08 isolation performance/functional audit (`I-500`–`I-509`).
- `ui-issues.md` — UI/UX-only issue register (`I-600`+). Does not replace `issues.md`.
- `oracle-free-memory-spike.md` — gitignored name (not in public git; may be absent locally).

### Do not edit (generated / vendor)

One line each; do not hand-edit:

- `node_modules/`, `ui/stem_mixer_component/frontend/node_modules/`, `ui/region_picker_component/frontend/node_modules/`, `ui/mix_tabs_component/frontend/node_modules/`
- `.venv/`, `.venv311/`, `.venv312/`, `.venv-desktop/`, `.venv-desktop-x64/`, `.venv-*/`
- `web/dist/`
- `ui/stem_mixer_component/frontend/build/assets/*` (hashed Vite output)
- `ui/region_picker_component/frontend/build/assets/*` (hashed Vite output)
- `ui/mix_tabs_component/frontend/build/assets/*` (hashed Vite output)
- `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `audio_to_tab_pdf.egg-info/`
- `dist/`, `build/`, `.build/`, `packaging/ffmpeg/`
- `data/`, `output/` (local runs)

## Do not edit unless

- Mixer iframe **build**: `ui/stem_mixer_component/frontend/build/` is committed so testers need no Node. Change `frontend/src/` then `make mixer-build`. Do not rewrite hashed `assets/*` by hand.
- Region picker iframe **build**: `ui/region_picker_component/frontend/build/` is committed the same way. Change `frontend/src/` then `make region-picker-build`.
- Mix tabs iframe **build**: `ui/mix_tabs_component/frontend/build/` is committed the same way. Change `frontend/src/` then `make mix-tabs-build`.
- Desktop fonts: prefer editing `ui/satoshi_font.py` / replacing woff2 under `ui/fonts/`; do not reintroduce a CDN `<link>` for Satoshi.
- Env: copy `.env.example` / `.env.lite.example` / `web/.env.example` → `.env`. Never commit `.env`.
- Do not commit wavs (except `eval/fixtures/*.wav`), Demucs/torch weights, or `packaging/ffmpeg/` binaries.
- `CONTEXT_TREE.md` (and `docs/oracle-free-memory-spike.md`) are gitignored; `PROJECT_TREE.md` is tracked and is the canonical in-repo tree.

## Last verified

2026-09-12 — paths checked against disk (`ui/`, `src/audio_to_tab/`, `tests/`, `docs/`, root `*.md`, `.github/workflows/`, `.streamlit/config.toml`, `web/src/`, `web/public/`, `packaging/`, `backend/`, `scripts/`).
