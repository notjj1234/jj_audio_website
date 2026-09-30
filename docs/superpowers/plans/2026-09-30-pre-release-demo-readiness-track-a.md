# Pre-Release Demo Readiness — Track A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the AudioTools 0.1.4 desktop demo reachable and usable by a friend — working download links, both Windows installers shipping, and a first click of "Separate" that succeeds on a machine with no NVIDIA GPU.

**Architecture:** Three independent fixes. (1) `hardware.py` gains one probe-aware GPU decision helper that every recommendation path routes through, so a CUDA string present in the *offered options* no longer implies a CUDA *default*. (2) A pure `default_isolate_device()` helper in `ui/isolate_state.py` seeds the persisted device session key from the recommendation instead of positional order. (3) The CI release workflow stops renaming installer artifacts, making `packaging/make_windows_installer.ps1` and `packaging/make_pkg.sh` the single naming authority. Documentation is then corrected against assets that actually exist.

**Tech Stack:** Python 3.11 (`audio_to_tab.hardware`, `ui.isolate_state`), pytest, GitHub Actions YAML, Streamlit.

**Spec:** `docs/superpowers/specs/2026-09-30-pre-release-demo-readiness-design.md` — the plan argues from the spec, so the spec travels with it; executors read both.

## Global Constraints

- **`packaging/**` MUST NOT be modified.** Not `AudioTools.iss`, `make_windows_installer.ps1`, `make_pkg.sh`, `make_app.sh`, `bundle_ffmpeg.py`, `macos_signing.py`, `audio_tools.spec`. Task 4's verification gate is `git diff --stat -- packaging/` returning empty.
- **Both Windows installers ship** — CPU and NVIDIA CUDA — as `desktop-release.yml:32-53` already produces them. No combined `both` flavour is added.
- **No commit and no push without explicit human approval.** Tasks 1 and 6 are approval gates. Stop and ask.
- Test command: `.venv311/bin/python -m pytest tests/ -q` (POSIX). Windows equivalent: `.\.venv311\Scripts\python.exe -m pytest tests/ -q`.
- Lint command: `.venv311/bin/python -m ruff check src/audio_to_tab`. CI lints **only** `src/audio_to_tab` — not `ui/`, `backend/`, or `web/`.
- Python 3.10–3.12; target `py310`. Use `from __future__ import annotations` style already present in the modules touched.
- The mixer iframe bundle hash is content-derived. Any edit to `ui/stem_mixer_component/frontend/src/` requires `make mixer-build` and committing the rebuilt `build/` output.

---

### Task 1: Verify the existing baseline

**The dirty-baseline premise of this plan is obsolete.** An earlier draft assumed 14 modified
/ 2 deleted / 2 untracked files needing a baseline commit. That work is already committed —
`HEAD` is `8df2fa6`, `git status` is clean apart from the untracked `docs/superpowers/`
planning docs, and the mixer bundle's hashed assets are already tracked. There is nothing
to stage and **no baseline commit to make**.

What remains is verification: confirm the committed tree is internally consistent and
establish the true test baseline before any task below changes code.

**Files:**
- Inspect: `ui/stem_mixer_component/frontend/build/index.html`
- Inspect: `ui/stem_mixer_component/frontend/build/assets/`
- Do NOT stage or commit `docs/superpowers/` — local planning artifacts, not product code.

**Interfaces:**
- Consumes: nothing.
- Produces: a verified green baseline and a known-good test invocation. Every later task
  and Task 6's tag build on this.

- [ ] **Step 1: Confirm the working tree state**

```bash
git status --porcelain
git log --oneline -1
```

Expected — only the planning docs untracked, nothing else:

```
?? docs/superpowers/
```

**If any product file appears as modified, stop and report it to the human.**

- [ ] **Step 2: Confirm the bundle is tracked and self-consistent**

```bash
git ls-files ui/stem_mixer_component/frontend/build/assets/
for f in $(grep -o 'assets/[^"]*' ui/stem_mixer_component/frontend/build/index.html); do
  test -f "ui/stem_mixer_component/frontend/build/$f" && echo "OK   $f" || echo "MISS $f"
done
```

Expected: the hashed assets (`index-WQFJj3jX.js`, `index-C2MVm22X.css`, plus the
Satoshi fonts) appear in `git ls-files`, and both `index.html` references report `OK`.
If a referenced asset is `MISS` or untracked, the mixer iframe renders blank on first run —
stop and report.

- [ ] **Step 3: Run the Python suite with the correct invocation**

```bash
PYTHONPATH=src .venv311/bin/python -m pytest tests/ -q 2>&1 | tail -20
```

`PYTHONPATH=src` is **required**. `tests/conftest.py` injects `src/` into `sys.path` for
in-process tests, but `tests/test_cli_smoke.py` shells out via `subprocess.run`, which does
not inherit that injection. Omitting it produces **5 spurious
`test_cli_help_exits_zero[...]` failures** (`ModuleNotFoundError: No module named
'audio_to_tab'`) that are environment noise, not product defects. This matches the
`PYTHONPATH=src;.` that `scripts/dev.ps1 test` sets on Windows.

Use the `.venv311` interpreter, not system `python3` — system Python here is 3.13, and
Basic Pitch requires <3.13.

Expected: **795 passed, 1 skipped, 1 failed** (797 collected). The single failure is the
stale assertion handled in Step 6. Record the actual counts in your report — the spec
could not verify this (§6.3).

- [ ] **Step 4: Run the web test suite**

```bash
cd web && npm test 2>&1 | tail -20
```

Expected: 21 passing tests across 3 files. `jsdom` may emit
`Not implemented: HTMLMediaElement.prototype.play` on stderr — that is pre-existing noise,
not a failure. `cd ..` afterwards.

- [ ] **Step 5: Run lint**

```bash
.venv311/bin/python -m ruff check src/audio_to_tab
```

Expected: `All checks passed!` (CI lints only `src/`, not `ui/`, `backend/`, or `web/`.)

- [ ] **Step 6: Fix the one stale test assertion**

