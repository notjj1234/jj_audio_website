# Desktop UI redesign — Phase 1.5 (Tyrian Nocturne)

**Status:** plan only. Not started. No code changes are made by this document.
**Date:** 2026-10-20. **Home parity revision: 2026-10-21, §12.** §12 supersedes §0–§11 for the Home screen, the shell, and the phase exit. Player tasks in UI-5 and UI-6 are deferred to Phase 1.6. Do not treat them as the Home gate.
**Measurements:** `10-MOISES-UI-CRAFT.md` §13. Do not re-derive them.
**Scope:** desktop only (`ui/` + the existing desktop component sources). Do not edit `web/` or
`backend/`; do not change the audio engine, analysis algorithms, pan/solo laws, metronome contract,
wake hooks, or export semantics.
**Design reference:** `10-MOISES-UI-CRAFT.md`. Read it before this file.
**Repo rules:** `AGENTS.md`, `PROJECT_TREE.md`, `PLANNING.md` still govern. No commit, push, tag, or
PR without explicit approval.

---

## 0. Decision summary

### 0.1 What we are building

**2026-10-21:** the Home target in this subsection is superseded by §12. The rail is 240px at every measured width. 216px is the nav row, not a collapsed sidebar.

A **UI craft layer** on top of the existing Phase 1 product:

1. A real Home: a primary action, two secondary actions, a horizontal recents rail, and a library
   table that survives 1024×768.
2. A desktop shell that looks owned: 240px rail, icons, 14px UI type, parchment text, amber signal,
   no Streamlit promo/header.
3. A player that reads as one instrument: fixed stem rail, timeline, bottom practice sheet, one
   transport center.
4. Consistent popovers/dialogs, empty/loading/error states, keyboard/focus, and reduced motion.
5. A design-token module that keeps the Tyrian identity and still supports the existing theme
   presets.

It is not a new feature phase. Every control and data path already exists in Phase 1.

### 0.2 Architecture decision

**Use a hybrid:**

- **Streamlit remains the shell** for navigation, upload, job state, page routing, and the existing
  mixer iframe.
- **Home content becomes a custom Streamlit component** built in vanilla TypeScript + Vite, using the
  existing `streamlit-component-lib` pattern. No React, no new UI framework, no new runtime
  dependency.
- **The existing mixer iframe is restyled/recomposed**, not rewritten. The audio graph, SoundTouch
  worklet, stem state, pan law, loop/count-in logic, and wake hooks stay.
- **The sidebar remains Streamlit navigation**, styled to 240px at every width in §12. 216px is the nav row, not the rail. Only if the
  Gate 0 shell spike proves the sidebar width/full-bleed component cannot work cleanly do we fall
  back to a native Streamlit Home and a smaller custom table. Do not force a broken shell.

Why not keep native Streamlit for Home:

- **2026-10-21 correction:** the page does not clip at 1024. Content width shrinks with the viewport (`10` §13.12). The remaining failure is density: a 300px rail, 74px buttons, and recents that wrap. `st.columns` still cannot hold a 150px card rail and a 56px table without that squash.
- A real table needs `<table>` semantics, 56px rows, hover/focus states, and client-side search. The
  current button stack has none of these.
- The existing component pattern is already used by the mixer, region picker, and mix tabs; the repo
  knows how to build/commit/test a Vite component.

Why not a full React shell:

- It would require rewriting navigation, session state, file upload, page routing, job polling, and
  the player host. That is a Phase 2+ architecture change, not a UI polish pass.
- It would increase risk to the audio workflow for no practice gain.
- The user asked for a perfect desktop UI, not a new app framework.

### 0.3 The fallback, stated honestly

If Gate 0 cannot make a full-bleed component behave inside the Streamlit shell without double
scrollbars, a layout gap, or a broken sidebar at 1024:

- Keep the Streamlit shell.
- Build Home as a **native Streamlit layout** with a CSS-styled table-like list (not a custom
  component) for the first release.
- Keep the player restyle and the token layer.
- Record the failure and the fallback in `08-EVIDENCE-LOG.md`; do not silently ship a clipped page.

The plan is allowed to stop at Gate 0 and re-decide. That is cheaper than forcing the wrong
architecture.

### 0.4 Feature flag and rollback

- `AUDIO_TOOLS_UI_V2` (env, default `1`) gates the new Home component and the new shell CSS.
- Keep the old Home body reachable as `ui/home_legacy.py` for one release. `ui/pages/home.py` switches
  between legacy and V2; do not keep both designs forever.
- The player changes are additive CSS/structure behind `data-ui="v2"`; removing the attribute
  restores the old presentation while keeping the same IDs/listeners.
- No data migration. Tokens are presentation only.
- Remove the flag and legacy file after one successful release and one real-song regression.

---

## 1. Gate 0 — prove the shell before building the house

**2026-10-21:** the baseline in §1.1 is already recorded in `08` §13 and `10` §13. Do not re-run it to “confirm” the old 980px clip. The shell spike to execute is §12.3: sidebar **240px at both 1440 and 1024**. A 216px rail is not the target.

**Estimate:** 0.5–1 day. **No product code beyond a throwaway spike.**

### 1.1 Baseline evidence

- Capture current Home at 1440×900 and 1024×768 with CDP; record:
  - main content x/width;
  - sidebar width;
  - H1/button sizes;
  - overflow/clipping;
  - the Streamlit promo.
- Capture current player at 1440/1024; record the region heights and the control inventory.
- Store raw captures in `/tmp` only (they contain local library titles). Record measurements and
  redacted findings in `08-EVIDENCE-LOG.md` §11.
- Do not commit screenshots.

### 1.2 Shell spike

Build a throwaway Streamlit page (not shipped) that proves:

1. The sidebar can be set to 240px at 1440 and 216px at 1024 without a gap, overlap, or hidden
   collapse control.
2. The Streamlit header/footer/deploy/status/promo can be hidden without hiding the sidebar collapse
   control.
3. A custom component can start at the top of the main area, span the full remaining width, and
   report a content height that does not create a nested scrollbar.
4. The page background matches the component background (transparent iframe body or exact token).
5. A 40-row table can scroll with the page (not inside a 300px iframe viewport) and still keep the
   sidebar fixed.
6. The page works at 1024×768 and 1440×900, including the sidebar collapse/expand cycle.

Record the CSS/selector set that works. If selectors are fragile, prefer a small, documented set
over a giant override sheet.

### 1.3 Dependency check

- Reuse `streamlit-component-lib`, TypeScript, and Vite versions already present in
  `ui/stem_mixer_component/frontend/package.json` (or the nearest existing component). Do not add
  React, a CSS framework, an icon package, or a chart library.
- The Home component should not need audio/font packages. It may reuse Satoshi assets already in the
  repo; if font duplication pushes the bundle over budget, use the system UI stack in the component
  and keep Satoshi in the Streamlit shell. Do not add a new font.
