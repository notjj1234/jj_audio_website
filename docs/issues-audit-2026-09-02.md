# Issues Audit — 2026-09-02

Full-project audit generated 2026-09-02. **Scope: desktop app first, website parked.** This file
supplements `issues.md` (which covers I-001 through I-104, all desktop items resolved). New IDs
start at I-200 to avoid collisions.

## Legend

| Severity | Meaning |
|---|---|
| **Critical** | Don't ship a build with these: UI hangs, infinite loops, data loss, or broken frozen builds. |
| **High** | Real bugs users hit often: silent failures, misleading output, missing error handling, security gaps. |
| **Medium** | Robustness gaps, edge cases, confusing UX, or performance concerns. |
| **Low** | Polish, accessibility, cosmetic, or documentation. |
| **Parked** | Website-only (backend/ + web/ + Docker/Caddy). Nothing here affects the desktop app. |

**Scope tags:** `Engine` (src/audio_to_tab, shared core) · `Desktop UI` (ui/, mixer) · `Packaging` ·
`CI` · `Deps` · `Tests` · `Docs` · `Web` (web/src/) · `API` (backend/).

## Summary

| Tier | Count |
|---|---|
| Critical | 3 |
| High | 13 |
| Medium | 22 |
| Low | 14 |
| **Active (desktop) total** | **52** |
| Parked (website) | 67 |
| **Grand total** | **119** |

---

# Tier 1 — Critical (block a desktop release)

| ID | Sev | Scope | Where | Issue | Suggested fix | Status |
|---|---|---|---|---|---|---|
| I-200 | Critical | Desktop UI | `pages/isolate.py:2233-2236` | When a picked library run's files are deleted, `apply_listen_picker_pending` sets `LISTEN_PICKER_NEXT_KEY = loaded_dir` then reruns. If `loaded_dir` is also gone, `_apply_listen_pick` sets `isolate_listen_missing` and reruns, which re-applies the dead dir → **infinite rerun loop** → Streamlit "too many reruns" error and the page becomes unusable. | Guard against non-existent dirs before setting `LISTEN_PICKER_NEXT_KEY`; break the loop by clearing the picker on missing runs instead of rerunning. | - [ ] |
| I-201 | Critical | Desktop UI | `pages/isolate.py:1807-1822` | `ffmpeg` conversions in `_save_all_tracks` / `_save_current_mix` (`desktop_export.convert_audio`) run **synchronously with no spinner or progress indicator**. For a long track converting to MP3/FLAC/Opus, the entire Streamlit UI freezes for many seconds with zero feedback. `st.success()` only fires at the very end. Users think the app has crashed. | Wrap in `st.spinner()` or `st.status()` with a format-specific label. | - [ ] |
| I-202 | Critical | Packaging | `desktop_export.py:86-88` | `_ffmpeg_path()` only checks `shutil.which("ffmpeg")` via PATH. In the **frozen desktop app**, the bundled ffmpeg (`packaging/ffmpeg/`) may not be on PATH. `main()` verifies ffmpeg at startup (line 2475) so it works in practice, but `convert_audio` itself won't find a bundled copy — any code path that calls conversion without the upfront check silently fails. | Have `_ffmpeg_path()` also check `sys._MEIPASS` / the packaging bundle directory as a fallback. | - [ ] |

---

# Tier 2 — High