`tests/test_isolate_state.py:824` asserts the literal string
`_enqueue_confirmed_job(choice, audio_path)` appears inside the `_render_new_workspace`
region of `ui/pages/isolate.py`. It does not, because that call was moved behind a new
indirection:

- `ui/pages/isolate.py:4240` `_try_enqueue_choice(choice)` — validates the choice, resolves
  the audio path, then calls `_enqueue_confirmed_job(choice, audio_path)` at `:4258`.
- `ui/pages/isolate.py:4292` — the "Separate tracks" button now calls `_try_enqueue_choice`.

**The product code is correct** — the validated behaviour the test cared about is
preserved through the indirection, and `tests/test_isolate_state.py:1376` already asserts
the new call site. Only the `:824` assertion is stale.

Update that one assertion to match the current call site, leaving the rest of the test
untouched:

```python
    assert "_try_enqueue_choice(choice)" in new_ws
```

Re-run to confirm green:

```bash
PYTHONPATH=src .venv311/bin/python -m pytest tests/test_isolate_state.py -q 2>&1 | tail -5
```

Expected: all pass.

- [ ] **Step 7: Re-run the full suite and lint to confirm a green baseline**

```bash
PYTHONPATH=src .venv311/bin/python -m pytest tests/ -q 2>&1 | tail -5
.venv311/bin/python -m ruff check src/audio_to_tab
```

Expected: `795 passed, 1 skipped` (796 collected after no tests are added or removed) and
`All checks passed!`. **This is the gate** — do not begin Task 2 until the baseline is
green.

- [ ] **Step 8: Confirm `packaging/` is untouched**

```bash
git status --porcelain -- packaging/ && git diff --stat -- packaging/
```

Expected: empty output. `packaging/**` is off-limits for this entire plan.

---

### Task 2: Probe-aware GPU selection in `hardware.py`

Four sites pick CUDA purely because the string `"cuda"` is present in the offered
options, never consulting the live hardware probe. On a Windows machine with no NVIDIA
GPU this makes the app default to a device that does not exist, and the first click of
Separate shows an error banner. This task adds one probe-aware helper and routes all four
call sites through it.

`desktop_device_options` is deliberately **not** changed — a friend who does have an
NVIDIA GPU must still be able to select CUDA by hand.

**Files:**
- Modify: `src/audio_to_tab/hardware.py:519-525` (`_preferred_gpu`)
- Modify: `src/audio_to_tab/hardware.py:550` (`desktop_recommend` call site)
- Modify: `src/audio_to_tab/hardware.py:602` (`resolve_desktop_speed` call site)
- Test: `tests/test_hardware.py`

**Interfaces:**
- Consumes: `HostProbe` (fields `.cuda: bool`, `.mps: bool`, `.ram_gb: float | None`), already imported in `tests/test_hardware.py`.
- Produces: `_preferred_gpu(options: Sequence[str], probe: HostProbe | None = None) -> str`. When `probe` is `None`, behaviour is unchanged. When `probe` is given, `"cuda"` is only returned if `probe.cuda` is true, and `"mps"` only if `probe.mps` is true; otherwise `"cpu"`. Task 3 relies on `desktop_recommend` and `resolve_desktop_speed` honouring the probe.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_hardware.py`. Fixtures `CPU_MID`, `CUDA_HIGH`, `MPS_MAC` already
exist at lines 40-44; the autouse `_cpu_edition_by_default` fixture at :47 clears
`AUDIO_TOOLS_EDITION`.

```python
def test_both_edition_recommends_cpu_when_no_nvidia_gpu(monkeypatch):
    """A friend with no NVIDIA GPU must not default to CUDA on the both edition."""
    monkeypatch.setenv("AUDIO_TOOLS_EDITION", "both")
    rec = desktop_recommend(CPU_MID, platform="win32")
    assert rec["device"] == "cpu"


def test_both_edition_still_recommends_cuda_with_nvidia_gpu(monkeypatch):
    monkeypatch.setenv("AUDIO_TOOLS_EDITION", "both")
    rec = desktop_recommend(CUDA_HIGH, platform="win32")
    assert rec["device"] == "cuda"


def test_both_edition_faster_speed_uses_cpu_when_no_nvidia_gpu(monkeypatch):
    monkeypatch.setenv("AUDIO_TOOLS_EDITION", "both")
    resolved = resolve_desktop_speed("faster", CPU_MID, platform="win32")
    assert resolved["device"] == "cpu"


def test_both_edition_balanced_speed_uses_cpu_when_no_nvidia_gpu(monkeypatch):
    monkeypatch.setenv("AUDIO_TOOLS_EDITION", "both")
    resolved = resolve_desktop_speed("balanced", CPU_MID, platform="win32")
    assert resolved["device"] == "cpu"


def test_both_edition_offers_cuda_even_without_gpu(monkeypatch):
    """Options are unchanged: a real NVIDIA GPU user can still pick CUDA by hand."""
    monkeypatch.setenv("AUDIO_TOOLS_EDITION", "both")
    assert desktop_device_options(CPU_MID, platform="win32") == ["cuda", "cpu"]


def test_low_ram_both_edition_without_gpu_recommends_cpu(monkeypatch):
    monkeypatch.setenv("AUDIO_TOOLS_EDITION", "both")
    rec = desktop_recommend(CPU_LOW, platform="win32")
    assert rec["device"] == "cpu"
    assert rec["quality"] == "fast"
