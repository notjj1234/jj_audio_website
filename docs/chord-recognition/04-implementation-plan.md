# 04 — Implementation plan: chords that are right, bars that are right, chart that follows

**Goal:** move the desktop practice player from "draft chords on a full mix, 4/4 assumed, chart
that doesn't scroll" to a chart a musician would trust: correct *symbol*, correct *bar*, visible
*follow*, and an exportable document.

**Grounding:** every baseline number in this document is measured and cited in
`01-current-system-audit.md`; competitor behaviour is in `02-moises-behaviour-spec.md`; method and
licence choices are in `03-sota-research.md`.

**Non-goals:** no Moises cloning, no hosted-analysis work (the backend has no analysis worker), no
paid corpora, no new global dependencies in Phase 1–5. Phase 6 is optional and gated.

**Rule for this plan:** a step is done when its named test passes. No step says "improve X"; each
one names a file, a symbol and an assertion.

---

## 1. Target architecture

```
                       ┌──────────────────────────────────────────────┐
 stems / mix ─────────►│ 1. harmony source selection  (NEW RULES)     │
                       │    guitar+piano+other+bass  >  no_vocals     │
                       │    > other  > mix        (never delete last) │
                       └───────────────────┬──────────────────────────┘
                                           ▼
                       ┌──────────────────────────────────────────────┐
                       │ 2. front end                                 │
                       │    estimate_tuning → chroma_cqt(tuning=t)    │
                       │    hpss → harmonic component                 │
                       │    bass chroma (CQT, octaves 2–4)            │
                       └───────────────────┬──────────────────────────┘
                                           ▼
   provisional key (chroma) ──────────────►┌──────────────────────────┐
   Krumhansl + bass tie-break              │ 3. scorer v2             │
                                           │    weighted templates    │
                                           │    z-normalised scores   │
                                           │    quality prior + key   │
                                           └──────────┬───────────────┘
                                                      ▼
                                           ┌──────────────────────────┐
                                           │ 4. decoder               │
                                           │    Viterbi (z-units)     │
                                           │    metrical prior        │
                                           │    min-duration merge    │
                                           └──────────┬───────────────┘
                                                      ▼
                              ┌───────────────────────────────────────┐
                              │ 5. ChordTrack (per event)             │
                              │    root, bass, quality, symbol,       │
                              │    confidence, simple, medium         │
                              └──────────────┬────────────────────────┘
                                             ▼
                    ┌──────────────────────────────────────────────┐
                    │ 6. key (from decoded chords + bass)          │
                    │ 7. chart document: bars × beats, sections,   │
                    │    lyrics, spelling                          │
                    └──────────────┬───────────────────────────────┘
                                   ▼
        ┌──────────────────┬───────────────────┬──────────────────────┐
        │ desktop strip    │ hosted sheet      │ export               │
        │ rAF + scroll     │ rAF + highlight   │ MusicXML / text      │
        └──────────────────┴───────────────────┴──────────────────────┘
```

Two ordering decisions matter and are not obvious:

1. **Key is computed twice.** A provisional key from chroma feeds the chord prior; the final key is
   recomputed from the decoded chords. Today key is derived *only* from chords (`key.py:198-202`),
   which is circular: a chromatically-biased chord track produces a key that then justifies itself.
2. **Rendering is downstream of detection.** The event carries one detected label plus derived
   `simple`/`medium` strings. The UI never re-derives harmony. This is the cheap version of
   Moises's poly-label annotations (`02` B-21) without pretending we have their model.

---

## 2. Per-stage specification

### 2.1 Harmony source selection — `ui/isolate_jobs.py:1396-1408`

**Problem (measured):** the reference run analysed `source.mp3`. `htdemucs_6s` emits
`drums,bass,other,vocals,guitar,piano`; `fold_other_into_guitar` can delete `other.wav`; the current
code looks only for `no_vocals` then `other`, so it falls through to the full mix.

**New rule, in order:**

| Priority | Condition | Source |
|---|---|---|
| 1 | `guitar.wav` exists | sum of `guitar + piano + other + bass` (skip missing; `other` optional) |
| 2 | `no_vocals.wav` exists | that file |
| 3 | `other.wav` exists | that file |
| 4 | anything else | full mix, and log `harmony_source="mix_fallback"` |

