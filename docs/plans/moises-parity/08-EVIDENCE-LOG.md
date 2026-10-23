# Evidence log — Moises 2.0.18 runtime + public research (2026-10-19, UI pass 2026-10-20)

This is the audit trail behind `01-MOISES-SURFACE.md`, `02-CURRENT-STATE.md`, and
`03-FEATURE-MATRIX.md`. It separates what was **observed**, what was **bundle-observed**, what is
**public-source**, and what is **inferred**.

## 1. Scope and safety

- The installed Moises app was inspected on the user's machine with a local Chrome DevTools Protocol
  port. The account was already signed in on a Free plan.
- Existing projects/library entries were opened read-only. No separation, export, delete, purchase,
  rename, or upload was triggered.
- No Moises source code or assets were copied into this repo. Only feature labels, DOM text, prices,
  and screenshots for analysis were read.
- The app was launched with `--remote-debugging-port=9222`. That is a local development flag, not a
  product change. The app should be returned to Home and quit after the pass.
- The user's library contains personal data (60 files, Japanese titles). Screenshots and raw DOM were
  kept in `/tmp` and are **not** committed. The docs use redacted IDs and no personal track titles.

## 2. Environment

| Item | Value |
|---|---|
| App | `/Applications/Moises.app` |
| Version | 2.0.18 |
| Electron | 43.4.1 |
| Chromium | 150 |
| ASAR SHA256 | `5dc37ecac6601fdf9e07af7029560f6e6cc9294b66e1bd79cdf7a6418a548721` |
| ASAR size | 61,150,158 bytes |
| Previous recorded 2.0.3 ASAR | `8c244bb62ecd4725625225b8edccdc4f56bb5e9831a2e48776349979acb20827`, 22,408,285 bytes |
| Hosted Studio | `https://studio.moises.ai/home?client=desktop` |
| Local shell | `file:///Applications/Moises.app/Contents/Resources/app.asar/out/renderer/index.html` |
| Debug endpoint | `http://127.0.0.1:9222` |

Package clues (from the bundled `package.json` / `node_modules`): `@moises-ai/plugin-server@0.8.33`,
`@todesktop/runtime`, `@sentry/electron`, native `rtaudio`/`audify` prebuilds. These support the
plugin/live-audio plumbing; they are not proof of a local mixer.

## 3. Runtime captures

The following files were produced in `/tmp` (not committed):

| Capture | File |
|---|---|
| Local shell tab strip | `moises-shell.png`, `moises-shell-dom.json` |
| Studio landing | `moises-studio.png`, `moises-studio-dom.json` |
| Play library | `moises-play.png`, `moises-play-dom.json` |
| Play library (second pass) | `moises-play2.png`, `moises-play2-dom.json` |
| Opened track | `moises-player2.png`, `moises-player2-dom.json` |
| Mastering landing | `moises-mastering.png`, `moises-mastering-dom.json` |
| Voice Studio landing | `moises-voice-studio.png`, `moises-voice-studio-dom.json` |
| Lyric Writer landing | `moises-lyric-writer.png`, `moises-lyric-writer-dom.json` |
| Downloads | `moises-downloads.png`, `moises-downloads-dom.json` |
| Pricing iframe (top page) | `moises-billing-pricing.png`, `moises-billing-pricing-dom.json` |
| Pricing iframe (second pass) | `moises-pricing2.png`, `moises-pricing2-dom.json` |
| Library/Home UI craft | `moises-ui-play-2026-10-20.png`, `moises-ui-home-2026-10-20.png` |
| Player UI craft | `moises-ui-player-2026-10-20.png`, `moises-ui-player-chord-chart-2026-10-20.png`, `moises-ui-player-chord-seek-2026-10-20.png`, `moises-ui-player-lyrics-2026-10-20.png` |
| Stems / export / tempo / count-in / metronome | `moises-ui-stems-picker-2026-10-20.png`, `moises-ui-export-2026-10-20.png`, `moises-ui-tempo3-2026-10-20.png`, `moises-ui-countin-2026-10-20.png`, `moises-ui-metronome-2026-10-20.png` |
| Responsive | `moises-ui-1024-2026-10-20.png`, `moises-ui-900-2026-10-20.png`, `moises-ui-home-1024-2026-10-20.png` |
| Current Audio Tools Home | `audio-tools-home-live.png` (1440×1000), `audio-tools-home-1024.png` (1024×768); raw DOM in `/tmp/audio-tools-home-live-dom.json` |