```

Also add `CPU_LOW = HostProbe(cuda=False, mps=False, ram_gb=6.0)` — check whether it
already exists near line 40 and add it only if missing.

- [ ] **Step 2: Run the new tests and confirm they fail**

```bash
.venv311/bin/python -m pytest tests/test_hardware.py -k "both_edition or low_ram_both" -v
```

Expected: the four `_device == "cpu"` assertions **FAIL** with `assert 'cuda' == 'cpu'`.
The two "still offers cuda" / "still recommends cuda with gpu" tests **PASS**.

- [ ] **Step 3: Make `_preferred_gpu` probe-aware**

Replace `src/audio_to_tab/hardware.py:519-525`:

```python
def _preferred_gpu(options: list[str], probe: HostProbe | None = None) -> str:
    """First usable GPU id in ``options``, else ``cpu``.

    When ``probe`` is supplied, an accelerator is only selected if the host actually
    reports it. Without a probe the old behaviour is kept: the first GPU id listed wins.
    """
    if "cuda" in options and (probe is None or probe.cuda):
        return "cuda"
    if "mps" in options and (probe is None or probe.mps):
        return "mps"
    return "cpu"
```

- [ ] **Step 4: Pass the probe at the `desktop_recommend` call site**

Change `src/audio_to_tab/hardware.py:550` from:

```python
    gpu_dev = _preferred_gpu(options)
```

to:

```python
    gpu_dev = _preferred_gpu(options, probe)
```

- [ ] **Step 5: Route `resolve_desktop_speed` through the same helper**

Change `src/audio_to_tab/hardware.py:602` from:

```python
    gpu = "cuda" if "cuda" in options else ("mps" if "mps" in options else "cpu")
```

to:

```python
    gpu = _preferred_gpu(options, probe)
```

- [ ] **Step 6: Run the new tests and confirm they pass**

```bash
.venv311/bin/python -m pytest tests/test_hardware.py -v
```

Expected: all pass, including the pre-existing `test_both_edition_windows_device_options_gpu_first`
(options are unchanged) and `test_resolve_faster_uses_cuda_on_both_edition` (uses
`CUDA_HIGH`, so still cuda).

- [ ] **Step 7: Run the full suite and lint**

```bash
.venv311/bin/python -m pytest tests/ -q 2>&1 | tail -15
.venv311/bin/python -m ruff check src/audio_to_tab
```

Expected: suite passes, ruff `All checks passed!`.

- [ ] **Step 8: Commit**

**Do not commit.** The human has stated explicitly that nothing in this repository is to
be committed or pushed to GitHub. Leave the change in the working tree and report it.

```bash
git status --porcelain -- src/audio_to_tab/hardware.py tests/test_hardware.py
```

Expected: the paths above modified, uncommitted. Do not run `git add`, `git commit`,
`git push`, or `git tag`.

---

### Task 3: Seed the persisted device session key from the recommendation

`ui/pages/isolate.py:2437-2438` seeds the `isolate_device` session key — which is
**persisted to disk** (`ui/isolate_state.py:2109`) — from `allowed_devices[0]`, i.e.
positional order. On the `both` edition that is `"cuda"` regardless of hardware, so Task 2
alone is not enough: the UI re-seeds the bad default.

The logic lives inside a large Streamlit render function and cannot be unit-tested where
it sits. Following the existing pattern (`ui/isolate_state.py` is the module of pure,
well-tested helpers, and already imports from `audio_to_tab.hardware` at line 18), extract
a pure helper there and call it.

**Files:**
- Modify: `ui/isolate_state.py` — add `default_isolate_device()` after `resolve_speed_preset` (which ends at line 725)
- Modify: `ui/pages/isolate.py:2437-2438` — call the helper
- Test: `tests/test_isolate_state.py`

**Interfaces:**
- Consumes: `default_isolate_device` depends on `desktop_recommend(probe, platform=None)` from `audio_to_tab.hardware` — add it to the existing import at `ui/isolate_state.py:18`.
- Produces: `default_isolate_device(probe, allowed_devices: Sequence[str], current: str | None = None, *, platform: str | None = None) -> str`. Returns `current` unchanged when it is in `allowed_devices` (respects the persisted choice); otherwise the recommended device when that is in `allowed_devices`; otherwise `allowed_devices[0]`. Returns `current` when `allowed_devices` is empty.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_isolate_state.py`:

```python
def test_default_isolate_device_prefers_recommendation_over_position(monkeypatch):
    from audio_to_tab.hardware import HostProbe

    monkeypatch.setenv("AUDIO_TOOLS_EDITION", "both")
    cpu_only = HostProbe(cuda=False, mps=False, ram_gb=12.0)
    assert default_isolate_device(cpu_only, ["cuda", "cpu"], None, platform="win32") == "cpu"


def test_default_isolate_device_keeps_persisted_choice(monkeypatch):
    from audio_to_tab.hardware import HostProbe

    monkeypatch.setenv("AUDIO_TOOLS_EDITION", "both")
    cpu_only = HostProbe(cuda=False, mps=False, ram_gb=12.0)
    assert default_isolate_device(cpu_only, ["cuda", "cpu"], "cpu", platform="win32") == "cpu"


def test_default_isolate_device_respects_stale_persisted_choice(monkeypatch):
    """A persisted device no longer offered must be replaced, not kept."""
    from audio_to_tab.hardware import HostProbe

    monkeypatch.setenv("AUDIO_TOOLS_EDITION", "both")
    cpu_only = HostProbe(cuda=False, mps=False, ram_gb=12.0)
    assert default_isolate_device(cpu_only, ["cpu"], "cuda", platform="win32") == "cpu"


def test_default_isolate_device_with_nvidia_prefers_cuda(monkeypatch):
    from audio_to_tab.hardware import HostProbe

    monkeypatch.setenv("AUDIO_TOOLS_EDITION", "both")
    nvidia = HostProbe(cuda=True, mps=False, ram_gb=24.0)
    assert default_isolate_device(nvidia, ["cuda", "cpu"], None, platform="win32") == "cuda"


def test_default_isolate_device_empty_options_returns_current():
    assert default_isolate_device(None, [], None) is None
```

- [ ] **Step 2: Run the new tests and confirm they fail**

```bash
.venv311/bin/python -m pytest tests/test_isolate_state.py -k default_isolate_device -v
```

Expected: **collection ERROR** — `ImportError: cannot import name 'default_isolate_device'`
(or `NameError` at the import line). The function does not exist yet.

- [ ] **Step 3: Add `desktop_recommend` to the hardware import**

