# Phase 1 implementation plan — Song Workbench (desktop)

**Status 2026-10-20:** Tasks 1–14 implemented. Automated gate green; real Waltz run completed end to
end; manual three-song/install/playback checklist incomplete. Phase 1.5 (UI craft) is planned in
`10`/`11`; packaged lyrics are deferred to Phase 1.6. This file is the implementation history, not a
claim that the product is shipped.
**Scope:** desktop only. Do not edit `web/` or `backend/` in this phase. Web parity is Phase 2.
**Goal:** one real song, end to end, locally: import → separate → analyse → practise with chords,
sections, tab, count-in, A/B loop → export a matching mix and a tab PDF.

**Repo rules still apply.** Read `AGENTS.md`, `PROJECT_TREE.md`, and `PLANNING.md` before starting.
Do not commit, push, tag, or open a PR without explicit approval. Desktop isolation is serial. Model
weights download via SHA256-pinned `urllib`, never `huggingface_hub`.

**Test discipline:** every task adds or updates a test before the implementation. Run the narrow test
while working; run the full suite at each gate. The component has no test runner today; the plan keeps
the pure time-lookup logic in a separate module and uses a manual sync checklist unless the user
approves adding `vitest`.

---

## Task 0 — Baseline and decision record (no product code)

**Files:** `docs/plans/moises-parity/_work/analysis-decision.md` (new), `_work/spike-songs.md` (new).

1. Run the baseline:
   ```bash
   python -m pytest tests/ -q
   ruff check src/audio_to_tab
   ```
   Record the pass/fail count and the date. At Task 0 the suite was ~882 tests; the Phase 1 gate is
   now **1030 passed, 1 skipped**. Do not trust the old “809” that was in `AGENTS.md`.
2. Pick three local reference songs and record why:
   - clean electric guitar, little bleed;
   - dense full band with drums/bass/keys;
   - quiet intro / dynamic song.
   Do not commit the audio. Record local paths only.
3. Spike the chord recogniser. Compare at least:
   - a `librosa` chroma + template baseline (zero new dependency);
   - one pretrained CRNN/chord model (for example `chord-extractor`/BTC; verify licence, weights,
     CPU latency, and Python 3.11 compatibility).
   Measure weighted chord accuracy on a 60–90 s hand-labelled section, CPU time per minute, model size,
   and licence. Choose the baseline if the pretrained model cannot be licensed or pinned.
4. Spike lyrics with `faster-whisper` (or `whisper.cpp` if the Python package cannot be pinned):
   word timestamps, English first, model size, CPU time per minute, licence, and a local model path
   that does **not** call `huggingface_hub`.
5. Write `analysis-decision.md` with: chosen model, rejected model, measured numbers, download URL +
   SHA256, licence, and the fallback. If lyrics fails the gate, write “lyrics deferred to P2” and
   continue; do not add a cloud fallback.

**Done when:** the decision record names one chord path, one lyrics path (or an explicit defer), and
the three songs. No dependency is added until the licence and hash are recorded.

---

## Task 1 — Analysis schema and cache contract

**Files:** `src/audio_to_tab/analysis.py` (new), `tests/test_analysis.py` (new).

Define the shared JSON contract. Keep it boring and versioned:

```python
SCHEMA_VERSION = 1

@dataclass(frozen=True)
class ChordEvent:
    start: float
    end: float
    symbol: str
    confidence: float

@dataclass(frozen=True)
class Section:
    start: float
    end: float
    label: str
    confidence: float

@dataclass(frozen=True)
class LyricWord:
    start: float
    end: float
    text: str

@dataclass(frozen=True)
class LyricLine:
    start: float
    end: float
    text: str
    words: tuple[LyricWord, ...]

@dataclass(frozen=True)
class AnalysisResult:
    schema_version: int
    source_fingerprint: str
    duration_sec: float
    bpm: float | None
    bpm_confidence: str
    key: str | None
    key_confidence: str
    beats: tuple[float, ...]
    downbeats: tuple[float, ...]
    beats_per_measure: int
    chords: tuple[ChordEvent, ...]
    sections: tuple[Section, ...]
    lyrics: tuple[LyricLine, ...]
    lyrics_language: str | None
    models: dict[str, Any]
    warnings: tuple[str, ...]
    created_at: float
```

