# Roadmap — desktop first, website second, Studio last

**Estimates** assume one developer plus agents, a working desktop build, and the existing test suite.
They are planning ranges, not promises. The order matters more than the dates.

**Rules:** every phase ends with a demo on a real song, a test run, and a written decision. No phase
starts because it is exciting; it starts because the previous gate passed.

## Dependency graph

```
P0  Spikes + schema
      |
P1  Song Workbench (desktop)
      |
P1.5 Desktop Home parity (measured Moises Home; player visuals wait)
      |
P1.6 Desktop hardening / installer / packaged lyrics / 3-song regression
      |
P2  Practice parity (desktop) ──► P2.5 Web parity
      |
P3  Studio go/no-go (buy / partner / build)
      |
P4  Studio MVP (only if go)
      |
P5  Platform: mobile, VST, Live, cloud/collab
```

The website is a **copy**, not a second design. Port the desktop practice player to `web/` after the
desktop interaction is stable. Do not run two UI experiments at once.

**Why UI craft comes before hardening:** the installer should freeze the final shell, not a design
that is about to change. Phase 1.5 is a presentation/recomposition pass; Phase 1.6 then packages that
surface, adds the first-run model download, and decides whether lyrics ship in the freeze.

---

## Phase 0 — Decide the analysis stack (3–5 days)

**Goal:** replace guesses with measured choices. No product code beyond throwaway scripts.

| Task | Output | Gate |
|---|---|---|
| 0.1 Pick 3 reference songs (clean guitar, dense mix, quiet intro) | `_work/spike-songs.md` (local paths only; not committed audio) | Three songs cover the failure modes |
| 0.2 Chord-model spike | Accuracy on a 60–90 s labelled section, CPU time per minute, model size, licence | ≥70% weighted chord accuracy and ≤1.5× real time on the reference CPU, or fall back to templates |
| 0.3 Lyrics-model spike | Word-timestamp quality, language coverage, model size, licence, download path | Word-level timestamps usable; install/download ≤ ~500 MB; SHA256 `urllib` path works |
| 0.4 Section algorithm spike | Boundary quality on the three songs; label heuristic | Sections are useful enough to navigate; labels can be user-edited later |
| 0.5 Schema + cache design | `analysis.json` schema, versioning, invalidation rules | One song's analysis round-trips; changing the model version invalidates cleanly |
| 0.6 Privacy/licence review | Model and weight licences; no cloud calls | Every chosen model is redistributable or download-on-demand with pinned hashes |

**Decision record:** `docs/plans/moises-parity/_work/analysis-decision.md` with the chosen model, the
rejected options, and the measured numbers. If a spike fails, the roadmap does not stop: chords or
lyrics move to P2 explicitly.

---

## Phase 1 — Song Workbench (2–4 weeks)

**Goal:** one real song, end to end, locally: import → separate → analyse → practise with chords,
sections, tab, count-in, loop → export a matching mix and a tab PDF.

### 1A — Project manifest + analysis artifact

- Extend the existing run directory with `project.json` (source, stems, mixer state, artifacts) and
  `analysis.json` (schema version, model versions, BPM, key, beats, chords, sections, lyrics, warnings).
- Add a loader that tolerates missing/old artifacts; never block the mixer because analysis is missing.
- Add a cache key: source hash + model versions + settings. Re-analysis is explicit, not automatic.
- **Gate:** reopen an old run, see the same stems/mixer state, and read the cached analysis without
  recomputing.

### 1B — Analysis core

- BPM/key/beats: reuse the existing tempo/metronome code; expose a stable result object.
- Chords: chosen P0 model; produce `ChordEvent(start, end, symbol, confidence)`; merge tiny gaps.
- Sections: self-similarity + boundary detection; label with a conservative heuristic; confidence.
- Lyrics: only if the P0 gate passed; word-level timestamps; English first, language field in the schema.
- Every stage reports progress and can be skipped; all failures are warnings, not crashes.
- **Gate:** the three reference songs produce a usable analysis in the serial worker; no UI thread
  blocking; cache hit is instant.

### 1C — Practice player panels

- Extend the existing mixer iframe, not a new player:
  - **Chords:** bar/beat grid, current chord highlight, chord diagrams, capo display (read-only).
  - **Sections:** list with start/end, click-to-seek, loop button.
  - **Lyrics:** line/word highlight, click-to-seek (if P1 lyrics passed).
  - **Tab:** on-screen tab with current-bar highlight, PDF download.
- Keep the existing stem rows, pan, speed/key, metronome, picture, and save flow. Add a collapsible
  right panel; below the stems on narrow windows.
- **Gate:** playback time, chord highlight, section highlight, lyric highlight, and tab bar stay
  aligned after seek, loop, speed change, and key change.

### 1D — Practice controls