- If a new dependency appears necessary, **stop at Gate 0** and ask. Gate 1 is not a place to
  discover a framework.

### 1.4 Gate 0 output

Write `docs/plans/moises-parity/_work/ui-craft-decision.md` with:

- the shell spike result (pass/fallback);
- the exact sidebar width/selector decision;
- the component height/scroll decision;
- the dependency decision;
- the bundle budget;
- the open risks.

**Gate 0 passes when** the shell spike works at 1440 and 1024, the fallback is explicit, and no new
dependency is needed. If it fails, stop and update `11` before writing product code.

---

## 2. Architecture and contracts

### 2.1 Data flow

```
ui/app.py
  ├─ design tokens → CSS variables for the Streamlit shell
  ├─ hide framework chrome; style sidebar/nav
  └─ st.navigation(...)

ui/pages/home.py
  ├─ AUDIO_TOOLS_UI_V2 ? V2 : legacy
  ├─ build_home_model() from ui/home_model.py
  ├─ home_component(model=..., theme=..., key="home_v2")
  │     └─ iframe: ui/home_component/frontend (vanilla TS)
  │            └─ returns {event, id, nonce, source:"home"}
  └─ validate event/id, resolve run_dir server-side, call existing actions

ui/pages/isolate.py
  └─ existing mixer iframe; restyled/recomposed in place
```

### 2.2 Token flow

- `ui/design_tokens.py` is the canonical semantic token definition. It has no Streamlit import and
  is unit-testable.
- `tokens_to_css()` emits `--att-*` custom properties for the Streamlit shell.
- `component_theme()` returns the flat color/type subset passed to iframes. The component sets CSS
  variables on its root; it never hard-codes the active theme.
- The component has a small default token set for `npm run dev` only. A test asserts the required
  keys exist; Python is the source of truth.
- `ui/theme_presets.py` remains the source of user theme choices. `design_tokens.py` derives
  semantic surfaces/text from the active preset. The default is Tyrian Nocturne; other presets must
  remain legible, not pixel-identical.
- The mixer currently receives a `theme` arg; extend that payload with the semantic tokens. Do not
  change the audio component's state contract.

### 2.3 Home model

`ui/home_model.py`:

```python
@dataclass(frozen=True)
class HomeRow:
    id: str                 # opaque, stable hash of run_dir; never the path
    title: str
    source_kind: str        # "file" | "youtube"
    duration_label: str     # "4:12" or ""
    age_label: str          # "2 mo ago" or ""
    analysis: AnalysisChip  # status, bpm, key, sections, warnings
    state: str              # "ready" | "needs-analysis" | "analysing" | "failed"
    has_tab: bool
    has_lyrics: bool

@dataclass(frozen=True)
class HomeModel:
    product: str
    edition: str
    version: str
    local_badge: str
    rows: list[HomeRow]
    recents: list[HomeRow]
    jobs: list[JobChip]
    counts: dict[str, int]
    empty: bool
    generated_at: float
```

Rules:

- **Never send `run_dir` or any filesystem path to the browser.** The component gets opaque IDs.
- The Python page resolves an ID against the current model before acting; reject unknown IDs and
  stale nonces.
- Titles are escaped in the component; the model does not contain HTML.
- The model is a snapshot; a refresh/rerun rebuilds it.
- `rows` max 40, recents max 6, jobs max 20. If there are more, show `40+` and a P2 note; do not
  silently paginate.

### 2.4 Event protocol

```ts
type HomeEvent =
  | { type: "open-learn" }
  | { type: "open-youtube" }
  | { type: "open-tab-pdf" }
  | { type: "open-settings" }
  | { type: "open-run"; id: string }
  | { type: "practice"; id: string }
  | { type: "analyse"; id: string }
  | { type: "cancel-job"; id: string }
  | { type: "retry-job"; id: string }
  | { type: "refresh" };

interface HomeEventEnvelope {
  source: "home";
  nonce: string;      // generated per user action
  event: HomeEvent;
}
```

Python:

- `_handle_home_event(envelope, model)`:
  - validate `source`, `nonce` (not seen), `event.type`;
  - for row events, resolve `id` in `model.rows`;
  - call existing handlers:
    - `open-learn` → `open_new_separation()`
    - `open-youtube` / `open-tab-pdf` / `open-settings` → `_go(...)`
    - `open-run` → `open_saved_run(run_dir)`
    - `practice` → `open_practice_run(run_dir)`
    - `analyse` → `guard worker_busy()`, `analyse_existing_run(run_dir)`, flash, rerun
    - `cancel-job` / `retry-job` → existing job actions
    - `refresh` → `st.rerun()`
- Store seen nonces in `st.session_state` (bounded set) so a Streamlit rerun does not repeat an
  action.
- Do not accept arbitrary command strings or paths from the component.
- Do not run analysis inside the component's iframe; it is a Python action after the event returns.

### 2.5 Home component rendering

- `main.ts`: subscribe to `Streamlit.RENDER_EVENT`, validate the model shape, set tokens, call
  `renderHome`.
- `render.ts`: pure template functions returning HTML strings; every dynamic string passes through
  `escapeHtml` (or is set with `textContent`). No `innerHTML` of untrusted titles without escaping.
- `home.css`: tokens + grid + components. No CDN, no external images, no remote fonts.
- `Streamlit.setComponentReady()` after first render; `Streamlit.setFrameHeight()` from
  `document.documentElement.scrollHeight` with a small debounce. Observe resize with `ResizeObserver`
  if available.
- The component owns: top bar, page heading, action deck, recents, library, empty/loading states,
  queue drawer. It does not own the sidebar.
- The component must render a usable skeleton before the model arrives (if the first render is
  delayed), and a readable error if the model is malformed. Never a blank iframe.

### 2.6 Build integration

- `ui/home_component/frontend/package.json`:
  - `streamlit-component-lib` same version as the mixer;
  - `typescript`, `vite`, `@types/node` same major versions;
  - scripts: `dev`, `build`, `preview`.
- `vite.config.ts`: `base: "./"`, output to `../build`, stable asset names/hashes via Vite.
- `make home-build` → `cd ui/home_component/frontend && npm ci && npm run build` (or the repo's
  existing pattern; do not assume `npm ci` if the other components use `npm install`).
- `scripts/dev.sh` / `scripts/dev.ps1`: add `home-build` beside the other component builds.
- `PROJECT_TREE.md`: add the new component, tests, tokens, and docs.
- `AGENTS.md`: add the fourth committed frontend build to the table; update the test count only if it
  changes.
- `tests/test_home_component.py`: assert the build directory, manifest, index, at least one hashed
  JS/CSS asset, no `localhost`/dev-server URLs, and the event strings. This mirrors
  `tests/test_stem_mixer_component.py`.