**IO:** reads stem paths; returns `(path, source_kind)`; writes both into
`analysis_diagnostics.json` under `harmony_path` / `harmony_source_kind`.

**Never** delete `other.wav` when `guitar.wav` is absent — that deletion is what caused the fallback.
Audit `fold_other_into_guitar` and guard the unlink with "only if guitar stem exists".

**Test:** `tests/test_isolate_jobs.py::test_harmony_source_prefers_stem_sum` and
`::test_harmony_source_keeps_other_when_no_guitar`.

### 2.2 Front end — `src/audio_to_tab/chords.py`

| Step | Call | Params | Why |
|---|---|---|---|
| tuning | `librosa.estimate_tuning(y=y, sr=sr)` | default | `chroma_cqt(tuning=None)` does no tuning correction (verified in librosa source; audit H4) |
| harmonic | `librosa.effects.hpss(y)` | defaults | removes drum transients from chroma; cheap |
| chroma | `librosa.feature.chroma_cqt(y=harmonic, sr=22050, hop_length=512, tuning=tuning)` | `bins_per_octave` default 36 | keep current hop/window |
| bass chroma | `librosa.feature.chroma_cqt(y=y, sr=sr, hop_length=512, octwidth=2)` | `octwidth=2` emphasises low octaves | inversions and root disambiguation |

**Cost:** measured 0.34 s chroma for 125 s audio; HPSS roughly doubles front-end cost — still
under 1 s. Budget in §7.

**Gate:** tuning estimate on the 30-cent-detuned synthetic track is within ±0.15 semitone
(`tests/test_chords.py::test_tuning_estimated_on_detuned_render`).

### 2.3 Scorer v2 — `src/audio_to_tab/chords.py`

Replace the binary template matrix with **weighted** templates:

```python
_TONE_WEIGHTS = {"root": 1.00, "third": 0.90, "fifth": 0.70, "seventh": 0.55,
                 "sixth": 0.55, "ninth": 0.45, "eleventh": 0.35, "thirteenth": 0.30}
```

A chord tone's weight reflects how much evidence it contributes; the fifth is doubled by the root's
3rd harmonic, so it is down-weighted to stop it voting twice. This directly attacks the measured
`maj7` bias: the major 7th is also the 3rd harmonic of the major third, so its weight must be
*lower* than the third's, not equal.

**Score normalisation (the important change):** per window, z-score across the 12·Q candidate
scores before adding priors:

```python
scores = (scores - scores.mean(axis=1, keepdims=True)) / (scores.std(axis=1, keepdims=True) + 1e-9)
scores = scores - _QUALITY_PRIOR[None, :] - key_prior[None, :]
```

Priors are therefore in **standard deviations**, not raw cosine units. The current absolute
`0.03` (`chords.py:53`) is meaningless without knowing the score spread — that is why it does
nothing.

**Prior table (in σ):**

| Quality | Prior | Basis |
|---|---|---|
| `maj`, `min` | 0.0 | default |
| `7` | 0.10 | common but over-fires on blues/rock |
| `maj7` | **0.55** | measured 40–66 % of events on band mixes |
| `m7` | 0.15 | over-fires on the waltz (29/145) |
| `6`, `m6` | 0.45 | rare in the repertoire we serve |
| `sus4`, `sus2` | **0.50** | 23–34 % of waltz events; also masks thirds |
| `dim`, `aug` | 0.35 | rare, unstable under detune |
| `m7b5` | 0.30 | jazz-only |

**Key prior:** +0.20 σ for qualities diatonic to the provisional key's scale (triads/sevenths built
on degrees 1–7); −0.10 σ for roots outside the key. This is the "no key-aware prior" gap (audit H8).

**Vocabulary expansion** happens in `_QUALITY_INTERVALS` only — add `sus2`, `6`, `m6`, `m7b5`,
`mMaj7`, `5` (power). Parse/render moves to `chord_symbols.py` (§2.6), and `chords.py` imports it so
there is one grammar.

**Test:** `tests/test_chords.py::test_maj7_prior_beats_overtone_template` — a synthetic C major
triad with a strong 3rd harmonic must decode as `C`, not `Cmaj7`.

