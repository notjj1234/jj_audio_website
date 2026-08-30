# App Issue Tracker

Static analysis of the app, generated 2026-08-29. **Scope reframed 2026-08-29: this project is a
Windows/macOS desktop app for now — the website (FastAPI + React + Docker hosting) is parked,** not
deleted. Issues that only affect the website live in the Parked section at the bottom; everything
above it is what matters for shipping installers. Use the Status checkbox to track work.

## Legend

| Severity | Meaning |
|---|---|
| **Critical** | Don't ship a Windows/macOS build with these: data corruption, unbounded temp-garbage, app that looks hung, or stale code in installers. |
| **High** | Real bugs users hit often (silently wrong output, memory creep, non-reproducible builds, no test CI). |
| **Medium** | Less common bugs or quality/robustness gaps. |
| **Low** | Hygiene and polish. |
| **Parked** | Website-only (backend/ + web/ + Docker/Caddy hosting). Nothing here affects the desktop app; revisit if the site comes back. |

**Scope tags:** `Engine` (src/audio_to_tab, shared core) · `Desktop UI` (ui/, mixer) ·
`Packaging` (installers/ffmpeg) · `CI` · `Deps` · `Tests` · `Docs` · `Eval` · `Git`.

## Summary

| Tier | Count |
|---|---|
| Critical | 5 |
| High | 10 |
| Medium | 10 |
| Low | 16 |
| **Active (desktop) total** | **41** |
| Parked (website, on hold) | 63 |
| **Grand total** | **104** |

---

# Tier 1 — Critical (block a desktop release)

| ID | Sev | Scope | Where | Issue | Suggested fix | Status |
|---|---|---|---|---|---|---|
| I-046 | Critical | Engine | `ingest.py:345`; `separate.py:349` | `tempfile.mkstemp` returns an open FD that is never closed; the temp WAV is never deleted. On Windows the locked file makes `transcribe.py:50-54`'s `unlink()` raise `PermissionError` silently — temp files accumulate for the process lifetime and can fill the disk. | Close the FD (`os.fdopen`) immediately and delete the temp WAV afterwards, or use `TemporaryDirectory`. | - [x] |
| I-045 | Critical | Engine | `pipeline.py:76-93`; `cli/pipeline.py:25` | `max_duration_sec <= 0` runs `ffmpeg -t 0` → a 44-byte corrupt WAV is returned as success (the `out.exists()` check passes). CLI default is 90 with no "0 = unlimited" handling (isolate treats 0 as full file). Downstream Demucs/Basic Pitch then fails confusingly. | In `_trim_audio` treat `<= 0` as `None`; make the pipeline CLI follow isolate's `0 = unlimited` convention. | - [x] |
| I-049 | Critical | Engine | `pipeline.py:87-92`; `isolate.py:1442-1457` | Both ffmpeg trim paths run `subprocess.run(check=False)` and return the partial file on failure. A failed ffmpeg after creating a partial file yields corrupt output as success. | Check `returncode != 0` → fall back to input or raise. | - [x] |
| I-062 | Critical | Engine | `separate.py:236`; `isolate.py:284,310,1442`; `pipeline.py:87` | No subprocess timeouts, and `should_abort` is only checked between stages — a hung ffmpeg/demucs blocks the app forever and the UI "Stop" can't interrupt an in-flight job. | Add timeouts; give the abort path a `Popen` handle it can `.terminate()`. | - [x] |
| I-066 | Critical | Packaging | `make_app.sh:47-55` | "Refresh Streamlit sources" only copies `isolate.py` and `media.py`, but `audio_tools.spec:85-94` ships the entire `ui/` tree → macOS `.app`/`.pkg` mixes fresh and stale UI for app.py, common.py, isolate_jobs.py, etc. | Loop over the whole `ui/**/*.py` tree, or drop the partial refresh and require a fresh `pyinstaller --clean`. | - [x] |

---

# Tier 2 — High

