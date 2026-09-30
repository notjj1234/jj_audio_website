# Pre-Release Demo Readiness — Design

**Date:** 2026-09-30
**Status:** Draft for review
**Target:** AudioTools 0.1.4 desktop demo (Windows + macOS), distributed via public GitHub Releases
**Audience:** friends and anyone who finds the public repo

---

## 1. Scope and intent

### 1.1 What this demo is

The PyInstaller-frozen Streamlit desktop app, downloaded as a macOS `.pkg` or a Windows
Setup `.exe` from a public GitHub Release, run locally on a friend's own machine. Isolation,
stem mixer, Tab PDF, YouTube-to-MP3.

### 1.2 In scope

- Desktop freeze and its release pipeline (`.github/workflows/desktop-release.yml`,
  `packaging/**`).
- Desktop UI (`ui/`), including the three committed iframe frontends.
- Shared engine code that the desktop ships (`src/audio_to_tab/`).
- Tester-facing documentation (`README.md`, `DESKTOP.md`).
- Test suite and the CI gates that protect the shipped artifact.

### 1.3 Explicitly out of scope

The hosted website (`backend/`, `web/`, `docker-compose*.yml`, `DEPLOY.md`) is **not**
part of this release. `AGENTS.md` already states Streamlit is absent from the hosted
stack and the freeze must not ship `backend/`/`web/`; that boundary is correct and stays.

The audit surfaced roughly 60 hosted-stack findings (rate limiting, absent DB
migrations, artifact-URL expiry, mixer memory leaks, the SPA's 90-second silent
truncation). Several are real. They are **not** release blockers for a desktop demo and
are deliberately deferred; the intent is to file them in `docs/issues.md` so they are not
lost, as a bookkeeping step at the end of Track A rather than work in this plan.

Two hosted findings do touch shared code and therefore **are** in scope, because the
desktop ships the same code:

- `web/src/mixer/engine.ts` and `ui/stem_mixer_component/frontend/src/main.ts` are two
  implementations of the same mixer contract with near-identical leak profiles. Fixing
  one and not the other would leave the desktop leaking.
- `backend/jobs/runner.py` and `src/audio_to_tab/isolate.py` share the timeout/resource
  story; the fix lands in `src/`.

### 1.4 Non-goals

No new features. No obfuscation. No code signing or notarisation (see §6.4). No
universal macOS binary. No 32-bit Windows. No new separation model.

### 1.5 Out of bounds — do not modify

**`packaging/**` is untouchable.** That means `AudioTools.iss`,
`make_windows_installer.ps1`, `make_pkg.sh`, `make_app.sh`, `bundle_ffmpeg.py`,
`macos_signing.py`, `audio_tools.spec`, and everything else under that directory.

**Both Windows installers continue to ship as separate artifacts** — the CPU build and
the NVIDIA CUDA build — exactly as `desktop-release.yml:32-53` already produces them.
Nothing in this plan collapses them into a combined `both` build, and the `both` edition
support in `src/audio_to_tab/edition.py` is left alone.

The `both` flavour currently sitting on the v0.1.4 release is an artifact of a manual
local build, not of this pipeline. The next release ships CPU + CUDA and no `both`.

If a future change seems to require touching `packaging/`, that is a signal to stop and
re-scope, not a licence to edit the installers.

### 1.6 What is in scope on the workflow side

`.github/workflows/desktop-release.yml` **is** in scope — but only to the extent of
stopping it from overriding the filenames the installer scripts choose (§4.3), and
correcting the release body text. The build matrix, the flavor set, the onedir
verification steps, and the PyInstaller invocation are all left exactly as they are.

---

## 2. The core problem

The demo is not blocked by product quality. It is blocked by **distribution** and by
**one first-click failure**.

A friend who finds this repo, opens `DESKTOP.md`, and follows the download instructions
gets a 404. Every documented download path is broken. Separately, a friend on the
Windows build with no NVIDIA GPU clicks "Separate" and gets an error banner on their
first attempt, because the app defaults to a CUDA device that does not exist on their
machine.

These two account for most of the gap between "working build on my machine" and "friend
successfully runs the demo".

---

## 3. Root causes

### 3.1 Download links: three stacked defects

Verified live against the GitHub REST API on 2026-09-30.