Change `ui/isolate_state.py:18` from:

```python
from audio_to_tab.hardware import HostProbe, resolve_desktop_speed
```

to:

```python
from audio_to_tab.hardware import HostProbe, desktop_recommend, resolve_desktop_speed
```

- [ ] **Step 4: Add the helper**

Insert immediately after `resolve_speed_preset` ends (line 725), before the blank lines
preceding `LITE_MAX_DURATION_SEC`:

```python
def default_isolate_device(
    probe: HostProbe | None,
    allowed_devices: Sequence[str],
    current: str | None = None,
    *,
    platform: str | None = None,
) -> str | None:
    """Seed the persisted ``isolate_device`` key from the host recommendation.

    Positional order is wrong on the ``both`` edition: ``cuda`` is listed first even when
    the machine has no NVIDIA GPU, so ``allowed_devices[0]`` would persist a CUDA default
    that the run gate then rejects. An existing, still-valid choice always wins so a
    deliberate user pick survives a restart.
    """
    if current and current in allowed_devices:
        return current
    if probe is not None and allowed_devices:
        recommended = str(desktop_recommend(probe, platform=platform)["device"])
        if recommended in allowed_devices:
            return recommended
    return allowed_devices[0] if allowed_devices else current
```

- [ ] **Step 5: Run the new tests and confirm they pass**

```bash
.venv311/bin/python -m pytest tests/test_isolate_state.py -k default_isolate_device -v
```

Expected: 5 passed.

- [ ] **Step 6: Wire it into the isolate page**

Change `ui/pages/isolate.py:2437-2438` from:

```python
    if st.session_state.get("isolate_device") not in allowed_devices:
        st.session_state["isolate_device"] = allowed_devices[0]
```

to:

```python
    st.session_state["isolate_device"] = default_isolate_device(
        probe, allowed_devices, st.session_state.get("isolate_device")
    )
```

- [ ] **Step 7: Add the import to the isolate page**

Add `default_isolate_device` to the existing `from ui.isolate_state import (...)` block
at `ui/pages/isolate.py:76-…`. That block is grouped by concern rather than sorted
alphabetically, so place the new name with the other plain helper functions near
`resolve_speed_preset`.

- [ ] **Step 8: Verify the page still imports cleanly**

```bash
.venv311/bin/python -c "import sys; sys.path.insert(0,'.'); import ui.pages.isolate" 2>&1 | tail -20
```

Expected: no output (clean import). Streamlit is installed in this venv, so a missing
name or typo surfaces here rather than at runtime in the frozen app.

- [ ] **Step 9: Run the full suite and lint**

```bash
.venv311/bin/python -m pytest tests/ -q 2>&1 | tail -15
.venv311/bin/python -m ruff check src/audio_to_tab
```

Expected: suite passes (ruff does not cover `ui/` — that is expected and matches CI).

- [ ] **Step 10: Commit**

**Do not commit.** The human has stated explicitly that nothing in this repository is to
be committed or pushed to GitHub. Leave the change in the working tree and report it.

```bash
git status --porcelain -- ui/isolate_state.py ui/pages/isolate.py tests/test_isolate_state.py
```

Expected: the paths above modified, uncommitted. Do not run `git add`, `git commit`,
`git push`, or `git tag`.

---

### Task 4: Stop the release workflow renaming installer artifacts

The installer scripts already produce correctly versioned filenames. The workflow then
discards them: on Windows it renames the built `.exe` to a hardcoded unversioned label, and
on macOS it overrides the script's own name. That is why the published 0.1.4 asset names
differ from what the docs promise.

The fix is to **stop the override**. `packaging/**` is not touched, and the installer
scripts remain the single source of truth for naming.

**Files:**
- Modify: `.github/workflows/desktop-release.yml:181-187` (Windows packaging step)
- Modify: `.github/workflows/desktop-release.yml:189-193` (macOS packaging step)
- Modify: `.github/workflows/desktop-release.yml:195-201` (upload artifact step)
- Modify: `.github/workflows/desktop-release.yml:213-231` (release body copy)

**Interfaces:**
- Consumes: nothing from Tasks 1-3. `matrix.artifact` survives as the Actions artifact identifier.
- Produces: release asset filenames byte-identical to `make_windows_installer.ps1:93` and `make_pkg.sh:18,20` output. Task 5's `DESKTOP.md` URLs are written against exactly these names.

- [ ] **Step 1: Record the current state for the diff check**

```bash
git diff --stat -- packaging/
```

Expected: empty. Re-check this in Step 7 after all edits.

- [ ] **Step 2: Fix the Windows packaging step**

Replace `.github/workflows/desktop-release.yml:181-187`:

```yaml
      - name: Package Windows installer
        if: runner.os == 'Windows'
        shell: pwsh
        run: |
          $version = python -c "from audio_to_tab import __version__; print(__version__)"
          powershell -ExecutionPolicy Bypass -File packaging/make_windows_installer.ps1 -AppVersion $version -Flavor ${{ matrix.edition }}
          Copy-Item -Path "dist/AudioTools-$version-windows-x64-${{ matrix.edition }}-setup.exe" -Destination ${{ matrix.artifact }} -Force
```

with — note the rename is gone; the script's own filename is uploaded as-is:

```yaml
      - name: Package Windows installer
        if: runner.os == 'Windows'
        shell: pwsh
        run: |
          $version = python -c "from audio_to_tab import __version__; print(__version__)"
          powershell -ExecutionPolicy Bypass -File packaging/make_windows_installer.ps1 -AppVersion $version -Flavor ${{ matrix.edition }}
          Get-ChildItem -Path dist -Filter "AudioTools-$version-windows-x64-${{ matrix.edition }}-setup.exe"
```

- [ ] **Step 3: Fix the macOS packaging step**

Replace `.github/workflows/desktop-release.yml:189-193`:

```yaml
      - name: Package macOS pkg
        if: runner.os == 'macOS'
        run: |
          chmod +x packaging/make_pkg.sh packaging/make_app.sh packaging/pkg_scripts/postinstall
          export AUDIO_TOOLS_VERSION="$(python -c 'from audio_to_tab import __version__; print(__version__)')"
          AUDIO_TOOLS_OUTPUT_DIR="$PWD" AUDIO_TOOLS_PKG_NAME="${{ matrix.artifact }}" ./packaging/make_pkg.sh
```

with — `AUDIO_TOOLS_PKG_NAME` is dropped so `make_pkg.sh:18,20` chooses the name:

```yaml
      - name: Package macOS pkg
        if: runner.os == 'macOS'
        run: |
          chmod +x packaging/make_pkg.sh packaging/make_app.sh packaging/pkg_scripts/postinstall
          export AUDIO_TOOLS_VERSION="$(python -c 'from audio_to_tab import __version__; print(__version__)')"
          AUDIO_TOOLS_OUTPUT_DIR="$PWD" ./packaging/make_pkg.sh
```

- [ ] **Step 4: Fix the upload step to carry the real filename**

The Actions artifact **name** must stay unique per matrix job, but the uploaded
**filename** must be the script-generated one — GitHub derives each release asset's name
from the filename, not from the Actions artifact name.

Replace `.github/workflows/desktop-release.yml:195-201` (the single upload step) with two
OS-gated steps. Two rather than one multi-pattern glob, so the behaviour does not depend
on how `if-no-files-found` aggregates across unmatched patterns:

```yaml
      - name: Upload artifact (Windows)
        if: runner.os == 'Windows'
        uses: actions/upload-artifact@v4
        with:
          name: ${{ matrix.artifact }}
          path: dist/AudioTools-${{ needs.version.outputs.version }}-windows-x64-${{ matrix.edition }}-setup.exe
          if-no-files-found: error
          retention-days: 14

      - name: Upload artifact (macOS)
        if: runner.os == 'macOS'
        uses: actions/upload-artifact@v4
        with:
          name: ${{ matrix.artifact }}
          path: AudioTools-${{ needs.version.outputs.version }}-macos-${{ matrix.arch }}.pkg
          if-no-files-found: error
          retention-days: 14
```

`matrix.arch` is `arm64` or `x64`, matching the suffixes in `make_pkg.sh:18,20`
(`macos-arm64-silicon` / `macos-x64-intel`) **only if** those two values line up. Verify
before relying on it:

```bash
awk 'NR>=15 && NR<=22 {printf "%d: %s\n", NR, $0}' packaging/make_pkg.sh
```

Expected: the pkg name is selected on something other than a bare `arch` value — confirm
the exact string, then adjust the `path:` glob above to match. If `make_pkg.sh` derives
the suffix differently, use a glob instead of an exact filename:

```yaml
          path: AudioTools-*-macos-*.pkg
```

Prefer the glob — it is correct regardless of how `make_pkg.sh` composes the suffix, and
exactly one `.pkg` exists in the workspace root per macOS job.

- [ ] **Step 5: Add the `version` job the upload paths reference**

The `path:` lines above reference `needs.version.outputs.version`. Add a small job ahead
of `build` in `desktop-release.yml` and declare the dependency. This is purely additive —
no existing job changes beyond `build` gaining `needs:`.

Read the version by extracting it from the source file rather than importing it: this job
runs before any `pip install`, and `src/audio_to_tab/__init__.py` is dependency-free
(it is only a docstring plus `__version__`).

Verify the extraction works locally first:

```bash
sed -n 's/^__version__ = "\(.*\)"$/\1/p' src/audio_to_tab/__init__.py
```

Expected: `0.1.4`

Then insert as the **first** entry under the existing `jobs:` key:

```yaml
jobs:
  version:
    runs-on: ubuntu-latest
    outputs:
      version: ${{ steps.read.outputs.version }}
    steps:
      - name: Read version
        id: read
        run: echo "version=$(sed -n 's/^__version__ = \"\(.*\)\"$/\1/p' src/audio_to_tab/__init__.py)" >> "$GITHUB_OUTPUT"

  build:
    needs: version
    # The existing strategy/matrix/torch/edition/arch/artifact block follows unchanged.
    strategy:
```

If the nested quoting in the `echo` proves fragile in review, split it across two lines —
the value is identical:

```yaml
      - name: Read version
        id: read
        run: |
          sed -n 's/^__version__ = "\(.*\)"$/\1/p' src/audio_to_tab/__init__.py > version.txt
          echo "version=$(cat version.txt)" >> "$GITHUB_OUTPUT"
```

- [ ] **Step 6: Correct the release body copy**

In `.github/workflows/desktop-release.yml:213-231`, the release body hardcodes the
unversioned names. Substitute the real version so the release notes name the actual files
sitting beside them. Get the version first:

```bash
python -c "import sys; sys.path.insert(0,'src'); from audio_to_tab import __version__; print(__version__)"
```

Expected: `0.1.4`. Then replace, inside the `body: |` block:

- `` `AudioTools-windows-x64-cpu-setup.exe` `` → `` `AudioTools-0.1.4-windows-x64-cpu-setup.exe` ``
- `` `AudioTools-windows-x64-cuda-setup.exe` `` → `` `AudioTools-0.1.4-windows-x64-cuda-setup.exe` ``
- `` `AudioTools-macos-arm64-silicon.pkg` `` → `` `AudioTools-0.1.4-macos-arm64-silicon.pkg` ``
- `` `AudioTools-macos-x64-intel.pkg` `` → `` `AudioTools-0.1.4-macos-x64-intel.pkg` ``

Leave `draft: true` at `:216` as-is — the human publishes the draft by hand in Task 6
Step 6. The body itself contains no draft or prerelease wording to correct.

- [ ] **Step 7: Validate the YAML**

```bash
python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/desktop-release.yml')); print('yaml ok')"
```

Expected: `yaml ok`. If `pyyaml` is unavailable, use
`python -c "import ruamel.yaml"` — if neither is installed, skip and flag it in your report.

- [ ] **Step 8: Verify `packaging/` is still untouched**