| ID | Sev | Scope | Where | Issue | Suggested fix | Status |
|---|---|---|---|---|---|---|
| I-048 | High | Engine | `isolate.py:1518-1537` vs `separate.py:412-413` | `guitar-ft` checkpoint: isolate auto-downloads the 330 MB weights on first use; the pipeline silently falls back to stock when weights aren't cached — the user thinks they got guitar-ft. | Explicitly surface the fallback (or reuse a seeded cache) on both paths. | - [x] |
| I-047 | High | Engine | `isolate.py:1647-1650` vs `separate.py:354-361` | Isolate raises `RuntimeError` when a RoFormer model is selected without the backend; the tab/pipeline path silently falls back to `htdemucs_6s`. Same option, two opposite behaviors. | Pick one (prefer raising or reporting the fallback on both paths). | - [x] |
| I-052 | High | Engine | `pipeline.py:54,148` | Pipeline defaults to `max_duration_sec=90.0` and trims unconditionally → Tab PDF path silently drops everything after 90s (isolate defaults to full file). | Default to `None` or surface truncation in progress callbacks. | - [x] |
| I-050 | High | Engine | `isolate.py:1676-1686,1436-1437` | When `probe_duration_sec` returns `None` (or duration ≤ requested start) `trim_length` stays `None` and the whole file is separated ("Using full audio") — a requested region silently becomes the whole track. | Raise `RegionError` when a requested region can't be honored. | - [x] |
| I-051 | High | Engine | `ingest.py:157-165` | Happy path returns the raw extracted WAV (arbitrary sample rate/channels) instead of `normalize_audio`; the fallback mtime-based file pick can select a stale WAV in a reused dir, and `if safe[:20] in p.stem` with an empty/short `safe` matches the first entry. | Always normalize; match by exact sanitized title stem; handle the empty-safe case explicitly. | - [x] |
| I-065 | High | Desktop UI | `stem_mixer_component/frontend/src/main.ts:130-137,159-161` | `loadStems` clears `this.gains` without `disconnect()`-ing the old `GainNode`s, which stay wired into `masterGain`. Every song/stem switch accumulates orphaned gain nodes in the audio graph → growing memory/stale routing. (`stopSources` only disconnects sources.) | Iterate `this.gains.values()` and `.disconnect()` before clearing. | - [x] |
| I-067 | High | Packaging | `bundle_ffmpeg.py:18-62` | Comment claims "Versions pinned for reproducibility" but Windows/Linux URLs use BtbN `latest` master builds (macOS pins `b6.0`) → a rebuild silently swaps ffmpeg behavior/DLLs, so installers aren't bit-reproducible. | Pin all entries to a dated `autobuild-<date>` release. | - [x] |
| I-072 | High | CI | `.github/workflows/` | The only workflow is `desktop-release.yml`; there is no CI that runs `pytest` (~25 files) or the web Vitest suite. Tests can silently rot. | Add a `ci.yml`: `pytest tests/ -q` (CPU torch / mocked Demucs) + web Vitest + ruff. | - [x] |
| I-083 | High | CI | `.github/workflows/desktop-release.yml` | Release notes and `make_pkg.sh` claim "signed and notarized when certs exist," but the workflow never imports certs or passes notarization secrets → every CI `.pkg` is actually unsigned. | Wire cert import + notary secrets, or reword to "unsigned in CI". | - [x] |
| I-085 | High | Packaging | `pyproject.toml:42`; `requirements-demucs.txt:3-5`; `desktop-release.yml:99,108` | Unbounded `torch>=2.0`/`torchaudio>=2.0` alongside a tight `torchcodec>=0.14,<0.15` (bound to specific torch releases); CI uses unpinned `--upgrade torch`. Resolution-too-deep workarounds already documented in DESKTOP.md — fresh builds can break. | Cap torch to a verified range consistently everywhere. | - [x] |

---

# Tier 3 — Medium