**Defect 1 — every release is flagged as a prerelease.**

```
v0.1.4-alpha-audio-tools   draft=False  prerelease=True   published=2026-09-20
v0.1.3-alpha-audio-tools   draft=False  prerelease=True   published=2026-09-14
v0.1.2-alpha-audio-tools   draft=False  prerelease=True   published=2026-08-29
v0.1.1-alpha-audio-tools   draft=False  prerelease=True   published=2026-08-27
v0.1.0-alpha-audio-tools   draft=False  prerelease=True   published=2026-08-24
```

GitHub's `/releases/latest/` endpoint **excludes prereleases**. Verified:

```
GET /releases/latest          -> 302, Location: /releases
GET /releases/latest/download/AudioTools-macos-arm64-silicon.pkg      -> 404
GET /releases/latest/download/AudioTools-0.1.4-windows-x64-cpu-setup.exe -> 404
GET /releases/latest/download/AudioTools-windows-x64-cpu-setup.exe     -> 404
```

**Defect 2 — the asset names in `DESKTOP.md` disagree with each other.**

| Source | Windows name | macOS name |
|---|---|---|
| `DESKTOP.md:94-95` (table) | — | `AudioTools-macos-arm64-silicon.pkg` (unversioned) |
| `DESKTOP.md:96-97` (table) | `AudioTools-0.1.4-windows-x64-cpu-setup.exe` (versioned) | — |
| `DESKTOP.md:107` (prose) + all `curl` blocks | `AudioTools-windows-x64-cpu-setup.exe` (unversioned) | unversioned |
| **Actually on the release** | `AudioTools-0.1.4-windows-x64-both-setup.exe` | `AudioTools-0.1.4-macos-*.pkg` |

Three conventions, none of them matching reality.

**Defect 3 — the workflow overwrites the installer scripts' filenames.**

Local build scripts version their output:

- `packaging/make_pkg.sh:18,20` → `AudioTools-${APP_VERSION}-macos-arm64-silicon.pkg`
- `packaging/make_windows_installer.ps1:93` → `AudioTools-$AppVersion-windows-x64-$Flavor-setup.exe`

The CI workflow discards that name and substitutes a hardcoded unversioned matrix label
(`desktop-release.yml:186` on Windows, `:193` on macOS). So the published 0.1.4 assets
were built by the **local** process, and the committed workflow would produce a
**different** set. The docs were written against the workflow's names; the release
contains the local names.

There are two naming authorities that must not both exist. §4.3 resolves this by removing
the workflow's, rather than by editing the installer scripts.

**Defect 4 (compound) — `desktop-release.yml` has never run.**

```
GET /actions/workflows/desktop-release.yml/runs -> total_count: 0
git tag -l 'desktop-v*'                          -> (empty)
```

`desktop-release.yml:16` triggers on `tags: ["desktop-v*"]`. All real tags are
`v0.1.x-alpha-audio-tools`, which match nothing. The pipeline is **completely
unvalidated** — including its own guard that checks the committed mixer bundle
(`:83-98`) and its onedir exclusion assertions (`:149-155`).

Note also that the release step is gated on the tag
(`desktop-release.yml:205`, `if: startsWith(github.ref, 'refs/tags/desktop-v')`). A
`workflow_dispatch` run builds the four artifacts but creates **no release at all** —
they land only in the Actions UI under a 14-day artifact retention (`:201`). So the
release path is the tag path, and `DESKTOP.md:103`'s claim that
"`workflow_dispatch` also produces the four artifacts without a tag" is true only in the
narrow sense that it produces no *downloadable* release.

### 3.2 The Windows CUDA default

`_both_edition_windows` (`src/audio_to_tab/hardware.py:483-486`) appends `"cuda"` to the
device options **unconditionally**, ignoring the live hardware probe:

```python
# hardware.py:501-505
gpu: list[str] = []
if _both_edition_windows(platform=platform) or (
    plat.startswith("win") and probe.cuda
):
    gpu.append("cuda")
```

Four separate sites then pick CUDA purely because the string is present, never
consulting the probe:

| Site | Code | Reached by |
|---|---|---|
| `hardware.py:525-531` `_preferred_gpu` | `if "cuda" in options: return "cuda"` | `desktop_recommend` |
| `hardware.py:602` `resolve_desktop_speed` | `gpu = "cuda" if "cuda" in options else ...` | Lite speed radio → `isolate.py:1499,2430` |
| `isolate.py:2437-2438` | `if ... not in allowed_devices: = allowed_devices[0]` | first render, seeds the **persisted** `isolate_device` key |
| `isolate.py:3696-3698` | `ensure_cuda_available(...)` → `st.error(...)` → `return` | the run gate |

Consequence on a `both`-edition install with no NVIDIA GPU:

1. `allowed_devices == ["cuda", "cpu"]`
2. `isolate.py:2438` seeds `isolate_device = "cuda"` (and `ui/isolate_state.py:2109`
   persists it across app restarts)
3. User clicks Separate
4. `ensure_cuda_available("cuda", probe)` → `probe.cuda` is False → `RuntimeError`
5. `isolate.py:3697` renders the red "NVIDIA CUDA is not available" banner and returns

The user must discover the device dropdown and manually select CPU. Lite mode
self-corrects because it re-probes at submit (`isolate.py:2440-2450`); **Pro does not.**

The same defect affects the `cuda`-only edition far worse: `desktop_device_options`
returns `["cuda"]` (`hardware.py:499-500`) with no CPU option at all, so there is no
escape hatch — yet `packaging/AudioTools.iss:187` tells the user:

> You can still install. Without NVIDIA hardware, Audio Isolation will run on CPU
> (same as the smaller CPU Setup).

That is false for the CUDA-only build. Fixing it is a prerequisite to shipping that
flavor, which is why Fork 1 (§7.1) prefers CPU-only as the default download.

**A test documents the options half of this, and stays valid.**
`tests/test_hardware.py:144-147`:

```python
def test_both_edition_windows_device_options_gpu_first(monkeypatch):
    monkeypatch.setenv("AUDIO_TOOLS_EDITION", "both")
    assert desktop_device_options(CPU_MID, platform="win32") == ["cuda", "cpu"]
```

That test asserts the *offered options* on a CPU-only probe, and it continues to hold:
`desktop_device_options` is deliberately **not** changed, because a friend who does have
an NVIDIA GPU must still be able to select CUDA by hand. What changes is only the
**default**. The missing coverage is on `desktop_recommend` and `resolve_desktop_speed`,
which is where the four unconditional `"cuda" in options` checks live.

### 3.3 The uncommitted baseline

`git status` shows 14 modified files, 2 deleted, 2 untracked — **+1313 / −270** lines,
spanning the mixer video-resize work, the mixer wake-policy fix, `ingest.py`, and
`ui/isolate_state.py`.

The committed mixer bundle is mid-swap:

```
D  build/assets/index-DTQQgzxu.css
D  build/assets/index-wVmHbnf8.js
M  build/index.html
?? build/assets/index-C2MVm22X.css
?? build/assets/index-WQFJj3jX.js
```

**Current on-disk state is self-consistent** — `build/index.html` references
`index-WQFJj3jX.js` and `index-C2MVm22X.css`, and both exist. `HEAD` is also
self-consistent. Neither is broken.

The risk is procedural: `git commit -a` and `git add -u` stage the deletions and the
`index.html` edit but **not** the new untracked assets. The result is an `index.html`
pointing at two files that do not exist in the commit — a blank mixer iframe, failing
silently at runtime. `AGENTS.md` requires the hashed output to be committed; the fix is
`git add -A` scoped to that directory, verified by the check at
`desktop-release.yml:83-98` once the workflow runs.

### 3.4 Disk exhaustion

`ui/isolate_jobs.py` deletes a job folder only on explicit cancel (`:448`) or
`remove_job` (`:550`). There is no age, count, or size sweep. Each job retains, per
`isolate.py:2489-2532`: `checkpoint/trimmed.wav`, a full `demucs_out/` stem copy,
`guitar.wav`, and `work/normalized*.wav` — on the order of 1 GB.

In the frozen app `DATA_DIR` resolves to `<app>/_internal/data/ui_runs`
(`ui/common.py:28`), so `isolate_jobs/` accumulates on the **install volume**, not a
scratch dir. A friend running a handful of songs fills their disk, at which point every
subsequent job fails with an opaque error and there is no in-app way to reclaim space.
This is the most likely "it worked yesterday" failure and it is invisible until it is
fatal.