| ID | Sev | Scope | Where | Issue | Suggested fix | Status |
|---|---|---|---|---|---|---|
| I-203 | High | Desktop UI | `pages/isolate.py:751,1738` | Building the current mix (`_build_current_mix` → `mix_stems_to_wav`) and computing waveform peaks (`_stem_waveform_peaks`) happen synchronously in the render path with **no `st.spinner`**. For long stems this stalls the UI with no indication of work. The `except Exception: return []` in `_stem_waveform_peaks` silently returns no waveform on failure. | Wrap mix-building and peak-computation in `st.spinner()` or move to a fragment with a loading state. | - [ ] |
| I-204 | High | Desktop UI | `pages/tab_pdf.py:355-361` | The generic `except Exception` block catches **all** conversion errors and shows "Conversion failed — your file and settings are still here, so you can just try again." The actual error is buried in a collapsed expander. Many failures (bad file, disk full, missing model weights) are non-retryable and the message gives the user no idea what went wrong or how to fix it. | Distinguish retryable vs non-retryable errors; show specific guidance (e.g. "disk full" vs "missing model weights" vs "corrupt audio"). | - [ ] |
| I-205 | High | Desktop UI | `pages/isolate.py:2515-2517` | `_render_tab_pdf_artifact` catch-all: `st.error("Could not draw New. Click Refresh.")` — no expander with details, no specific hint. The only recovery instruction is "Refresh." which is weak UX for a desktop app. | Add a `help` caption or expander with the actual exception text. | - [ ] |
| I-206 | High | Desktop UI | `pages/isolate.py:784` | `st.error(f"Could not prepare track audio for the mixer: {exc}")` leaks raw exception text (often a full filesystem path or internal API name) directly to users. | Sanitize the error; show a user-friendly message with the raw error in an expander. | - [ ] |
| I-207 | High | Desktop UI | `stem_mixer_component/__init__.py:47` | `components.declare_component("stem_mixer", url="http://localhost:3001")` — hardcoded dev-server port 301. If the Vite dev server runs on a different port, the mixer silently fails to load. No detection or fallback messaging. | Use an env var or detect the port; log a warning when the dev server is unreachable. | - [ ] |
| I-208 | High | Engine | `roformer.py:333-334,533-534` | `torch.load(..., weights_only=False)` is used as a **fallback** when `weights_only=True` fails. `weights_only=False` allows arbitrary code execution from checkpoint files. The user gets no warning that weights are being loaded unsafely. If a malicious or corrupt checkpoint is downloaded, this is a code-execution vector. | Log a warning when falling back to `weights_only=False`; consider pinning model sources and verifying integrity before load. | - [ ] |
| I-209 | High | Engine | `roformer.py:340,540` | `model.load_state_dict(state, strict=False)` silently ignores missing/unexpected keys. A corrupted checkpoint or architecture version mismatch produces a model that runs but gives **garbage results** with no error message. | Use `strict=True` or at least log the missing/unexpected keys at WARNING level. | - [ ] |
| I-210 | High | Engine | `isolate.py:302-363` | `probe_duration_sec()` returns `None` with **no logging** when all three backends (ffprobe, ffmpeg, soundfile) fail. Callers like `_ingest_trimmed()` then raise a confusing `RegionError` saying "audio duration is unknown" when the real problem is a missing tool or corrupted file. | Log each backend failure; return a more descriptive error or raise instead of returning None. | - [ ] |
| I-211 | High | Engine | `isolate.py:904-913` | `_stem_rms()` catches `except Exception` and returns `0.0` on **any** error (corrupted file, permission error, disk full), making the stem appear "near-silent." Downstream `detect_present_stems` then skips or misclassifies the stem without any warning. | Log the exception; return a sentinel that triggers a warning rather than silently zero. | - [ ] |
| I-212 | High | Engine | `isolate.py:587-603` | `apply_fold_other_into_guitar()` catches `except Exception` on the spectral overlap check and sets `piano_overlap = None`, causing the fold to proceed as if the check passed. No log message. A file-system error causes Other to be **blindly folded into Guitar** when it should have been skipped. | Log the exception; default to skipping the fold when the overlap check fails. | - [ ] |
| I-213 | High | Engine | `isolate.py:314-352; ingest.py:445; isolate.py:1989-2006; pipeline.py:95-103` | `subprocess.run()` calls for ffprobe, ffmpeg normalize, and ffmpeg trim have **no timeout**. A corrupted file could cause ffprobe/ffmpeg to hang indefinitely, blocking the job forever. The UI "Stop" button can't interrupt an in-flight subprocess. | Add `timeout=` to all `subprocess.run()` calls; use `subprocess.Popen` with `terminate()` support for the abort path. | - [ ] |
| I-214 | High | Engine | `isolate.py:2155,2174` | `progress("guitar_refine", "Refining guitar stem")` is called **twice** with the same message — once before refine starts and once after it finishes. The second call sends "Refining guitar stem" even though refinement is complete. The UI shows confusing duplicate progress messages. | Change the second call to "Guitar refinement complete" or remove it. | - [ ] |

---

# Tier 3 — Medium