### 2.4 Decoder — `src/audio_to_tab/chords.py:164-188`

| Change | From | To | Reason |
|---|---|---|---|
| switch penalty | `0.06` raw cosine | `0.8` σ | 0.06 vs a 0.25 score span is ~0.2 σ — far too weak |
| metrical prior | none | −0.15 σ to change **off** a downbeat; +0.10 σ to change **on** one | chords change on bars, not mid-beat |
| minimum duration | drop events < 0.10 s at the end | merge runs < 0.5 beat into the louder neighbour | dropping leaves holes; the audit shows 50 % of events < 1 beat |
| silence | skip window if `norm < 1e-6` | same, but emit an explicit `N` region | prevents phantom chords in intros |

**Output:** `confidence = softmax_top1 - softmax_top2` over the three best states in that window,
clamped to [0,1]. Today it is hard-coded `0.0` (`chords.py:309`), which forces the UI to label every
chart "Draft" (`main.ts:2828-2831`) — a trust bug, not a cosmetic one.

**Test:** `tests/test_chords.py::test_short_flicker_is_merged`,
`::test_confidence_is_not_constant`, `::test_no_chords_in_silence`.

### 2.5 Meter / downbeat — `src/audio_to_tab/metronome.py:891-941`

Current behaviour: score candidates, and **return 4 whenever contrast is weak**
(`metronome.py:935-941`). The reference waltz is stored as 4/4.

New scoring:

1. Candidates `(2, 3, 4, 6)`.
2. Accent series = RMS of the percussive component in a ±60 ms window around each beat.
3. For each *m*, fold the series at period *m*; score = mean of the top position ÷ mean of the
   others, **averaged over all complete bars** (consistency, not one lucky bar).
4. Pick the best; apply a **tie-break prior of 1.03 in favour of 4**, not a default.
5. Write `meter_confidence = best / runner_up` and `meter_candidates` into
   `metronome_diagnostics.json`.

**Test:** `tests/test_metronome.py::test_three_four_waltz_detected` (new fixture: 3/4 click + bass on
1) and `::test_four_four_not_regressed` (existing 4/4 fixture). Also
`::test_weak_contrast_keeps_4_but_low_confidence`.

### 2.6 Symbol grammar — new `src/audio_to_tab/chord_symbols.py`

One module, one grammar. `chords.py`'s `_parse_head` / `_quality_from_rest` / `_normalize_symbol`
(`chords.py:73-133`) and `key.py`'s `_parse_chord` (`key.py:39-62`) currently duplicate this.

```python
@dataclass(frozen=True)
class Chord:
    root: str                  # "C#"
    quality: str               # "maj7"
    bass: str | None = None    # "E" for C/E

def parse(symbol: str) -> Chord | None: ...
def render(chord: Chord, *, spelling: str = "sharp") -> str: ...
def transpose(chord: Chord, semitones: int) -> Chord: ...
def capo_shape(chord: Chord, fret: int) -> Chord: ...   # existing behaviour, moved
def level_symbol(chord: Chord, level: str) -> str: ...  # see §3
def chord_tones(chord: Chord) -> tuple[str, ...]: ...   # "every note in the chord"
```

`chords.py` re-exports `_normalize_symbol = chord_symbols.parse_render` for backward compatibility
so no other module breaks.

**Test:** `tests/test_chord_symbols.py` — round-trip every template name, flats in, sharps out,
`C/E` preserved, `H`/`N`/garbage → `None`.

### 2.7 Key — `src/audio_to_tab/key.py`

```python
def provisional_key(chroma_mean: np.ndarray, bass_mean: np.ndarray) -> tuple[str, float]:
    """Krumhansl correlation over 24 keys; bass energy on the tonic breaks relative maj/min ties."""
```

- Correlate the duration-weighted chroma mean against Krumhansl–Kessler major/minor profiles.
- If `|score(rel_maj) - score(rel_min)| < 0.05`, pick the one whose tonic has more **bass** energy.
- Final key still comes from `_key_from_chords` (`key.py:65-123`), now using the shared parser and
  duration × metrical weighting (a chord on beat 1 counts 1.5×).
- Confidence = margin between top two keys, normalised.

