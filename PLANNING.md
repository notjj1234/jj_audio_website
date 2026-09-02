# PLANNING.md

## Purpose

This file guides how to plan multi-step work in this codebase. Just as `AGENTS.md` governs execution, this governs the planning phase — what to investigate, how to structure a plan, and what to verify before handing a plan to the user.

## When to plan

Plan before touching code on anything non-trivial:

- New features or UI surfaces
- Multi-file changes or refactors
- Anything touching the shared engine boundary
- Changes that affect desktop packaging, CI, or deployment
- Cross-cutting concerns (auth, config, storage)

A one-line typo fix does not need a plan. Use judgment.

## Pre-planning checklist

Before writing a plan, do the following. Every time.

1. **Read `PROJECT_TREE.md`** — identify the exact files and modules involved. Use the "change X → start here" table.
2. **Read `AGENTS.md`** — know the commands, test quirks, and gotchas that apply to the affected surface(s).
3. **Read `docs/issues.md`** — check whether the feature area has prior design decisions or rejected approaches.
4. **Identify the surface(s)** — which of these does the plan touch?
   - Desktop (Streamlit `ui/`)
   - Website (React `web/` + FastAPI `backend/`)
   - Shared engine (`src/audio_to_tab/`)
   - Tests (`tests/`)
   - Packaging / CI
5. **Explore the relevant files** — read the actual code that will change. Do not plan from memory or assumptions.

## Planning workflow

```
requirements → codebase exploration → design → written plan → user review
```

1. **Gather requirements** — understand what the user wants and why. Ask clarifying questions if ambiguous.
2. **Explore the codebase** — read the files that will be affected. Understand the existing patterns, data flow, and constraints.
3. **Design the approach** — decide what changes are needed, in what order, and what alternatives were considered.
4. **Write the plan** — structured document (see template below) that the user can review and approve.
5. **User review** — present the plan. Do not proceed to implementation until the user approves.

## Plan structure

Every plan should contain these sections. Omitting a section is acceptable only when it is genuinely not relevant.

### Goal

One sentence. What does this plan accomplish? What is the user's intent?

### Scope

Which surfaces are affected. Be explicit:

- [ ] Desktop (`ui/`)
- [ ] Website (`web/`)
- [ ] API (`backend/`)
- [ ] Engine (`src/audio_to_tab/`)
- [ ] Tests (`tests/`)
- [ ] Packaging / CI
- [ ] Docs (`PROJECT_TREE.md`, `AGENTS.md`, etc.)

### Files

List every file to be created or modified, with a brief note on why:

| File | Action | Purpose |
|------|--------|---------|
| `path/to/file.py` | Modify | What changes and why |
| `path/to/new_file.py` | Create | What it does |

### Implementation steps

Ordered list. Group by logical unit (not by file). Note dependencies between steps.

```
1. [depends on: nothing] — Do X
2. [depends on: 1] — Do Y using the output of X
3. [depends on: nothing] — Do Z (parallel-safe with 1–2)
```

### Verification

How to confirm the plan worked. Include specific commands where applicable:

- [ ] Lint passes: `ruff check src/audio_to_tab`
- [ ] Tests pass: `.venv311\Scripts\python.exe -m pytest tests/ -q`
- [ ] Web tests pass: `cd web && npm test`
- [ ] Manual verification: what to check and how
- [ ] No regressions in unaffected surfaces

### Gotchas

Anything from `AGENTS.md` or the codebase that could trip up implementation. Examples:

- "Desktop packaging must not ship `backend/` — CI asserts this."
- "Tests mock torch/demucs but a few assert a real Demucs is importable."
- "`st.expander()` does not support `help` kwarg — use `st.caption()` inside."

## Project-specific considerations

These are not optional. Every plan must account for them where relevant.

### Two products, one engine

The shared engine (`src/audio_to_tab/`) is imported by both desktop and website. Changes to the engine can break either surface. Plans that touch the engine must:

- Note which product surfaces use the changed code
- Include testing for all affected surfaces
- Avoid leaking desktop-only or website-only concerns into the engine

### Desktop vs website parity

Desktop (Streamlit) and website (React) often have parallel UI for the same feature. When planning changes to one:

- Consider whether the other surface needs the same change
- Note whether parity is required or intentionally divergent
- Do not assume Streamlit APIs exist in React or vice versa

### Streamlit gotchas

- `st.expander()` does not accept `help` — use `st.caption()` inside
- Streamlit re-runs the entire script on every interaction — state management matters
- Desktop iframe mixer output (`frontend/build/`) is committed; rebuild with `make mixer-build`

### Testing quirks

- Tests mock torch/demucs; a few assert real Demucs is importable (need `[dev,demucs]` profile)
- YouTube tests skip unless `RUN_YOUTUBE_INTEGRATION=1`
- macOS CI deselects `test_upload_and_job` (tensorflow issue)

### Packaging constraints

- `$env:AUDIO_TOOLS_EDITION = "cpu" | "cuda"` selects freeze flavor
- Desktop onedir must not ship `backend/`, `web/`, or `.env*`
- `packaging/ffmpeg/` is gitignored and must be downloaded before desktop builds

## Anti-patterns

Do not do these things in a plan:

- **Plan across too many surfaces at once.** Split into separate plans if touching engine + desktop UI + website.
- **Skip the shared engine boundary.** A change to `src/audio_to_tab/` that only tests on desktop may break the website.
- **Forget desktop packaging.** If you add a new dependency, it must be available in the frozen environment.
- **Assume APIs without checking.** Read the actual source. `st.expander(help=...)` looked reasonable but was wrong.
- **Plan without reading `PROJECT_TREE.md`.** The "change X → start here" table exists for a reason.
- **Skip verification steps.** Every plan must end with "how do we know this works."
- **Bundle multiple unrelated changes.** One plan, one goal. Multiple goals → multiple plans.

## After plan approval

Once the user approves a plan:

1. Create a todo list from the implementation steps
2. Execute in order, respecting dependencies
3. Run verification commands at each step (not just at the end)
4. If a step fails, stop and reassess — do not pile on more fixes
5. Report completion with evidence (test output, lint output)