| ID | Sev | Scope | Where | Issue | Suggested fix | Status |
|---|---|---|---|---|---|---|
| I-053 | Medium | Engine | `separate.py:104-105` | `download_guitar_ft_weights` slurps the whole 330 MB response into RAM and sends no `User-Agent` (may be rejected by HF redirect endpoints). | Stream to a temp file with SHA256 computed during write (like `roformer.download_sha256_file`); set a UA. | - [x] |
| I-054 | Medium | Engine | `separate.py:57-64` | `guitar_ft_weights_cached()` hashes the full 330 MB file on every isolated job using the checkpoint (then `download_guitar_ft_weights` hashes again). | Cache the digest or check size/mtime first. | - [x] |
| I-055 | Medium | Engine | `pipeline.py:43`; `separate.py:336` | `fold_other_mode` in `PipelineConfig` is passed then immediately `del`'d — a documented option that silently does nothing on the tab path. | Remove the field or honor it. | - [x] |
| I-068 | Medium | Desktop UI | `media.py:64-88`; `pages/isolate.py:1695-1722` | Mixer media files are registered inside a `@st.fragment` via `stem_media_urls`/`media_url_for_file`; fragment-scoped media registrations can be GC'd on the next full/fragment rerun → intermittent "trouble loading" stems. | Register media URLs in the full page run and pass the URLs into the fragment. | - [x] |
| I-069 | Medium | Desktop UI | `media.py:40-61`; `stem_mixer_component/frontend/src/main.ts:130-167` | `should_use_previews` (90s / 400 MB budget) is dead code: `ensure_mixer_audio_paths` returns full-res paths and the browser decodes every full stem → hundreds of MB in the WebView on long songs. | Actually produce clipped/downsampled previews and point `mixer_paths` at them, or remove the dead budget code. | - [x] |
| I-084 | Medium | Deps | `requirements.txt` vs `pyproject.toml:12-39` | `requirements.txt` omits backend deps (SQLAlchemy, redis, arq, boto3, slowapi, python-jose, passlib, …) yet adds `onnxruntime` and dev/eval extras — the file can't install a complete runtime, and PROJECT_TREE.md mislabels it "pip pin of runtime." | Make it an exact lock of `[project.dependencies]` or scope it "desktop-only" with a comment. | - [x] |
| I-086 | Medium | Packaging | `pyproject.toml:7` vs `src/audio_to_tab/__init__.py:3` | pyproject says `version = "1.0.0"` while build/installers all use `__version__ = "0.1.3"`. | Align to one source of truth (0.1.3). | - [x] |
| I-093 | Medium | CI | `desktop-release.yml:172` | Fresh `choco install innosetup` is the slowest/flakiest install path on `windows-latest`. | Fetch the Inno installer directly or via winget. | - [x] |
| I-094 | Medium | CI | `desktop-release.yml` | No `concurrency` guard (double `workflow_dispatch` runs = 4 heavy jobs concurrently) and no artifact retention config. | Add group concurrency + `retention-days`. | - [x] |
| I-098 | Medium | Tests | `ui/app.py`, `ui/pages/isolate.py`, `ui/pages/tab_pdf.py` | Streamlit pages untested (only their backing helpers are). | Add page-logic unit tests (state helpers, not st.*). | - [x] |

---

# Tier 4 — Low

