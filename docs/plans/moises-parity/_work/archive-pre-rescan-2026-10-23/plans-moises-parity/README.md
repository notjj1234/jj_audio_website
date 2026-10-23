# Moises parity program — evidence, cut, and build plan

**Status:** Phase 1 is implemented on desktop (Tasks 1–14) and the automated gate is green. Real
Waltz evidence is recorded in `06-PHASE-1-PLAN.md` §Verification and `08-EVIDENCE-LOG.md` §12; the
manual three-song/install/playback checklist is still incomplete, so this is **not** a “shipped”
claim. Phase 1.5 is planned and not started. Home measurements are `10-MOISES-UI-CRAFT.md` §13.
The Home build order is `11-DESKTOP-UI-REDESIGN.md` §12. The player visual redesign is Phase 1.6.
`08-EVIDENCE-LOG.md` §13 is the 2026-10-21 Home ledger.
**Date:** 2026-10-20 (Home parity revision 2026-10-21)
**Owner surface:** desktop first (`ui/` + `src/audio_to_tab/`), website second (`web/` + `backend/`).
**Repo rules:** `AGENTS.md`, `PROJECT_TREE.md`, `PLANNING.md` still govern implementation. This folder
does not relax them.

## What this is

Moises is now two products in one shell: a practice player and a browser DAW (Moises Studio, Sept
2026). This program separates the two so we do not try to build a DAW while we are still winning the
practice job.

The wedge is **tablature**. Moises has chords, capo, chord diagrams, and a chord-chart export, but no
guitar tab and no tab/PDF export. We already have a guitar-first separation engine and a tab PDF
pipeline. The plan makes that the centre of the product, then adds the practice features Moises has and
we do not.

## Relationship to the existing Moises research

- `docs/research/moises/` (the 2.0.3 static REA pass) is still authoritative for the app stack, IPC,
  mixer literals, and the pan/solo/summing/design constraints. This folder **does not duplicate** it and
  does not replace its evidence.
- This folder adds the **2.0.18 runtime pass**, the **full-surface matrix**, and the **2026-10-21 Home parity pass** (`10-MOISES-UI-CRAFT.md` §13). The 2026-10-20 Tyrian Nocturne Home direction is historical where §13 disagrees.
- Where `docs/research/moises/COMPETITIVE-INSPIRATION-PLAN.md` set mixer-only non-goals (no analysis,
  no practice panels, no player expansion), this program **explicitly supersedes those non-goals** for
  the phases listed in `04-SCOPE-CUT.md` and `05-ROADMAP.md`. Its pan-law, solo-law, summing, and
  physical-constraint rules still apply and must not be changed.
- Home parity is layout and interaction, not a clone. It keeps the Audio Tools name, the existing logo, Satoshi, and original icons. It does not copy Moises artwork, font files, or markup. Global Tyrian tokens stay until a separate approval. The player is unchanged in Phase 1.5.

## Read in this order

| # | File | What it answers |
|---|---|---|
| 1 | `01-MOISES-SURFACE.md` | What Moises actually ships, by product, platform, and plan. Includes the 2026-10-19 runtime pass on Moises 2.0.18 and the logged-in Studio. |
| 2 | `02-CURRENT-STATE.md` | What this repo already has, with file evidence. Written from the code, not from old gap notes. |
| 3 | `03-FEATURE-MATRIX.md` | Feature-by-feature: Moises vs us, verdict, phase. The full gap map. |
| 4 | `04-SCOPE-CUT.md` | The bone. What we build now, what waits, what we never build. |
| 5 | `05-ROADMAP.md` | Phases, exit criteria, and the order that keeps the desktop shippable. |
| 6 | `06-PHASE-1-PLAN.md` | The first implementation plan, task by task, with tests. |
| 7 | `07-BUILD-PROMPT.md` | The portable prompt for OpenCode (DeepSeek) or Cursor. Paste this into a fresh agent session. |
| 8 | `08-EVIDENCE-LOG.md` | Commands, URLs, screenshots, and what was observed vs inferred. |
| 9 | `09-SKILL-WORKFLOW.md` | The ordered skill list for each stage: evidence, scope, plan, build, verify, review, prompt. |
| 10 | `10-MOISES-UI-CRAFT.md` | Measured UI reference. **§13 (2026-10-21) is the Home source of truth.** Earlier Home numbers in that file are historical. |
| 11 | `11-DESKTOP-UI-REDESIGN.md` | Phase 1.5 plan. **§12 is the Home implementation plan.** Player tasks in the older sections are deferred to Phase 1.6. |

