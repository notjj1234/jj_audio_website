# Player shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recompose the desktop practice player so the stage stays put and the practice sheet sits below it, without changing the audio graph.

**Architecture:** The player is the existing Vite iframe in `ui/stem_mixer_component/frontend/`. This phase moves regions and empty-state copy in `main.ts` and CSS. Playback, seek, pan, solo, mute, speed, key, count-in, and loop stay on their current functions.

**Tech Stack:** TypeScript, Vite 5, the existing Streamlit v1 component. Python tests read the source. No new dependency.

## Global Constraints

- `MPS_MIN_RAM_GB` stays `12.0` in `src/audio_to_tab/hardware.py`.
- Desktop Interface Lite is not hosted `lite`.
- Desktop isolation jobs stay serial.
- Do not copy Moises artwork, font files, or markup.
- Do not copy an unmeasured pan, solo, or fader law. Do not edit `ui/stem_mixer_component/frontend/src/pan.ts` or `web/src/mixer/pan.ts`.
- Pixels in `10-MOISES-UI-CRAFT.md` §1.3 and §2.5 are our spec, not Moises 2.1.0 parity.
- Do not rebuild Home. Do not start Studio, Mastering, Voice, credits, or plugins.
- Rebuild with `make mixer-build` or `scripts/dev.ps1 mixer-build`. Do not hand-edit `frontend/build/`.
- No commit, push, or PR unless that conversation asks.
- Do not log into Moises, upload audio, or buy a plan.

## File map

| File | Role |
|---|---|
| `ui/stem_mixer_component/frontend/src/main.ts` | Region order, popover, empty copy. Audio methods stay. |
| `ui/stem_mixer_component/frontend/src/style.css` | Sheet, rail, and transport layout. |
| `tests/test_stem_mixer_component.py` | Source-order and copy assertions. |

Current order, read at `main.ts` 2994–3113: `.mixer-header`, `.mixer-transport` (Play/Stop/Restart, seek, `#master-vol`, Speed & Key), `.mixer-master`, `<details id="practice-panel">`, then `.mixer-stage`.

---

### Task 1: Practice sheet after the stage

**Files:**
- Modify: `ui/stem_mixer_component/frontend/src/main.ts` (the `root.innerHTML` template around lines 2992–3114)
- Test: `tests/test_stem_mixer_component.py`

**Interfaces:**
- Consumes: existing ids `practice-panel`, `btn-playpause`, `seek`, `stems`
- Produces: DOM order header, transport, stage, practice panel, plus `data-ui="v2"` on `.mixer`

- [ ] **Step 1: Write the failing test**

```python
def test_player_v2_puts_practice_after_stage():
    text = _mixer_main_ts()
    stage = text.find('<div class="mixer-stage">')
    panel = text.find('<details class="mixer-practice-panel"')
    assert stage != -1 and panel != -1
    assert stage < panel
    assert 'data-ui="v2"' in text
```

- [ ] **Step 2: Run it**

Run: `.venv311\Scripts\python.exe -m pytest tests/test_stem_mixer_component.py::test_player_v2_puts_practice_after_stage -q`

Expected: FAIL because the panel is currently before the stage and `data-ui` is absent.

- [ ] **Step 3: Move the block**

Cut the `<details class="mixer-practice-panel" ...>` element, including its summary, toolbar, tabs, and body, and paste it after the `.mixer-stage` closing `</div>`. Add `data-ui="v2"` on the `.mixer` root. Do not rename `id="practice-panel"`, `id="practice-body"`, or the tab `data-practice-tab` values. Do not edit `setPracticeRate`, `setPracticeSemitones`, `startCountIn`, or `startSources`.

- [ ] **Step 4: Re-run the test**

Expected: PASS.

- [ ] **Step 5: Stop before commit**

Do not commit unless this conversation asks.

**Rollback:** restore `main.ts` from git. The audio graph is untouched, so playback behavior returns with the file.

**Done when:** the test passes and `.mixer-stage` precedes `#practice-panel` in the template.