| ID | Sev | Scope | Where | Issue | Suggested fix | Status |
|---|---|---|---|---|---|---|
| I-215 | Medium | Desktop UI | `pages/isolate.py:961-974` | `_closed_selectbox` wraps `st.selectbox` in a try/except to handle the `filter_mode` kwarg. But the `except TypeError` catches **any** TypeError — including wrong `help=`/`key=` conflicts — masking real bugs and silently producing a free-text combobox the developer didn't intend. | Check the Streamlit version explicitly (e.g. `st.__version__`) rather than relying on exception-based feature detection. | - [ ] |
| I-216 | Medium | Desktop UI | `pages/isolate.py:1827` | `st.segmented_control(...)` requires Streamlit ≥1.41. There is no version guard or fallback. If the pinned Streamlit is older, the Downloads panel throws a `TypeError` on load. | Add a version check; fall back to `st.radio` or `st.selectbox` on older Streamlit. | - [ ] |
| I-217 | Medium | Desktop UI | `pages/isolate.py:2403-2411,2454-2465` | When a new file is pending while old results are in the mixer, both the "New file selected" caption and the file-ready banner appear simultaneously. This **dual messaging** confuses users about what's "current." | Consolidate into a single status message; suppress the stale-results caption when the banner is visible. | - [ ] |
| I-218 | Medium | Desktop UI | `pages/isolate.py:2434` (fragment media registration) | `register_mixer_media` must run during full page run (documented in `media.py:63-74`). The fragment `_mixer_and_downloads_fragment` will **not** re-register URLs on its own reruns. If Streamlit GC's the media manager entries between fragment reruns, stems **intermediately fail to load**. The risk is acknowledged in comments but remains a latent race. | Move media registration into the fragment or ensure URLs survive GC (e.g. via `st.cache_resource`). | - [ ] |
| I-219 | Medium | Desktop UI | `pages/isolate.py:1397-1403` | Progress bar caps at 95% (`intra_stage_fraction` in `isolate_state.py:1282`). Combined with ETA that says "estimating…" for the first 3 seconds, users see a bar **stuck at 95%** with a growing ETA — a common source of confusion. | Show stage name alongside the percentage; consider a two-level bar (stage + intra-stage). | - [ ] |
| I-220 | Medium | Desktop UI | `common.py:64-65` | `desktop_app_version()` catches `except Exception` and returns a **hardcoded version "0.1.3"**. If this fallback ever fires, users/testers see a stale version that no longer matches the actual installer — confusing for bug reports. No warning is surfaced. | Log a warning when the fallback fires; never hardcode a version string. | - [ ] |
| I-221 | Medium | Desktop UI | `pages/isolate.py:2118-2140` | `_clear_loaded_mixer` clears many session keys but **does not clear** `isolate_listen_missing` or reset `LISTEN_PICKER_KEY`. After "Delete this run" the selectbox may retain a dangling value pointing at a deleted run. | Clear `LISTEN_PICKER_KEY` and related state in `_clear_loaded_mixer`. | - [ ] |
| I-222 | Medium | Desktop UI | `pages/isolate.py:1196-1197` | Guitar fix-up panel shows metrics like "high-end share: 0.34" without explaining what "high-end >4 kHz share" means. Non-technical users see raw numbers with no context. | Add a tooltip or rephrase in plain language (e.g. "Brightness: moderate"). | - [ ] |
| I-223 | Medium | Desktop UI | `pages/isolate.py:1201-1206` | "Output name" text input has **no length/sanitization validation**. A user pasting a 1000-char string or `foo/bar:baz` won't know about the problem until export. The name is eventually sanitized by `sanitize_export_name` but with no upfront feedback. | Add `max_chars` and inline validation. | - [ ] |
| I-224 | Medium | Engine | `isolate.py` (multiple) | No guard against **extremely large audio files**. A 10-hour file attempts full-file processing, consuming unbounded memory — especially in RoFormer (`roformer.py:344`) and SCNet (`scnet.py:212`) which load entire audio into RAM. OOM crash with no meaningful error. | Add a max-duration or max-file-size check early; warn or reject before processing. | - [ ] |
| I-225 | Medium | Engine | `roformer.py:463` | `_demix_track` division guard: `result /= np.maximum(counter, 1e-8)`. If `counter` is exactly 0 for some samples (very short audio), the output is scaled to `1e8` instead of being zero, producing **huge audio spikes**. | Use `np.where(counter > 0, result / counter, 0.0)` instead. | - [ ] |
| I-226 | Medium | Engine | `scnet.py:246` | `estimated = result / counter.unsqueeze(0).unsqueeze(0)` — no guard against zero in `counter`. If a segment was never covered by any chunk, counter is 0 → NaN/inf. `np.nan_to_num` fixes NaN to 0.0 but **inf remains**. | Add explicit zero-guard: `np.where(counter > 0, result / counter, 0.0)`. | - [ ] |
| I-227 | Medium | Engine | `isolate.py:510-517,619-626,719-748` | Multiple functions (`_write_band_limited_other`, fold gain search) read full files into RAM. Peak memory for a bleed-gated file can reach **~5x the file size** (mono STFT + stereo STFT + band-limited copy + gain search copies). No file-size-aware early bail. | Add a memory budget check; process in chunks where possible. | - [ ] |
| I-228 | Medium | Engine | `separate.py:59-90` | `_guitar_ft_digest_sidecar` write/read race: concurrent jobs checking `guitar_ft_weights_cached()` could race on the sidecar file. One process reads while another writes → partial read → unnecessary re-hashing of 330 MB. | Use file locking (e.g. `fcntl` / `msvcrt`) or atomic rename with a temp file. | - [ ] |
| I-229 | Medium | Engine | `roformer.py:103-165` | `download_sha256_file()` checks `dest.is_file()` then writes a `.part` file then `tmp.replace(dest)`. Two concurrent downloads of the same model could race → `replace()` is **not atomic on Windows** → corrupted checkpoint. | Use a lock file or verify hash after replace. | - [ ] |
| I-230 | Medium | Engine | `ingest.py:166-174` | `_clear_ytdlp_cache()` catches `except Exception: pass` — if the cache directory is locked or missing, the stale cache persists and 403 errors continue with no indication the cache-clear failed. | Log a warning; don't silently swallow. | - [ ] |
| I-231 | Medium | Engine | `tempo.py:34-45` | `estimate_tempo_from_audio()` catches `except Exception: return None` with **no logging**. If librosa crashes due to a real bug or memory error, the pipeline silently falls back to MIDI tempo — silent quality degradation with no diagnostic trail. | Log the exception at WARNING level. | - [ ] |
| I-232 | Medium | Engine | `cli/isolate.py:67` | `--device` choices are `["cpu", "cuda"]` — **Apple Silicon users cannot select MPS** from the CLI. They must use `resolve_safe_device()` programmatically. | Add `"mps"` to the choices. | - [ ] |
| I-233 | Medium | Engine | `isolate.py:2050-2054` | `_collect_stem_wavs` doesn't deduplicate: `found[stem_path.stem] = stem_path` overwrites silently. In single-pass mode, duplicate filenames could mask real issues. | Log a warning when a duplicate stem name is encountered. | - [ ] |
| I-234 | Medium | Engine | `pipeline.py:37-64` | `PipelineConfig` doesn't validate `demucs_quality` or `beats_per_measure`. Invalid quality strings silently use defaults; `beats_per_measure=0` causes division-by-zero in `pdf_render.py:114`. | Validate quality against known values; reject `beats_per_measure <= 0`. | - [ ] |
| I-235 | Medium | Engine | `midi_cleanup.py:87-88` | `pitch_min/pitch_max` hard-coded to guitar range (40–88). Notes outside guitar range are **silently dropped**. If the source is bass or piano, this produces incorrect output. | Make pitch bounds configurable or detect instrument type. | - [ ] |
| I-236 | Medium | Engine | `ingest.py:351-395` | `download_youtube_audio` retry doesn't reset previously downloaded files. On retry, a partial/corrupt file from attempt 1 may be returned instead of the successful attempt 2's file. | Clear the output directory before retrying. | - [ ] |
| I-237 | Medium | Engine | `pipeline.py:87-103` | `_trim_audio` in the pipeline doesn't use `subprocess_run_kwargs()` — unlike the isolate version. The Windows `CREATE_NO_WINDOW` flag is missing, causing a **console window flash** on desktop when running the pipeline CLI. | Use `**subprocess_run_kwargs()` consistently. | - [ ] |