The **original Home** screenshot from the first pass was accidentally overwritten by the Studio landing
capture because both used the same `/tmp/moises-studio` prefix. The 2026-10-20 UI-craft pass captured
Home again under a distinct prefix (`moises-ui-home-*`), so the UI reference now has a Home capture.
The current-app captures contain local library titles; they stay in `/tmp` and are not committed.

## 4. CDP method

Temporary helper scripts lived in `/tmp/cdp/`:

- `probe.js` — connect to a target matching a URL substring, print href/title/text/buttons/inputs/
  links/resources, capture a screenshot.
- `navprobe.js` — navigate, wait, then capture the same shape.
- `clickprobe.js` — click by row/button text, then capture.
- `eval.js` — evaluate arbitrary page JavaScript and print the JSON result.
- `menus.js` — open the Play menus/dialogs, capture dialog text, close with Escape/Close.
- `frame-eval.js` — find a child frame by URL and evaluate inside it with `Page.createIsolatedWorld`.
  This was required for the pricing table, which is an iframe at
  `https://studio1.moises.ai/billing/pricing/?cycle=yearly&shellDisabled=true`.
- UI-craft pass helpers: `eval-target.js` / `shot-id.js` (target by ID), `cdp-shot.js`, `eval-port.js`,
  `click-xy.js`, `press-key.js`, `resize-shot.js`. Use target IDs, not URL matching: two `/play`
  targets existed (one visible, one stale). Moises titles can use decomposed Unicode (e.g. Japanese
  dakuten), so substring matching is unreliable; use row IDs.

For the current Audio Tools Home, a headless Chrome CDP session on port 9333 used
`/tmp/chrome-audio-tools-cdp`; it captured 1440×1000 and 1024×768. The OS screenshot tool was still
unavailable, so this was the only reliable current-app capture path.

Example commands (paths are temporary):

```bash
node /tmp/cdp/probe.js 'out/renderer/index.html' /tmp/moises-shell
node /tmp/cdp/navprobe.js 'https://studio.moises.ai/play' /tmp/moises-play
node /tmp/cdp/frame-eval.js 'studio1.moises.ai/billing/pricing' \
  '(() => document.body.innerText)()'
node /tmp/cdp/menus.js
```

OS-level `screencapture` failed with “could not create image from display”; CDP `Page.captureScreenshot`
worked. That is why all screenshots are CDP captures.

## 5. Bundle inspection

The Studio SPA loads these chunks (observed in the resource list):

```
https://studio.moises.ai/assets/index-DEGHzQaz.js
https://studio.moises.ai/assets/react-_8SPL4h_.js
https://studio.moises.ai/assets/ui-DwZkyyHt.js
https://studio.moises.ai/assets/lyric-writer-9e8afvdg.js
https://studio.moises.ai/assets/daw-Cm3Md_qP.js
https://studio.moises.ai/assets/module-BqslCbXU.js
```

They were fetched with `curl` into `/tmp/moises-assets/` (not committed). `daw-Cm3Md_qP.js` is 17 MB
and contains the DAW labels listed in section 17.7. The presence of a label is **bundle-observed**, not
proof that the control is enabled or reachable on this account.

The bundle contains `OpenDAW AudioUnit` strings. This is the basis for the **inferred** statement that
Studio uses OpenDAW (or a fork). Licence/terms were not reviewed in this pass; do not reuse it without a
separate legal/technical review.

## 6. Public sources

The full public citation list is in `_work/moises-public.md` (52 help-center URLs, 40+ marketing URLs,
App Store/Google Play, official blog). Primary entry points:

- `https://moises.ai/`
- `https://moises.ai/pricing/`
- `https://help.moises.ai/` (Zendesk; the public `/api/v2/help_center/en-us/articles.json` index was
  used to read 112 articles)
- `https://apps.apple.com/us/app/moises-ai-music-chooser/id451732904`
- `https://play.google.com/store/apps/details?id=ai.moises`
- `https://studio.moises.ai/` (login-gated)
- `https://studio.moises.ai/downloads`
- `https://studio.moises.ai/billing/pricing` (the visible content is the iframe
  `https://studio1.moises.ai/billing/pricing/?cycle=yearly&shellDisabled=true`)