**Test:** `tests/test_key.py::test_relative_minor_broken_by_bass`,
`::test_provisional_key_matches_profile_on_c_major_scale`.

### 2.8 Chart document model — new `src/audio_to_tab/chart.py`

The exportable artefact (and the desktop/hosted renderer input) is a document, not a chip list:

```python
@dataclass(frozen=True)
class ChartBar:
    index: int
    start: float
    end: float
    meter: int
    cells: tuple[ChartCell, ...]     # one per beat; cell.chord is None on a held beat

@dataclass(frozen=True)
class ChartDocument:
    title: str
    key: str
    bpm: float
    time_signature: str             # "4/4", "3/4"
    bars: tuple[ChartBar, ...]
    sections: tuple[Section, ...]
    lyrics: tuple[LyricLine, ...]
```

Built from `AnalysisResult` + `BeatGrid` by a pure function; no audio access, fully unit-testable.
`ChartCell.chord` is filled **only where the chord changes**; continuation cells are `None`, which
is what makes a chart readable instead of a wall of repeated symbols.

**Test:** `tests/test_chart.py::test_three_four_gives_three_cells`,
`::test_chord_only_on_change`, `::test_sections_align_to_bar_starts`.

---

## 3. Vocabulary and the three display levels

### 3.1 Detected vocabulary (what the model may output)

12 roots × 12 qualities + `N`:

`maj`, `min`, `dim`, `aug`, `sus2`, `sus4`, `5`, `6`, `m6`, `7`, `maj7`, `m7`, `m7b5`,
`mMaj7`, `dim7` — plus an optional `/<bass>`.

That is 12 × 15 + 1 = **181 states**, against 96 today. Bigger is only safe because of the prior +
z-normalisation work in §2.3; do **not** ship the vocabulary expansion before the priors.

### 3.2 Rendering rules (`level_symbol`)

| Level | Rule | Example |
|---|---|---|
| **simple** (default) | reduce to a triad; drop 7ths/6ths/9ths/extensions; keep sus as sus; keep slash bass | `Cmaj7` → `C`; `Dm7` → `Dm`; `G7/F` → `G/F`; `Asus4` → `Asus4` |
| **medium** | simple + seventh where the seventh is *structural* (7, maj7, m7, m7b5, dim7); drop 6/9/11/13 and alterations | `Cmaj9` → `Cmaj7`; `C6` → `C`; `G7b9` → `G7` |
| **advanced** | the detected label verbatim, including bass | `Cmaj9` → `Cmaj9`; `G7b9` → `G7b9` |

Rules that are easy to get wrong and are therefore asserted in tests:

- **Never change the root or the bass when reducing.** A wrong root is a different bug.
- **`sus` survives every level.** Reducing `Asus4` to `A` asserts a third that is not sounding.
- **`5` (power chord) survives every level.** There is no third to add.
- **Slash chords survive simple/medium.** They are the one thing a beginner needs most (the bass
  note they must play).
- **Default = simple**, matching `02` B-01 ("basic chords by default").

### 3.3 Spelling

Spelling is a *display* transform, not a model output: `render(chord, spelling=...)`.
Key-aware default (flats for F, Bb, Eb, Ab, Db, Gb and their relative minors), overridable. The
desktop already has `spelling`; the hosted sheet does not (`02` §2).

---

## 4. Timing, sync and latency compensation

### 4.1 What is wrong today

| Symptom | Cause (measured) |
|---|---|
| Chart looks frozen | `.chord-strip` never scrolls — no `scrollIntoView` anywhere in `frontend/src`; `style.css:1482-1488` |
| Highlight feels late | panel repaint throttled to 96 ms (`main.ts:3094`) → 10.4 Hz, plus no output-latency compensation |
| Highlight missing entirely on web | `PracticeSheet.tsx` shows a "Now" symbol but no active chip |
| Wrong chord flashes at boundaries | `chordAt()` does an exact interval test with no hysteresis and no lookahead |

### 4.2 Target behaviour

1. **Drive from `requestAnimationFrame`**, not `setInterval` + throttle. Read the audio clock once
   per frame; keep the 96 ms throttle *only* for the text readout, never for the highlight.