Functions:

```python
def save_analysis(path: Path, result: AnalysisResult) -> Path
def load_analysis(path: Path) -> AnalysisResult | None
def analysis_cache_key(source_fingerprint: str, model_versions: Mapping[str, str], settings: Mapping[str, Any]) -> str
```

Rules:
- Unknown/newer `schema_version` returns `None` and logs a warning; never crash the player.
- Missing optional fields default; malformed events are dropped individually, not the whole file.
- Times are seconds from the start of the **processed** audio (the same timeline as the stems).
- `start <= end`, sorted, non-overlapping where the type requires it.
- JSON uses plain dicts/lists; no numpy types.

**Tests:** round-trip, unknown version, missing file, malformed event, empty result, deterministic cache
key changes when model version/settings change.

**Done when:** `pytest tests/test_analysis.py -q` is green and the JSON shape is documented in the
module docstring.

---

## Task 2 — BPM, key, and beat grid

**Files:** `src/audio_to_tab/analysis.py`, `src/audio_to_tab/key.py` (new), `tests/test_key.py` (new).

- Reuse the **stored** `metronome_diagnostics.json` when present: `bpm`, `click_times_1x`,
  `beats_per_measure`, `downbeat_sec`, `bpm_curve`. Do not re-track beats for analysis; the metronome
  artifact is already the contract.
- If diagnostics are missing, fall back to `estimate_tempo_from_audio()` and a single beat grid. Record
  a warning that the grid is low confidence.
- `key.py`:
  ```python
  def estimate_key(audio_path: Path, *, bpm: float | None = None, beats: Sequence[float] = ()) -> tuple[str | None, str]
  ```
  Use chroma (beat-synchronous if beats exist) + Krumhansl-style profiles. Return `("F#m", "high")`
  or `(None, "low")`. Do not invent a key on silence.
- Convert `downbeat_sec` to a downbeat list aligned to `beats_per_measure`.

**Tests:** diagnostics precedence (no re-track), missing diagnostics fallback, key on a synthetic triad,
silence returns `None`, beat/downbeat ordering and bounds.

**Done when:** the three reference songs produce a BPM and key without running a second tempo tracker.

---

## Task 3 — Chord detection

**Files:** `src/audio_to_tab/chords.py` (new), `tests/test_chords.py` (new).

Interface:

```python
def detect_chords(
    audio_path: Path,
    *,
    beats: Sequence[float],
    bpm: float | None,
    model_dir: Path | None = None,
    progress: Callable[[str], None] | None = None,
) -> list[ChordEvent]
```

Rules:
- The P0 model is loaded lazily; a missing model returns `[]` + a warning, not an exception.
- Snap chord boundaries to the nearest beat when the model’s boundary is within a tolerance; keep
  model boundaries otherwise. Merge adjacent identical symbols. Drop events shorter than 0.10 s.
- Normalise symbols to a small vocabulary (`C`, `Cm`, `C7`, `Cmaj7`, `Cm7`, `Csus4`, `Cdim`, `Caug`,
  slash chords if the model emits them). Reject unknown symbols rather than passing garbage.
- Confidence is model-provided or `0.0` for the template baseline. Never fake high confidence.
- Do not run on the full mix if a `no_vocals` or `other` stem exists; the caller chooses the harmony
  source. The module just takes a path.

**Tests:** symbol normalisation, boundary snap/merge, silence/empty, model-missing path, events sorted
and within duration. Add a fixture of 8–12 hand-labelled chords and assert the merged output; keep the
accuracy measurement in the P0 decision record, not in the unit test.

**Done when:** the chosen path produces a chord list for all three songs and the UI can consume it.

---

## Task 4 — Section detection

**Files:** `src/audio_to_tab/sections.py` (new), `tests/test_sections.py` (new).

Interface:

```python
def detect_sections(
    audio_path: Path,
    *,
    beats: Sequence[float],
    duration_sec: float,
) -> list[Section]
```

Algorithm (keep it small):
- Beat-synchronous chroma + RMS.
- Self-similarity / recurrence matrix; checkerboard novelty; pick boundaries with a minimum section
  length (e.g. 8 s) and a minimum count.
- Label conservatively: first = `Intro`, last = `Outro`, repeated high-energy cluster = `Chorus`,
  repeated lower-energy cluster = `Verse`, one-off = `Bridge` or `Section`. Confidence from boundary
  strength; do not pretend the label is semantic truth.
- Cover `0..duration_sec` with no gaps; merge tiny sections; if the song is too short or silent, return
  one `Full song` section.
- Never fail the job: on error return one `Full song` + warning.

**Tests:** coverage/no gaps, sorted, minimum length, short song, silence, deterministic labels on a
synthetic repeated structure (monkeypatch the feature matrix if needed).

**Done when:** sections are useful for navigation on the three songs and the panel can loop them.

---

## Task 5 — Lyrics transcription (gated by Task 0)

**Files:** `src/audio_to_tab/lyrics.py` (new), `tests/test_lyrics.py` (new).

Interface:

```python
def lyrics_available(model_dir: Path | None = None) -> bool
def transcribe_lyrics(
    audio_path: Path,
    *,
    model_dir: Path,
    language: str | None = None,
    progress: Callable[[str], None] | None = None,
) -> tuple[list[LyricLine], str | None, list[str]]
```

Rules:
- Use the P0-approved local model. `faster_whisper` imports lazily; the module must import without the
  dependency installed.
- Word timestamps are required. If the model returns segment-only timestamps, treat word sync as
  unavailable and return lines without words (the UI still shows lines).
- Prefer the isolated `vocals.wav`; the caller chooses it.
- Clamp to `duration_sec`; drop empty/whitespace words; merge words into lines by segment.
- No network at runtime. Model download uses the existing `download_sha256_file` helper with a pinned
  hash and a documented URL.
- If the model is missing or fails, return `([], None, [warning])`; the job still succeeds.

**Tests:** fake transcriber injection (no model), word/line mapping, clamping, missing model, empty
audio, language passthrough. Mark a real-model test `@pytest.mark.slow` and skip unless the model is
present.

**Done when:** the three songs produce word-timed English lyrics, or the P0 decision explicitly defers
lyrics and this task is removed from the phase.

---

## Task 6 — Analysis orchestrator

**Files:** `src/audio_to_tab/analysis.py`, `tests/test_analysis_orchestrator.py` (new).

Interface:

```python
def analyze_audio(
    audio_path: Path,
    *,
    harmony_path: Path | None = None,
    vocals_path: Path | None = None,
    metronome_diagnostics: Path | None = None,
    source_fingerprint: str,
    duration_sec: float,
    include_lyrics: bool = True,
    progress: Callable[[str, str], None] | None = None,
) -> AnalysisResult
```

Order: BPM/beats (stored diagnostics) → chords → key → sections → lyrics (vocals path,
optional). Chords precede key so the key can use the chord histogram (Task 0 decision). Each stage
catches its own failure and appends a warning. The result always contains BPM/beats if the
diagnostics exist; a missing chord model does not invalidate the key/BPM.

**Tests:** stage order, a failing chord model still returns BPM/key/sections, `include_lyrics=False`
does not import/load the lyrics model, cache key stable, warnings preserved.

**Done when:** `analyze_audio` is a pure-ish orchestration layer with no UI imports and no hidden
network.

---

## Task 7 — Worker integration and progress

**Files:** `ui/isolate_jobs.py`, `ui/isolate_state.py`, `tests/test_isolate_jobs.py` (existing, extend),
`tests/test_isolate_state.py` (existing, extend).