The public pass was done independently of the runtime pass. Where they disagree, section 17 of
`01-MOISES-SURFACE.md` records both and labels which is newer.

## 7. Key observations and their labels

| Claim | Label | Evidence |
|---|---|---|
| Desktop shell is only a tab strip: Home / Play / Moises Studio / + | observed | `moises-shell.png`, `moises-shell-dom.json` |
| The real player and Studio are hosted at `studio.moises.ai` | observed | CDP target URLs, shell screenshot |
| Play library shows Title/Created/Genre/BPM/Key/Duration and “Try the New Player” | observed | `moises-play-dom.json` |
| Player exposes Separate Stems, Chords, Sections, Lyrics, stem M/S, metronome, export, loop, BPM/key | observed | `moises-player2-dom.json`, `moises-player2.png` |
| Stem picker has Basic/Voice/Strings/Keyboards/Winds/Drums/Multimedia groups | observed | `menus.js` output, section 17.5 |
| Export dialog has Mix/Tracks/Chord Chart, MP3/WAV/FLAC/M4A/OGG, 44.1/48 kHz, metronome/count-in | observed | `menus.js` output, section 17.5 |
| Moises has chord-chart export but no guitar tab export | observed (chord chart) + public (no tab) | export dialog; help-center tab absence |
| Studio is a full DAW surface (tracks/buses/clips/automation/MIDI/VST/AI/collab) | bundle-observed | `daw-Cm3Md_qP.js` labels |
| Studio is built on OpenDAW (or a fork) | inferred | `OpenDAW AudioUnit` strings |
| Moises Live is a free system-audio real-time isolator | observed | `moises-downloads.png` |
| Logged-in pricing is Free/Premium/Pro with 5/20/20-minute caps and 10/200/unlimited credits | observed | pricing iframe DOM |
| Desktop 2.0.18 ASAR is much larger than 2.0.3 | observed | hash/size comparison |
| The old repo note “shell only, no local mixer” still holds | observed | shell page + hosted player |
| Mobile/TV/visionOS apps were not run | unknown | — |
| Studio project/collaborator limits are not public | unknown | — |
| Audio quality/latency were not measured | unknown | — |

## 8. What was not verified

- Every Studio menu and control; the labels are from the shipped bundle, not exercised.
- Mobile, iPad, TV, visionOS, VST/AU/AAX plugin behavior.
- Real separation/audio quality, latency, and export fidelity.
- Moises Live's audio output; only its marketing page and screenshot were read.
- Studio plan limits for projects, collaborators, and session length.
- The exact tier gate for each of the 27 stem targets; the picker was opened but no target was run.
- Whether the Play player has hidden pan/EQ/comp controls behind an unopened options menu. The visible
  row and the help center say no; treat it as “not visible in this pass.”

## 9. Repo-side checks

- `02-CURRENT-STATE.md` is a code inventory with `path:line` evidence, produced on 2026-10-19. Its §0
  delta is the 2026-10-20 status; where the old table rows conflict, §0 wins.
- Known current-state issues recorded there and used by the plan:
  - tab-strip duplicate/close-others/close-right helpers exist but are not wired (still true);
  - ~~`backend/main.py:343` has `allow_youtssube` (typo)~~ — fixed 2026-10-20;
  - `web/` has 8 `tsc` errors (still true; out of scope);
  - ~~desktop mix export omits pan~~ — fixed 2026-10-20; web still omits speed/key;
  - hosted metronome is only a muted stem (still true);
  - ~~count-in and A/B loop are absent~~ — implemented on desktop in Phase 1.
- Test count is **1030 passed, 1 skipped** at the Phase 1 gate; `AGENTS.md` now says 1030. The old
  notes said 809/882.

## 10. Cleanup

After the pass, navigate the hosted app back to Home and quit the debug instance. Do not leave a
remote-debugging port open. The temp `/tmp` captures may be deleted; they contain account data and are
not part of the repo.

---

## 11. UI-craft pass — 2026-10-20

### 11.1 Scope and method

A second read-only Moises runtime pass, focused on UI craft rather than feature coverage, plus a
current-app audit.

- Moises 2.0.18, CDP `http://127.0.0.1:9222`; no separation, upload, export, purchase, rename, or
  delete. Captures in `/tmp/moises-ui-*-2026-10-20.png`; personal library titles are not recorded here.