---

# Tier 4 — Low

| ID | Sev | Scope | Where | Issue | Suggested fix | Status |
|---|---|---|---|---|---|---|
| I-238 | Low | Desktop UI | `pages/isolate.py:2473` | "Refresh" button has **no tooltip** or help text. New users don't know it re-scans the disk library vs. the auto-updating fragment poll. | Add `help="Re-scan the local run library"`. | - [ ] |
| I-239 | Low | Desktop UI | `pages/isolate.py:1106; tab_pdf.py:234` | File uploader labels "Upload MP3 / WAV / FLAC / M4A" do not indicate **maximum size** or that files are saved locally. | Add a caption below the uploader with size limit and privacy note. | - [ ] |
| I-240 | Low | Desktop UI | `pages/tab_pdf.py:88-99` | "Tab title" text input has `value="Guitar Tab"` as default but **no `help` tooltip** explaining it's used as the PDF title. | Add `help="This text appears as the title on the generated tab PDF."`. | - [ ] |
| I-241 | Low | Desktop UI | `pages/isolate.py:1827-1835` | Export format help text mentions "ffmpeg" — non-technical users won't know what that is. | Rephrase as "Conversion is handled automatically" or similar. | - [ ] |
| I-242 | Low | Desktop UI | Mixed `width="stretch"` vs `use_container_width=True` | `isolate.py` uses both the modern `width="stretch"` and the deprecated `use_container_width=True` without version detection. A Streamlit upgrade could break one style. | Standardize on `width="stretch"` everywhere. | - [ ] |
| I-243 | Low | Desktop UI | `app.py:70-76` | `st.set_page_config` fallback chain ends in a bare `pass` — the page may end up with no valid page config and the user never knows. | Log a warning when page config fails. | - [ ] |
| I-244 | Low | Engine | `ingest.py:50-55` | `_YoutubeFileLogger._write()` catches `except OSError: pass` — if the log file can't be written (disk full, permissions), all yt-dlp debugging output is **lost silently**. | Log to stderr as fallback. | - [ ] |
| I-245 | Low | Engine | `separate.py:64-70` | `_write_guitar_ft_digest_sidecar()` catches `except OSError: logger.debug(...)` — sidecar write failures are debug-only. Every subsequent call re-hashes the 330 MB file unnecessarily. | Log at INFO level; consider a fallback location. | - [ ] |
| I-246 | Low | Engine | `roformer.py:272-277` | `_cap_cpu_threads()` catches `except Exception: pass` — if `recommended_cpu_threads()` fails, torch uses all cores, potentially causing poor performance on Apple Silicon with no user indication. | Log a warning. | - [ ] |
| I-247 | Low | Engine | `isolate.py:1993-1994` | `_enqueue_confirmed_job`: when `probe_duration_sec` fails, the exception is silently swallowed and `job_audio_sec = None`. User gets no warning that audio length probing failed — only job timing estimates degrade silently. | Log a warning; surface "Timing estimates unavailable" in the UI. | - [ ] |
| I-248 | Low | Engine | `ingest.py:417-454` | `normalize_audio()` hardcodes `-ar 44100 -ac 2 -sample_fmt s16` with no way to override. Files already at 44.1kHz stereo 16-bit are **re-encoded unnecessarily**. | Check format first; skip ffmpeg if already matching. | - [ ] |
| I-249 | Low | Engine | `ingest.py:213-226` | `_resolve_downloaded_wav` picks the most recent `.wav` by `st_mtime`. If yt-dlp produces multiple WAVs (e.g. from post-processing) and title match fails, the **wrong file** may be selected. | Improve matching logic; prefer exact stem matches. | - [ ] |
| I-250 | Low | Engine | `ingest.py:201-209` | `_normalize_in_place` temp file leaks if `normalize_audio` raises and the `finally` block can't unlink (Windows file lock). Orphaned `.audio_norm_*` files accumulate. | Use `TemporaryDirectory` for the temp file. | - [ ] |
| I-251 | Low | Engine | `isolate.py:619-626` | `_write_band_limited_other` temp file (`tmp_band`) may leak if the exception propagates before reaching the `finally` in `apply_fold_other_gain_search`. | Ensure the temp dir cleanup is in a top-level `try/finally`. | - [ ] |
| I-252 | Low | Engine | `separate.py:369-621` | `separate_guitar_stem` returns a `Path` but never verifies the output file **exists and is non-zero**. If all processing paths silently fail, the caller gets a path to a missing or empty file. | Add an existence/non-empty check before returning. | - [ ] |