```bash
git diff --stat -- packaging/
```

Expected: empty output. **If this is non-empty, revert the `packaging/` changes
immediately and report — the Global Constraints forbid it.**

- [ ] **Step 9: Verify the workflow's own guards are intact**

```bash
grep -n 'Verify mixer frontend is committed\|must not ship\|website web/ must not ship\|edition' .github/workflows/desktop-release.yml | head
```

Expected: the onedir exclusion assertions (`backend`, `web`, `.env`) and the edition check
are all still present. This task must not weaken any existing gate.

- [ ] **Step 10: Commit**

**Do not commit.** The human has stated explicitly that nothing in this repository is to
be committed or pushed to GitHub. Leave the change in the working tree and report it.

```bash
git status --porcelain -- .github/workflows/desktop-release.yml
```

Expected: the paths above modified, uncommitted. Do not run `git add`, `git commit`,
`git push`, or `git tag`.

---

### Task 5: Correct `DESKTOP.md` against assets that will exist

Every download instruction in `DESKTOP.md` is currently wrong — verified 404 against the
live GitHub API. Three separate conventions appear (versioned table rows, unversioned
`curl` blocks, and a third naming on the actual release), and every release is flagged as
a prerelease so `/releases/latest/` cannot resolve at all.

The names used here must be exactly what Task 4's pipeline produces.

**Files:**
- Modify: `DESKTOP.md:88-140` (installer table + signing claim + all `curl` blocks)

**Interfaces:**
- Consumes: Task 4's output naming. Version from `__version__` (`0.1.4`); tag `desktop-v0.1.4`.
- Produces: the single canonical download section. Task 6 verifies every URL here.

- [ ] **Step 1: Read the current section**

```bash
awk 'NR>=88 && NR<=145 {printf "%d: %s\n", NR, $0}' DESKTOP.md
```

Confirm the exact span before editing.

- [ ] **Step 2: Replace the installer table (`:92-97`)**

```markdown
| Tester machine | File | Notes |
|----------------|------|--------|
| Apple Silicon Mac (M1–M4) | `AudioTools-0.1.4-macos-arm64-silicon.pkg` | macOS **12+**. Double-click → **Install**. The app launches when install finishes. If Finder blocks: Terminal `xattr -cr` + `sudo installer`, or **System Settings → Privacy & Security → Open Anyway**. |
| Intel Mac | `AudioTools-0.1.4-macos-x64-intel.pkg` | Same install steps. An arm64 pkg will not launch here. |
| Windows 10 or 11 (x64), no NVIDIA GPU | `AudioTools-0.1.4-windows-x64-cpu-setup.exe` | **64-bit only.** Small Setup. Start Menu: **Audio Tools (CPU)**. Needs [WebView2](https://go.microsoft.com/fwlink/p/?LinkId=2124703). |
| Windows 10 or 11 (x64) with NVIDIA GPU | `AudioTools-0.1.4-windows-x64-cuda-setup.exe` | **64-bit only.** Large Setup. Start Menu: **Audio Tools (NVIDIA)**. Isolation is faster on NVIDIA + drivers. Can be installed next to the CPU edition. |
```

- [ ] **Step 3: Fix the signing claim (`:99`)**

The line currently reads "macOS builds are signed and notarized when Developer ID
certificates are available on the build Mac." That is misleading in a tester runbook:
`desktop-release.yml:2-3` states CI artifacts are **never** signed. Replace that sentence
with:

```markdown
This is a **0.1.4 demo**. **Downloaded builds are unsigned** — macOS shows the
"Apple could not verify" Gatekeeper warning and Windows shows SmartScreen "Unknown
publisher". Both are expected; the Terminal commands below handle macOS. The PyInstaller
onedir is not obfuscated (Python is extractable); the freeze ships **no** hosted-site
code, `.env`, or cloud credentials. No 32-bit Windows 10 build. No native Windows ARM
build. No App Store.
```

- [ ] **Step 4: Fix the release-provenance sentence (`:103`)**

Replace with:

```markdown
Published under a `desktop-v*` GitHub Release. The download URLs below are pinned to the
`desktop-v0.1.4` tag so they always resolve to these exact files.
```

- [ ] **Step 5: Rewrite the whole terminal download section (`:105-145`)**

Replace everything from `## Download & install (terminal)` to the end of the Windows CUDA
block with the following. Every URL is tag-pinned, so it is immune to the prerelease and
draft semantics that broke `/releases/latest/`.

````markdown
## Download & install (terminal)

Use the file that matches your OS. Windows has two 0.1.4 Setups: **`AudioTools-0.1.4-windows-x64-cpu-setup.exe`** (default, ~330 MB) and **`AudioTools-0.1.4-windows-x64-cuda-setup.exe`** (NVIDIA, large). Pick CPU unless your machine has an NVIDIA GPU.

### Apple Silicon Mac (M1–M4)

```bash
curl -fL -o ~/Downloads/AudioTools-0.1.4-macos-arm64-silicon.pkg \
  "https://github.com/notjj1234/jj_audio_website/releases/download/desktop-v0.1.4/AudioTools-0.1.4-macos-arm64-silicon.pkg"

xattr -cr ~/Downloads/AudioTools-0.1.4-macos-arm64-silicon.pkg
sudo installer -pkg ~/Downloads/AudioTools-0.1.4-macos-arm64-silicon.pkg -target /
open /Applications/AudioTools.app
```

Finder: double-click the `.pkg` → **Install**. The app should launch when install finishes.

If Finder shows "Apple could not verify…", use the Terminal block above, or **System Settings → Privacy & Security → Open Anyway**.

### Intel Mac

```bash
curl -fL -o ~/Downloads/AudioTools-0.1.4-macos-x64-intel.pkg \
  "https://github.com/notjj1234/jj_audio_website/releases/download/desktop-v0.1.4/AudioTools-0.1.4-macos-x64-intel.pkg"

xattr -cr ~/Downloads/AudioTools-0.1.4-macos-x64-intel.pkg
sudo installer -pkg ~/Downloads/AudioTools-0.1.4-macos-x64-intel.pkg -target /
open /Applications/AudioTools.app
```