### 3.5 Untested flagship path

797 tests collect cleanly across 32 files. None exercise **isolate → mixer → export**
as a sequence. `test_mixer.py` covers mixdown math, `test_desktop_export.py` covers
saving, `test_isolate.py` covers separation — but a regression at any hand-off (stem
filenames, sample rates, path layout, mixer manifest keys) passes CI and breaks the
demo on a stranger's machine.

Separately, `ci.yml:49` installs `.[dev,demucs]` while the freeze requires
`.[demucs,desktop,roformer,separator]` (`desktop-release.yml:106,123`). The exact
dependency surface that ships is never exercised by a gate.

### 3.6 Correctness defects in shipped code

| Defect | Location | Impact |
|---|---|---|
| guitar-FT is unrequestable | `separate.py:582-586` raises when weights are uncached, but the only downloader (`:123`) is called at `:220` — after the guard. `GUITAR_FT_CACHE_HINT` (`:35`) tells the user to run a CLI flag that hits the same guard. | Ticking the option hard-fails with no recovery, for a 330 MB model the code can already download. |
| Structured tab PDF drops half its measures | `pdf_render.py:93,117` lays out 2 × 4.5in + 0.2in gap = 9.2in on 7.3in of usable letter width | Measures 2, 4, 6 … render off-page. Every structured PDF, silently. |
| Metronome failures swallowed | `isolate.py:2703-2724` catches all metronome-stage exceptions at debug level | The job reports success with no metronome output and no warning. |
| Timeout cannot kill Demucs; models never released | `separate.py`/`roformer.py`/`scnet.py` never `del` models or call `torch.cuda.empty_cache()` | A long-lived host degrades across jobs; a timed-out job keeps burning CPU. |
| Tab PDF has no cancel or timeout | `ui/pages/tab_pdf.py:360-366` calls `run_pipeline` synchronously | Blocks the script thread with no escape for the length of the conversion. |
| Metronome decodes float64, uncapped | `metronome.py:1136` `sf.read(..., always_2d=True)` on the full file, on every job (`emit_metronome` defaults True) | A 5-minute track costs ~211 MB resident, in-process, on every isolation. |
| `lead_rhythm` ignores its own window cap on two paths | `lead_rhythm.py:308,407` load the full file where `:465,516` truncate to `ANALYZE_WINDOW_SEC` | Full-track STFT on the mild-pan path. |

---

## 4. Decisions

### 4.1 Two-track sequencing

Track A makes the demo physically possible; Track B fixes root causes. Track A is
completed and verified before Track B begins, so a working demo exists at every moment
rather than after one large risky change.

Rejected alternatives:

- *Triage only* — fix blockers, defer everything else to a backlog. With no deadline
  this only defers work that was going to happen anyway, and leaves the 1.9 GB installer
  and 404 links in place.
- *Single big-bang pass* — everything at once. Maximises the window where the demo is
  broken, for no benefit when there is no deadline.

### 4.2 Tag-pinned download URLs, plus a non-prerelease release

`DESKTOP.md` download URLs become **tag-pinned**:

```
https://github.com/notjj1234/jj_audio_website/releases/download/desktop-v0.1.4/AudioTools-0.1.4-macos-arm64-silicon.pkg
```

Tag-pinned URLs are deterministic and immune to the prerelease/draft semantics that
broke `/releases/latest/`. They survive a release being marked draft-then-published, and
they do not silently point at a different artifact after the next release. The cost is
that they need updating each release, which is a one-line change in one file.

Additionally, the release is published as **not-a-prerelease** so that
`/releases/latest/` also resolves as a convenience for anyone who lands on the repo
root.

### 4.3 The installer scripts stay the single source of truth for filenames

**`packaging/**` is not modified. Not the Inno Setup script, not the PowerShell or shell
packagers, not the PyInstaller spec.** Both Windows installers (CPU and NVIDIA) continue
to ship as separate artifacts, as they already do.

The workflow is currently *discarding* the versioned filename that the installer scripts
already produce, then hardcoding an unversioned one of its own:

- `desktop-release.yml:186` (Windows) — `make_windows_installer.ps1` writes
  `dist/AudioTools-$version-windows-x64-$edition-setup.exe`, then
  `Copy-Item … -Destination ${{ matrix.artifact }}` renames it to the unversioned label.
- `desktop-release.yml:193` (macOS) — `AUDIO_TOOLS_PKG_NAME="${{ matrix.artifact }}"`
  overrides the script's own default from `make_pkg.sh:18,20`.

The fix is to **stop the override**, not to change either script:

1. Drop the `Copy-Item` rename on Windows; upload the file the script produced.
2. Drop `AUDIO_TOOLS_PKG_NAME` on macOS; let `make_pkg.sh:18,20` choose its own name.
3. Keep `matrix.artifact` only as the `actions/upload-artifact` **artifact** identifier,
   which must stay unique per matrix job for Actions bookkeeping. Because the release job
   uploads `release-assets/**/*` and GitHub derives each release asset's name from the
   **filename**, not from the Actions artifact name, the user-visible asset names are the
   script-generated versioned ones:

   ```
   AudioTools-0.1.4-windows-x64-cpu-setup.exe
   AudioTools-0.1.4-windows-x64-cuda-setup.exe
   AudioTools-0.1.4-macos-arm64-silicon.pkg
   AudioTools-0.1.4-macos-x64-intel.pkg
   ```

This removes the duplicate naming logic rather than adding a third convention, and it
means the local build and CI can never drift again — there is only one place that names a
file.

The workflow's **release body** (`:213-231`) hardcodes the unversioned names in its "pick
one file for your machine" instructions. Those strings are corrected to match the assets
uploaded beside them; otherwise the release notes contradict their own attachments.

### 4.4 Probe-aware GPU selection, in one helper

Rather than patching four call sites independently, `_preferred_gpu` gains a `probe`
parameter and becomes the single decision point; the other three sites route through it.

```python
def _preferred_gpu(options: list[str], probe: HostProbe | None = None) -> str:
    if "cuda" in options and (probe is None or probe.cuda):
        return "cuda"
    if "mps" in options and (probe is None or probe.mps):
        return "mps"
    return "cpu"
```

`probe=None` preserves today's behaviour for callers that genuinely have no probe. The
`cuda`-only edition is unaffected: `desktop_device_options` short-circuits at
`hardware.py:499-500` before `_both_edition_windows` is consulted, and the run gate at
`isolate.py:3696` keeps its `ensure_cuda_available` guard as the last line of defence.

`desktop_device_options` **keeps** offering `cuda` on the `both` edition regardless of
probe — a friend who has an NVIDIA GPU should still be able to select it manually, and
the installer explicitly ships CUDA torch there. Only the *default* changes.

### 4.5 Prune by age and count, with a visible affordance

`ui/isolate_jobs.py` gains a sweep, reusing the existing `remove_job(job_id) -> bool`
primitive (`ui/isolate_jobs.py:550`, already covered by `tests/test_isolate_jobs.py:219`).
The sweep selects candidates and delegates deletion, so the destructive path stays in
one tested place.

Concrete defaults, sized against the ~1 GB per job measured in §3.4:

| Constant | Value | Rationale |
|---|---|---|
| `_JOB_RETENTION_SEC` | `7 × 86400` | a week of history is plenty for a demo |
| `_JOB_MAX_KEPT` | `10` | ~10 GB ceiling, comfortable on any laptop |
| sweep trigger | app start, and after each job reaches a terminal state | — |

Selection rules, in order:

1. Never prune a job that is queued or running.
2. Keep the most recent `_JOB_MAX_KEPT` jobs by creation time regardless of age.
3. Among the rest, prune any older than `_JOB_RETENTION_SEC`.

Deletion failures are logged and skipped, never raised — a locked file on Windows must
not break app start.

Retention lives in module constants, not UI controls. A demo does not need a settings
surface for this, and a silent sweep with a log line is the right amount of ceremony.

### 4.6 One integration test for the flagship path

A single test drives a small generated fixture through the real sequence — separate →
build mixer manifest → export — and asserts the hand-offs (filenames, sample rate, channel
layout, manifest keys) that no existing test covers. It uses mocked separation, matching
the existing convention in `tests/test_isolate.py`, so it runs in CI without weights.