- Optional: `desktop-release.yml` asserts the Home build is present if the component ships. Do not
  change packaging semantics; only add a presence check if needed.

---

## 3. File-level change map

| File | Change | Risk |
|---|---|---|
| `ui/design_tokens.py` (new) | Semantic tokens, CSS emitter, component payload, contrast helper | Low; pure Python |
| `ui/theme_presets.py` | Map presets to semantic tokens; keep existing names | Medium; other themes |
| `ui/app.py` | Inject tokens; hide chrome/promo; sidebar 240/216; nav icons; base type; focus/reduced motion; input styling | Medium; Streamlit selectors |
| `ui/pages/home.py` | Thin switcher; V2 component; event handling; legacy fallback | Medium; actions/session |
| `ui/home_model.py` (new) | Pure model/format/status/ID functions | Low; tests |
| `ui/home_legacy.py` (new) | Move current Home body for one-release rollback | Low; duplicate temporarily |
| `ui/home_component/` (new) | Vanilla TS/Vite Home component + committed build | Medium; build/height |
| `ui/pages/isolate.py` | Add classes/hooks for header/progress/queue; no logic change | Low–medium |
| `ui/iframe-theme.css` (shared source; copies exist in each component’s `src/`) | Extend semantic tokens/radii; copy to all three components | Low; copy drift |
| `ui/stem_mixer_component/frontend/src/style.css` | Player shell, rail, transport, sheet, states | High; visual regression |
| `ui/stem_mixer_component/frontend/src/main.ts` | Move practice panel below stage; popovers; no audio changes | High; DOM/listeners |
| `ui/mix_tabs_component/frontend/src/style.css` | Token/height pass | Low |
| `ui/region_picker_component/frontend/src/style.css` | Token pass | Low |
| `Makefile`, `scripts/dev.sh`, `scripts/dev.ps1` | `home-build` target | Low |
| `tests/test_design_tokens.py` (new) | Token/contrast/derivation tests | Low |
| `tests/test_home_model.py` (new) | Model/ID/status/search tests | Low |
| `tests/test_home_component.py` (new) | Build/protocol source tests | Low |
| `tests/test_home.py` | Event handling + V2 switch | Medium |
| `tests/test_stem_mixer_component.py` | Build/source assertions for the new layout | Low |
| `PROJECT_TREE.md`, `AGENTS.md` | New files/build table | Low |
| `docs/plans/moises-parity/*` | Status/evidence/plan updates | Low |

No changes to:

- `src/audio_to_tab/` engine modules.
- `web/` or `backend/`.
- `packaging/audio_tools.spec` or release semantics (unless the Home build presence check is added).
- `.env*`.
- Model weights/download paths.

---

## 4. Work breakdown

**2026-10-21:** do not execute UI-0–UI-9 in this section. The Home tasks are §12. UI-5 and UI-6 below are the deferred player work.

The order is deliberate. Do not start the player until Home is usable at 1024. Do not start the
component until Gate 0 has passed.

### UI-0 — Gate 0 + baseline (0.5–1 day)

**Goal:** prove the shell and freeze the contract.

**Files:** throwaway spike only; `_work/ui-craft-decision.md`; `08-EVIDENCE-LOG.md` §11.

1. Capture current Home/player at 1440/1024; record measurements.
2. Run the shell spike from §1.2.
3. Check the existing component package versions and build pattern.
4. Freeze the token names from `10` §4; list any missing token.
5. Write the decision note and update `08`.

**Tests:** none; visual evidence only.

**Done when:** pass/fallback is written, no new dependency is proposed, and the shell works at both
widths.

**Stop if:** the sidebar/full-bleed component cannot work without a hack; fall back or replan.

---

### UI-1 — Tokens + shell (2–3 days)

**Goal:** make the app frame feel owned before touching Home content.

**Files:** `ui/design_tokens.py`, `ui/theme_presets.py`, `ui/app.py`,
`tests/test_design_tokens.py`.

1. Implement `design_tokens.py`:
   - semantic color, type, spacing, radius, motion, breakpoint tokens;
   - `tokens_to_css()`, `component_theme()`, `contrast_ratio()`;
   - derive from the active theme preset, with Tyrian defaults;
   - no Streamlit import.
2. In `ui/app.py`:
   - inject `tokens_to_css()` before the existing shell CSS;
   - replace hard-coded `#192542`/`#F6AD49` in the shell CSS with `var(--att-...)` where safe;
   - hide Streamlit header, footer, deploy, status widget, and the developer promo;
   - set sidebar width 240/216 and nav rows 40px; add Material icons to `st.Page`;
   - set base type 14/20, headings 28/34/20/28, weights 400/500/700;
   - style search/inputs/selects/radios/sliders to the tokens;
   - focus ring 2px, 2px offset; reduced-motion branch;
   - remove the universal `scale(0.97)` press; use background/border shifts;
   - keep the existing app-loading/rerun behavior; do not change page logic.
3. Add `st.Page` icons: Home, Audio Isolation, YouTube, Tab PDF, Settings.
4. Add the compact `Interface Lite/Pro` segmented control in the rail footer; keep the same session
   state key.
5. Add `tests/test_design_tokens.py`:
   - required keys;
   - contrast of each text/surface pair;
   - default preset is Tyrian;
   - alternate preset returns a complete token set;
   - no 600 weight in the generated type tokens.
6. Run targeted tests; then full `pytest`/`ruff` before moving on.

**Tests:** token tests, source-level assertions for hidden chrome, manual 1440/1024 shell screenshots.

**Done when:** the shell has no Streamlit promo/header, the sidebar is 240/216, body text is
parchment, the only amber is the active/primary signal, and 1024 does not clip the shell.

**Risk:** Streamlit selectors change. Keep the override list documented and minimal; retest after a
Streamlit bump.

---

### UI-2 — Home model + event contract (1–2 days)

**Goal:** separate data/format/validation from rendering.

**Files:** `ui/home_model.py`, `ui/pages/home.py` (model/event only), `tests/test_home_model.py`,
`tests/test_home.py`.

1. Move `relative_age`, `library_rows`, `run_label`, `analysis_summary`, `analysis_line`, and search
   matching into `ui/home_model.py`; keep re-exports/wrappers so existing imports do not break.
2. Add `HomeRow`, `HomeModel`, `build_home_model(rows, jobs, ...)`:
   - opaque stable IDs (e.g., `sha1(run_dir).hexdigest()[:16]`);
   - source kind, duration, age, analysis state, tab/lyrics flags;
   - statuses: `ready`, `needs-analysis`, `analysing`, `failed`;
   - counts, recents, jobs, empty flag.