- Count-in: 1/2 bars, audible, respects the current tempo and meter; does not leak into the exported mix
  unless “include count-in” is on.
- A/B loop: drag handles on the waveform; loop region survives seek; section loop uses the same code.
- **Gate:** loop + count-in work with speed/key changes and with the metronome on/off.

### 1E — Tab integration

- Reuse the existing tab pipeline on the isolated guitar stem (not the full mix).
- Store `tab.json` + `tab.pdf`; show the tab in the player; keep the existing Tab PDF page working.
- Add a clear empty/confidence state when the guitar stem is silent or the transcription is weak.
- **Gate:** tab PDF and on-screen tab are generated for all three reference songs; no double
  transcription when the user opens the Tab PDF page.

### 1F — Export parity + polish

- Desktop mix export: include pan (and verify master/mute/solo/speed/key).
- Web is **not touched in Phase 1**. Its export still omits speed/key; record the required honest warning
  as a Phase 2 task and do not edit `web/` now. Do not let the desktop work silently claim web parity.
- Add tab PDF and MIDI to the project's download surface; keep stems and mix formats.
- Add “Learn” as the primary Home action; opening a completed project goes straight to the practice
  player.
- **Gate:** a desktop user cannot produce an export that differs from playback. Manual A/B on all three
  songs.

### Phase 1 exit criteria

- [ ] Three reference songs complete the flow without a terminal.
- [ ] `pytest` green; new analysis tests cover schema, cache, chord merge, section boundaries, timestamp
      mapping, and failure paths.
- [ ] `ruff check src/audio_to_tab` green.
- [ ] `web/` unchanged in Phase 1; its known export warning is documented for P2.
- [ ] Mixer/region-picker/mix-tabs builds regenerated and committed **only if** the user approves a
      commit; otherwise left as working-tree changes.
- [ ] Network-off playback works after models are installed.
- [ ] Installer smoke test on macOS; Windows if the change touches packaging.
- [ ] `PROJECT_TREE.md` updated for new modules/artifacts.

**Status 2026-10-21:** automated gate green after the final review (`1030 passed, 1 skipped`; ruff
clean; mixer tsc/build clean); a real Waltz run completed end to end; tab PDF link fixed; lyrics UI
path verified in dev. The three-song regression, network-off, 8 GB Mac, and installer checks remain
open. Do not mark Phase 1 “shipped” yet. See `06` §Verification and `08` §12.

---

## Phase 1.5 — Desktop Home parity (2026-10-21)

**Goal:** the desktop Home matches the measured Moises Home. No new practice feature. No engine change. No global theme change.

**Read:** `10-MOISES-UI-CRAFT.md` §13 for every pixel, and `11-DESKTOP-UI-REDESIGN.md` §12 for the tasks. Earlier sections of those files are history where §13 and §12 disagree.

### 1.5A — Gate 0

- Prove a v1 iframe Home can be full-bleed beside a 240px sidebar at 1440 and 1024.
- No new dependency. Vite and `streamlit-component-lib` stay the mixer’s versions.
- If the iframe cannot do it, stop. Native Streamlit Home is the fallback and must record what parity it loses. Components v2 is an approval gate, not an automatic switch.

### 1.5B — Home shell

- Flag `AUDIO_TOOLS_UI_V2`, default on. `0` restores the old Home.
- Sidebar 240px at 1440, 1280, 1024, and 900. Nav rows 216×36, 16px filled icons, weight 400.
- Home-scoped neutrals from `10` §13.9. Satoshi. Do not edit `theme_presets.py`.
- Hide the 60px Streamlit header under the flag.

### 1.5C — Home surface

- Three 100px action cards, gap 12, radius 8.
- Recents 150×210, horizontal scroll, no snap.
- Files table, 56px rows, search 315×32, selected All pill.
- Inset 33px above 1124px viewport width, else 13px.

### 1.5D — Player

Not in this phase. The mixer stays as it is until Phase 1.6. The old player bullet list is historical.

### 1.5E — Home audit

- Keyboard order, visible focus, reduced motion, contrast ≥4.5:1 for the group label.
- No page-level horizontal scroll at 900, 1024, 1280, or 1440.
- Flag off restores today’s Home.

**Gate:** Gate 0 passed or the fallback is written down; the four viewports match `10` §13 within 2px for rail, cards, recents, and row height; `pytest` and the Home component `tsc`/build are green. Evidence goes in `08` §13.

**Not in Phase 1.5:** player restyle, Isolate restyle, chord/lyric editing, capo, setlists, batch, web parity, packaged lyrics, new models, new fonts, new icon packages, or a DAW.

---

## Phase 1.6 — Desktop hardening (2–4 days)

Not a feature phase. Make the finished surface survive real users.