2. **Look up the active chord with a moving index**, not a linear scan:
   `while (i + 1 < n && chords[i+1].start <= t) i++` — O(1) amortised, and it survives long songs.
3. **Compensate output latency:**

```ts
const latencyMs = Math.min(250, Math.max(0,
  ((ctx.outputLatency ?? ctx.baseLatency ?? 0) * 1000) + (userOffsetMs ?? 0)));
const chartTime = audioTime + latencyMs / 1000;
```

`outputLatency` is absent in some Safari versions → fall back to `baseLatency`, then 0. Clamp at
250 ms so a Bluetooth device cannot push the highlight a bar ahead. Expose `userOffsetMs` in
settings later; not in this plan.

4. **Scroll, but never fight the user.** When the active bar changes, scroll the active cell to the
   horizontal centre **only if** the user has not scrolled manually in the last 3 s. On manual
   scroll, suspend auto-follow and show a "follow" affordance.
5. **Hysteresis:** switch the highlighted cell when `chartTime >= cell.start + 0.02` (20 ms), not at
   exact equality, so float jitter cannot flicker between two cells.

### 4.3 Acceptance

| Check | Target |
|---|---|
| highlight update rate | ≥ 30 Hz during playback |
| highlight error vs click track | p95 ≤ 50 ms after compensation |
| auto-scroll keeps active cell visible | active cell within the middle 60 % of the strip |
| manual scroll pause | auto-follow resumes only on explicit tap |
| web sheet | active chip + same rAF loop |

---

## 5. Evaluation harness

### 5.1 Three tiers

| Tier | Data | Runs where | Purpose |
|---|---|---|---|
| **T1 synthetic** | `bench/synth_bench.py` (6 progressions × clean/realistic) | CI, fast, no external audio | catch decoder regressions; **hard gate** |
| **T2 proxy** | `data/ui_runs/*` (4 real runs, unlabelled) | local + nightly | catch the maj7/sus4/meter failures without labels |
| **T3 labelled** | 5 hand-annotated tracks (owner task) | local only, audio not committed | the only true WCSR we will have |

### 5.2 New script: `bench/score_chords.py`

```
--audio DIR --annotations DIR --out JSON
```
- Reads `*.lab` / JAMS (`mir_eval` handles both via `mir_eval.io`).
- Runs `detect_chords` with `build_beat_grid` from the same run's diagnostics (so we score chords,
  not beats, in T3a) and with *ground-truth* beats when the annotation provides them (T3b).
- Emits: `root`, `majmin`, `sevenths`, `mirex`, plus `wrong_quality_right_root`,
  `segs_per_bar`, `share_events_under_one_beat`, `median_event_sec`, `meter_correct`.
- Deterministic; seeded; writes a JSON with a `git_sha` and `librosa.__version__`.

### 5.3 Baseline vs target (this is the contract)

| Metric | Baseline (measured) | Target | Gate type |
|---|---|---|---|
| majmin WCSR, realistic synthetic | 0.995 | **≥ 0.990** | T1 hard (no regression) |
| sevenths WCSR, realistic synthetic | 0.814 | **≥ 0.900** | T1 hard |
| root WCSR, clean synthetic | 0.997 | ≥ 0.995 | T1 hard |
| `maj7` share of events, 3 band mixes | 0.40 / 0.53 / 0.66 | **≤ 0.20 each** | T2 hard |
| `sus4` share, waltz | 0.23 | **≤ 0.08** | T2 hard |
| non-diatonic share | 0.43 – 0.56 | **≤ 0.25** | T2 hard |
| segments per bar | 0.85 – 2.64 | **0.6 – 1.2** | T2 hard |
| events shorter than one beat | 0.50 (waltz) | **≤ 0.15** | T2 hard |
| meter on 3/4 fixture | 0/1 | **1/1** | T1 hard |
| majmin WCSR, 5 labelled tracks | not measurable | **≥ 0.70** (stretch 0.80) | T3, provisional |
| highlight latency p95 | not measured (10.4 Hz repaint) | **≤ 50 ms** | manual + instrumented |
| highlight rate | 10.4 Hz | **≥ 30 Hz** | instrumented |