3. Add `resolve_home_row(model, id)` and event validation.
4. Trace every action to its existing handler; no new backend.
5. Tests:
   - empty/1/6/40 rows;
   - long English/Japanese titles;
   - missing analysis, running, failed;
   - no raw paths in `model.to_dict()`;
   - unknown IDs rejected;
   - nonce replay rejected;
   - source-level assertions that `home.py` uses the model.
6. Keep the legacy Home functions working for the flag.

**Done when:** the model is renderable without Streamlit and the event mapping is testable.

---

### UI-3 — Home component scaffold + layout (2–3 days)

**Goal:** a real Home at 1440 and 1024.

**Files:** `ui/home_component/frontend/*`, `ui/pages/home.py`, `Makefile`, `scripts/dev.*`,
`tests/test_home_component.py`, `PROJECT_TREE.md`, `AGENTS.md`.

1. Scaffold the component using the existing mixer pattern:
   - `package.json`, `tsconfig.json`, `vite.config.ts`, `index.html`, `src/main.ts`,
     `src/render.ts`, `src/types.ts`, `src/home.css`, `src/tokens.ts`.
2. Render:
   - top bar (local badge, queue pill, refresh);
   - page heading (eyebrow, H1, subline);
   - action deck (primary card + two secondary cards);
   - recents rail;
   - library table (header, rows, search);
   - empty/loading/error states (static first).
3. Use the 12-column grid from `10` §5.2; no `st.columns`.
4. Add `escapeHtml` and a strict render path; no raw model paths.
5. Add the Streamlit wrapper in `home.py`; remove the old `_HOME_CSS` for V2; keep legacy behind the
   flag.
6. Add `make home-build` and the dev script entries; run the build; commit the hashed output only
   when the user approves a commit (otherwise leave working-tree changes).
7. Tests: build presence/manifest/no dev URLs/event strings; `npx tsc --noEmit`.
8. Manual: 1440 and 1024 screenshots; 6 rows; long titles; no horizontal overflow.

**Done when:** Home looks like the 10 §5.2 wireframe, the table is readable at 1024, and the build
is reproducible.

**Risk:** iframe height. Use content height + `ResizeObserver`; do not set a fixed 900px that leaves
a blank area.

---

### UI-4 — Home interactions, states, queue (2–3 days)

**Goal:** make the new Home fully functional and honest.

**Files:** `ui/pages/home.py`, `ui/home_model.py`, `ui/home_component/frontend/src/main.ts`,
`src/render.ts`, tests.

1. Wire the event protocol from §2.4:
   - open/practice/analyse/navigate;
   - cancel/retry/refresh;
   - nonce/ID validation;
   - flash messages and reruns.
2. Client-side search + clear; `/` focuses search; result count; no filter/sort controls (P2).
3. Recent card opens the mixer; status chip; last-opened/selected row.
4. Queue drawer:
   - idle/running/needs-attention pill;
   - 56px rows, progress, cancel/retry;
   - `aria-live` summary; explicit Refresh if live updates are unavailable.
5. States:
   - empty library, no search results, loading skeleton;
   - analysis running/failed;
   - missing tab/lyrics;
   - 40 rows.
6. Accessibility: `<table>`/`<th>`/`<td>`, contextual action labels, focus ring, keyboard order.
7. Tests: event handling, nonce replay, unknown ID, model status, no path leakage; manual action
   matrix.

**Done when:** a user can open, practice, analyse, cancel, retry, and search from Home; every state
has a clear next step; no raw path is exposed.

---

### UI-5 — Player shell + transport (3–4 days)

**Goal:** make the player read as one instrument before changing the practice content.

**Files:** `ui/stem_mixer_component/frontend/src/main.ts`, `style.css`, `iframe-theme.css`,
`tests/test_stem_mixer_component.py`.

1. Take a control inventory before/after: every `id`, listener, and state path. Do not remove or
   rename IDs without updating the listener.
2. Recompose the DOM into:
   - header 56px;
   - stem rail 280/240/210px with master/presets;
   - timeline + waveform stage;
   - practice sheet below the stage;
   - transport 88px / two rows at 1024.
3. Move:
   - Speed & Key into a 32px pill + popover (UI-6 can finish the popover; UI-5 can keep the sliders
     temporarily but hide the permanent block);
   - master volume into the stem rail header;
   - presets/reset/mute-all/clear-solo into a compact menu or a chip row;
   - practice panel below the stage.
4. Style with the tokens; keep the audio graph, SoundTouch, wake hooks, pan/solo logic unchanged.
5. Add `data-ui="v2"` for rollback.
6. Responsive: two-row transport at 1024; rail 210 at 900; no overlap.
7. Tests: `npx tsc --noEmit`, `make mixer-build`; source assertions for the new order; manual
   playback/seek/restart/stop/mute/solo/pan/speed/key.

**Done when:** the player at 1440/1024 has one clear transport center, no overlapping controls, and
all existing behavior still works. The practice sheet is below the stage, not pushing it.

**Risk:** moving DOM nodes can break `querySelector`/event listeners. Do it in small steps, run the
manual control inventory after each.

---

### UI-6 — Practice sheet + practice popovers (3–4 days)

**Goal:** make the practice surface the reason to use the player.

**Files:** `ui/stem_mixer_component/frontend/src/main.ts`, `style.css`, tests.

1. Build the bottom sheet:
   - drag handle, 40px tab bar, body, expand/collapse, 240–360px;
   - tabs Chords / Sections / Lyrics / Tab;
   - default open at ≥1280, 280 at 1024, collapsed at 900 with a transport toggle.
2. Chord grid:
   - 4 bars/row at ≥1280, 2 at 1024, 1 at 900;
   - bar-number gutter, 4 beat cells, active amber, empty state, chord diagram panel;
   - draft-chords note; click-to-seek.
3. Sections: 44px rows, active rule, loop button, click-to-seek.
4. Lyrics: active line, word highlight, click-to-seek, reason-based empty state.
5. Tab: measure grid, current/next, PDF link, confidence note, empty state, panel-only scroll.
6. Popovers:
   - Speed & Key (sliders, values, reset);
   - Count-in (Off/1/2 segmented);
   - Metronome (on/off, sound, accent/follow if existing);
   - tempo/key pill in the transport.
7. Keep all existing sync code; only change the surface. Verify after seek, loop, speed, key.
8. Tests: existing practice tests; source assertions for tabs/active class; manual sync.

**Done when:** Chords/Sections/Lyrics/Tab work at 1440/1024, the current beat is unmistakable, the
sheet can collapse without hiding the transport, and no empty state says “re-run” when the real
reason is “no vocal stem” or “model unavailable.”

**Risk:** practice sync is time-sensitive; do not change timing code. If a layout change causes a
drift, revert that change and isolate.

---

### UI-7 — Isolate, dialogs, shared components (2–3 days)

**Goal:** Home should not lead into a default Streamlit form.