| ID | Sev | Scope | Where | Issue | Suggested fix | Status |
|---|---|---|---|---|---|---|
| I-056 | Low | Engine | `ingest.py:315-318,86-90` | `ydl.params["logger"] = None` is set after `YoutubeDL.__init__` already fixed the logger → verbose output never reaches the log path; the path itself only exists on macOS, so `AUDIO_TOOLS_DEBUG=1` never logs on Windows. | Set the logger before init; make the path platform-neutral. | - [x] |
| I-057 | Low | Engine | `pdf_render.py:107-108` | `int(end_time / sec_per_measure) + 1` renders a trailing empty measure when the last note ends exactly on a bar line. | Use ceil-style rounding that drops strictly-empty trailing measures. | - [x] |
| I-058 | Low | Engine | `tab_generate.py:251-252` | `bpm` is actually `beats_per_measure`; `chars_per_beat` is really chars-per-measure (16) divided by beats → for 3/4 the per-beat char count is fractional and the grid drifts from `rhythm.py`'s 16th-note quantization. | Rename and compute `chars_per_beat = chars_per_measure / beats_per_measure`. | - [x] |
| I-059 | Low | Engine | `lead_rhythm.py:874-880` | Both branches of `if best.method == "midside" / else` assign `"a_lead"`, while the comment implies distinguishing logic. Misleading/dead branch. | Single assignment + accurate comment. | - [x] |
| I-060 | Low | Engine | `isolate.py:1841-1843,1864-1872` | If `emit_stems` policy dropped bass/drums, recovery reports "sub_bass_debleed requested but bass stem missing" — the diagnostic misattributes the emit policy as the cause. | Check the emit policy and report accurately. | - [x] |
| I-061 | Low | Engine | `roformer.py:692,757` | `_guitar_refine` work dir (`_guitar_refine/out/melband_roformer_guitar/...`, `refine_input.wav`) is never cleaned; junk accumulates per run. | Clean up in `try/finally`. | - [x] |
| I-063 | Low | Engine | `cli/isolate.py:54` | `--device` is an unvalidated free string; typos flow into demucs `-d` as a cryptic error. | Validate against `{"cpu","cuda"}`. | - [x] |
| I-064 | Low | Engine | `midi_cleanup.py:117-125` | `estimate_tempo_bpm` returns raw `pm.estimate_tempo()` with no plausibility clamp and no note-based rejection, diverging from the robust `tempo.py:48-79` version (no current callers → latent bug). | Delete it or delegate to `tempo`. | - [x] |
| I-070 | Low | Desktop UI | `pages/isolate.py:1817,1844,1851` | `use_container_width=True` is deprecated in newer Streamlit. | Replace with `width="stretch"`. | - [x] |
| I-095 | Low | CI | `.github/dependabot.yml` | Only root-pip and `/web` npm are covered; Docker images, GitHub Actions, and `ui/stem_mixer_component/frontend/package.json` are missed. | Add the missing ecosystems. | - [x] |
| I-096 | Low | Tests | `cli/` (5 entrypoints) | No tests at all for the CLI argparse paths (`isolate`, `pipeline`, `transcribe`, `tab2pdf`, `mid2tab`). | Add smoke/CLI tests. | - [x] |
| I-100 | Low | Git | `.gitignore` | Missing `.ruff_cache/` (PROJECT_TREE.md:259 claims it's ignored). | Add it. | - [x] |
| I-101 | Low | Docs | `README.md:5,31,68,95` | Leftover personal "For the following is for JJs bs, feel free to ignore" in the public README (also the package long_description), plus machine-specific absolute `cd` paths. | Remove the note; use `<repo>`-style placeholders. | - [x] |
| I-102 | Low | Docs | `PROJECT_TREE.md:60,268` | Says "Python 3.10–3.13" but pyproject is `<3.13`; header/heading naming drift. | Fix to match pyproject. | - [x] |
| I-103 | Low | Docs | `DESKTOP.md:213`; `eval/lead_rhythm/README.md:5` | DESKTOP example `AUDIO_TOOLS_VERSION=0.6` inconsistent with 0.1.3 framing; eval README links to gitignored `RESEARCH.md`/`RESULTS.md` (public 404s). | Sane version example; annotate local-only files. | - [x] |
| I-104 | Low | Eval | `eval/score_transcription.py:112-119` | `gate_solo_melody_f1` is computed but never enforced; `results.json` gitignored and no CI consumes it → eval is manual-only. | Wire a CI eval threshold or document as manual tool. | - [x] |

---

# Parked — Website (on hold)

Website-only (backend/ + web/ + Docker/Caddy hosting). Nothing here affects the desktop app;
revisit if the website work resumes. Rows are preserved verbatim from the original analysis.

## Parked · Backend (FastAPI) — I-001–I-021

| ID | Sev | Where | Issue | Suggested fix | Status |
|---|---|---|---|---|---|
| I-001 | High | `main.py:336,359,363`; `jobs/runner.py:31,134`; `jobs/single_flight.py:9-33` | Single-flight gate is acquired in the API process (`main.py:336`) but released in whichever process runs the job. `_busy` is process-local, so in worker mode (`use_worker=True`) the API process never releases it → after the first tab job, every later tab create returns 503 forever. The `except` at `main.py:357-364` also doesn't wrap the enqueue (`_enqueue_or_run` failure → held gate). Per-process gate is not global across uvicorn workers. | Fix: in worker mode rely on arq `max_jobs=1` instead of `acquire_or_503` at create; release the gate on any enqueue failure; or use a shared (Redis) gate. | - [ ] |
| I-002 | High | `jobs/runner.py:82-99,134,205-225` | `run_in_executor` futures are never cancelled — on cancel the DB is marked cancelled but Demucs/Basic Pitch keeps running. The `finally` releases the single-flight gate while the old job is still hogging CPU/RAM, so the memory-safety property the gate exists to protect is violated. | Track the executor future; release the gate / mark terminal only when the future actually returns; or run separation in a killable subprocess. | - [ ] |
| I-003 | Medium | `auth.py:128-140` | Access tokens are accepted via `?access_token=` in the query string on every authenticated route (through `get_current_user`), so tokens land in proxy/access logs, browser history, and referrers. The SPA already sends `Authorization: Bearer`. | Restrict the query-string fallback to the WebSocket endpoint only (parse it there). | - [ ] |
| I-004 | Medium | `auth.py:56-62`; `main.py:243-269` | Refresh tokens carry a `jti` that is never stored/checked. Logout only deletes the cookie and rotation issues a new token while the old one stays valid for `refresh_token_days` → stolen refresh cookie survives logout; replay works. | Persist `jti` bound to the user; revoke on logout and on use (enforce single-use rotation). | - [ ] |
| I-005 | Medium | `events.py:38-51` | `publish_redis` opens a fresh `redis.Redis(...)` per progress event (via `asyncio.to_thread`) and never closes it → socket/pool leak over long jobs. | Reuse one module-level client, or close in `finally`. | - [ ] |
| I-006 | Medium | `main.py:233-240`; `auth.py:97-108` | Every `POST /v1/auth/session` inserts a permanent DB user (`is_anonymous=True`) with no expiry/reaping → unbounded DB growth on public deployments. | Reap expired anonymous users (JWT exp is already in the token), cap session creation, add a disk/user-count guard. | - [ ] |
| I-007 | Medium | `limits.py:24-28`; `main.py:518-520`; `jobs/manager.py:82` | Upload filename relies on `Path(name).name`: quotes, control chars (`\r\n`), and (on POSIX) backslashes survive. The name is interpolated unescaped into the streaming `Content-Disposition` header → header injection; `..\..` style names stored literally on Linux. | Sanitize control chars/quotes/backslashes in `normalize_filename`; `quote()` the value used in the header. | - [ ] |
| I-008 | Medium | `main.py:213-218` | Login does `verify_password` (bcrypt ~100ms) only when the user exists → timing oracle for account existence. | Run a dummy bcrypt verify when the user is missing. | - [ ] |
| I-009 | Medium | `main.py:155-159,284,320,378` | `_rate_key` reads `request.state.user_id`, but that attribute is set *inside* the handler — after slowapi already evaluated the key. Every rate limit is keyed by IP, never per-user; with a reverse proxy all users share one bucket. | Set `request.state.user_id` in the `get_current_user` dependency (before the limiter); trust a configured forwarded-header IP. | - [ ] |
| I-010 | Medium | `main.py:336` vs `main.py:409-411` | Tab `create_job` returns 503 the moment the single-flight slot is busy, while isolate create queues (comment: "not at create"). Inconsistent policy breaks the SPA's serial-queue flow on busy hosts. | Apply one coherent policy to both job kinds (queue all, or 503 all). | - [ ] |
| I-011 | Medium | `main.py:326-334` | When `body.processing_mode` is given, the resolved cap silently replaces the validated `max_duration_sec` and the client isn't told (isolate threads it through at `main.py:391-393`). | Pass `requested_duration_sec` into the mode resolution too. | - [ ] |
| I-012 | Medium | `main.py:326-356` vs `main.py:379-380` | Tab jobs accept arbitrary `model` / `guitar_checkpoint`; invalid values (`IsolateConfig.__post_init__`) fail at runtime after queueing instead of a 400 at create (isolate validates). User waits in the single-flight queue then gets a generic failed job. | Validate model/checkpoint in tab `create_job`, surface a 400. | - [ ] |
| I-013 | Medium | `jobs/manager.py:197-199,277-280,515-535` | Job work dirs, uploads, temp stems, `stems.zip` and PDFs live in `data/jobs/<id>/` forever; `_local_work` grows per job in-process. No deletion endpoint or retention sweep. | Clean work dir after terminal status; periodic reap of old jobs/uploads; stop caching in `_local_work`. | - [ ] |
| I-014 | Low | `jobs/manager.py:438-464` | `set_artifacts` silently drops missing files (no log) and never removes the storage objects referenced by the `JobArtifact` rows it deletes. | Log warnings; delete stale storage keys after replacing artifacts. | - [ ] |
| I-015 | Low | `jobs/manager.py:79-115` | Upload object is fully written to storage *before* the DB row commits → orphaned storage file if the insert fails. | Insert the row first, or delete the object in an except handler. | - [ ] |
| I-016 | Low | `worker.py:32` | `WorkerSettings.job_timeout` is set to the "extreme" 4h for every job; per-quality timeouts computed in `manager.py:256-259` are unused. | Set per-job timeout at enqueue time (arq supports it). | - [ ] |
| I-017 | Low | `storage.py:66-75`; `main.py:290-309` | `open_temp` / artifact streaming load whole objects into RAM; the upload path buffers the full file as chunk bytes (2x memory). | Stream-copy with `shutil.copyfileobj` / spool to disk. | - [ ] |
| I-018 | Low | `main.py:507-520,542-557` | If a `StreamingResponse` is aborted mid-stream (client disconnect), `tmp.unlink()` is skipped — `unlink` is outside `finally` → temp-file leak. | Move cleanup into `finally`. | - [ ] |
| I-019 | Low | `main.py:455` | `list_jobs?limit=0` returns 1 row instead of being rejected (`max(1, limit)`). | Reject `limit < 1` with a 400, or treat 0 as "no limit". | - [ ] |
| I-020 | Low | `tests/test_single_flight.py:23-28,74-101` | Test mutates the process-global `_busy` and releases it manually; an assert failure before release poisons the rest of the suite. | Use a teardown fixture (consider `autouse` reset). | - [ ] |
| I-021 | Low | `tests/test_api.py:220` | `Path("eval/fixtures/solo_melody.mid")` is CWD-relative; silently skips unless pytest runs from repo root. | Resolve against the project root. | - [ ] |

## Parked · Web frontend (React/TS) — I-022–I-044

| ID | Sev | Where | Issue | Suggested fix | Status |
|---|---|---|---|---|---|
| I-022 | High | `App.tsx:52-58`; `pages/LoginPage.tsx` | `/login` route is never registered and `LoginPage` is imported nowhere. In production `require_auth` + `demo_mode=false` rejects anonymous sessions → no way to sign in; the whole app 401s. | Register `<Route path="/login" .../>`, gate shell routes behind `auth.email`, redirect unauthenticated users to `/login`. | - [ ] |
| I-023 | High | `auth.tsx:24-41`; `api.ts:26-52` | Access tokens expire (default 30 min) but the frontend never calls `/v1/auth/refresh`. On expired token `api.me().catch` drops the token and returns, stranding the user with no anonymous fallback and 401s on every call. | Add `refresh()` (cookie-based); on 401 attempt refresh once then retry, else fall back to anonymous session / logout. | - [ ] |
| I-024 | High | `api.ts:172-181`; `pages/IsolatePage.tsx:663-666,644`; `pages/TabPage.tsx:114-119`; `backend/contracts.py:148-154`; `backend/main.py:592-601` | WebSocket payloads are `JobEvent`-shaped (`job_id`, no `id`/`error`) but are cast `as JobResponse`. First WS update clobbers `job` with an object lacking `id` → Cancel calls `/v1/jobs/undefined/cancel` (404); failures swallowed (`error` undefined). | Normalize before `setJob`: `onUpdate({ id: data.job_id ?? jobId, error: data.error ?? null, ...data })`; type the WS payload explicitly. | - [ ] |
| I-025 | High | `IsolatePage.tsx:683,688`; `TabPage.tsx:127,131`; `mixer/engine.ts:175`; `backend/jobs/manager.py:512` | Backend returns relative signed URLs (`/v1/artifacts/...`); frontend uses them directly. With `VITE_API_BASE_URL` set (the cross-origin deploy `.env.example` promotes) they resolve against the frontend origin → downloads are `index.html`, `decodeAudioData` fails. | Prefix artifact URLs with `API_BASE` like `api()` does, or have the backend emit absolute URLs. | - [ ] |
| I-026 | High | `IsolatePage.tsx:198,421-422,640-646`; `TabPage.tsx:16,40-41` | `watchJob`'s `stop` is only called on re-submit, never on unmount → open WS + 2s poll loop continues after navigating away. | `useEffect(() => () => stopWatchRef.current?.(), [])` (hold latest stop in a ref). | - [ ] |
| I-027 | Medium | `api.ts:150-163`; `IsolatePage.tsx:640-646` | `poll()` checks `stopped` before `await getJob` but not after; `onUpdate` can run for a stale watcher after `stop()` → old job overwrites the newly selected queue row. | Guard `onUpdate` with `if (stopped) return;` after the await (or use a watcher generation counter). | - [ ] |
| I-028 | Medium | `api.ts:155-158`; `IsolatePage.tsx:682-691` | Signed artifact links expire after `artifact_sign_ttl_sec = 600` while the job stays "done"; `stop()` halts polling so URLs go stale ~10 min in. Returning users get 403s on downloads and mixer loads. | Re-fetch `getJob` when results render/are opened, or refresh signed URLs on click. | - [ ] |
| I-029 | Medium | `components/StemMixer.tsx:26,72-75`; `mixer/engine.ts:89-103,123-142` | AudioContext, buffers and gain/source nodes are never disposed; unmount only calls `pause()`. Every remount leaks an AudioContext; StrictMode double-mount can run `loadStems` twice concurrently with no generation guard. | Add `StemMixerEngine.dispose()` (`ctx.close()`, clear buffers/gains/sources, cancel RAF) and call it in cleanup; add a load-generation counter. | - [ ] |
| I-030 | Medium | `IsolatePage.tsx:201-203,283-297,340-358,542-544` | `objectUrlRef.current` is read during render (may hold a previously-revoked URL), and `previewRegion()` plays a detached `new Audio()` in parallel with the in-DOM `<audio>`; `void audio.play()` leaves its rejection unhandled when autoplay is blocked. | Store the object URL in state and derive `src`; `audio.play().catch(() => {})`. | - [ ] |
| I-031 | Medium | `api.ts:186-205` | `ws.onclose` fires an immediate `poll()` *and* the unconditional `pollTimer` may still run → two polling loops; polling also runs on top of a healthy WS, making it redundant. | Schedule polling from exactly one place; track all timer handles. | - [ ] |
| I-032 | Medium | `components/StemMixer.tsx:184-198,220-235`; `mixer/engine.ts:44-51` | `isAudible` ignores the volume floor (a stem at −60 dB shows as audible), and Mute/Solo buttons have accessible names "Mute"/"Solo" with no stem label → screen readers can't tell which stem. | Include `dbToLinear(...) > 0` in `isAudible`; add `aria-label={`Mute ${stem.label}`}` etc. | - [ ] |
| I-033 | Medium | `components/ProcessingModeSelect.tsx:29-68`; `IsolatePage.tsx:233-246` | `helperText` flashes "Could not detect host" while `caps === null` (still loading), `selectValue` can hold a mode id absent from `caps.modes`, and `getSystemCapabilities` is fetched twice per mount. | Track loading separately; clamp the select value to a known mode; lift the fetch, or drop the page-level duplicate. | - [ ] |
| I-034 | Medium | `api.ts:26-52` | No client-side timeouts or abort anywhere → uploads/requests can hang forever, `busy` stuck "Starting…". | Add an `AbortController` timeout (longer for uploads); surface timeout as a friendly message. | - [ ] |
| I-035 | Low | `api.ts:166` | Access token passed in the WS query string → lands in proxy/access logs and `Referer`. Backend supports header fallback. | Send token via a first message after `onopen` or a subprotocol. | - [ ] |
| I-036 | Low | `components/StemMixer.tsx:67-71`; `mixer/engine.ts:283-293` | `setTimeCallback` drives ~3 React set-states per animation frame while playing → whole mixer re-renders at ~60 fps. | Throttle the callback to ~4 Hz; keep the RAF loop only for playback math. | - [ ] |
| I-037 | Low | `main.tsx:8`; `auth.tsx:24-41` | StrictMode double-mount creates two anonymous users per dev load (rate-limited endpoint + orphan DB rows). | Guard with a module-level/ref flag. | - [ ] |
| I-038 | Low | `components/StemMixer.tsx:26` | `useRef(new StemMixerEngine())` constructs the engine on every render. | Lazy-init: `useRef<StemMixerEngine | null>(null)` + `if (!ref.current) ref.current = new StemMixerEngine();`. | - [ ] |
| I-039 | Low | `styles.css:451-459` | Dead CSS: `.nav span` / `.nav button.secondary` and the `@media (max-width: 400px)` block match no rendered markup. | Remove. | - [ ] |
| I-040 | Low | `IsolatePage.tsx:268` | `jobList` interval effect depends on `[job?.id, job?.status]`; because of I-024 `job.id` oscillates → interval torn down/recreated constantly. | Narrow deps (stable job id only). | - [ ] |
| I-041 | Low | `TabPage.tsx:88-96`; `backend/contracts.py:59` | UI caps `low_end_restore_db` at 6, backend allows up to 12 → users can't reach the supported range. | Align the caps. | - [ ] |
| I-042 | Low | `vite.config.ts:9-13` | Dev proxy target `http://127.0.0.1:8000` is hardcoded; any other backend port breaks `npm run dev`. | `process.env.ATT_API_PROXY ?? "http://127.0.0.1:8000"`. | - [ ] |
| I-043 | Low | `IsolatePage.tsx:292` | `Math.min(d, Math.max(5, 30))` lets a region end shorter than the 5s minimum; the user only learns at submit time. | Pre-check in the UI and show inline when region mode is on. | - [ ] |
| I-044 | Low | `components/JobProgress.tsx:29-40` | No `role="status"` / `aria-live` on job progress → assistive tech never hears status changes. | Add `role="status"` / `aria-live="polite"`. | - [ ] |

## Parked · Hosting / Docker / Caddy — I-071, I-073–I-082, I-087–I-092

| ID | Sev | Where | Issue | Suggested fix | Status |
|---|---|---|---|---|---|
| I-071 | High | `docker-compose.yml:42,46,54,73`; `separate.py:46-49`; `roformer.py:103-106` | `TORCH_HOME` is never set, so Demucs/Basic Pitch weights cache to `/root/.cache/torch` (ephemeral layer) instead of the shared `app_data` volume → API and worker re-download GBs on every recreate. | Set `TORCH_HOME=/app/data/torch` on `api` and `worker`. | - [ ] |
| I-073 | Medium | `Dockerfile`; `docker-compose.yml` | No `HEALTHCHECK` anywhere and uvicorn/arq run as root. | Add an API `HEALTHCHECK`; create a non-root user. | - [ ] |
| I-074 | Medium | `Dockerfile:13` | Production image installs `.[dev,eval]` (pytest/ruff/mir_eval/scipy) into the runtime image. | Install runtime deps only (+ `-r requirements-demucs.txt`); separate test target. | - [ ] |
| I-075 | Medium | repo root | No `.dockerignore` — the build context ships `.venv*` (multi-GB), `data/`, `dist/*.exe`, `node_modules/`. | Add `.dockerignore` mirroring `.gitignore`. | - [ ] |
| I-076 | High | `docker-compose.yml`; `docker-compose.lite.yml` | No `restart:` policy on any service → host reboot or crash leaves the stack down. | `restart: unless-stopped` on all services. | - [ ] |
| I-077 | Medium | `docker-compose.yml:96,105` | `minio:latest` and `minio/mc:latest` unpinned. | Pin to a specific release tag. | - [ ] |
| I-078 | Medium | `docker-compose.yml:113` | `minio-init` uses `sleep 3; mc mb ... || true` — on slow hosts the bucket isn't created and the error is swallowed; later uploads fail with opaque boto errors. `S3Storage._ensure_bucket` also swallows failures. | Retry loop (`mc ready local`) and/or surface bucket-create errors. | - [ ] |
| I-079 | Medium | `docker-compose.yml:49-52,68-71,84-88` | Only Postgres has a healthcheck; api/worker start on `service_started` for redis/minio → flaky startup when those aren't ready. | Add redis/MinIO/api healthchecks; use `service_healthy`. | - [ ] |
| I-080 | Medium | `storage.py:94-100` | boto3 client has no `Config(s3={'addressing_style': 'path'})`; default auto addressing with `endpoint_url=http://minio:9000` resolves to `audio-tools.minio:9000` → DNS failure in the compose network. No S3 test exists. | Set path-style addressing; add a MinIO smoke test. | - [ ] |
| I-081 | Medium | `docker-compose.yml:35-36,79-80,99-100` | Hardcoded defaults in compose: Postgres `att/att`, MinIO `minioadmin/minioadmin`, Redis no password. Wide open on a misconfigured public host. | Require overrides (`:?`) for secrets or document loudly. | - [ ] |
| I-082 | Medium | `Caddyfile` | No security headers (only `encode gzip`). | Add `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, CSP, HSTS via a `headers` snippet. | - [ ] |
| I-087 | Medium | `config.py:84-97`; `.env.example:2`; `.env.lite.example:4` | The prod guard rejects empty/`dev-only-change-me` secrets but not the shipped `replace-with-long-random-string` placeholder → a public demo copied from `.env.example` uses a publicly-known JWT signing secret. | Add the shipped placeholders to the weak-secret denylist. | - [ ] |
| I-088 | Low | `Dockerfile:1`; `Dockerfile.web:1,8` | Unpinned base images (`python:3.11-slim`, `node:20-alpine`, `caddy:2-alpine`). | Pin patch tags or digests. | - [ ] |
| I-089 | Low | `Dockerfile.web:4` | `npm install` ignores the lockfile for reproducibility. | Use `npm ci`. | - [ ] |
| I-090 | Low | `DEPLOY.md:52` | Backup strategy is doc-only (no script/cron for pg_dump + mc mirror), and no job/upload/anon-user pruning exists. | Add a backup script and optional prune job. | - [ ] |
| I-091 | Low | `Caddyfile:3`; `.env.example:7` | `email {$ATT_ACME_EMAIL:}` with an empty env var can produce a bare `email` option that Caddy rejects. | Use a safe default or drop when unset. | - [ ] |
| I-092 | Low | `Caddyfile:9-11` | No reverse-proxy transport timeouts; a hung API wedges connections. | Add `transport http { dial_timeout / read_timeout }`. | - [ ] |

## Parked · Website-only tests — I-097, I-099

| ID | Sev | Where | Issue | Suggested fix | Status |
|---|---|---|---|---|---|
| I-097 | Low | `backend/events.py`, `backend/worker.py`, `backend/storage.py` (S3) | No functional tests for WebSocket/Redis events, arq worker, or the S3 backend. | Add targeted tests (S3 via MinIO + mocked boto). | - [ ] |
| I-099 | Low | `web/src` | Only `mixer/engine.test.ts` exists; `api.ts`, `auth.tsx`, `StemMixer`, `JobProgress`, `ProcessingModeSelect`, and all pages are untested. | Add unit tests for api/auth + component tests. | - [ ] |

---

## Cross-cutting themes (desktop-first)

- **Temp-file & memory hygiene (I-045, I-046, I-049, I-053, I-054, I-061, I-065, I-068, I-069):** files, FDs, gain nodes, and browser buffers leak. Batch-fix — this is one coherent "we need a cleanup discipline in the engine + mixer" sweep. Highest desktop impact.
- **Tab-quality path (I-047, I-048, I-050, I-052, I-055):** the product's core feature silently degrades — options ignored, weak-model fallbacks, silent truncation. Fix so what the user picks is what they get.
- **Release reproducibility (I-066, I-067, I-085, I-072, I-083, I-093, I-094):** installers must capture the code you tested: pinned ffmpeg + torch, a refresh that ships current UI, a test CI gate, and honest signing claims.
- **Version + dependency confusion (I-084, I-086):** one source of truth for version; requirements.txt that describes what it actually installs.
- **Verification hygiene (I-096, I-098, I-104, I-100):** untested CLI/pages and an unevaluated eval gate strip your safety net exactly when you're about to ship.