1. Add an `analysis` stage (and `tab` if Task 8 runs in the same worker) to the visible stage list:
   - `ISOLATION_STAGE_ORDER`: insert `"analysis"` before `"done"`; add `"tab"` before `"analysis"` if
     tab is generated here.
   - `STAGE_WEIGHTS`: add a realistic share; progress is normalised by the stages actually present, so
     no manual rebalancing is required.
   - `STAGE_CHECKLIST_LABELS`: “Analyse song” and “Transcribe tab”.
   - `isolation_stages_for_job(..., analyse=True, tab=True)` so a job that cannot analyse (no
     diagnostics, no source) can omit the stage.
2. In `_run_one_job_inner`, after `separate_stems` and before `write_run_metadata`:
   - choose `harmony_path`: `no_vocals.wav` → `other.wav` → source;
   - choose `vocals_path`: `vocals.wav` → `None`;
   - call `analyze_audio` with the metronome diagnostics path;
   - write `analysis.json` in the run dir;
   - on failure, write `analysis_error` and continue to `succeeded` (separation is still useful).
3. `write_run_metadata` adds `artifacts["analysis"] = str(analysis_path)` and a small
   `meta["analysis"]` summary (BPM, key, section count, lyrics line count). Do not put the full arrays
   in `meta.json`.
4. Status: `analysis` progress stage; a warning field for partial results. Do not mark the job failed
   for a model download failure.
5. Re-separate children: write analysis into the child run dir only when they have their own meta; do
   not clobber the parent.

**Tests:** mocked `separate_stems` + `analyze_audio` writes `analysis.json`; analysis failure still
`succeeded`; stages include analysis; progress percentage monotonic; no analysis on a re-separate
parent.

**Done when:** a real job writes `analysis.json` and the status panel shows the analysis stage.

---

## Task 8 — Tab artifact in the run

**Files:** `src/audio_to_tab/tab_generate.py`, `ui/isolate_jobs.py`, `tests/test_tab_generate.py`
(existing, extend), `tests/test_isolate_jobs.py` (extend).

1. Add serialisation helpers:
   ```python
   def tab_document_to_dict(doc: TabDocument) -> dict[str, Any]
   def tab_document_from_dict(data: Mapping[str, Any]) -> TabDocument
   def tab_measure_spans(doc: TabDocument) -> list[dict[str, Any]]
   ```
   `tab_measure_spans` returns `{start, end, text}` per measure, using the doc tempo and
   `beats_per_measure`. The UI uses this for the current-bar highlight.
2. In the worker, after analysis and only if a `guitar.wav`/`guitar_stem.wav` exists:
   - call `run_pipeline(audio_path=guitar_stem, output_dir=run_dir/"tab", config=PipelineConfig(
     separate_stems=False, title=spec.title, ...), on_progress=...)`;
   - write `tab/tab.json` with the serialised document + measure spans;
   - add `artifacts["tab"]` (text), `artifacts["tab_pdf"]`, `artifacts["tab_json"]`,
     `artifacts["tab_midi"]` to meta;
   - on `EmptyTranscriptionError`, write a warning and continue; do not fail separation.
3. Do not run Basic Pitch twice. If the user later opens the Tab PDF page, it should reuse the existing
   artifact when the source fingerprint matches.

**Tests:** `tab_document_to_dict` round-trip; measure spans cover the song; worker calls `run_pipeline`
with `separate_stems=False` and the guitar stem; empty transcription is a warning not a failure; meta
contains the tab artifacts.

**Done when:** the three songs have `tab/tab.json`, `tab/transcription.tab`, and
`tab/transcription.pdf` in the run dir.

---

## Task 9 — Mixer component arguments and practice panel

**Files:** `ui/stem_mixer_component/__init__.py`, `ui/stem_mixer_component/frontend/src/main.ts`,
`ui/stem_mixer_component/frontend/src/analysis.ts` (new),
`ui/stem_mixer_component/frontend/src/style.css`, `ui/pages/isolate.py`.

1. Add args:
   ```python
   analysis: dict[str, Any] | None = None,
   tab: dict[str, Any] | None = None,
   initial_loop: dict[str, float] | None = None,
   count_in_bars: int = 0,
   ```
   Update the docstring and pass-through. Keep the args JSON-serialisable; do not pass numpy.