T3's 0.70 is provisional and calibrated against published numbers, not ours: BTC reports 71.8 %
maj-min over 471 mixed songs (`03` §3). If our 5 tracks are pop, 0.70 should be reachable; if they
are jazz, it may not be. **Re-set T3 after the first run, and record why.**

### 5.4 What must *not* regress

- 1030 existing tests, especially `tests/test_chords.py` and `tests/test_metronome.py`.
- `load_analysis` compatibility: **do not bump `SCHEMA_VERSION`**. New fields are optional with
  defaults; `_coerce_chord` (`analysis.py:211`) keeps working with old files, and old readers ignore
  new keys. Bumping to 2 would silently discard every cached analysis on every install
  (`analysis.py:608-613` rejects mismatched versions).
- Desktop onedir contents (`AGENTS.md`): no new hosted code, no `.env`.

---

## 6. Phased migration — file by file

Each phase ships independently and is revertible. Phases 1–5 add **no dependency**.

### Phase 0 — Harness first (no behaviour change)

| File | Change |
|---|---|
| `docs/chord-recognition/bench/score_chords.py` | new scorer script (§5.2) |
| `docs/chord-recognition/bench/run_baseline.sh` | one command that writes `baseline.json` |
| `tests/test_chord_bench.py` | asserts the scorer runs on a 10 s synthetic clip and writes all keys |

**Exit:** `baseline.json` reproduces `01` §5 numbers within ±0.01.

### Phase 1 — Input and front end (largest measured win per hour)

| File | Change |
|---|---|
| `ui/isolate_jobs.py:1396-1408` | new source priority (§2.1); guard `other.wav` deletion |
| `src/audio_to_tab/chords.py:266-272` | HPSS + `estimate_tuning` + bass chroma (§2.2) |
| `src/audio_to_tab/analysis.py:445-575` | pass `harmony_path` + `harmony_source_kind` through; log both |
| `tests/test_chords.py` | detuned-render tuning test; silence test |
| `tests/test_isolate_jobs.py` | two source-selection tests |

**Exit:** T2 `maj7` share drops on at least 2 of 3 band mixes; T1 unchanged (≥ 0.99 majmin).

### Phase 2 — Scorer and decoder (the accuracy phase)

| File | Change |
|---|---|
| `src/audio_to_tab/chord_symbols.py` | **new** — grammar, levels, tones (§2.6, §3) |
| `src/audio_to_tab/chords.py:29-70` | weighted templates, expanded vocabulary, priors (§2.3) |
| `src/audio_to_tab/chords.py:164-188` | z-unit penalty + metrical prior (§2.4) |
| `src/audio_to_tab/chords.py:297-313` | real `confidence`, short-run merge, `N` regions |
| `src/audio_to_tab/key.py:39-123` | use shared parser; metrical weighting |
| `tests/test_chord_symbols.py` | **new** — round-trip, levels, capo, tones |
| `tests/test_chords.py` | maj7-overtone test, flicker merge, confidence |

**Exit:** all T1/T2 hard gates in §5.3 pass. This is the phase that must not be declared done
without running the bench.

### Phase 3 — Meter and key

| File | Change |
|---|---|
| `src/audio_to_tab/metronome.py:891-941` | candidate scoring + tie-break prior + confidence (§2.5) |
| `src/audio_to_tab/metronome.py:1549-1580` | write `meter_candidates`, `meter_confidence` |
| `src/audio_to_tab/key.py` | `provisional_key()` + bass tie-break (§2.7) |
| `src/audio_to_tab/analysis.py:456-461` | two-pass key: provisional → decode → final |
| `tests/test_metronome.py` | 3/4 detected, 4/4 not regressed, weak-contrast low confidence |
| `tests/test_key.py` | relative-minor bass tie-break |
| `tests/fixtures/` | 3/4 click+bass fixture (generated, committed — it is our own audio) |

**Exit:** the reference waltz run reports 3 beats per bar; 4/4 runs unchanged.
**Note:** re-running the waltz requires re-analysis, not just reload — say so in the PR.

### Phase 4 — Chart document and UI follow

