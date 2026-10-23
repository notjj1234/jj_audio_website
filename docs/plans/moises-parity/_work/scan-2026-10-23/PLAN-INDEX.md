# Plan index — action for every Moises document

Source of truth after this scan: `docs/research/moises/` for what Moises is, `docs/plans/moises-parity/` for what we build. This scan's raw notes stay in `_work/scan-2026-10-23/`.

| File | Action | Reason |
|---|---|---|
| `docs/research/moises/README.md` | REWRITE | Version, stack, and re-run steps were 2.0.3. |
| `docs/research/moises/REFERENCE.md` | REWRITE | Handoff must match 2.1.0. |
| `docs/research/moises/architecture.md` | REWRITE | Hosted boundary and capture path changed. |
| `docs/research/moises/FULL-TEARDOWN.md` | REWRITE | New evidence IDs. |
| `docs/research/moises/mixer-ux.md` | REWRITE | Mixer was not in the local bundle; say so, and do not keep 2.0.3 mixer literals as current behavior. |
| `docs/research/moises/gaps-vs-audio-tools.md` | REWRITE | Gaps re-checked against code citations. |
| `docs/research/moises/evidence-index.md` | REWRITE | New dated section. Prior IDs kept as historical. |
| `docs/research/moises/PAGE-INVENTORY.md` | REWRITE | New file. Page source of truth. |
| `docs/research/moises/FUNCTION-INVENTORY.md` | REWRITE | New file. Function source of truth. |
| `docs/research/moises/NETWORK-AND-API-MAP.md` | REWRITE | New file. |
| `docs/research/moises/STATE-MATRIX.md` | REWRITE | New file. |
| `docs/research/moises/FEATURE-DEEP-DIVE.md` | REWRITE | New file. |
| `docs/research/moises/COVERAGE-LEDGER.md` | REWRITE | New file. |
| `docs/research/moises/COMPETITIVE-INSPIRATION-PLAN.md` | SUPERSEDE | Banner points at `04-SCOPE-CUT.md`. Pan, solo, and summing constraints stay in that file. |
| `docs/plans/moises-parity/README.md` | REWRITE | Reading order and status. |
| `docs/plans/moises-parity/01-MOISES-SURFACE.md` | REWRITE | 2.1.0 surface. |
| `docs/plans/moises-parity/02-CURRENT-STATE.md` | REWRITE | Code citations refreshed. |
| `docs/plans/moises-parity/03-FEATURE-MATRIX.md` | REWRITE | Evidence column. |
| `docs/plans/moises-parity/04-SCOPE-CUT.md` | REWRITE | Decisions restated, not silently dropped. |
| `docs/plans/moises-parity/05-ROADMAP.md` | REWRITE | Phase order after the rescan. |
| `docs/plans/moises-parity/06-PHASE-1-PLAN.md` | REWRITE | Phase 1 stays the completed baseline; next build is 1.5 with a measurement gate. |
| `docs/plans/moises-parity/07-BUILD-PROMPT.md` | REWRITE | Portable prompt matches the new plan. |
| `docs/plans/moises-parity/08-EVIDENCE-LOG.md` | REWRITE | Append-only new section. History kept. |
| `docs/plans/moises-parity/09-SKILL-WORKFLOW.md` | LEAVE | Build workflow did not change. Rescan notes live in this folder, not in the build skill list. |
| `docs/plans/moises-parity/10-MOISES-UI-CRAFT.md` | REWRITE | Banner only. No new pixel measurements were taken. |
| `docs/plans/moises-parity/11-DESKTOP-UI-REDESIGN.md` | REWRITE | Banner: do not treat §13 numbers as confirmed on 2.1.0. |
| `docs/plans/moises-parity/12-COVERAGE-LEDGER.md` | REWRITE | New file. |
| `docs/plans/moises-parity/13-PARITY-DELTA.md` | REWRITE | New file. |
| `docs/plans/moises-parity/14-RESCAN-OPEN-QUESTIONS.md` | REWRITE | New file. |
| `docs/plans/moises-parity/_work/*.md` and `_work/spikes/` | LEAVE | Audit trail. Not a second source of truth. |
| `docs/plans/moises-parity/_work/archive-pre-rescan-2026-10-23/` | LEAVE | Frozen copy of the pre-scan docs. |
| `PROJECT_TREE.md` | LEAVE | Project map, not a Moises plan. It does not carry product claims that override these folders. |
| `.kilo/plans/`, `.opencode/plans/`, `.planning/` | LEAVE | Not present in this repo on 2026-10-23. |

No other Moises plan file was found by a repo search for `moises` in Markdown.