### 4.7 CI gains a web job and an aligned install profile

`ci.yml` gains a `web` job running `npm ci && npm test && npx tsc --noEmit`, and its
Python install profile is aligned to what the freeze actually requires
(`roformer` + `separator` included). Without this, 21 passing Vitest tests and 8 latent
type errors in `web/` are both invisible to every gate.

### 4.8 Correctness fixes land in `src/`, verified by unit tests

Each §3.6 defect gets a focused unit test that fails before the fix. These are small,
localised changes; none alters a public API.

---

## 5. Work breakdown

### Track A — ship blockers

Ordering matters: A4 must precede A3, because the workflow creates a **draft** release
(`desktop-release.yml:216`) which `/releases/latest/` cannot see until published.

| ID | Work | Files | Done when |
|---|---|---|---|
| A6 | Commit the baseline with `git add -A`; confirm bundle consistency | `ui/stem_mixer_component/frontend/build/**` | committed `index.html` references only committed assets |
| A5 | Probe-aware GPU default (§4.4) | `hardware.py:519-525,550,602`, `ui/isolate_state.py`, `isolate.py:2437-2438` | `both` + CPU-only probe selects `cpu`; `desktop_device_options` unchanged |
| A2 | Stop the workflow renaming/overriding installer filenames; align the release body (§4.3) | `desktop-release.yml:181-198,213-231` | release asset names equal the filenames `make_windows_installer.ps1` / `make_pkg.sh` produce |
| A4 | Push a `desktop-v0.1.4` tag; let the workflow run end to end | `.github/workflows/desktop-release.yml` | run count ≥ 1, all four matrix jobs green, draft release created |
| A3 | **Publish** the draft release; leave `prerelease` false | GitHub release settings | `/releases/latest` resolves to it (200, not a 302) |
| A1 | Correct all download names and URLs; pin to tag; fix the signing claim | `DESKTOP.md:88-140` | every `curl -fL` returns 200 |

A6 and A5 are code-and-commit work and come first; A2/A4/A3/A1 are the release mechanics
that depend on them, because the docs can only be written against assets that exist.

**Requires explicit approval before any commit or push.** Nothing in this document is
committed automatically.

**Track A is the scope of the implementation plan.** Track B is sequenced into
follow-up plans, one per group, so that no single plan is large enough to risk the
working demo.

### Track B — root causes

| ID | Work | Files | Priority |
|---|---|---|---|
| B1 | Job-folder pruning sweep (§4.5), reusing `remove_job` | `ui/isolate_jobs.py` | 1 |
| B2 | Integration test: isolate → mixer → export (§4.6) | `tests/` | 1 |
| B3 | CI web job + aligned install profile (§4.7) | `ci.yml` | 1 |
| B4 | guitar-FT: let the guard download, or hide the option | `separate.py:123,220,582-586`, `:35` | 2 |
| B5 | PDF two-measures-per-row overflow | `pdf_render.py:93,117` | 2 |
| B6 | Metronome float32 + duration cap | `metronome.py:1136` | 2 |
| B7 | Release models after each job; make timeouts kill the work | `separate.py`, `roformer.py`, `scnet.py`, `isolate.py` | 2 |
| B8 | Cancel/timeout for desktop Tab PDF | `ui/pages/tab_pdf.py:360-366` | 2 |
| B9 | Metronome failures surface as warnings, not debug | `isolate.py:2703-2724` | 2 |
| B10 | `lead_rhythm` window cap on the spatial/midside paths | `lead_rhythm.py:308,407` | 3 |
| B11 | Mixer `dispose()`; close AudioContext; drop wake hooks on unmount | `ui/.../main.ts`, `web/src/mixer/engine.ts` | 3 |

B11 touches the website too, so it is scheduled after the desktop release rather than
with it.

### Track C — hygiene

Dependabot is missing `ui/region_picker_component/frontend` and
`ui/mix_tabs_component/frontend`. `README.md:72` documents a `both` build the workflow
will not produce. `DESKTOP.md:99` claims CI artifacts are signed — they are not
(`desktop-release.yml:2-3`). `web/package.json` and all three component
`package.json` files say `0.1.0` while the project is `0.1.4`. Git history is 92 MB, 73%
of it committed `node_modules`; if the repo is going public, `git filter-repo` is worth a
quiet moment. None of this blocks the demo.