| File | Change |
|---|---|
| `src/audio_to_tab/chart.py` | **new** — `ChartDocument` builder (§2.8) |
| `src/audio_to_tab/analysis.py` | serialise `chart` alongside `chords` (additive) |
| `ui/stem_mixer_component/frontend/src/main.ts:2633,3092-3140` | rAF highlight, moving index, latency comp, level selector (§4) |
| `ui/stem_mixer_component/frontend/src/style.css:1482-1488` | scroll container + active-chip style |
| `web/src/components/PracticeSheet.tsx:107-217` | active chip, rAF, level toggle |
| `ui/.../frontend/src/analysis.ts`, `web/src/mixer/analysis.ts` | types for `simple`/`medium`/`chart` |
| `tests/test_chart.py` | **new** — bar cells, change-only symbols, section alignment |
| `ui/stem_mixer_component/frontend/` | **rebuild** via `make mix-tabs-build` / `make mixer-build` — committed build is asserted by pytest |

**Exit:** highlight ≥ 30 Hz, p95 ≤ 50 ms; auto-scroll works; web sheet highlights.
**Do not** hand-edit `frontend/build/`; the committed-build tests will fail and that is correct.

### Phase 5 — Export

| File | Change |
|---|---|
| `src/audio_to_tab/export_musicxml.py` | **new** — `ChartDocument` → MusicXML (chords as harmony elements, lyrics as verses) |
| `src/audio_to_tab/export_text.py` | **new** — ChordPro-ish plain text (`[C]lyric`) |
| `ui/isolate_jobs.py` | write `chart.musicxml` + `chart.txt` next to `analysis.json` |
| `tests/test_export_musicxml.py` | **new** — assert structure against the MusicXML schema subset (music21 is **not** a dependency; do not add one) |

**Exit:** a chart opens in MuseScore; text export is readable.

### Phase 6 — Optional neural scorer (gated, do not start without a decision)

Only if Phase 2 leaves symbol accuracy as the top complaint **and** a labelled corpus exists.

| Item | Detail |
|---|---|
| Model | BTC, 170-chord vocabulary (`03` §3) |
| Integration point | `detect_chords(model_dir=...)`, which already exists (`chords.py:243-248`) |
| Weights | ~100 MB, SHA256-pinned `urllib` download per `AGENTS.md` — **never** `huggingface_hub` |
| Licence | code MIT; **training-data provenance undocumented** → record as a legal risk, get a decision before shipping |
| Performance | budget ≤ 0.15 RTF CPU; see §7 |
| Fallback | template-v2 stays the default until BTC wins on T3 by ≥ 5 points majmin |

---

## 7. Performance budget

Measured on the reference run (125 s, `.venv311`, CPU):

| Stage | Measured now | Budget after plan | Headroom |
|---|---|---|---|
| audio load + chroma | 0.34 s | ≤ 1.2 s (HPSS + tuning + bass chroma) | 3.5× |
| `detect_chords` total | **0.37 s** (RTF 0.0029) | ≤ 1.5 s | 4× |
| key | < 0.05 s | ≤ 0.3 s | 6× |
| chart document | n/a | ≤ 0.1 s | — |
| **chord+key+chart per 5-min track** | ~0.9 s | **≤ 6 s** | 6× |
| peak extra RAM | not measurable here (`ru_maxrss` unreliable on macOS) — assert via `tracemalloc` | ≤ 300 MB | — |

Perspective: 0.37 s for 125 s of audio is **0.3 % of realtime**. Demucs separation dominates the
job by orders of magnitude. This is why a neural chord model is affordable *later* (BTC at
~0.1 RTF would be 30 s for 5 min — still small next to separation), and why "performance" must not
be used as an argument against fixing accuracy now.

Also worth noting: `detect_chords` **re-loads and re-decodes the audio** (`chords.py:258`) even
though the caller already has it. Not worth fixing in Phase 1; note it, and revisit if T3 scoring
runs get slow (batch = 5 tracks × several variants).

---