---

# Parked — Website (on hold)

Website-only issues. Nothing here affects the desktop app; revisit if website work resumes.

## Parked · Web Frontend (React/TS) — I-300–I-336

| ID | Sev | Where | Issue | Suggested fix | Status |
|---|---|---|---|---|---|
| I-300 | High | `web/src/` (all) | **No React Error Boundary** anywhere in the app. Any uncaught rendering exception (e.g. unexpected null from API, component crash) results in a **blank white screen** with no recovery path. | Add an `ErrorBoundary` wrapping the Router with a fallback UI and "reload" button. | - [ ] |
| I-301 | High | `api.ts:145-209` | **Dual WebSocket + polling causes duplicate callbacks.** `watchJob` opens a WebSocket AND starts a polling timer simultaneously. Both run concurrently, so `onUpdate` fires twice per state change → wasteful renders and potential flicker. | Remove the redundant poll when WebSocket is connected; only start poll as fallback after WS fails. | - [ ] |
| I-302 | High | `api.ts:150-162` | **Polling never stops on permanent server failure.** The `poll` function recursively schedules itself every 2 seconds. If `getJob()` consistently throws, polling runs **forever** with no backoff, no max-retry, and no user notification. | Add exponential backoff; show "Server unreachable" after N failures. | - [ ] |
| I-303 | High | `api.ts:165-169` | **JWT passed in WebSocket URL query parameter** — lands in server access logs, browser history, proxy logs, and `Referer` header. Backend supports header fallback. | Send token via a first message after `onopen` or a subprotocol. | - [ ] |
| I-304 | High | `auth.tsx:37-39` | **Auth startup failure silently swallowed.** If `startAnonymousSession()` fails, the error is caught with `/* demo session unavailable */`. The user's email stays null and the app continues without indication. | Show a retry button or fallback UI when anonymous session fails. | - [ ] |
| I-305 | High | `components/StemMixer.tsx:26,43-77` | **AudioContext is never closed.** When the component unmounts or `stemKey` changes, cleanup calls `engine.pause()` but never `ctx.close()`. Each remount leaks an AudioContext. Browsers limit concurrent contexts (typically 6); exceeding this suspends all of them. | Add `engine.dispose()` that calls `ctx.close()`; call in cleanup effect. | - [ ] |
| I-306 | Medium | `pages/IsolatePage.tsx:609-618` | "Advanced options" `<details>` panel contains **no controls** — only a paragraph of explanatory text. Users expect toggles/sliders but find only information. This is a misnamed element. | Rename to "About advanced options" or add actual controls. | - [ ] |
| I-307 | Medium | `pages/IsolatePage.tsx:640-652` | **Clicking a completed job replaces the active running job.** If the user is watching live progress and clicks a completed job in the queue, `setJob(j)` replaces the active job, stopping live progress. No way back except clicking the running job again (if it still appears). | Preserve the active watch separately from the selected job. | - [ ] |
| I-308 | Medium | `pages/IsolatePage.tsx:248-266` | **Job list polling runs every 3 seconds unconditionally.** No backoff when idle; no `visibility API` check to pause when tab is backgrounded. Creates unnecessary network traffic. | Pause polling when tab is hidden; backoff when no active jobs. | - [ ] |
| I-309 | Medium | `components/ProcessingModeSelect.tsx:52-65; pages/IsolatePage.tsx:233-246` | **`getSystemCapabilities` fetched twice per mount** — both `ProcessingModeSelect` and `IsolatePage` independently call the API. Two independent loading/error states for the same data. | Lift the fetch to `IsolatePage` and pass data as props. | - [ ] |
| I-310 | Medium | `pages/IsolatePage.tsx:648-649` | **Job queue buttons show raw status text** — `{j.status} -- {j.message}`. No visual differentiation between job states (no color, no icons). A "failed" job looks identical to "running" except text. | Add color coding or status icons. | - [ ] |
| I-311 | Medium | `pages/IsolatePage.tsx:216-231,517` | **Dual error display for track selection.** The `resolved` memo silently falls back to defaults when `resolveTrackSelection` throws, while `pickerError` separately shows the error. User sees an error message but the form silently used different defaults — contradictory. | Surface the error in the form state, not just the message. | - [ ] |
| I-312 | Medium | `pages/TabPage.tsx:18-47; pages/IsolatePage.tsx:364-429` | **No file size validation before upload.** User could select a multi-GB file; upload consumes bandwidth and may time out with no progress indication. | Validate size client-side; show a warning before upload. | - [ ] |
| I-313 | Medium | `components/StemMixer.tsx:111` | **StemMixer loading status is plain text** — "Loading stems..." with no spinner or animation. | Add a CSS animation or spinner. | - [ ] |
| I-314 | Medium | `components/StemMixer.tsx` | **No "no stems loaded" state.** If all stems fail to load (0 out of N succeeded), the mixer UI renders fully but is completely non-functional — all stems "silent." | Show a message when 0 stems loaded successfully. | - [ ] |
| I-315 | Medium | `pages/TabPage.tsx:123` | **TabPage shows nothing when job succeeds but has no `pdf` artifact.** If backend doesn't return a `pdf` key (bug, partial failure), results section is hidden. User sees succeeded job with no files and no explanation. | Show "Job completed but no PDF was generated" with details. | - [ ] |
| I-316 | Medium | `pages/IsolatePage.tsx:621-623` | **No upload progress indicator.** Submit button changes to "Starting..." during upload + job creation. For large files this could take minutes with no progress. | Use `XMLHttpRequest` or `fetch` with upload progress tracking. | - [ ] |
| I-317 | Medium | `api.ts:86-90` | **`uploadAudio` has no AbortController or timeout.** Large file uploads can hang forever with the button stuck on "Starting...". | Add timeout and cancel support. | - [ ] |
| I-318 | Medium | `pages/IsolatePage.tsx` | **No form reset after successful job.** After download, the form remains populated with previous settings. No "Start new job" button. | Auto-reset or add a reset button. | - [ ] |
| I-319 | Medium | `components/JobProgress.tsx:36-39` | **No confirmation before cancel.** Cancel button immediately cancels with no dialog. For long-running jobs, an accidental click is unrecoverable. | Add a confirmation prompt. | - [ ] |
| I-320 | Medium | `web/src/` (all) | **No token refresh / expiration handling.** JWT is stored in `sessionStorage` and never refreshed. After expiry, all API calls return 401 with no recovery except page reload. | Implement refresh flow or auto-renew before expiry. | - [ ] |
| I-321 | Medium | `mixer/engine.ts:172-189` | **Stems loaded sequentially** in a `for` loop. 6 stems could take 6x longer than `Promise.all`. | Load stems in parallel with a concurrency pool. | - [ ] |
| I-322 | Medium | `api.ts:182-184` | **WebSocket error handler is a no-op.** `ws.onerror = () => { /* fall through to poll */ }` silently swallows errors. No user indication. | Log the error; show a connection status indicator. | - [ ] |
| I-323 | Medium | `pages/IsolatePage.tsx:251-258` | **`listJobs` polling silently ignores failures.** `.catch(() => { /* ignore */ })` — queue display freezes with stale data and no indication if API goes down. | Show "Connection lost" after consecutive failures. | - [ ] |
| I-324 | Low | `pages/LoginPage.tsx` (entire file) | **Dead code: LoginPage defined but never routed.** `App.tsx` has no `/login` route. 64 lines of unmaintained logic. | Delete the file or register the route. | - [ ] |
| I-325 | Low | `App.tsx:56` | **No 404 page.** Catch-all silently redirects to `/isolate`. If someone shares a bad link, the recipient lands on Isolate with no explanation. | Show a 404 message before redirecting. | - [ ] |
| I-326 | Low | `styles.css:12,86` | **Content width constrained to 720px.** On wide desktop monitors, content is a narrow column. StemMixer with many stems feels cramped. | Allow wider layout or make it configurable. | - [ ] |
| I-327 | Low | `styles.css` (all) | **No dark mode / `prefers-color-scheme` support.** Users who prefer dark mode see a light page with no option. | Add a dark theme or respect OS preference. | - [ ] |
| I-328 | Low | `styles.css` (all) | **No custom `focus-visible` styles.** App relies on browser defaults which may be invisible or clash with color scheme. | Add `:focus-visible` styles. | - [ ] |
| I-329 | Low | `components/StemMixer.tsx:135-145` | **Seek slider has no accessible label.** `<input type="range">` has no `aria-label` or associated `<label>`. | Add `aria-label="Seek"`. | - [ ] |
| I-330 | Low | `components/StemMixer.tsx:109` | **Mixer wrapper has no role or landmark.** `<div className="mixer">` has no `role` or `aria-label`. | Add `role="region"` and `aria-label="Mixer"`. | - [ ] |
| I-331 | Low | `index.html` | **No `<noscript>` fallback.** If JS is disabled, user sees a completely blank page. | Add `<noscript>` with a message. | - [ ] |
| I-332 | Low | `index.html` | **No SEO meta tags or Open Graph metadata.** `<title>` only. When shared on social media, link preview is generic. | Add `<meta name="description">` and OG tags. | - [ ] |
| I-333 | Low | `pages/LoginPage.tsx:8` | **Hardcoded "admin@localhost" default email.** Development artifact in dead code. | Delete with the file (I-324). | - [ ] |
| I-334 | Low | `api.ts:162,193; IsolatePage.tsx:261` | **Poll intervals are hardcoded magic numbers** (2000ms, 3000ms). No configuration. | Extract to constants; consider env var override. | - [ ] |
| I-335 | Low | `main.tsx:7` | **Non-null assertion on DOM element** `document.getElementById("root")!`. If `#root` is missing, produces unhelpful `Cannot read properties of null`. | Add a fallback message. | - [ ] |
| I-336 | Low | `components/StemMixer.tsx:115-131` | **Play/Pause buttons lack consistent aria states.** Play changes text to "Playing..." but doesn't use `aria-pressed`. Pause always says "Pause" even when nothing is playing. | Use `aria-pressed` consistently; update label dynamically. | - [ ] |