2. `analysis.ts` pure helpers:
   - `chordAt(chords, t)`, `sectionAt(sections, t)`, `lyricLineAt(lines, t)`,
     `measureAt(measures, t)`, `formatChordSymbol`, `clampLoop`.
   - Unit-test these if `vitest` is approved; otherwise keep them dependency-free and manual-check.
3. Render a collapsible `.mixer-practice-panel` beside/below the stems:
   - header tabs: `Chords`, `Sections`, `Lyrics`, `Tab` (hide a tab if no data);
   - Chords: bar/beat grid, current chord, chord diagrams, capo label; click a chord to seek;
   - Sections: list with time, label, loop button;
   - Lyrics: lines, current line highlight, click to seek; word highlight if words exist;
   - Tab: `<pre>` of the current measure group, current measure highlight, PDF download link;
   - empty state: “No chords found — re-run analysis” etc.
4. `onTimeUpdate` updates the panel at ~10 Hz, not every animation frame. Do not rerender the whole
   panel; toggle classes and text nodes.
5. Keep the existing stem rows, transport, speed/key, pan, metronome, picture, and presets. Do not
   change the pan law or solo rule.
6. On narrow widths, stack the panel below the stems; keep the mixer usable at 900 px.

**Tests:** `make mixer-build` succeeds and the build-completeness test passes. Manual checklist:
seek, loop, speed, key, mute/solo, open/close panel, keyboard focus, no layout jump. If `vitest` is
added, run it; do not add it silently.

**Done when:** the panel shows chords/sections/lyrics/tab for a real run and stays aligned after seek
and speed/key changes.

---

## Task 10 — Count-in and A/B loop

**Files:** `ui/stem_mixer_component/frontend/src/main.ts`,
`ui/stem_mixer_component/frontend/src/analysis.ts` (loop clamp), CSS,
`tests/test_mixer.py` (extend for Python-side constants if any).

1. Add a loop region to the engine:
   - `setLoopRegion(startSec: number | null, endSec: number | null)`.
   - Apply `loop`, `loopStart`, `loopEnd` to each source when starting; clamp to duration; minimum
     length 0.5 s; `start < end`.
   - When looping, the transport time should wrap, not stop. Keep the picture in sync.
2. Add count-in:
   - `setCountInBars(0 | 1 | 2)`; default 0.
   - On play, schedule the existing metronome click synth for N bars at the current tempo, then start
     the stems after the count-in. Show “Count-in 1/2…” in the status.
   - Count-in must not be included in the exported mix unless the explicit “include count-in” option is
     on. The default is off.
3. UI: a loop toggle + “Set loop from section” button; count-in select (Off / 1 bar / 2 bars). Persist
   in `project.json` when Task 11 lands.
4. Keyboard: `L` toggles loop, `C` cycles count-in; do not steal space/arrow keys from inputs.

**Tests:** pure clamp/loop math; manual audio check with speed 0.75× and key +2. Confirm no double
clicks and no drift after 10 loops.

**Done when:** looping a chorus and starting with a one-bar count-in works with the metronome on/off.

---

## Task 11 — Project manifest and mixer persistence

**Files:** `ui/project.py` (new), `ui/pages/isolate.py`, `ui/pages/home.py`,
`tests/test_project.py` (new), `tests/test_home.py` (extend).

Manifest `project.json` in the run dir:

```json
{
  "schema_version": 1,
  "title": "Song",
  "source_fingerprint": "...",
  "created_at": 0,
  "updated_at": 0,
  "mixer": {"volumesDb": {}, "pan": {}, "muted": {}, "soloed": {}, "masterVolumeDb": 0},
  "practice": {"rate": 1.0, "semitones": 0, "loop": null, "countInBars": 0},
  "analysis": "analysis.json",
  "tab": "tab/tab.json"
}
```

Rules:
- `meta.json` stays the run-index file; `project.json` is the mutable player state. Do not rewrite
  `meta.json` from the mixer.