Raw research lives in `_work/`. Do not edit `_work/` by hand; it is the audit trail. Screenshots of the
Moises library and the current Home contain personal titles and stay in `/tmp`; only measurements and
redacted findings belong in this repo.

## The one-screen thesis

1. **Desktop is the product.** The website is a thin upload-and-mix surface until the desktop workflow
   is complete. A perfect desktop is easy to copy to React; a half-finished DAW is not.
2. **Tab is the differentiator.** "Import a song, get a playable tab, practise it with the original"
   is a job Moises cannot finish. Chords and lyrics are supporting evidence, not the headline.
3. **Local-first is the second differentiator.** No upload, no monthly separation credits, no 5-minute
   cap, no cloud dependency. Cloud sync and collaboration are later, optional, and never required to
   practise.
4. **The practice player is the battlefield.** Moises' consumer player is volume + mute/solo + speed +
   pitch + metronome + chords/lyrics/sections. It is not a DAW. Match and beat that before building
   Studio.
5. **Studio is a separate product.** It is a browser DAW that the bundle suggests is built on OpenDAW
   (inferred; see `08-EVIDENCE-LOG.md`), with AI generation, voice conversion, mastering, Auto Mix,
   VST3, and real-time collaboration. Treat it as Phase 3, not Phase 1. Buy/partner/integrate before
   building a DAW from scratch.
6. **Do not copy unknown laws.** Pan law, solo law, fader scale, and summing are ours. The existing
   `docs/research/moises/COMPETITIVE-INSPIRATION-PLAN.md` constraints still apply.

## Phase 1.5 at a glance

The product works. Phase 1.5 makes the **desktop Home** match the measured Moises Home (`10` §13, `11` §12):

- **Home:** three 100px action cards, a 150×210 recents rail, a 56px Files table, no page H1.
- **Shell:** 240px rail at 1440, 1280, 1024, and 900, shared by every desktop page. Nav rows 216×36 with 16px filled icons. Original navy `#192542`, blue `#2A4467`, amber `#F6AD49`. Satoshi. The Audio Tools name and logo stay.
- **Flag:** `AUDIO_TOOLS_UI_V2` defaults on. Set it to `0` to keep the old Home. Global Tyrian tokens are not changed.
- **Architecture:** Streamlit plus a vanilla TypeScript Home component (Vite / `streamlit-component-lib`). No React. The mixer is not restyled in this phase.
- **Not in 1.5:** player/mixer visual redesign. That waits for Phase 1.6.

Do not start Phase 2 until the Home gate in `05` passes.

## What "literally everything" means here

`01-MOISES-SURFACE.md` and `03-FEATURE-MATRIX.md` cover the whole Moises surface, including the parts
we will not build soon. `04-SCOPE-CUT.md` then makes an explicit build decision for every row:
**now / next / later / never**. Nothing is silently dropped. "Later" is a scheduling decision, not a
claim that the feature does not matter.

## Guardrails for any agent using this pack

- Read `AGENTS.md`, `PROJECT_TREE.md`, and `PLANNING.md` before touching code.
- Desktop isolation is serial. Do not parallelise heavy jobs on an 8–16 GB machine.
- Do not raise the MPS 12 GB gate, do not move desktop to a cloud-first flow, and do not unify Desktop
  Interface Lite with hosted processing mode `lite`.
- Edit frontend sources, then rebuild: `make mixer-build`, `make region-picker-build`, or
  `make mix-tabs-build`. Phase 1.5 adds `make home-build` for the new Home component. Never hand-edit
  hashed `frontend/build/`.
- Run `pytest` and `ruff` on every engine/desktop change. Run `cd web && npm test` and
  `cd web && npx tsc --noEmit` only when the web surface is actually touched (not in Phase 1/1.5). CI
  does not run the last two.
- UI work is gated at 1440, 1280, 1024, and 900. Home geometry is `10-MOISES-UI-CRAFT.md` §13.
  The build order is `11` §12. A 1440-only screenshot is not a pass.
- Do not commit, push, tag, or open a PR unless the user explicitly approves it in that conversation.