- Installer size and first-run model download UX.
- Packaged lyrics decision: include `faster-whisper` + the pinned model, or ship without lyrics and
  label the tab. The dev path exists; the freeze does not collect it yet.
- Failure states: missing model, corrupt analysis, silent guitar stem, long file, low disk.
- 8 GB Mac regression: analysis + separation serial, memory ceiling respected.
- Crash/log bundle includes analysis version, model version, and cache key (no audio, no lyrics).
- Installer smoke on macOS; Windows if packaging changes.

**Gate:** a clean install on a fresh machine completes one song, including the model download, without
a terminal. The UI gate is already green before packaging starts.

---

## Phase 2 — Practice parity and polish (2–4 weeks)

**Goal:** match the consumer practice surface and remove the rough edges. Still no DAW.

- Chord/lyric/section **editing** (the analysis is a draft, the user is the authority).
- Capo, alternate tunings, chord difficulty/voicing simplification.
- Chord-chart PDF export (Moises has it; we do not).
- Setlists/queue, library filter/sort, delete/undo.
- Web parity: port the practice player and analysis panels to `web/`; keep the shared schema.
- Batch/queue for desktop (serial, explicit).
- Localization scaffolding; accessibility polish.
- Resolve the 8 pre-existing `web/` TypeScript errors and any debt found in P1 (only if touching that surface).
- **Gate:** matrix rows marked P2 are green or explicitly deferred with a reason; 10-song regression;
  desktop and web produce the same analysis JSON for the same source.

---

## Phase 3 — Studio go/no-go (2 weeks)

**Goal:** decide whether Studio is a product we build, buy, or refuse.

- Licence/terms review: OpenDAW and at least one commercial web-DAW SDK.
- Vendor shortlist: stem/sample generation, voice conversion, mastering.
- 2-week prototype: open a project, play a stem, arrange two clips, export a mix. No AI, no collab.
- Cost model: engineering months, hosting per user, model credits, support.
- User research: would our guitar users pay for Studio, or is it a different buyer?

**Gate:** a written go/no-go with a recommendation. **Default answer is no** unless the prototype and
the cost model both clear the bar. If no, close P3 and invest in P2 polish and distribution.

---

## Phase 4 — Studio MVP (3–6 months, only if go)

Split into two releases so the first one is usable:

**4A — DAW core:** timeline, tracks/groups/buses, audio clips, split/trim/fade, automation, markers,
undo/version history, mixdown/stem export. No MIDI editor, no VST hosting yet.

**4B — AI + collaboration:** stem/sample generation, voice conversion, mastering, Auto Mix, real-time
sessions, roles/presence/chat, comments. Each capability has its own cost/rights gate.

**Gate for each:** a real project can be completed and exported; collaboration latency and conflict
handling are measured, not assumed.

---

## Phase 5 — Platform (later, optional)

- Mobile companion (practice-first, shares analysis JSON and project manifest).
- VST/AU/AAX plugin (stems first).
- Moises Live-style system-audio mode (separate app).
- Cloud sync/accounts/billing, only if the local product has demand and the costs are understood.

---

## What runs in parallel

- P0 spikes can run in parallel; they write separate decision notes.
- P1 analysis and P1 UI can overlap once the schema is frozen: UI uses fixture JSON before the real model
  lands.
- P1.5 tokens/shell and the Home model can overlap (UI-1/UI-2) once Gate 0 passes.
- P2 web parity can start when the desktop interaction stops changing.
- P3 vendor research can run in the background during P2, but no Studio code is written before the gate.

## What never runs in parallel

- Heavy separation and heavy analysis on the same 8–16 GB machine.
- A desktop UI rewrite and a web UI rewrite.
- Home and player component builds in the same working tree without coordinating committed assets.
- Packaging/installer work before the P1.5 UI gate; the installer would freeze a moving surface.
- Studio and practice-player feature work with the same small team.

## Release gates (commands)

```bash
# shared engine
python -m pytest tests/ -q
ruff check src/audio_to_tab

# web (only if web changed)
cd web && npm test
cd web && npx tsc --noEmit

# desktop frontend components (only if changed)
make mixer-build
make region-picker-build
make mix-tabs-build
make home-build

# typecheck the changed components (no repo-wide gate exists)
cd ui/home_component/frontend && npx tsc --noEmit
cd ui/stem_mixer_component/frontend && npx tsc --noEmit
```

CI runs only pytest + ruff. The other gates are manual and must be reported with evidence. `web/`
checks are not part of P1.5 because `web/` is not touched.

## Roadmap anti-goals

- No phase that exists only to “catch up” on a feature nobody using the practice flow asked for.
- No cloud dependency in the core loop.
- No model that cannot be pinned, licensed, and downloaded locally.
- No Studio work before the P3 gate.
- No commit, push, tag, or PR without explicit approval in that conversation.