- `load_project(run_dir)` returns defaults for missing files; unknown version returns defaults + a
  warning, not a crash.
- Save on mixer state change only when the serialised state differs; debounce/compare, do not write on
  every animation frame.
- Seed the mixer from `project.json` on open; write on “Save current mix”, on tab close, and at most
  once per second while playing.
- Home shows a small “BPM · Key · Sections” line when analysis exists, and a “Practice” action that
  opens the run’s mix tab.

**Tests:** round-trip, missing/old file, mixer state seeding, write-on-change, Home row with/without
analysis.

**Done when:** reopening a run restores volumes, pans, speed, key, loop, count-in, and opens the panel.

---

## Task 12 — Desktop export parity

**Files:** `src/audio_to_tab/mixer.py`, `ui/pages/isolate.py`, `tests/test_mixer.py` (extend),
`tests/test_desktop_export.py` (extend).

1. Add `pan_matrix(pan: int) -> tuple[float, float, float, float]` to `mixer.py` using the exact law in
   `ui/stem_mixer_component/frontend/src/pan.ts`:
   - `unit <= 0`: `ll=1`, `lr=cos((unit+1)*pi/2)`, `rl=0`, `rr=sin((unit+1)*pi/2)`;
   - `unit > 0`: `ll=cos(unit*pi/2)`, `lr=0`, `rl=sin(unit*pi/2)`, `rr=1`.
2. Extend `mix_stems_to_wav(..., pans: Mapping[str, int] | None = None)`:
   - apply the matrix per stem after gain, before summing;
   - center remains bit-identical to the old path (test it);
   - hard left/right route both channels correctly; total energy follows the existing pan law.
3. `_build_current_mix` passes `pans` from the mixer state and includes pan in
   `_mixer_export_fingerprint`. Remove the UI copy “saved files stay centered.”
4. Do **not** change the web export in this phase. Add a visible desktop note only if the web path is
   reachable from the same screen; web parity is P2.
5. Add a test that the exported mix fingerprint changes when pan changes but not when an inaudible
   stem’s pan changes.

**Tests:** center passthrough, hard left, hard right, pan + mute/solo, fingerprint.

**Done when:** the saved mix matches the desktop playback for pan, speed, key, mute/solo, and master.

---

## Task 13 — Home and flow polish

**Files:** `ui/pages/home.py`, `ui/pages/isolate.py`, `ui/isolate_state.py`,
`tests/test_home.py` (extend).

- Rename the primary Home action to **Learn a song** (or add it above the existing separation CTA).
- After a job succeeds, the Home/library row shows analysis status and a **Practice** button.
- Opening a job with `analysis.json` goes straight to the mixer with the practice panel open.
- Opening a job without analysis shows a small “Analyse” action, not a broken panel.
- Keep the existing tabs, recents, queue, YouTube, and Tab PDF flows working. Do not delete or reorder
  unrelated actions.

**Tests:** source-level assertions for the new labels/actions; manual smoke.

**Done when:** a first-time user can start from Home, pick a song, and land in the practice view without
knowing the word “isolate”.

**Status 2026-10-20:** implemented. Home has the primary “Learn a song” action, an analysis line
(`BPM · Key · N sections`), `Practice` for analysed runs, and `Analyse` for older runs. The real Waltz
run opens the mixer with the practice panel; `project.json` is created. The visual craft is the
Phase 1.5 gap — see `10` §2 and `11`.

---

## Task 14 — Verification and handoff

Run, in order:

```bash
python -m pytest tests/ -q
ruff check src/audio_to_tab
make mixer-build
# only if the component test harness was approved:
# cd ui/stem_mixer_component/frontend && npm test
```

Then the three-song manual checklist:

- [ ] Import → separate → analysis status completes; no terminal errors.
- [ ] Chords highlight in time; diagrams match the symbol; click-to-seek works.
- [ ] Sections list covers the song; loop a chorus; no gap/overlap.
- [ ] Lyrics highlight (if enabled); click a line to seek; no drift after pause/resume.
- [ ] Tab panel shows the current measure; PDF opens; tab matches the guitar stem, not the mix.
- [ ] Count-in of 1 and 2 bars; A/B loop after seek, speed change, key change.
- [ ] Save mix matches playback (pan, speed, key, mute/solo, master).
- [ ] Reopen the project: mixer/loop/count-in restored.
- [ ] Network off: playback and analysis cache work.
- [ ] 8 GB Mac: analysis runs after separation, serial, no UI freeze.