### Windows 10 / 11 CPU (PowerShell)

```powershell
curl.exe -fL -o "$env:USERPROFILE\Downloads\AudioTools-0.1.4-windows-x64-cpu-setup.exe" `
  "https://github.com/notjj1234/jj_audio_website/releases/download/desktop-v0.1.4/AudioTools-0.1.4-windows-x64-cpu-setup.exe"
```

### Windows 10 / 11 with NVIDIA GPU (PowerShell)

```powershell
curl.exe -fL -o "$env:USERPROFILE\Downloads\AudioTools-0.1.4-windows-x64-cuda-setup.exe" `
  "https://github.com/notjj1234/jj_audio_website/releases/download/desktop-v0.1.4/AudioTools-0.1.4-windows-x64-cuda-setup.exe"
```

The two Windows Setups install to separate Start Menu entries and can sit side by side.
````

Preserve any section that follows line 145 (troubleshooting, uninstall, privacy notes) —
only replace the download blocks. Read the tail first:

```bash
awk 'NR>=140 && NR<=175 {printf "%d: %s\n", NR, $0}' DESKTOP.md
```

- [ ] **Step 6: Verify no stale names remain anywhere in the repo docs**

```bash
grep -rn 'AudioTools-windows-x64\|AudioTools-macos-arm64\|AudioTools-macos-x64\|releases/latest' README.md DESKTOP.md DEPLOY.md
```

Expected: **no matches**. Every occurrence is now the versioned form.

- [ ] **Step 7: Sanity-check the version is consistent repo-wide**

```bash
grep -n 'version' pyproject.toml | head -3
grep -n '__version__' src/audio_to_tab/__init__.py
```

Expected: `0.1.4` in both.

- [ ] **Step 8: Commit**

**Do not commit.** The human has stated explicitly that nothing in this repository is to
be committed or pushed to GitHub. Leave the change in the working tree and report it.

```bash
git status --porcelain -- DESKTOP.md
```

Expected: the paths above modified, uncommitted. Do not run `git add`, `git commit`,
`git push`, or `git tag`.

---

### Task 6: Cut and publish the release (approval-gated, manual)

This proves the pipeline actually runs and makes the links real. It pushes a tag and
publishes a public release — both require explicit human approval.

**Files:**
- No file edits. This task is git and GitHub operations only.

**HUMAN-EXECUTED ONLY — DO NOT RUN AS AN AGENT.**
The human has stated explicitly that nothing here is to be committed, pushed, tagged, or
published to GitHub by an agent. Steps 3–6 push a branch and a tag and publish a release.
Those are irreversible, public actions. Leave them for the human to run, or run them only
when the human gives explicit, specific, one-time approval for that exact step. The
read-only steps (1, 2, 7, 8, 9) may be run freely to produce a verification report.

**Interfaces:**
- Consumes: all prior tasks. Requires a clean `main` with every task committed.
- Produces: a published, non-prerelease release with four correctly named assets, and verified-working download URLs.

- [ ] **Step 1: Confirm the tree is clean and CI is green**

```bash
git status --porcelain
git log --oneline -6
```

Expected: clean tree; the commits from Tasks 1-5 are the most recent entries.

- [ ] **Step 2: Confirm no `desktop-v*` tag already exists**

```bash
git tag -l 'desktop-v*'
```

Expected: empty. If `desktop-v0.1.4` already exists, stop and report.

- [ ] **Step 3: STOP — human takes over here**

Hand the human this checklist and stop. Do not run Steps 4–6.

- Step 4: push the branch — `git push origin main`
- Step 5: push the tag — `git push origin desktop-v0.1.4`
- Step 6: publish the draft release

Explain to the human: pushing the tag triggers a 4-job CI matrix (2 Windows + 2 macOS
runners, several hours, large downloads) and creates a GitHub release. That is their
decision to make, not the agent's.

- [ ] **Step 4: Push the commit and the tag — HUMAN ONLY, do not run**

```bash
git push origin main
git push origin desktop-v0.1.4
```

- [ ] **Step 5: Watch the workflow — HUMAN ONLY, do not run**

Watch `desktop-release` on GitHub Actions. All four matrix jobs must be green. Note two
expected failure modes and what they mean:

- `Mixer frontend assets missing` at `:83-98` → Task 1's Step 2 check was wrong; the
  committed bundle is inconsistent. Stop and report.
- Any onedir layout assertion failure (`:149-155`) → the freeze is shipping `backend/`,
  `web/`, or a `.env`. **Stop and report — never publish that.**

- [ ] **Step 6: Publish the draft release — HUMAN ONLY, do not run**

The workflow creates the release with `draft: true` (`desktop-release.yml:216`). A draft
is invisible to the public and `/releases/latest/` cannot see it. Publish it in the GitHub
UI, and **leave "Set as a pre-release" unchecked** so `/releases/latest/` resolves.

- [ ] **Step 7: Verify the four assets exist with the expected names**

```bash
curl -sS "https://api.github.com/repos/notjj1234/jj_audio_website/releases/tags/desktop-v0.1.4" | python3 -c "
import json,sys
r=json.load(sys.stdin)
print('draft=%s prerelease=%s' % (r['draft'], r['prerelease']))
for a in r['assets']: print('  %-52s %8.1f MB' % (a['name'], a['size']/1e6))
"
```

Expected: `draft=False prerelease=False` and exactly these four names:

```
AudioTools-0.1.4-macos-arm64-silicon.pkg
AudioTools-0.1.4-macos-x64-intel.pkg
AudioTools-0.1.4-windows-x64-cpu-setup.exe
AudioTools-0.1.4-windows-x64-cuda-setup.exe
```

**If the names are unversioned, Task 4 did not take effect — stop and report.**

- [ ] **Step 8: Verify every download URL from `DESKTOP.md` returns 200**