**Files:** `ui/pages/isolate.py`, `ui/app.py`, `ui/stem_mixer_component/frontend/src/style.css`
(dialog/popover styles), `ui/mix_tabs_component/frontend/src/style.css`,
`ui/region_picker_component/frontend/src/style.css`, tests.

1. Isolate header, upload card, advanced disclosure, primary/secondary actions, progress panel,
   queue. Reuse the existing widgets; style them; do not rewrite the job logic.
2. Export dialog and stems picker: 560px, tabs/sections, focus trap, Esc, primary/secondary.
3. Style the mix-tabs strip and region picker with the tokens; keep the components' behavior.
4. Settings: theme swatches, Interface switch, About/local badge; no new settings semantics.
5. Tests: source assertions; manual forms/progress/queue.

**Done when:** the flow from Home → Isolate → Player feels like one product; no white/default
Streamlit control breaks the surface.

---

### UI-8 — Accessibility, responsive, motion audit (1.5–2 days)

**Goal:** prove it is not just a screenshot.

1. Keyboard-only pass on Home and player; fix tab order, focus return, Esc, shortcuts.
2. Screen-reader labels: table rows, transport, tabs, sliders, chord diagrams, tab alternative.
3. Contrast: run the token script; check actual backgrounds (active row, popover, amber button).
4. 1024 and 900 at 100% and 200% zoom; no horizontal page scroll, no clipped text.
5. `prefers-reduced-motion`: no sheet slide/pulse/skeleton shimmer/button scale.
6. Grayscale screenshot: hierarchy still readable.
7. Touch/pen: 44px targets on icon buttons; no hover-only primary action.
8. Fix findings; re-run the matrix.

**Done when:** the accessibility checklist in `10` §7 passes, with evidence in `08`.

---

### UI-9 — Verification and handoff (1 day)

**Goal:** prove the phase and leave the next agent a clean runway.

1. Run the full automated gate:
   ```bash
   python -m pytest tests/ -q
   ruff check src/audio_to_tab
   cd ui/home_component/frontend && npx tsc --noEmit
   cd ui/stem_mixer_component/frontend && npx tsc --noEmit
   make home-build
   make mixer-build
   ```
2. Run the real Waltz run end to end: Home → Practice → Chords → Sections → Tab → loop/count-in →
   export. Record evidence, not claims.
3. Run the 1024/900 matrix; attach no personal screenshots to the repo.
4. Update `08-EVIDENCE-LOG.md`, `README.md`, `02`, `03`, `05`, `06`, `PROJECT_TREE.md`, `AGENTS.md`.
5. Check `git diff -- web backend` is empty; check no `.env`, audio, model, or `node_modules` staged.
6. Do not commit unless the user explicitly approves.

**Done when:** the acceptance gates in §6 pass and the handoff notes are written.

---

## 5. Build order and estimates

| Task | Estimate | Depends on | Can overlap? |
|---|---:|---|---|
| UI-0 Gate 0 | 0.5–1 d | — | No |
| UI-1 tokens + shell | 2–3 d | UI-0 | With UI-2 |
| UI-2 model + events | 1–2 d | UI-0 | With UI-1 |
| UI-3 Home component | 2–3 d | UI-1, UI-2 | No |
| UI-4 Home states/queue | 2–3 d | UI-3 | No |
| UI-5 player shell | 3–4 d | UI-1 | With UI-4 only if different files |
| UI-6 practice sheet | 3–4 d | UI-5 | No |
| UI-7 Isolate/dialogs | 2–3 d | UI-1, UI-5 | With UI-6 |
| UI-8 audit | 1.5–2 d | UI-4/6/7 | No |
| UI-9 verification | 1 d | all | No |

**Total:** ~18–24 working days for one developer plus agents; plan 3–4 weeks. The critical path is
UI-1 → UI-3 → UI-5 → UI-6 → UI-8.

Rules:

- Do not run the player and Home component builds in parallel in the same working tree without
  coordinating the committed build assets.
- Do not start UI-5 until UI-3 passes 1024; otherwise you will be fixing the same overflow twice.
- Do not start UI-7 before the player transport is stable; dialogs share the token/layer system.

---

## 6. Test plan

### 6.1 Automated

```bash
# targeted
python -m pytest tests/test_design_tokens.py tests/test_home_model.py \
  tests/test_home_component.py tests/test_home.py -q
python -m pytest tests/test_stem_mixer_component.py -q

# component type/build
cd ui/home_component/frontend && npx tsc --noEmit && npm run build
cd ui/stem_mixer_component/frontend && npx tsc --noEmit
make home-build
make mixer-build

# full gate
python -m pytest tests/ -q
ruff check src/audio_to_tab

# new contrast/token checker
python scripts/check_ui_tokens.py
```

`web/` checks are **not** required because `web/` is not touched. If the agent edits `web/`,
that is a scope violation; stop and revert.

### 6.2 New tests

**`tests/test_design_tokens.py`**

- default Tyrian tokens include every required semantic key;
- all **actual** text/surface pairs pass 4.5:1 (large text 3:1); muted is not allowed on
  `bg-hover`/`bg-active`, where metadata switches to secondary;
- disabled is exempt but present;
- alternate theme preset returns a complete set;
- `tokens_to_css()` emits parseable custom properties;
- `component_theme()` has no `None` values;
- generated type weights are only 400/500/700 (no 300/600/900).

**`tests/test_home_model.py`**

- empty, one row, six rows, forty rows;
- title/source/age/analysis formatting;
- statuses ready/needs-analysis/analysing/failed;
- opaque IDs are stable and differ by run;
- `to_dict()` contains no `run_dir`, absolute path, username, or filename;
- unknown IDs rejected;
- long English/Japanese titles are preserved, not truncated in the model;
- recents max 6, rows max 40;
- counts match.

**`tests/test_home_component.py`**

- `ui/home_component/frontend/build/index.html` exists;
- at least one hashed JS and CSS asset;
- no `localhost`/`127.0.0.1`/dev-server URLs in the build;
- event type strings are present in the source/build;
- Python wrapper imports the component and passes `model`/`theme`;
- no `web/` or `backend/` imports;
- `AGENTS.md`/`PROJECT_TREE` mention the build (source-level).

**`tests/test_home.py`**

- V2 flag off → legacy path; on → component wrapper;
- event handling for open/practice/analyse/navigate;
- nonce replay ignored;
- invalid ID ignored;
- analysis guard when worker busy;
- flash/rerun behavior.

**`tests/test_stem_mixer_component.py`**

- build exists and is complete;
- source contains the practice sheet/tab/transport hooks;
- no audio-engine changes are required (source assertions only).

### 6.3 Manual matrix

