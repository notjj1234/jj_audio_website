# Moises parity program — 2026-10-23 rescan

**Status:** Home is done. The 2026-10-23 check used our spec, not a Moises 2.1.0 remeasure. The next code is Phase 1.6 in `15-PHASE-1.6-PLAN.md`. Logged-in Moises interiors were not walked. This is not a ship claim.

**Archive:** `docs/plans/moises-parity/_work/archive-pre-rescan-2026-10-23/`.

**Scan trail:** `docs/plans/moises-parity/_work/scan-2026-10-23/`.

## Thesis

1. Desktop is the product. The website stays thin until the desktop practice flow is the one we want.
2. Tab and tab/PDF are the wedge. The hosted player was not opened on 2.1.0, so "Moises has no tab" is still an assumption, not a new proof.
3. Local-first is the second wedge. The Moises shell opens `studio.moises.ai`.
4. The practice player is the battlefield. Studio, Mastering, Voice Studio, and Lyric Writer are other products in the same shell.
5. Do not copy an unknown mixer law. None was measured this scan.
6. Do not raise the 12 GB MPS gate. Do not unify Desktop Interface Lite with hosted `lite`.

## Read in this order

| # | File | What it answers |
|---|---|---|
| 1 | `docs/research/moises/PAGE-INVENTORY.md` | Pages actually found |
| 2 | `docs/research/moises/FUNCTION-INVENTORY.md` | Shell actions and IPC |
| 3 | `01-MOISES-SURFACE.md` | Products and plan tiers this scan can defend |
| 4 | `02-CURRENT-STATE.md` | This repo, with file citations |
| 5 | `03-FEATURE-MATRIX.md` | Row-level verdicts |
| 6 | `13-PARITY-DELTA.md` | What changed versus the previous matrix |
| 7 | `04-SCOPE-CUT.md` | now / next / later / never |
| 8 | `05-ROADMAP.md` | Phase order |
| 9 | `06-PHASE-1-PLAN.md` | Finished Home contract |
| 10 | `15-PHASE-1.6-PLAN.md` | Next code: the player |
| 11 | `11-DESKTOP-UI-REDESIGN.md` | Home spec. Player tasks in the older sections are superseded by `15` |
| 12 | `07-BUILD-PROMPT.md` | Portable prompt for Phase 1.6 |
| 13 | `14-RESCAN-OPEN-QUESTIONS.md` | Closed or blocked, with whether each blocks 1.6 |
| 14 | `12-COVERAGE-LEDGER.md` | Counts |
| 15 | `08-EVIDENCE-LOG.md` | Append-only log. Section 16 is the planning close. |
| 16 | `10-MOISES-UI-CRAFT.md` | Our spec. Banner says the numbers are not 2.1.0 parity. |
| 17 | `09-SKILL-WORKFLOW.md` | Unchanged build workflow |

`docs/research/moises/COMPETITIVE-INSPIRATION-PLAN.md` is superseded for scope. Its pan, solo, and summing warnings still apply.

## Guardrails

- Desktop isolation is serial.
- Do not raise `MPS_MIN_RAM_GB` (`src/audio_to_tab/hardware.py`).
- Do not unify Desktop Interface Lite with hosted processing mode `lite`.
- Edit frontend sources, then rebuild. Do not hand-edit hashed `frontend/build/`.
- UI gates at 1440, 1280, 1024, and 900 still apply to our Home. They are our checks, not a claim that Moises was remeasured.
- No commit, push, tag, or PR unless the user asks in that conversation.
