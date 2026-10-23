# Moises reference handoff — 2026-10-23

Give this file to the next session before any implementation.

## Current build

Windows Moises **2.1.0** build **`261021a1gygumpb`**. Feed checked the same day. Details and hashes: `docs/plans/moises-parity/_work/scan-2026-10-23/MANIFEST.json`.

## Read order

1. `PAGE-INVENTORY.md` — every page this scan actually found.
2. `FUNCTION-INVENTORY.md` — shell actions and IPC.
3. `FEATURE-DEEP-DIVE.md` — what is behavior, what is help text, what is unknown.
4. `COVERAGE-LEDGER.md` — the counts.
5. `docs/plans/moises-parity/13-PARITY-DELTA.md` — what changed in our beliefs.
6. `docs/plans/moises-parity/04-SCOPE-CUT.md` — what we build.

## Thesis that still stands

Guitar tab and tab/PDF export, local-first processing, and the practice player are the product. Moises Studio is a separate hosted DAW. Do not raise `MPS_MIN_RAM_GB`. Do not unify Desktop Interface Lite with hosted `lite`. Do not copy a mixer law. Desktop isolation stays serial. No commit, push, or PR unless the user asks in that conversation.

## Thesis this scan did not verify

That the hosted player lacks tab, chords, or a metronome. The player route exists. It was not opened. Treat older "no tab" notes as still the working assumption, labeled historical, until P-S2-08 is walked.

## Hard corrections

- Audify is not the 2.1.0 capture addon. The unpacked README says it shipped through 2.0. The addon is `capture.node`.
- `sparkbars` is the Studio icon id, not a new app.
- Prices were not on the public pages this scan opened. The help credit article disagrees with itself (Premium 200 in the list, 100 in example 3).
- The local renderer does not mount the mixer. That part of the old teardown still matches, now on a new bundle hash `index-C76vPLoN.js`.

## Do not do

Purchase, start a paid trial, upload private audio, invite collaborators, delete an account, or dismiss a fullscreen video to reach the window.

## Resume

`docs/plans/moises-parity/_work/scan-2026-10-23/STATE.md`.