## 8. Risk register

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Priors tuned to the proxy metrics overfit the 4 local runs | High | High | T1 synthetic + T3 labelled must both improve; hold out one band mix from tuning; record which run tuned each constant |
| R2 | `maj7` suppression goes too far and real maj7 chords become triads | Medium | Medium | explicit test with a real maj7 voicing (0,4,7,11 with weak 9th) must stay `maj7` |
| R3 | Meter fix regresses 4/4 pop | Medium | High | 4/4 fixtures + tie-break prior; gate in T1 |
| R4 | Stem sums clip or phase-cancel | Medium | Medium | peak-normalise the sum; measure chroma energy vs mix; fall back to `no_vocals` if the sum is > 2× louder |
| R5 | `other.wav` deletion guard breaks existing runs | Low | High | keep the old path behind a flag for one release; diagnostics record which path ran |
| R6 | Schema change breaks cached analyses / old desktop builds | Medium | High | additive fields only, no version bump (§5.4); old reader ignores unknown keys |
| R7 | Committed frontend build drifts from source | High if forgotten | High (red tests, broken release) | rebuild in Phase 4; pytest already asserts completeness; `desktop-release.yml` fails on missing mixer build |
| R8 | Licence contamination (ChoCo NC, madmom DBN, Essentia AGPL) | Medium | High (legal) | allowlist in `03` §7; no NC dataset in fixtures; no madmom/Essentia import, not even behind a flag |
| R9 | BTC weight provenance | Medium | High (legal) | Phase 6 gated on an explicit decision; document training corpus (Isophonics/Robbie Williams/Billboard) |
| R10 | Auto-scroll fights the user | High | Low | 3 s manual-scroll pause + follow affordance (§4.2) |
| R11 | Latency compensation over-corrects on Bluetooth | Medium | Medium | clamp 250 ms; measure against a click track |
| R12 | T3 corpus never materialises | High | Medium | T1/T2 still gate every phase; T3 is a parallel owner task, not a blocker |
| R13 | Hosted sheet drifts from desktop again | Medium | Medium | shared `level_symbol` semantics documented in one table (`03` §3.2); web has no analysis worker, so it consumes the same JSON |

---

## 9. Prioritised quick wins

Ordered by (measured impact ÷ effort). Items 1–5 are all shippable before any neural model.

| # | Win | File | Effort | Expected effect |
|---|---|---|---|---|
| **1** | **Fix harmony source selection** — stop analysing `source.mp3` when stems exist | `ui/isolate_jobs.py:1396-1408` | ~30 min | removes drums+vocals from chroma; the single cheapest accuracy gain; confirmed regression from the reference run |
| **2** | **Quality priors + z-normalised scores** — `maj7` 0.55σ, `sus4`/`sus2` 0.50σ | `chords.py:53,294` | ~2 h | attacks the 40–66 % `maj7` and 23–34 % `sus4` directly |
| **3** | **Stronger decoder** — 0.8σ switch penalty + merge runs < 0.5 beat | `chords.py:52,146-161` | ~3 h | 2.64 → ~1 seg/bar; kills the <1-beat flicker (50 % of events) |
| **4** | **Meter: score candidates instead of defaulting to 4** | `metronome.py:935-941` | ~4 h | fixes every bar line, downbeat, count-in and section boundary on 3/4 songs |
| **5** | **Chart follow** — rAF + moving index + scroll + web active chip | `main.ts:3094`, `style.css:1482`, `PracticeSheet.tsx` | ~1 day | the *visible* symptom ("switches too slowly") that no model change fixes |

Cheap follow-ons once 1–5 land: tuning estimation (§2.2), real `confidence` so the "Draft" banner
stops lying (§2.4), chord-tone display (`chord_tones`, §2.6), MusicXML export (§Phase 5).

**What not to do first:** do not start with a neural model, a new dataset, a DB, or a hosted
analysis worker. The measured evidence says the decoder works and the inputs/priors/meter do not.

---

## 10. Open decisions for the owner

1. **T3 corpus:** approve 5 hand-annotated tracks (audio stays out of git) — otherwise real WCSR
   stays unmeasurable and only proxies gate the work.
2. **Phase 6:** decide whether a model trained on copyrighted audio is acceptable to ship; if not,
   stop at template-v2 and say so.
3. **Desktop vs hosted:** the hosted stack has no analysis worker. Confirm this plan targets desktop
   only, and that the hosted sheet consumes uploaded `analysis.json`.
4. **Default display level:** simple-by-default matches Moises and beginners; confirm it is the
   product's choice rather than advanced.