---

### Task 2: Speed and Key become a popover

**Files:**
- Modify: `ui/stem_mixer_component/frontend/src/main.ts`
- Modify: `ui/stem_mixer_component/frontend/src/style.css`
- Test: `tests/test_stem_mixer_component.py`

**Interfaces:**
- Consumes: `#practice-speed` (min 0.5, max 1.5, step 0.05) and `#practice-key` (min -6, max 6, step 1)
- Produces: a closed-by-default popover that still contains those two inputs and `#btn-practice-reset`

- [ ] **Step 1: Write the failing test**

```python
def test_speed_key_lives_in_a_popover():
    text = _mixer_main_ts()
    assert 'id="practice-speed-popover"' in text
    assert 'aria-controls="practice-speed-popover"' in text
    assert 'id="practice-speed"' in text
    assert 'id="practice-key"' in text
    transport = text[text.find('<div class="mixer-transport">') : text.find('<div class="mixer-master">')]
    assert 'id="practice-speed"' not in transport
```

- [ ] **Step 2: Run it**

Run: `.venv311\Scripts\python.exe -m pytest tests/test_stem_mixer_component.py::test_speed_key_lives_in_a_popover -q`

Expected: FAIL. The sliders are inside `.mixer-transport` today (`main.ts` 3023–3037).

- [ ] **Step 3: Move the controls**

Leave a button in the transport: label `Speed & Key`, `aria-expanded="false"`, `aria-controls="practice-speed-popover"`. Put the existing speed row, key row, and Reset button inside `<div id="practice-speed-popover" hidden>`. Wire the button to toggle `hidden` and `aria-expanded`. Escape sets `hidden` and returns focus to the button. Keep the existing `input` listeners. Range stays 0.5–1.5 and −6–+6.

- [ ] **Step 4: Re-run the test**

Expected: PASS.

**Rollback:** move the two rows back into `.mixer-transport` and delete the popover button.

**Done when:** the transport template no longer contains the sliders, and both slider ids still exist.

---

### Task 3: Master and presets leave the transport row

**Files:**
- Modify: `ui/stem_mixer_component/frontend/src/main.ts`
- Modify: `ui/stem_mixer_component/frontend/src/style.css`
- Test: `tests/test_stem_mixer_component.py`

**Interfaces:**
- Consumes: `#master-vol`, `#btn-muteall`, `#btn-reset`, `#btn-clearsolo`, `.preset-chip`
- Produces: `#master-vol` inside `.mixer-stage`, and the preset/reset buttons inside `<div id="mix-menu" hidden>`

- [ ] **Step 1: Write the failing test**

```python
def test_master_sits_with_the_stage():
    text = _mixer_main_ts()
    stage = text[text.find('<div class="mixer-stage">') : text.find('<details class="mixer-practice-panel"')]
    assert 'id="master-vol"' in stage
    assert 'id="mix-menu"' in text
    assert "data-preset=\"karaoke\"" in text
```

This assertion assumes Task 1 has already moved the practice panel after the stage. If Task 1 is not done, the slice is empty and the test fails closed.

- [ ] **Step 2: Run it**

Expected: FAIL. `#master-vol` is inside `.mixer-transport` (`main.ts` 3016–3021).

- [ ] **Step 3: Move the nodes**

Move the master `<label class="master-vol">` into `.mixer-stage`, above `#stems`. Move Mute all, Reset mix, Clear solo, Show video, and the four preset chips into `<div id="mix-menu" hidden>`. Add a transport button `Mix`, `aria-controls="mix-menu"`. Do not change preset `data-preset` values `all`, `karaoke`, `acapella`, `drumsBass`. Do not change `clampPan` or the solo/mute handlers.

- [ ] **Step 4: Re-run the test and the pan tests**

Run: `.venv311\Scripts\python.exe -m pytest tests/test_stem_mixer_component.py::test_master_sits_with_the_stage tests/test_mixer_pan.py -q`

