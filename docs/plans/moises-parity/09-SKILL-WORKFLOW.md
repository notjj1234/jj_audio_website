# Skill workflow — which skill at which stage

This is the ordered workflow for turning the Moises evidence into a shipped desktop practice player.
It names the skills that are actually installed in this OpenCode setup and says what each one is for.
Cursor does not have these skills; use the same order with the docs in this folder as the contract.

**Rule:** process skills come first. Do not start implementation until the evidence and scope are
settled. Do not load a skill that does not serve the current stage.

## 0. Session start — `using-superpowers`

- Load it once. It tells you to check for a relevant skill before acting.
- Do not reload it. It is already in the session.
- If you are a subagent dispatched for one task, skip it and follow the task.

## 1. Evidence — `reverse-engineer-anything` + `smart-explore` + `context7`

| Skill | Use | Output |
|---|---|---|
| `reverse-engineer-anything` | Runtime/static analysis of the shipped Moises app and Studio bundle. Label observations vs inferences vs unknowns. | `01-MOISES-SURFACE.md`, `08-EVIDENCE-LOG.md` |
| `smart-explore` | Structural search of this repo when the current-state map is stale or a symbol is unclear. | Exact files/functions, not guesses |
| `context7` | Current docs for a library you are about to use (librosa, faster-whisper, chord model, React/Vite). | API/version facts, not memory |
| `mem-search` / `claude-mem` | Optional: “did we already decide this?” prior-session search. | Avoid re-litigating old decisions |

**Stop:** do not write a feature row without a source or a `path:line`. If a claim cannot be sourced,
write “unknown” or “inferred”.

## 2. Scope — `ponytail` (ultra)

- Load `ponytail` and set ultra for the scope cut.
- Ask: does this feature make the tab, the practice mix, or the flow shorter? If not, it waits.
- Write `04-SCOPE-CUT.md`. Name every cut. Keep the full matrix; cut the build order.
- The output is a decision, not a wish list.

**Stop:** if the scope is “everything now”, re-read the three-products section. Do not start a DAW.

## 3. Plan — `writing-plans`

- Load `writing-plans` before writing `06-PHASE-1-PLAN.md` or `11-DESKTOP-UI-REDESIGN.md`.
- Use the repo’s `PLANNING.md` structure; the plan must name files, interfaces, tests, and gates.
- Write the plan for an engineer who has not seen this codebase.
- Do not write code in the plan. Do not leave “figure it out” steps; a spike with a measurable gate is
  allowed.
- The UI plan has two layers: `10-MOISES-UI-CRAFT.md` is the design contract (tokens, screens, states,
  audit); `11-DESKTOP-UI-REDESIGN.md` is the build plan (UI-0–UI-9, file map, tests, gates). Do not
  merge them into one vague “make it pretty” task.
- `gsd-spec-phase` / `gsd-plan-phase` are **optional**. This program uses portable Markdown under
  `docs/plans/moises-parity/`, not a GSD `.planning/` workspace. Use GSD only if the user explicitly
  asks for the GSD workflow; do not mix the two state systems.

**Stop:** if a task has no test or no “done when”, it is not a task yet.

## 4. Build — `test-driven-development` + `systematic-debugging`

| Skill | Use | Rule |
|---|---|---|
| `test-driven-development` | Every analysis module, export path, and state helper. | Failing test → smallest code → green → next |
| `systematic-debugging` | Any failing test, model failure, or UI sync bug. | Reproduce → isolate → hypothesise → fix → verify; do not guess-patch |

- Use `context7` at the point of a new library call, not from memory.
- Use `ponytail` while coding: smallest complete change, no speculative abstraction.
- Run the narrow test after each task; run the full suite at each gate.

**Stop:** if a model cannot be licensed/pinned, or a dependency is >100 MB, stop and ask. Do not
“temporarily” add a cloud call.

## 5. UI craft — `apple-design` (core for Phase 1.5) + design audit

For Phase 1.5 this is a **core** skill, not an optional review. It is the lens for the current-app
audit and the final accessibility/responsive pass.