**Checklist status 2026-10-20:** the Waltz path covers import → separate → analysis → chords/sections/
tab → PDF; the synthetic run covers Home Analyse/Practice/project restore. The three-song matrix,
lyrics in a real mix, actual playback/count-in audio, network-off, 8 GB Mac, and installer are still
open. See §Verification log.

Update `PROJECT_TREE.md` with the new modules and artifacts. Add a short “Phase 1 shipped” note to
`docs/plans/moises-parity/README.md` only after the gate passes. Do not commit unless the user approves.

---

## Verification log — 2026-10-20

This is the evidence for the status above. Commands were run from the repo root with the dev
`.venv311` unless noted. No commit/push/tag/PR was made.

### Automated gate

| Check | Result |
|---|---|
| `python -m pytest tests/ -q` | **1030 passed, 1 skipped** after the final media/lyrics/review changes |
| `ruff check src/audio_to_tab` | clean |
| `cd ui/stem_mixer_component/frontend && npx tsc --noEmit` | clean |
| `make mixer-build` / committed build | present and complete (component tests pass) |
| `cd web && npx tsc --noEmit` | **8 pre-existing errors**, unchanged: `App.test.ts` Node types; `engine.ts` closed/`playsInline`/unused symbols. `web/` was not edited in Phase 1. CI does not run tsc. |

The full suite was rerun after the PDF mime fix and the lyrics lazy-exception fix. The one skip is
pre-existing; record the exact skip reason from the pytest output before release. A skip is not a pass.

### Real Waltz run

Local file: the supplied Waltz reference (not committed). Run directory:
`data/ui_runs/46b84e7b-dbb5-4c25-817a-53c4cd85b02d` (local artifact; do not commit audio).

| Result | Value |
|---|---|
| Wall time | 124.9 s |
| Stems | 6 (guitar/vocals/drums/bass/piano/other) |
| BPM | 105.47, high confidence |
| Key | Dm, high confidence |
| Chords | 145 draft events |
| Sections | 7 |
| Lyrics | 0 lines (instrumental); path skipped without a vocals stem |
| Tab | 55 measures; tab JSON/MIDI/PDF written |
| Artifacts | `analysis.json`, tab JSON/MIDI/PDF present |

UI checks on this run:

- Home row shows `BPM 105.5 · Dm · 7 sections` and a `Practice` action.
- Practice opens the mixer with 6 stems.
- Chords/Sections/Lyrics/Tab tabs render; the Tab measure view shows fretted strings and the next
  measure; the PDF link opens.
- `project.json` was created with analysis/tab refs.
- The Chords tab shows the draft-chord label (`Draft chords — a starting point; verify by ear.`).

### Synthetic and Home checks

- Synthetic 30 s run: analysis succeeded with warnings; Home row updated to `BPM 92.3 · E · 1
  section`; Practice opened the mixer; `project.json` created; draft label shown.
- Home `Analyse` on an older run is a synchronous one-shot guarded by `worker_busy()`; success with
  warnings reports `"Analysis ready with warnings: …"` and uses warning styling.
- Manual synthetic smoke verified practice tabs, diagrams, section loops, count-in select, project
  persistence/restoration, and the draft chord label.
- Headless Chrome AudioContext is suspended, so **actual playback/count-in audio/save-mix were not
  manually verified** in the headless pass. UI state, persistence, and control wiring were verified;
  the listening checklist remains open.

### PDF link fix

`media_url_for_file` hardcoded `audio/wav`, so the tab PDF URL ended in `.wav`. Added
`media_mimetype_for_path` (`application/pdf`, `audio/wav`, fallback) and a test. Verified
`/media/f4b69a26d6b98f4c1a5ed6067ed1e5c2.pdf`:

- HTTP 200;
- `content-type: application/pdf`;
- body begins `%PDF-1.3`.

### Lyrics UI and engine

- Injected temporary real Japanese lines into a run's `analysis.json`; the Lyrics tab appeared, word
  spans and click-to-seek data rendered. The original `analysis.json` was restored; no debug prints or
  backup files remain.
- Direct real lyrics validation on a 45 s full-band excerpt (using the mix WAV as `vocals_path`):
  7 Japanese lines, language `ja`, word timestamps present. Errors from mix bleed are expected; this
  is evidence the model path works, not an accuracy claim.
- `transcribe_lyrics` now catches exceptions raised lazily while consuming faster-whisper segments,
  preserving partial lines and adding a warning. Test:
  `test_lazy_segment_error_keeps_partial_lines` in `tests/test_lyrics.py`.
- Full-band analysis on the 45 s excerpt: BPM 123.046875 low, key C#m high, 27 draft chords, 4
  sections; lyrics skipped without a vocals stem, as designed.

### Known failure / environment caveat

A 45 s/full-length Demucs separation under the temporary torchaudio/FFmpeg shim fails at the end with
the original `libtorchcodec`/FFmpeg error, despite writing all six stems. A 2 s run succeeds. Job
`0003f15e14e549bc984b8eea06ceae05`, run `b1e4f90b-82b4-4c4d-82be-ae8f56f40990`; status says
`Demucs failed` and `status.artifacts` is empty. This is a **dev-environment issue**, not proven
product-safe; do not cite the 45 s attempt as a successful full-length run. The real Waltz run above
succeeded through the normal path.

### Packaged lyrics decision

**Deferred to Phase 1.6.** The dev path works, but the frozen desktop installs
`.[demucs,desktop,roformer,separator]` without the `analysis` extra, the PyInstaller spec does not
collect `faster_whisper`, and there is no first-run model download UI. The pinned model must currently
be pre-seeded in `~/.cache/audio_to_tab/analysis/faster-whisper-small`. Phase 1.6 decides include vs
ship-without; Phase 1.5 only designs the Lyrics empty/availability states. No release/spec change was
made in Phase 1.

### Code review / unverified items

- The uncommitted Phase 1 changes include `tab_generate.py`, `analysis.py`/`chords.py`,
  `ui/project.py`, and the mixer practice panel. The automated gate is green; a line-by-line review
  and the manual listening checklist are still handoff items. Do not claim “reviewed” without a
  separate pass.
- Real three-song regression (quiet/dynamic, dense, instrumental), network-off, 8 GB Mac, and
  installer smoke are still open.
- Gate 1 chord accuracy is not certified: no labelled real-song chord/boundary corpus. Evidence is
  draft quality plus fixture ground truth.
- The 45 s job remains visible in the queue (queue chrome, not a navigation failure). Clean it up
  deliberately; restart Streamlit only when no job is running (`fileWatcherType=none`).

---

## Rollback plan

- Analysis is additive: if it fails, the run still has stems and the old mixer. Delete `analysis.json`
  and the panel hides.
- Tab is additive: if Basic Pitch fails, keep the run and show the warning; the existing Tab PDF page
  still works.
- Project manifest is additive: if `project.json` is missing/corrupt, seed from the current session
  defaults and continue.
- The pan export change is the only behavioral change to an existing output. Keep the old path behind
  `pans=None` so a regression can be isolated in one call.

## Explicit non-goals (do not “helpfully” add)

- No web/backend edits, no cloud, no accounts, no collaboration.
- No Studio/DAW, timeline, MIDI editor, effects, or VST.
- No AI stem/voice/mastering generation.
- No chord/lyric editing UI, capo, setlists, or batch upload.
- **Phase 1 only:** no new design system, no iframe rewrite, no second player. **Phase 1.5 supersedes
  the UI clause** with a bounded token layer + Home component + player recomposition; it still does
  not rewrite the audio engine or add a second player (`11`).
- No commit/push/tag/PR.