Expected: PASS. A pan failure means this task touched the law. Revert that part.

**Rollback:** put `#master-vol` back in the transport and the chips back in `.mixer-master`.

**Done when:** master is in the stage slice and `tests/test_mixer_pan.py` still passes.

---

### Task 4: Empty copy and the sheet heights

**Files:**
- Modify: `ui/stem_mixer_component/frontend/src/main.ts` (the empty strings near lines 2593, 2607, and 3086)
- Modify: `ui/stem_mixer_component/frontend/src/style.css`
- Test: `tests/test_stem_mixer_component.py`

**Interfaces:**
- Consumes: the lyrics string already at line 2667, which names the reason
- Produces: the same reason-shaped copy for the generic and chord empties, and a sheet that can collapse

- [ ] **Step 1: Write the failing test**

```python
def test_practice_empty_copy_names_the_reason():
    text = _mixer_main_ts()
    assert "Re-run separation to analyse this song." not in text
    assert "Re-run separation with analysis enabled." not in text
    assert "No chords found — re-run analysis." not in text
    assert "No sections found — re-run analysis." not in text
    assert "No lyrics found (instrumental, or the lyrics model is unavailable)." in text
    assert 'id="btn-practice-sheet"' in text
```

- [ ] **Step 2: Run it**

Expected: FAIL. Those two re-run strings are in `main.ts` today.

- [ ] **Step 3: Change copy and add a collapse control**

Replace the initial body string with `No analysis in this run.` Replace the chord empty string with `No chords in this run.` Replace `No sections found — re-run analysis.` with `No sections in this run.` Replace the all-tabs empty string with `No chords, sections, lyrics, or tab in this run.` Leave the lyrics string unchanged. Add `<button type="button" id="btn-practice-sheet">Practice</button>` in the transport. It toggles the `hidden` attribute on `#practice-panel`. Do not change lyric-word timestamps or tab measure ids.

In `style.css`, under `.mixer[data-ui="v2"]`:

- `.mixer-stage` is the flexible middle.
- `#practice-panel` is the last region. At `min-width: 1280px` its body max-height is 360px. At `max-width: 1023px` the max-height is 280px. At `max-width: 900px` the panel starts `hidden` and the transport button shows it.
- `.mixer-transport` wraps to two rows at `max-width: 1024px`.

These heights are our spec from `10` §1.3, not a new Moises measurement.

- [ ] **Step 4: Re-run the test**

Expected: PASS.

**Rollback:** restore the empty strings and delete `#btn-practice-sheet` plus the `data-ui="v2"` CSS block.

**Done when:** the re-run strings are gone, the lyrics reason string remains, and the sheet has a transport toggle.

---

### Task 5: Build and the four widths

**Files:**
- Modify: `ui/stem_mixer_component/frontend/build/` only by the build command
- Test: `tests/test_stem_mixer_component.py`

- [ ] **Step 1: Typecheck and build**

Run from `ui/stem_mixer_component/frontend`: `node .\node_modules\typescript\bin\tsc --noEmit`

Then from the repo root: `powershell -File scripts/dev.ps1 mixer-build` if that script exists, otherwise `npm run build` in the frontend directory.

Expected: exit 0. Then `.venv311\Scripts\python.exe -m pytest tests/test_stem_mixer_component.py tests/test_mixer_pan.py -q` passes.

- [ ] **Step 2: Browser check**

Open the desktop app. Load one existing mix. At 1440, 1280, 1024, and 900 confirm:

- Play, Stop, Restart, and the seek slider are visible.
- The stem list is above the practice sheet.
- Speed and Key open from the transport button and Escape closes them.
- At 900 the sheet starts collapsed and the Practice button opens it.
- Mute, solo, and a pan drag still change the mix. If pan behavior changed, revert Task 3.

**Rollback:** `git checkout -- ui/stem_mixer_component/frontend/src` and rebuild.

**Done when:** the pytest command is green and the four widths show the stage above the sheet.

Do not start Phase 2 from this plan.