- Load `apple-design` before writing/reviewing `10-MOISES-UI-CRAFT.md` and before UI-0.
- Use the HIG references for Layout, Typography, Color, Lists and tables, Sidebars, Popovers, Dark
  Mode, Loading, Focus and selection, Accessibility, Designing for macOS, and cross-platform
  translation. Cite the page names; do not paste the HIG into the plan.
- Audit the current app against the HIG and the observed Moises UI. Separate **brand differences**
  (Tyrian/amber/Satoshi) from **craft gaps** (hierarchy, density, table semantics, 1024, focus).
- Do not let the skill turn the phase into a native macOS restyle or a Moises clone. It is a review
  lens and a set of principles, not a mandate to copy Apple chrome.
- Use `test-driven-development` for the pure token/model/event tests; UI rendering itself is verified
  by component builds plus the manual visual/accessibility matrix.
- Use `ponytail` to keep the Home component vanilla TS: no React, no CSS framework, no icon package,
  no speculative abstractions. Reuse the existing Vite/`streamlit-component-lib` pattern.
- Check keyboard/focus, labels, contrast, 1024/900, 200% zoom, reduced motion, and the 40-row case.
- If a UI finding requires a new feature (filters, editing, capo, setlist), stop; it is P2.

**Stop:** if the UI work needs a new dependency/font/model, or if Gate 0’s shell spike fails, stop and
use the documented fallback rather than forcing a broken layout.

## 6. Verify — `verification-before-completion`

- Load it before claiming a task/phase is done.
- Run the commands, read the output, then report.
- Evidence: test counts, `ruff`, `make mixer-build`, the three-song manual checklist, and the export
  A/B check.
- Never say “should work” when you have not run it.

## 7. Review — `requesting-code-review` / `receiving-code-review` / `ponytail-review`

| Skill | Use |
|---|---|
| `requesting-code-review` | Before merging a phase, ask for a review with the diff, the plan, and the evidence. |
| `receiving-code-review` | When feedback arrives: verify each point against the code, do not perform agreement, do not implement a wrong suggestion. |
| `ponytail-review` | Check whether the change is over-engineered, risky, untested, or slow. |

**Stop:** do not commit/push/tag/PR until the user approves in that conversation. A review is not
approval to ship.

## 8. Prompting — `prompt-master`

- Use it only to write/repair the portable build prompt (`07-BUILD-PROMPT.md`).
- Target: agentic coding tools (OpenCode/DeepSeek and Cursor). One prompt, scope-locked, stop
  conditions, evidence contract.
- Do not use it for the plan itself or for code comments.

## 9. Parallel work — `dispatching-parallel-agents` (limited)

- Allowed: independent research, vendor/licence checks, reading separate doc sets.
- Not allowed: two agents editing the same mixer, two heavy desktop jobs, or parallel Studio/practice
  builds.
- Desktop isolation and analysis are **serial**; do not let parallel agents defeat that.

## 10. What not to load for this program

| Skill | Why not |
|---|---|
| `autoresearch` | Optimising the skill/prompt is not the current job. |
| `gsd-*` suite | The program uses portable docs; mixing state systems adds overhead. Use only on explicit request. |
| `swiftui-expert`, `update-swiftui-apis` | No SwiftUI surface. |
| `brainstorming` | The evidence/scope work is done; re-opening ideation now is scope creep. Use only for a genuinely new product question. |
| `subagent-driven-development` | The phase plan is sequential and desktop-serial; use subagents only for independent research. |

## One-line order

**using-superpowers → reverse-engineer-anything + smart-explore + context7 → ponytail (ultra) →
writing-plans → test-driven-development (+ systematic-debugging) → apple-design (core for UI craft) →
verification-before-completion → requesting/receiving-code-review + ponytail-review → prompt-master.**

## Phase 1.5 UI order (concrete)

1. `apple-design` + `10` → audit and design contract.
2. `writing-plans` + `11` → file-level tasks, gates, rollback.
3. `ponytail` + `test-driven-development` → tokens, Home model, events, component scaffold.
4. `apple-design` → 1024/900 layout, table semantics, focus, contrast, reduced motion.
5. `systematic-debugging` → any shell/iframe/player regression.
6. `verification-before-completion` → Gate A–E evidence.
7. `requesting-code-review` + `ponytail-review` → diff/risk review; no commit without approval.