---

## 6. Verification

### 6.1 Track A gate — all must pass before announcing the release

1. `curl -fL -o /dev/null <each of the four URLs in DESKTOP.md>` → HTTP 200
2. `GET /releases/latest` → 200 (not a 302 to `/releases`)
3. `desktop-release.yml` run count ≥ 1, all four matrix jobs green
4. Each asset name in the release matches `DESKTOP.md` byte for byte
5. Unit test: `both` edition + `CPU_MID` probe → `desktop_recommend` device `cpu`
6. Unit test: `both` edition + `CUDA_HIGH` probe → device `cuda` (no regression)
7. `git ls-files` shows the committed mixer `index.html` referencing only committed assets
8. Full suite green: `.venv311/bin/python -m pytest tests/ -q`
9. `ruff check src/audio_to_tab` clean

### 6.2 Manual smoke test, per platform

On a machine with **no NVIDIA GPU**, which is the common friend configuration:

- App launches; the recommended device reads CPU, not CUDA.
- Separate a ≤90 s clip end to end; stems appear; mixer plays; export succeeds.
- Repeat for Tab PDF and YouTube-to-MP3.
- Confirm disk usage after three jobs is bounded (validates B1).

On an NVIDIA machine, confirm the device defaults to CUDA and still completes.

### 6.3 Explicitly not verified by static analysis

Whether the current suite and lint pass — not run during design, since this pass made no
code changes. Whether clean-machine first-run behaves acceptably with no model weights
cached. Actual Gatekeeper and SmartScreen prompts. Install and uninstall flows. Whether
friends currently obtain the app by some route other than `DESKTOP.md`; if so, A1 is less
urgent than A5, though the repo is public so the broken links remain the first thing a new
visitor encounters.

### 6.4 Accepted for this demo

Unsigned artifacts. `desktop-release.yml:2-3` states plainly that no signing or
notarisation occurs, and every macOS tester will need `xattr -cr` + `sudo installer` or
right-click → Open. `DESKTOP.md:99` currently claims otherwise and is corrected in A1.
Gatekeeper friction is documented rather than solved; obtaining an Apple Developer ID is a
separate project with real cost.

---

## 7. Open decisions — flagged, not blocking

**7.1 Windows flavours — resolved, both ship.** Both the CPU and the NVIDIA CUDA
installers are required and both are produced by the existing matrix
(`desktop-release.yml:32-53`). The only open question was whether to keep the 1.9 GB
`both` flavour as a headline option; **it is dropped** (§1.5), since it duplicates the
two real installers at four times the size. Testers are pointed at CPU or CUDA by
whether their machine has an NVIDIA GPU.

**7.2 Release mechanics.** Fix the docs to match the local build, or make the local build
match the committed workflow? *Resolution: neither script is edited.* The workflow stops
overriding the filenames the installer scripts already produce (§4.3), then one real
`desktop-v0.1.4` release is cut so the pipeline is proven and the docs have a single
source of truth.

Both decisions are made as recommended and can be overruled without invalidating the rest
of this document.

---

## 8. Definition of done

The demo is pre-release ready when:

- The release publishes **four** artifacts: Windows CPU, Windows NVIDIA CUDA, macOS
  Apple Silicon, macOS Intel — with no combined `both` build.
- Every asset filename on the release is byte-identical to what
  `make_windows_installer.ps1` / `make_pkg.sh` produce locally, and `packaging/**` has
  zero diff against its committed state.
- A friend can reach the public repo, read `DESKTOP.md`, download a matching installer,
  install it, and launch it — on Windows and macOS, Intel and Apple Silicon.
- On a machine with no NVIDIA GPU, the first click of Separate succeeds.
- Three consecutive isolation jobs complete without the disk filling.
- Isolation, the stem mixer, Tab PDF, and YouTube-to-MP3 each work end to end from the
  frozen build.
- `pytest tests/ -q`, `ruff check src/audio_to_tab`, `npm test`, and `tsc --noEmit` are
  all green in CI, on a matrix that matches what actually ships.
- Every §3.6 correctness defect has a regression test that failed before its fix.