## Parked · Backend (FastAPI) — I-337–I-367

| ID | Sev | Where | Issue | Suggested fix | Status |
|---|---|---|---|---|---|
| I-337 | High | `main.py:188-192` | **Stuck jobs: in-process background tasks have no watchdog.** If the process crashes or executor hangs, jobs stay in `running`/`pending` forever. No reaper transitions stale jobs to `failed`. | Add a periodic reaper job that marks stale running jobs as failed. | - [ ] |
| I-338 | High | `backend/` (none) | **No job cleanup / TTL mechanism.** Old completed jobs, artifacts, uploads, and work directories persist forever. Database and disk grow unbounded. | Add periodic cleanup with configurable retention. | - [ ] |
| I-339 | High | `main.py:509-516,544-551` | **StreamingResponse temp file leak on client disconnect.** `tmp.unlink()` is inside the generator, not in `finally`. If client disconnects mid-stream, the temp file is orphaned. | Move cleanup into `finally` block. | - [ ] |
| I-340 | High | `main.py:291-301` | **Upload content fully buffered in memory.** With `max_upload_mb=50` and rate limit 10/min, 10 concurrent uploads = 500MB RAM. No per-request memory limit. | Stream to disk instead of buffering in memory. | - [ ] |
| I-341 | Medium | `main.py:474` | **`cancel_job` asserts after `request_cancel`** — `assert job` crashes with AssertionError if row was deleted between check and assert (TOCTOU race). | Use `if not job: raise HTTPException(404)`. | - [ ] |
| I-342 | Medium | `auth.py:40,156` | **Same secret key used for JWT and HMAC artifact signing.** If either algorithm has a weakness, both are compromised. | Derive separate keys from the secret. | - [ ] |
| I-343 | Medium | `auth.py:56-62` | **Refresh token rotation has no revocation of old tokens.** Stolen refresh token remains valid for `refresh_token_days` even after rotation. | Persist `jti`; revoke on logout and on use. | - [ ] |
| I-344 | Medium | `events.py:38-47` | **`publish_redis` creates a new Redis connection on every publish.** Under load, thousands of short-lived connections. | Reuse a module-level client. | - [ ] |
| I-345 | Medium | `main.py:180-187` | **`_enqueue_or_run` creates a new Redis pool for every job.** Wasteful; should share a pool. | Create and reuse a module-level pool. | - [ ] |
| I-346 | Medium | `main.py:203-205` | **`/v1/health` doesn't check database or Redis.** Reports healthy while DB is unreachable. | Ping DB and Redis; report degraded status. | - [ ] |
| I-347 | Medium | `jobs/manager.py:438-464` | **`set_artifacts` deletes all then re-inserts** — no atomicity. Crash between delete and commit loses all artifacts. | Use a transaction or upsert pattern. | - [ ] |
| I-348 | Medium | `main.py:560-648` | **WebSocket: no reconnection state token.** On disconnect/reconnect, client must re-fetch via snapshot. May miss events between disconnect and reconnect. | Add an event sequence number for resumption. | - [ ] |
| I-349 | Medium | `main.py:646-647` | **WebSocket `redis_task.cancel()` doesn't await.** Cancelled task's cleanup (closing Redis connection) may not complete, leaking subscriptions. | `await redis_task` after cancel. | - [ ] |
| I-350 | Medium | `main.py:602-641` | **WebSocket: no maximum connection lifetime.** Long-lived connections tie up resources indefinitely. | Add a max-lifetime and graceful close. | - [ ] |
| I-351 | Medium | `storage.py:104-111` | **S3Storage `_ensure_bucket()` silently swallows all exceptions.** If S3 is misconfigured, app starts but all storage operations fail with confusing errors later. | Log the error; raise on startup. | - [ ] |
| I-352 | Medium | `main.py:455` | **`list_jobs` limit capped at 50 with no offset/cursor pagination.** Heavy users can't access older jobs. | Add cursor-based pagination. | - [ ] |
| I-353 | Medium | `main.py:440-557` | **No rate limiting on read endpoints** (GET /jobs, /artifacts). Client could poll hundreds of times per second. | Add rate limits to read endpoints. | - [ ] |
| I-354 | Medium | `contracts.py:72` | **`two_stems` field not validated.** Any string passes through to the engine; invalid values cause deep crashes. | Validate against allowed values (enum). | - [ ] |
| I-355 | Medium | `contracts.py:86` | **`emit_stems` not validated.** Accepts any list of strings; invalid stem names pass to engine. | Validate against known stem IDs. | - [ ] |
| I-356 | Medium | `config.py:48` | **`database_url` defaults to relative path.** `sqlite:///./data/app.db` depends on working directory. | Use an absolute path or validate CWD. | - [ ] |
| I-357 | Medium | `main.py:111` | **CORS middleware logic redundancy.** `_origins if _origins != ["*"] else ["*"]` is a no-op. The intent was to strip `*` when credentials are enabled. | Fix the conditional logic. | - [ ] |
| I-358 | Low | `main.py` (none) | **No security headers** (X-Content-Type-Options, X-Frame-Options, HSTS, CSP). | Add security headers middleware. | - [ ] |
| I-359 | Low | `main.py:237` | **`create_session` returns bare 404 when demo mode is off** — no indication the endpoint exists but is disabled. | Return 403 with "Demo mode disabled" message. | - [ ] |
| I-360 | Low | `jobs/manager.py:77` | **`JobManager._local_work` is dead state.** Set on create, never read anywhere. | Remove. | - [ ] |
| I-361 | Low | `main.py:195-197` | **`_isolate_single_flight_enabled()` is dead code.** Defined but never called. | Remove. | - [ ] |
| I-362 | Low | `storage.py:80-83` | **`LocalStorage.delete()` doesn't clean empty parent dirs.** Over time, many empty directories accumulate. | Remove empty parents after delete. | - [ ] |
| I-363 | Low | `main.py:455` | **`list_jobs?limit=0` returns 1 row** instead of being rejected. | Reject `limit < 1` with 400. | - [ ] |
| I-364 | Low | `auth.py:128-140` | **`get_current_user_optional` silently ignores deleted users.** Valid JWT for deleted user returns None (same as no token). | Distinguish the two cases. | - [ ] |
| I-365 | Low | `jobs/manager.py:79-115` | **Upload written to storage before DB row commits.** If insert fails, orphaned storage file. | Insert row first, or clean up on failure. | - [ ] |
| I-366 | Low | `worker.py:32` | **`WorkerSettings.job_timeout` uses extreme 4h for every job.** Per-quality timeouts are unused. | Set per-job timeout at enqueue time. | - [ ] |
| I-367 | Low | `storage.py:66-75` | **`open_temp` loads whole object into RAM.** For large artifact WAVs (300MB+), doubles memory usage. | Stream-copy with `shutil.copyfileobj`. | - [ ] |

---

## Cross-cutting themes (desktop-first)

- **UI freeze / missing spinners (I-201, I-203, I-219):** synchronous ffmpeg and mix-building with no visual feedback. Users think the app crashed. Batch-fix all long-running render-path operations.
- **Silent engine failures (I-210, I-211, I-212, I-230, I-231):** `_stem_rms`, `probe_duration_sec`, fold-other overlap, yt-dlp cache, and tempo estimation all swallow errors silently. These hide real problems and make debugging nearly impossible.
- **Subprocess timeout gaps (I-213):** ffprobe, ffmpeg normalize, ffmpeg trim all have no timeout. A corrupted file hangs the job forever.
- **Model loading safety (I-208, I-209):** `weights_only=False` and `strict=False` mask security issues and weight mismatches. Silent garbage output.
- **Frozen-build ffmpeg (I-202):** bundled ffmpeg may not be found in the frozen app if PATH lookup fails.
- **Infinite rerun loop (I-200):** deleting a library run while it's selected breaks the page until refresh.
- **Error messages (I-204, I-205, I-206):** generic or raw exception text shown to users with no actionable guidance.