- Current Audio Tools Home, headless Chrome CDP `:9333`; 1440×1000 and 1024×768. Raw captures and DOM
  in `/tmp`; not committed because they contain local run titles.
- HIG references read for the audit: Layout, Typography, Color, Lists and tables, Sidebars, Popovers,
  Dark Mode, Loading, Focus and selection, Accessibility, Designing for macOS, cross-platform.
- Labels: **observed** = computed style/DOM/screenshot; **inferred** = pattern extrapolation;
  **unknown** = not verified. The populated Moises lyrics layout is inferred (no populated project was
  found).

### 11.2 Current Audio Tools Home — measured

At 1440×1000:

| Element | Value |
|---|---|
| Sidebar | 300px, `#192542`, amber text |
| Main content | 980px wide, starts at x=380 |
| Body font | Satoshi 16px/25.6px, weight 400 |
| H1 | 44px/52.8px, weight 700, amber |
| Nav item | 238×28px, 16px/32px, weight 600, active `#2A4467` |
| Action buttons | 316×74px, radius 14px, `#2A4467`, 1px amber border |
| Recent cards | 150×74px, text-only |
| Library row | 832×74px button + 132×74px Practice button |
| Analysis line | 14px, detached caption |
| Global text/background | `#F6AD49` on `#192542` (7.94:1) |

At 1024×768:

- The main block remains 980px wide at x=380; the viewport is 1024, so **336px overflows**.
- H1 is clipped (“Audio Tools (C…”); the third action card is clipped.
- Six recents compress into ~100px columns; titles wrap 4–5 lines and ages detach.
- The Streamlit developer promo (“Help agents write better apps / Install”) covers the title/actions.
- “Library” starts below the fold.

### 11.3 Moises UI reference — measured

| Area | Observed value |
|---|---|
| Library background | `#101213` |
| Player background | `#111313` |
| Canvas | `#121213` |
| Surface | `rgba(202,224,250,0.08)` / `#2B2F33` |
| Border | `rgba(203,221,242,0.12)` |
| Primary text | `#EDEEF0` / `#FFFFFF` |
| Secondary text | `rgba(216,233,254,0.49)` |
| Muted text | `rgba(203,223,247,0.38)` |
| Accent | `#78F7FF`; CTA `#00D8E2` |
| Waveform | `#00D1E1` → `#00B1F8` |
| Metronome active | `#FFC53D` on `#111113` |
| Font | Articulat (licensed; not copied) |
| Body / title / UI / meta | 16/24 · 28/36 · 14/20 · 12/16 |
| Library sidebar / header / nav / row / thumb | 240–241px · 76px · 216×36px · 56px · 48px |
| Player rail / splitter / canvas | 280px · 8px · 980px at 1260×760 |
| Player top / tracks / bottom bar | 132px · 531px · 96px |
| Stem row / transport / cover | 80px · 48×48px · 56×56px |
| Responsive | 1024 footer two rows; 900 rail ~210px; recents scroll/clip |

### 11.4 Findings

**Critical**

1. 1024 horizontal overflow/clipping; the primary action is not fully visible.
2. Visible Streamlit developer promo/default chrome in the product surface.
3. No hierarchy: all text amber; primary and secondary actions equal weight.

**High**

4. Library is a stack of 74px buttons, not a table; analysis is a detached caption.
5. Recents squash at 1024 instead of scrolling.
6. 300px text-only sidebar; no icons; 28px nav rows.
7. Player has no single transport center; Speed & Key, master, presets, and practice compete.
8. Practice panel sits above the stage and uses a native `<details>` disclosure.
9. No loading skeletons/stage progress; analysis blocks with a spinner.
10. No table/keyboard semantics; repeated action labels lack song context.

**Medium**

11. 16/25.6 UI type and 44px H1 are too large/loose for a desktop tool.
12. Satoshi 600 is synthesized (bundled faces: 300/400/500/700/900).
13. Universal `scale(0.97)` button press feels toy-like.
14. Muted amber at ≤60% opacity fails 4.5:1; use neutral tokens instead of opacity.
15. Library has no visual identity (text-only rows).
16. Queue/status is not visible at a glance.
17. Interface Lite/Pro is a radio form in the navigation rail.
18. Product name is the page H1; brand should live in the rail.
19. Ages are verbose/detached; no structured metadata.
20. No last-opened/selected row.

The design response and line-level target are in `10-MOISES-UI-CRAFT.md` §3–5. The implementation
plan is `11-DESKTOP-UI-REDESIGN.md`.

### 11.5 Labels and limits

- **Observed:** all measurements above, the 1024 clipping, the promo overlay, the all-amber computed
  styles, the Moises library/player/tokens, and the popover/dialog captures.
- **Inferred:** populated Moises lyrics layout; hover/pressed motion timings; some responsive intent.
- **Unknown:** exact Moises hover tokens; whether every Play project can expose lyrics; audio latency.
- No Moises code/assets were copied. The new Home component is our own vanilla TS, not a clone of
  Moises markup.

---

## 12. Phase 1 verification — 2026-10-20

This is the evidence behind `06-PHASE-1-PLAN.md` §Verification. No commit/push/tag/PR.

### 12.1 Commands

| Command | Result |
|---|---|
| `python -m pytest tests/ -q` | **1030 passed, 1 skipped** (final gate) |
| `ruff check src/audio_to_tab` | clean |
| `cd ui/stem_mixer_component/frontend && npx tsc --noEmit` | clean |
| `make mixer-build` | committed build present; component tests pass |
| `cd web && npx tsc --noEmit` | 8 pre-existing errors (out of scope; unchanged) |

### 12.2 Real song

Waltz reference (local, not committed), run
`data/ui_runs/46b84e7b-dbb5-4c25-817a-53c4cd85b02d`:

- 124.9 s; 6 stems; BPM 105.47 high; key Dm high; 145 draft chords; 7 sections; 0 lyrics
  (instrumental); 55 tab measures.
- `analysis.json`, tab JSON/MIDI/PDF present; `project.json` created.
- Home: `BPM 105.5 · Dm · 7 sections`; Practice opens 6 stems; Chords/Sections/Lyrics/Tab render;
  Tab measure view shows fretted strings and next measure; PDF opens.
- PDF mime fix verified: `/media/…pdf` returns HTTP 200, `application/pdf`, body starts `%PDF-1.3`.

### 12.3 Synthetic / UI evidence

- Home `Analyse` → `Practice` on a synthetic 30 s run; warning path
  `"Analysis ready with warnings: …"`; project manifest created; draft label shown.
- Practice tabs, diagrams, section loops, count-in select, project restore, draft label verified in a
  synthetic UI smoke.
- Headless AudioContext was suspended: actual playback/count-in audio/save-mix are **not** manually
  verified. Control state/persistence were.

### 12.4 Lyrics

- Injected real Japanese lines into `analysis.json`: Lyrics tab appeared; word spans/click-to-seek
  present; original restored; no debug/backup files.
- Direct 45 s full-band excerpt with the mix as `vocals_path`: 7 Japanese lines, `ja`, word
  timestamps. Mix bleed means errors are expected; this is path evidence, not accuracy.
- `transcribe_lyrics` now preserves partial lines when faster-whisper raises lazily; test added.
- Full-band 45 s analysis: BPM 123.046875 low, key C#m high, 27 draft chords, 4 sections; lyrics
  skipped without a vocals stem (by design).

### 12.5 Failure / deferred

- 45 s/full-length Demucs under the temporary torchaudio/FFmpeg shim fails at the end despite writing
  six stems (`libtorchcodec`/FFmpeg). 2 s succeeds. Job
  `0003f15e14e549bc984b8eea06ceae05`, run `b1e4f90b-82b4-4c4d-82be-ae8f56f40990`; status
  `Demucs failed`, empty `status.artifacts`. Dev-environment issue; not a successful full-length run.
- Packaged lyrics are deferred to Phase 1.6. The freeze lacks the `analysis` extra, does not collect
  `faster_whisper`, and has no first-run model download. The dev path works with a pre-seeded
  `~/.cache/audio_to_tab/analysis/faster-whisper-small`.
- Open: real three-song regression, actual playback/count-in listening, network-off, 8 GB Mac,
  installer smoke, labelled chord accuracy corpus, and the remaining line-by-line code review.
- Cleanup: the failed 45 s job and the synthetic test runs were removed after the review; the real
  Waltz run is retained. Restart Streamlit only when no job is running (`fileWatcherType=none`). Do
  not commit `data/`, run audio, or screenshots.

### 12.6 Final review pass — 2026-10-21

After the first green gate, a targeted code/consistency review found and fixed:

- **path containment** — `ui/project.py` rejects absolute analysis/tab artifact paths and `..`
  escapes; two tests added (`tests/test_project.py`).
- **count-in tempo** — count-in forces one click per beat and steady follow instead of inheriting
  the metronome subdivision/rate.
- **loop/seek sync** — seeking while playing clamps into the active loop so native source looping and
  the displayed time cannot diverge; word/line seek updates the panel from the engine's actual time.
- **chord diagrams** — open shapes such as `Cm`, `Gm`, `B` and `Bm` compute a base fret instead of
  drawing high frets at fret 1.
- **lyrics** — word clicks seek to the word, and CJK/Thai/Khmer text is joined without inserted
  spaces.
- **loop toggle** — a failed section loop no longer leaves the checkbox checked without a region.
- **tab PDF link** — the PDF media URL is registered during the full-page run (with a run-scoped
  coordinate) instead of inside the mixer fragment, so a later fragment rerun cannot GC it.
- **analysis write failure** — Home `Analyse` reports a failed `meta.json` update instead of raising.
- **install profile** — `make install` now includes the `analysis` extra, matching
  `scripts/dev.sh`/`dev.ps1`.

Post-restart verification (Streamlit `:8501`):

- Home → Waltz Practice opened 6 stems; Practice panel showed Chords, Sections, and Tab; section
  rows listed 7 sections; Tab showed measure 1 plus next measure; `Open tab PDF` returned HTTP 200,
  `application/pdf`.
- A fragment rerun (`Mute all`, then `Reset mix`) left the PDF URL at HTTP 200.
- Count-in `1 bar` persisted to `project.json`, then reset to Off; `Loop current section` persisted
  `{start: 0.0, end: 26.96}`, then `Clear loop` reset it to null. No console errors.
- Audio playback/count-in sound remain unverified in the headless browser because its AudioContext is
  suspended.

---

## 13. Home parity pass — 2026-10-21

Canonical numbers live in `10-MOISES-UI-CRAFT.md` §13. This section is the ledger. Personal library titles are not recorded.

### 13.1 Moises

| ID | What was measured |
|---|---|
| E-HOME-001 | Moises 2.0.18 (`261013w3pv02l1x`), Electron 43.4.1, Chrome 150.0.7871.224, macOS arm64, device-pixel ratio 2. Home URL `https://studio.moises.ai/home?client=desktop`. `EnableNodeCliInspectArguments` is enabled. Read-only layout inspection. No source, CSS, SVG, or image was written into the repo. |
| E-HOME-002 | 1440×1000 CSS pixels. Rail 240. No page H1. Action cards 218×100 at y=24, gap 12. Recents 150×210, gap 12. Files table row 56. Search wrap 315×32. |
| E-HOME-003 | 1280×900. Rail still 240. Cards 186×100, five visible. Seventh recent card clipped inside the rail. `scroll-snap-type: none`. |
| E-HOME-004 | 1024×768. Content origin moves to x=253. Fourth action card and fifth recent card clip inside their rails. Type and Duration columns measure 0. No page horizontal scroll. |
| E-HOME-005 | 900×800. Rail still 240. Cards 154×100. Same column hiding as 1024. Chip boxes overlap the search wrap; stacking was not confirmed. |
| E-HOME-006 | Type, color, radius, padding. Body `#101213`. Card `#17191C`. Nav row 216×36, radius 6, padding `8px 12px`. Selected pill `#E9EEF5`. Font on Moises is Articulat; we do not ship it. |
| E-HOME-007 | Logo slots 32×17, 16×16, and 73×12.3 with an 8px gap. Nav icon 16 filled. Card icon 20. First card icon `#75EBF5`. Other card icon colors were not sampled. |
| E-HOME-008 | Collapse click did not change the 240px rail within 350ms. Filter click did not expose a menu role. Empty, loading, error, hover target, and sticky header were not established. |
| E-HOME-009 | Content origin is x=273 at 1128px wide and x=253 at 1120px wide. Implementation uses 1124px. |
| E-HOME-014 | Group label composites to about 2.94:1. Meta text is about 4.38:1. Both are on `#101213`. |

### 13.2 Current Audio Tools Home

Streamlit 1.59.1 at `http://127.0.0.1:8501`. Scroll reset on `stMain`. Same four viewports.

| ID | Result |
|---|---|
| E-HOME-010 | 1440. Sidebar 300. Nav 260×28, active weight 600, fill `#2A4467`. H1 44/52.8 weight 700, box 980×89 at x=380, y=112. Buttons 316×74, radius 14, text `#F6AD49`. Header bar 60px. No page horizontal scroll. The “Help agents” promo string was not in the page text. |
| E-HOME-011 | 1280. Sidebar 300. H1 box width 820. Buttons 263×74. Content still starts at x=380. |
| E-HOME-012 | 1024. Sidebar 300. H1 box width 564 and the title is not clipped. Buttons 177×74 and fit. Recents about 100×80 with text wrapping to about 4 lines. No page horizontal scroll. This supersedes the 2026-10-20 “1024 clips the page” claim. |
| E-HOME-013 | 900. Sidebar 300. H1 box width 440. Buttons 136×74. Recents about 75×115. No page horizontal scroll. |

### 13.3 Docs checked, not copied

Streamlit 1.59.1 in `.venv311` exports both `streamlit.components.v1.declare_component` and `streamlit.components.v2.component`. Context7 (`/streamlit/docs`) describes v2 as the no-iframe API and v1 as the iframe API that remains supported. Vite 5.4 library mode is documented at `/vitejs/vite/v5.4.21`. `streamlit-component-lib` has no Context7 entry; the mixer source calls `Streamlit.setComponentValue` and `Streamlit.setFrameHeight`.

### 13.4 Not done

Moises was launched for this pass with a loopback debug port and was not used to separate, upload, delete, or purchase anything. Raw screenshots were not committed. Collapsed width, menus, and empty states remain `[unverified]` in `10` §13.15.

### 13.5 Gate 0 and UI-9 — 2026-10-21 implementation

Gate 0 passed on the v1 iframe. No fallback. No components v2.

`AUDIO_TOOLS_UI_V2=1`, Streamlit 1.59.1, `http://127.0.0.1:8501`. Scroll reset on `stMain`. CSS pixels. Library titles are not recorded.

| Viewport | Sidebar | Iframe left / size | Card | Recent | Row | Page `scrollWidth` |
|---|---|---|---|---|---|---|
| 1440×1000 | 240 | x=240, 1200×1000 | h=100, page x=273, pad 33px | 150×210 | 56 | 1440 |
| 1280×900 | 240 | x=240, 1040×900 | h=100, page x=273, pad 33px | 150×210 | 56 | 1280 |
| 1024×768 | 240 | x=240, 784×768 | h=100, page x=253, pad 13px | 150×210. Fifth card's box passes the viewport; the page does not grow | 56 | 1024 |
| 900×800 | 240 | x=240 | three cards 201×100, all end by x=880 | 150×210 | 56 | 900 |

The 1124px outer switch is `max-width: 884px` inside the iframe, because the frame starts after the 240px rail (1124 − 240). At 1280 the pad stays 33px. At 1024 and 900 it is 13px.

Also at 1440: lockup 113×32 at 24,26. Nav row 216×36 at 12,74, weight 400. Header `display: none`. No Home H1. Learn icon computed `rgb(117, 235, 245)`. Search 315×32 does not overlap the All pill at 900. `scroll-snap-type` is `none`. Iframe document `scrollHeight` equals `clientHeight` at 1440 (the file list scrolls inside the frame).

Interactions, still with the flag on: a search with no matches showed “No songs match that search.” Clearing it restored the rows. The row menu opened with Open and Practice, Esc closed it, and focus returned to “Row actions”. The Learn card opened Audio Isolation’s upload form. A recent item opened an existing mix. No separation job was started. Collapse changed the rail from 240 to 0 and hid the lockup. Expanding restored 240.

Flag unset, same 1440 viewport: sidebar 300, H1 44px, primary button 74px tall, header `display: flex`, no Home marker.

Not browser-proven this pass: an empty library, the three skeleton rows, and an analyse alert. The copy and the loading branch are in the component. Reduced motion was not toggled in the OS. The full Tab order was not walked. `tests/test_api.py::test_upload_and_job` failed locally (1035 passed, 1 skipped). That test is the one macOS CI deselects. It was not changed.