```bash
B=https://github.com/notjj1234/jj_audio_website/releases/download/desktop-v0.1.4
for f in AudioTools-0.1.4-macos-arm64-silicon.pkg \
         AudioTools-0.1.4-macos-x64-intel.pkg \
         AudioTools-0.1.4-windows-x64-cpu-setup.exe \
         AudioTools-0.1.4-windows-x64-cuda-setup.exe; do
  curl -sS -o /dev/null -w "$f -> %{http_code}\n" -L -r 0-0 "$B/$f"
done
```

`-r 0-0` requests a single byte so this does not download ~2.7 GB. Expected: `200` for all
four. **A `404` means the release notes are still wrong — fix `DESKTOP.md` before
announcing.**

- [ ] **Step 9: Verify `/releases/latest` now resolves**

```bash
curl -sS -o /dev/null -w "%{http_code} -> %{redirect_url}\n" \
  https://github.com/notjj1234/jj_audio_website/releases/latest
```

Expected: `200`, with no redirect to `/releases`. This is the check that was failing at
the start of this plan.

- [ ] **Step 10: Report completion**

Report: the release URL, the four verified asset names, the `curl` results from Steps 8-9,
and the test/lint results recorded in Task 1 Step 3. Flag that Track B (disk pruning,
integration test, CI web job, and the §3.6 correctness defects) is still outstanding.

### Task 6: SKIPPED by human decision — building locally instead

**Decision: the human builds the installers on their own Windows and Mac machines and does
not use GitHub Actions to build them.** Task 6 is therefore not executed. The human has
both machines, has already produced working builds by hand, and prefers the fast
edit-and-rebuild loop over a multi-hour CI run.

**What this changes — nothing in the fixes.** Tasks 1-5 are all still valid and all still
needed:

- Task 1 (green baseline) and Tasks 2-3 (probe-aware GPU default) fix a real first-run bug
  in the app itself. They apply no matter who compiles the installer.
- Task 4 (stop renaming artifacts) only matters if CI builds. Locally built files already
  carry the correct versioned names from `make_windows_installer.ps1:93` and
  `make_pkg.sh:18,20`, because nothing renames them. **Task 4 is harmless and can simply
  stay uncommitted** — or be reverted if the repo will never use CI for releases.
- Task 5 (DESKTOP.md) is still required and still correct, because a release has to exist
  for the download links to work at all.

**The release is still needed — just done by hand.** The tag-pinned URLs written in Task 5
(`releases/download/desktop-v0.1.4/<file>`) do **not** require Actions. GitHub serves any
asset attached to a release, however it got there. To publish manually:

1. Locally build all four installers (commands in README.md / DESKTOP.md).
2. In the GitHub UI: **Releases → Draft a new release**.
3. Tag: `desktop-v0.1.4`, target `main`.
4. Upload the four files. The **filename must match exactly** what DESKTOP.md says:
   - `AudioTools-0.1.4-macos-arm64-silicon.pkg`
   - `AudioTools-0.1.4-macos-x64-intel.pkg`
   - `AudioTools-0.1.4-windows-x64-cpu-setup.exe`
   - `AudioTools-0.1.4-windows-x64-cuda-setup.exe`
5. Publish, and **leave "Set as a pre-release" unchecked** (this is what makes
   `/releases/latest/` resolve, and it is the check that was silently failing before).
6. Note: `desktop-release.yml` is `on: push: tags: desktop-v*` — creating the tag in the UI
   will **trigger** the workflow. If the human does not want a CI run, build from a local
   tag and push the **branch only**, then create the release in the UI, or accept one
   redundant CI run. Confirm the preferred route before doing either.

**Verification still applies.** After a manual publish, these read-only checks are still
worth running, and are the only part of Task 6 the agent may run:

```bash
curl -sS "https://api.github.com/repos/notjj1234/jj_audio_website/releases/tags/desktop-v0.1.4" \
  | python3 -c "import json,sys; r=json.load(sys.stdin); print('draft=%s prerelease=%s'%(r['draft'],r['prerelease'])); [print('  %-52s %8.1f MB'%(a['name'],a['size']/1e6)) for a in r['assets']]"
```

Expected: `draft=False prerelease=False` and exactly the four versioned names above.
Then confirm each `DESKTOP.md` URL returns `200` using `-r 0-0` so no gigabytes download.

**Outstanding doc inconsistency found while skipping:** `README.md:70` documents
`-Flavor both` (the combined installer), but the agreed release shape is separate
`cpu` and `cuda` installers, and `packaging/edition.txt` is `cpu`. If the human builds
locally from the README, they will produce a `both` build that does not match the release
notes. Worth reconciling separately.

---

## Post-Plan Follow-Ups (not in this plan)

Recorded so they are not lost. These are Track B/C from the spec and need their own plan:

- **Disk pruning sweep** in `ui/isolate_jobs.py` — ~1 GB per job accumulates on the
  install volume at `<app>/_internal/data/ui_runs/isolate_jobs`, with no age or count
  sweep. Spec §4.5 has the retention constants and selection rules.
- **End-to-end isolate → mixer → export integration test** — the flagship path has no
  test today. Spec §4.6.
- **CI web job** (`npm ci && npm test && npx tsc --noEmit`) and aligning the CI Python
  install profile to include `roformer` + `separator`. Spec §4.7.
- **§3.6 correctness defects** — guitar-FT circular guard, PDF two-measures-per-row
  overflow, metronome failures swallowed at debug, model release after jobs, Tab PDF
  cancel/timeout, metronome float32 + duration cap, `lead_rhythm` window cap.
- **Mixer `dispose()`** — leaks an AudioContext and ~200 MB of decoded PCM per mount, in
  both `ui/stem_mixer_component/frontend/src/main.ts` and `web/src/mixer/engine.ts`.
- **File the ~60 hosted-stack findings** in `docs/issues.md`.
- **Doc drift** — `README.md:72` documents a `both` build; `web/package.json` says
  `0.1.0`; dependabot misses two of the three component frontends; git history is 92 MB
  and 73% committed `node_modules`.