| Check | 1440 | 1280 | 1024 | 900 |
|---|---|---|---|---|
| Home action deck fits | | | | |
| Recents rail scrolls, no squash | | | | |
| Library table readable | | | | |
| No horizontal page scroll | | | | |
| Player transport fits | | | | |
| Practice sheet no overlap | | | | |
| Chords/Sections/Lyrics/Tab | | | | |
| Loop/count-in after seek | | | | |
| Speed/key sync | | | | |
| Export matches playback | | | | |
| Keyboard/focus | | | | |
| 200% zoom | | | | |
| Reduced motion | | | | |
| Empty/no lyrics/no tab | | | | |
| 40 rows | | | | |

### 6.4 Performance budgets

- Home component JS+CSS: target <150KB uncompressed, <50KB gzip (excluding any font assets). If
  fonts push it, use the system stack inside the iframe and keep Satoshi in the shell.
- No audio decoding on Home. Recents art is CSS/SVG or a deterministic motif, not a waveform read.
- 40-row table: first render <100ms after model arrival on the reference machine.
- No layout shift after fonts load: preload the shell font; component font-display swap/optional.
- No memory growth after repeated Home reruns (event listeners cleaned up; `ResizeObserver`
  disconnected on unload).

---

## 7. Acceptance gates

**2026-10-21:** the Home gate is §12.10 and §11. A 216px sidebar is not a pass.

### Gate A — Shell (after UI-1)

- 1440/1024: sidebar 240/216, no gap/overlap, no horizontal overflow.
- No Streamlit header/deploy/footer/promo; nav icons; focus ring visible.
- Body text parchment; amber only for active/primary/signal.
- Token/contrast test green.
- Screenshot evidence recorded in `08`.

### Gate B — Home (after UI-4)

- 1440/1024: action deck, recents rail, table, search, queue all fit.
- 1024: no clipping; recents scroll; table hides Updated; action visible.
- Empty/6/40/long titles/no analysis/running/failed states pass.
- Open/practice/analyse/search/cancel/retry work.
- No path leakage; nonce replay ignored.
- Component build/test green.

### Gate C — Player (after UI-6)

- 1440/1024: rail, timeline, waveform, sheet, transport do not overlap.
- Play/stop/restart/seek/mute/solo/pan/speed/key/metronome/loop/count-in still work.
- Chords/Sections/Lyrics/Tab align after seek/loop/speed/key.
- Practice sheet can collapse/expand; transport remains visible.
- Real Waltz run passes.

### Gate D — Accessibility/responsive (after UI-8)

- Keyboard-only Home → Practice → Chords → Tab → Export.
- Focus returns from dialogs; no trap.
- All text ≥4.5:1; status not color-only.
- 900/1024/1440 no page horizontal scroll; 200% zoom usable.
- Reduced motion removes sheet/pulse/scale.
- Screen-reader labels present for table/transport/tabs/sliders.

### Gate E — Final (after UI-9)

- Full pytest/ruff/components green.
- No `web/`/`backend/` diff; no engine changes.
- Real song evidence and screenshots recorded.
- Docs updated; no commit without approval.
- README status says “Phase 1.5 implemented, manual checklist pending” rather than “shipped” until
  the listening/install gate passes.

---

## 8. Rollback and safety

- **Home:** `AUDIO_TOOLS_UI_V2=0` → legacy Home. Keep the old code for one release, then delete.
- **Player:** remove `data-ui="v2"` from the mixer root → old CSS/layout. Keep the same IDs and
  listeners so the audio engine never depends on the presentation.
- **Tokens:** if a theme preset fails contrast, fall back to the Tyrian semantic tokens for that
  preset; do not ship an unreadable theme.
- **Shell:** if a Streamlit update breaks selectors, reduce the override set; keep the product-owned
  CSS and the component; do not patch Streamlit internals with JS.
- **Data:** no migration. If the Home component fails to load, the page shows a readable error and
  the legacy link/flag; it does not delete or modify runs.
- **Analysis action:** never auto-run on Home load. It is explicit, guarded by `worker_busy()`, and
  uses the existing serial worker.

---

## 9. Risks and stop conditions

| Risk | Mitigation / stop |
|---|---|
| Sidebar width/full-bleed component breaks at 1024 | Gate 0 spike; fallback to native Home; do not force. |
| Iframe double scrollbar / blank height | Content height + `ResizeObserver`; test at 40 rows; if still broken, use native table fallback. |
| Streamlit selector drift | Pin the selectors in one shell CSS block; visual smoke after every Streamlit bump; no JS DOM patching. |
| Player DOM move breaks audio bindings | Control inventory before/after; small commits; manual play/seek/loop after each; revert structure if it drifts. |
| Practice sync drifts | Do not change timing code; layout only; test after seek/speed/key. |
| Home component adds too much JS | No framework; vanilla TS; budget <150KB; no audio/font duplication. |
| Theme presets fail contrast | Derive tokens; test default + one alternate; fall back to Tyrian. |
| 1024 still clips after two attempts | Stop; fix layout before any more polish; do not ship. |
| Scope creep into filters/editing/capo | 10 §10 non-goals; P2 only. |
| Two UI experiments (desktop + web) | Do not edit `web/`; web parity is P2. |
| New dependency/font/model | Gate 0; ask before adding. |
| Personal data in screenshots | `/tmp` only; redact titles; never commit images. |
| Build drift / hand-edited hashed assets | `make home-build`/`mixer-build`; `tests/test_*_component.py`; never hand-edit `build/`. |

**Stop conditions:**

- Gate 0 fails and the fallback is not acceptable.
- Any change requires editing the audio engine or `web/`/`backend/`.
- A new dependency/model/font is needed.
- The player loses a control or a timing behavior after two attempts.
- The 1024 layout still clips after two attempts.
- The user asks to commit/push; that is a separate approval, not part of this plan.

---

## 10. Agent prompt

Use the Phase 1.5 prompt in `07-BUILD-PROMPT.md` §Part B. Do not paste both the Phase 1 and Phase 1.5
prompts into the same session; they have different scopes and stop conditions.

Short form, for Cursor/OpenCode:

```markdown
You are implementing Phase 1.5 (desktop UI craft) only. Read AGENTS.md, PROJECT_TREE.md,
docs/plans/moises-parity/10-MOISES-UI-CRAFT.md, and 11-DESKTOP-UI-REDESIGN.md.

MODE: BUILD. Desktop only. Do not edit web/ or backend/. Do not change src/audio_to_tab, the audio
graph, pan/solo laws, analysis, export semantics, metronome timing, or wake hooks.

Start with UI-0 in §12. Prove a 240px sidebar and a full-bleed Home component at 1440 and 1024.
Do not build a 216px rail. If Gate 0 fails, stop and use the §12 fallback.

Build the §12 task order, not the older UI-5/UI-6 player tasks. Home tokens are `10` §13.
Keep Satoshi and the Audio Tools logo. Do not clone Moises assets. Do not retint `theme_presets.py`.

Rules:
- No new dependency without Gate 0 approval.
- No commit, push, tag, or PR without explicit approval.
- Run the targeted tests and `npx tsc --noEmit` after each task; full pytest/ruff at each gate.
- Rebuild committed frontend assets with `make home-build`/`make mixer-build`; never hand-edit build/.
- Stop at Gates A–E and report evidence, not claims.
```

