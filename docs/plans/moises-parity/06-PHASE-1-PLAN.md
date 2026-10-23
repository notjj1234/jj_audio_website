# Next phase — Home shell, after the 2.1.0 rescan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the desktop Home shell in `11-DESKTOP-UI-REDESIGN.md` §12 without pretending the pixel numbers were remeasured on Moises 2.1.0.

**Architecture:** Streamlit shell plus the existing Home component behind `AUDIO_TOOLS_UI_V2`. No new backend. No mixer law changes.

**Tech Stack:** The desktop UI already in `ui/`. Python 3.12. Streamlit. The Vite Home component `11` already names.

## Global Constraints

- `MPS_MIN_RAM_GB` stays `12.0` in `src/audio_to_tab/hardware.py`.
- Desktop Interface Lite is not hosted `lite`.
- Desktop isolation jobs stay serial.
- Do not copy Moises artwork, font files, or markup.
- No commit, push, or PR unless the user asks in that conversation.
- If a Moises pixel is required as parity, remeasure 2.1.0 first. Otherwise the numbers in `10` §13 are our spec, and the doc must say so in the PR text.

---

### Task 1: Choose the measurement stance

**Files:**
- Modify: `docs/plans/moises-parity/10-MOISES-UI-CRAFT.md` (one sentence in the 2026-10-23 banner, only if the stance changes)
- Test: none (documentation gate)

**Interfaces:**
- Consumes: `PAGE-INVENTORY.md` blocker on visual capture
- Produces: a written stance, either "remeasured on 2.1.0" or "our spec, not Moises parity"

- [x] **Step 1:** Moises was not remeasured. The display was left alone. Do not press Esc on a fullscreen video.

- [x] **Step 2:** Stance written into `10`: our spec, not Moises 2.1.0 parity. No new pixels.

### Task 2: Implement Home from `11` §12

**Files:**
- Modify: the files `11` §12 already lists
- Test: `tests/test_home.py`

**Interfaces:**
- Consumes: Task 1 stance
- Produces: Home behind `AUDIO_TOOLS_UI_V2`, old Home when the flag is `0`

- [x] **Step 1:** `11` §12 is already in the tree. No second implementation.

- [x] **Step 2:** `pytest tests/test_home.py tests/test_home_component.py` — 14 passed. `tsc --noEmit` in the Home frontend — exit 0.

- [x] **Step 3:** Flag on, measured in the browser: sidebar 240 and no page scroll at 1440, 1280, 1024, and 900. Cards 100px, recents 150×210, rows 56px. Search with no hits shows the empty copy and clearing it restores the rows. Sort menu opens and Escape closes it.

### Task 3: Rollback check

- [x] **Step 1:** `AUDIO_TOOLS_UI_V2=0` on port 8502. Sidebar 300 at 1440 and at 900. Header visible. Legacy "Learn a song" button. No Home iframe.

- [x] **Step 2:** Default flag on port 8501. Home iframe present, sidebar 240, header hidden.

Do not start Phase 2 in this plan.