Full prompt: `07-BUILD-PROMPT.md` §Part B.

---

## 12. Revised Phase 1.5 — Home parity (2026-10-21)

**Goal:** the desktop Home matches the measured Moises Home in layout, density, control placement, and states, using Audio Tools’ name, logo, Satoshi, and original icons.

**Architecture:** Streamlit shell plus a vanilla TypeScript Home component built with Vite and `streamlit-component-lib`, same pattern as the mixer. No React. No new framework. The mixer iframe is not restyled in this phase.

**Tech:** Python 3.11, Streamlit 1.59.1 (installed), Vite 5 (`^5.2.0` on the mixer), `streamlit-component-lib` `^2.0.0` (mixer `package.json`). Context7 Streamlit docs describe components v2 as the recommended no-iframe API (`st.components.v2.component` exists in 1.59.1) and v1 as the supported iframe API. Vite 5.4 library mode is the documented way to emit a browser bundle. There is no Context7 library for `streamlit-component-lib`; the mixer already calls `Streamlit.setComponentValue` and `Streamlit.setFrameHeight` from `RENDER_EVENT`.

### 12.1 Scope and non-goals

In scope: the Home route and the sidebar/header chrome needed for the Home geometry, behind `AUDIO_TOOLS_UI_V2`, for one release.

Out of scope: player/mixer visual redesign, Isolate redesign, global `theme_presets.py` edits, new fonts, new icon packages, new Python dependencies, `web/`, `backend/`, engine changes, setlists, paywall, and multi-select.

### 12.2 Architecture re-evaluation

Stay on the v1 iframe. The mixer already ships that way, and the Home component can own its background so the measured neutrals do not require a global theme change.

Gate 0 must prove the iframe can sit flush under a 240px sidebar at 1440 and at 1024, with no page-level horizontal scroll. If it cannot, stop. Do not silently switch stacks. The fallback is a native Streamlit Home plus CSS, and the parity that fallback loses (fixed 150px recent cards, 56px table, inner horizontal rails) must be written into `08` before any further Home tasks. Streamlit components v2 is an approval gate at that stop, not a quiet substitution: it is already installed, it is not an iframe, and it is a different API from the mixer.

### 12.3 Gate 0

Prove, with a throwaway component that is deleted or kept only if the gate passes:

- At 1440×1000 the sidebar is 240px and the component’s left edge is 240px.
- At 1024×768 the sidebar is still 240px and the component is not wider than the remaining viewport.
- The component receives a JSON props object and returns a JSON event.
- No `run_dir` string appears in the iframe document or the component props.

Record the pass or the fallback in `08`. Do not start UI-1 until that note exists.

### 12.4 Files

| File | Action | Role |
|---|---|---|
| `ui/pages/home.py` | Modify | When the flag is off, keep today’s Home. When on, render the component |
| `ui/app.py` | Modify | Flag-only CSS: sidebar 240, hide `stHeader`, nav row 36px. Do not change the default theme |
| `ui/design_tokens.py` | **Planned. Does not exist** | Home token dict only. Not imported by the mixer |
| `ui/home_component/__init__.py` | **Planned** | `components.declare_component` |
| `ui/home_component/frontend/` | **Planned** | Vite + vanilla TS. Mirror the mixer’s build, without its audio dependencies |
| `tests/test_home.py` | Modify | Flag off still renders today’s buttons. Flag on does not put `run_dir` in component args |
| `tests/test_home_component.py` | **Planned** | Committed build exists, same style as the mixer build test |
| `scripts/dev.sh`, `scripts/dev.ps1` | Modify | `home-build` target. Makefile only delegates |
| `ui/theme_presets.py` | No | Global tokens stay |

### 12.5 Data contract

The browser receives opaque tokens. The server maps them in `st.session_state` and resolves paths only in Python.

```python
# planned shape, not an existing type
{
  "nonce": "<per render>",
  "product": "Audio Tools",
  "cards": [{"id": "learn", "title": "Learn a song", "subtitle": "New track", "primary": True}],
  "recents": [{"token": "<opaque>", "title": "<redacted in logs>", "age": "3 months ago"}],
  "rows": [{"token": "<opaque>", "title": "...", "subtitle": "105.5 BPM · C", "age": "3 months ago", "action": "practice"}],
}
```

Events back to Python: `{"nonce", "type", "id"}` where `type` is `open_card`, `open_recent`, `open_row`, `practice`, or `analyse`. Ignore a stale nonce. `open_card` ids are the fixed strings `learn`, `youtube`, and `tab`. Song tokens are keys into the session map. Never put `run_dir` or an absolute path in the args.

### 12.6 Component tree

Order, matching §13.2 of `10`:

1. Rail (shell, not inside the iframe): logo lockup, collapse, nav, Lite/Pro, edition caption.
2. Action cards.
3. Recents heading and rail.
4. Files heading, All pill, search, sort button, table.

The iframe paints 2–4. The shell paints 1 and the page background `#101213` while the flag is on, so the iframe and the rail share one background.

### 12.7 Placement

Use the tables in `10` §13.4–§13.8. Do not invent a second set of pixels. Implementation checks:

| Control | Rule |
|---|---|
| Three action cards | Height 100, radius 8, gap 12, icon 20 at inset 20,16, label 16/24 weight 500 on one line |
| Card width | `(rail inner width − 24) / 3`. At 900 with the 13px inset they stay fully visible. If a card would be under 140px, the rail scrolls instead of shrinking further |
| Recents | 150×210, gap 12, art block 150×150, title and age nowrap with ellipsis. Scroll buttons 24×24. No scroll-snap |
| Table | Row 56. Columns: Title (name + subtitle), Created (age, 116px), action 32×32. No Type or Duration column until the run has that metadata |
| Search | 315×32, radius 6, placeholder `Search` |
| All pill | 32px tall, radius 9999, selected colors from §13.9 |
| Content inset | 33px when the viewport is wider than 1124px, else 13px. Rail stays 240 |

### 12.8 States, keyboard, and responsive

Responsive rules are `10` §13.5. Additional behavior:

- Empty library: cards and an empty Files region whose only line is “No songs yet.”
- No search hits: “No songs match that search.” Clearing the field restores the rows.
- Loading: three 56px skeleton rows. The shell stays visible. No full-page spinner.
- Analyse failure: an inline alert above the table using the existing `home_flash` message. `role="alert"`.
- Menus: min-width 180, radius 8, surface `#17191C`, row height 32. Esc and a click outside close the menu and return focus to the opener. This menu geometry was **not** measured on Moises.
- Tab order: collapse, logo, nav, Lite/Pro, cards, recents, search, sort, table rows.
- Keys: Enter and Space activate. Esc closes the open menu. No new Home shortcuts.
- Reduced motion: transitions 0ms under `prefers-reduced-motion`.
- Hit targets: painted collapse glyph is 16px; the button is 24×24. Kebab hit target is 32×32.

### 12.9 Tests

```python
def test_home_v2_props_have_no_run_dir(monkeypatch):
    monkeypatch.setenv("AUDIO_TOOLS_UI_V2", "1")
    # render the Home props builder once it exists
    props = build_home_props(rows=[{"run_dir": "/tmp/secret/song", "title": "x"}])
    assert "run_dir" not in json.dumps(props)
    assert props["rows"][0]["token"]
```

```python
def test_home_build_is_committed():
    build = Path("ui/home_component/frontend/build")
    assert (build / "index.html").is_file()
    assert list((build / "assets").glob("index-*.js"))
```

Also assert token contrast: every Home text token on `#101213` is ≥ 4.5:1 except the recorded meta exception, which UI-1 must either lift or document as a waived 12px meta. The muted group label must be lifted. Nav weight in the flag CSS is 400 or 500, never 600.

Commands the implementer runs:

- `python -m pytest tests/test_home.py tests/test_home_component.py -q`
- `cd ui/home_component/frontend && npx tsc --noEmit`
- `make home-build` once the target exists
- At the phase gate, `pytest tests/ -q` and `ruff check src/audio_to_tab`

### 12.10 Tasks

- [x] **UI-0 Gate 0.** Depends on nothing. Spike the iframe width. Acceptance: §12.3. Rollback: delete the spike.
- [x] **UI-1 Tokens and flag shell.** Depends on UI-0. Add planned `ui/design_tokens.py` and the flag CSS in `ui/app.py`. Acceptance: with the flag on, sidebar is 240 and the header bar is hidden; with it off, sidebar is still 300. Do not edit `theme_presets.py`.
- [x] **UI-2 Contract.** Depends on UI-0. Props builder and nonce check. Acceptance: the test in §12.9 fails before the builder exists and passes after. Rollback: flag off.
- [x] **UI-3 Layout.** Depends on UI-1 and UI-2. Planned `ui/home_component/` sections in §12.6 at the §12.7 sizes. Acceptance: DOM order matches §12.6 and the 1440 card/recent/table boxes match `10` §13.4 within 2px.
- [x] **UI-4 States.** Depends on UI-3. Empty, no-results, loading, alert, menu, ellipsis. Acceptance: §12.8 copy and focus return.
- [x] **UI-5 Icons and lockup.** Depends on UI-3. Original filled icons at the sizes in `10` §13.11. Acceptance: no new dependency in `package.json`; Learn icon color `#75EBF5`; other card icons `#E9EEF5`.
- [x] **UI-6 Responsive.** Depends on UI-3. Four viewports and the 1124px inset switch. Acceptance: no page horizontal scroll; recents stay 150px wide; at 1024 the fourth recent may clip only inside the rail.
- [x] **UI-7 Keyboard.** Depends on UI-4. Tab order, Esc, 24px collapse hit target, reduced motion. Acceptance: a keyboard-only pass opens a card and closes a menu.
- [x] **UI-8 Build and tests.** Depends on UI-3. `home-build`, committed hashed assets, `tsc`, pytest. Acceptance: §12.9 commands are green.
- [x] **UI-9 QA and rollback.** Depends on UI-4 through UI-8. Capture 1440, 1280, 1024, and 900. Confirm flag off restores today’s Home. Write the measurements into `08`. Acceptance: the gap rows in `10` §13.13 that are marked 1.5 are closed, or the miss is written down.

### 12.11 Flag and rollback

`AUDIO_TOOLS_UI_V2` defaults on and enables the shell CSS and the component. Set it to `0` for the old Home. Do not delete `home.py` in this phase.

### 12.12 Risks and approval gates

| Risk | What to do |
|---|---|
| Iframe cannot be full-bleed | Stop at Gate 0. Fallback or an approved v2 spike. Do not pretend the pixels fit |
| Theme leak | Home tokens stay in the component and the flag CSS. Global preset change is a separate approval; the blast radius is §13.9 of `10` |
| Font or icon package | Not approved. Satoshi and original icons only |
| 1024 | Current Home no longer page-clips, but it squashes recents. The new rail must scroll instead |
| Streamlit header | Hide under the flag. The promo string was absent on 2026-10-21; keep the deploy-button rule anyway |
| Component state | Nonce plus session token map. A rerun that drops the map must ignore stale events |
| Performance | Do not mount the mixer inside Home. Skeleton rows instead of a blocking spinner |
| Player looks different | Accepted until Phase 1.6 |
| Collapsed rail | Do not guess a 72px rail. Hide to 0 |

---

## 11. Definition of done

The Home exit is §12. The player checkboxes below are **not** required for Phase 1.5.

- [x] Gate 0 recorded in `08` §13. Sidebar 240 and the Home component flush at 1440 and 1024, or the fallback’s parity loss is written down.
- [x] Home tokens live in the planned `ui/design_tokens.py` and the flag CSS. `theme_presets.py` is unchanged.
- [x] Home component built and covered by the build test. Commit only when the user asks.
- [x] 1440, 1280, 1024, and 900 match `10` §13 within 2px for rail, card height, recent card size, and row height. No page-level horizontal scroll.
- [x] Empty, no-results, loading, and alert copy from `11` §12.8. No-results was exercised in the browser. Empty, skeletons, and the analyse alert were not.
- [x] Flag off restores the current Home, including the 300px sidebar.
- [x] Keyboard order, Esc, focus return, reduced motion, and the lifted group-label contrast pass. Esc and focus return were exercised. The full Tab walk and an OS reduced-motion toggle were not. Contrast is unit-tested.
- [ ] `pytest`, Home `tsc`, and `home-build` are green. Home `tsc` and `home-build` passed. `pytest tests/ -q` was 1035 passed, 1 skipped, and `tests/test_api.py::test_upload_and_job` failed. That failure is the macOS basic-pitch case CI already deselects. It was not changed.
- [x] No `web/`, `backend/`, or engine edits. No new font or icon package.
- [x] Player restyle is not part of this exit. It remains Phase 1.6.
- [x] No commit, push, tag, or PR without explicit approval.

**Not done until the evidence is in `08-EVIDENCE-LOG.md`.** A screenshot in `/tmp` is not evidence for
the repo until its measurements/redacted findings are written down.
