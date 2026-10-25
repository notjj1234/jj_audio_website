# 01 — Current system audit (chord / key / beat / chart)

**Status:** measured audit. Every claim below is tied to a `file:line` citation or to a
reproduction I ran. Anything I could not verify is marked **[UNVERIFIED]**.
**Date:** 2026-10-25
**Scope:** desktop Streamlit practice player (the only surface with chords today). The hosted
SPA has the same chord helpers but no analysis worker (`backend/` has no `analysis` or `chord`
reference — verified by grep).

---

## 1. What the product actually runs today

### 1.1 Pipeline map

```
upload / YouTube ─► Demucs-family separation (htdemucs_6s by default)
                         │  drums, bass, other, vocals, guitar, piano
                         │  (fold_other_into_guitar may DELETE other.wav)
                         ├─► metronome stage ──► metronome.wav + metronome_diagnostics.json
                         │      (beat_track + tempo curve + meter + downbeat)
                         └─► analysis stage (ui/isolate_jobs.py:_run_analysis_stage)
                                │
                                ├─ build_beat_grid(diagnostics)         → beats, downbeats, bpm
                                ├─ detect_chords(harmony_path, beats)   → ChordEvent[]
                                ├─ estimate_key(chords, chroma)         → "Dm" + confidence
                                ├─ detect_sections(audio)               → Section[]
                                └─ transcribe_lyrics(vocals)             → LyricLine[]
                                        │
                                        ▼
                                  analysis.json (schema_version 1)
                                        │
                                        ▼
                       Streamlit iframe mixer (ui/stem_mixer_component/frontend)
                       + hosted React PracticeSheet (web/src/components/PracticeSheet.tsx)
```

Stage order is deliberate and documented in `src/audio_to_tab/analysis.py:456-461`:
beats → chords → key → sections → lyrics. Key is derived **from the chord track**, not from audio
first (`src/audio_to_tab/key.py:198-202`).

### 1.2 Stage parameters, as implemented

| Stage | File | What it does | Parameters that matter |
|---|---|---|---|
| Harmony source selection | `ui/isolate_jobs.py:1396-1408` | `no_vocals` else `other` else **the original mix** | 6-stem Demucs produces neither `no_vocals` nor (after fold) `other` |
| Beat grid | `src/audio_to_tab/analysis.py:381-433` | Reuses `metronome_diagnostics.json`; only falls back to a tempo estimate | `click_times_1x` becomes the chord window boundaries |
| Beat tracking | `src/audio_to_tab/metronome.py:1334-1530` | `librosa.beat.beat_track` twice (global + tempo-curve), intro gate, gap fill, downbeat alignment | hop 512, `onset_strength(aggregate=np.median)`, tempo clamp 60–180 BPM |
| Meter | `src/audio_to_tab/metronome.py:891-941` | Chooses 3 or 4 from accent RMS contrast; **returns 4 when unsure** | `_METER_MIN_CONTRAST = 1.15`, `_METER_WIN_MARGIN = 1.05` |
| Chroma | `src/audio_to_tab/chords.py:267` | `librosa.feature.chroma_cqt(y, sr=22050, hop_length=512)` | 12 bins, `bins_per_octave=36`, **`tuning=None` → no tuning correction** |
| Aggregation | `src/audio_to_tab/chords.py:278-285` | Mean chroma **per beat window**, L2-normalised | window = one beat (0.4–0.7 s typical) |
| Acoustic model | `src/audio_to_tab/chords.py:56-70` | 96 binary templates: 12 roots × {maj, min, 7, maj7, m7, sus4, dim, aug}, L2-normalised | unweighted 1.0 per chord tone; cosine similarity |
| Prior | `src/audio_to_tab/chords.py:53,70` | −0.03 for any name ending in `7`; **no penalty for sus4 / dim / aug; no key prior** | 0.03 is ~1/30 of the cosine range |
| Decoder | `src/audio_to_tab/chords.py:164-188` | Viterbi, uniform switch penalty | `_CHANGE_PENALTY = 0.06` **per beat** |
| Post-process | `src/audio_to_tab/chords.py:146-161,302-303` | Snap boundaries to nearest beat (±0.12 s), merge identical neighbours, drop <0.10 s | no minimum chord length, no metrical prior |
| Key | `src/audio_to_tab/key.py:65-123` | Scores every tonic×mode against a diatonic-degree table, duration-weighted | chord histogram wins; raw chroma only if no chords |
| Chart UI (desktop) | `ui/stem_mixer_component/frontend/src/main.ts:3092-3140` | "Now" symbol + chip highlight at ≤10.4 Hz | `96 ms` throttle, `chordAt()` exact interval test, **no auto-scroll** |
| Chart UI (web) | `web/src/components/PracticeSheet.tsx:136-217` | "Now" symbol only | **no active-chip highlight at all**, no spelling toggle, capo only |

### 1.3 The data contract

`AnalysisResult` (`src/audio_to_tab/analysis.py:86-104`) stores `chords` as
`{start, end, symbol, confidence}` with `confidence` **hard-coded 0.0** by the draft detector
(`src/audio_to_tab/chords.py:309`). The UI treats "all zero" as a draft and renders the
"Draft chords — a starting point; verify by ear" note
(`ui/stem_mixer_component/frontend/src/main.ts:2828-2831`).

Vocabulary parse/print support already exists for slash chords
(`src/audio_to_tab/chords.py:110-133`) but **no template can ever emit one**, so inversions are
unrepresentable in the output.

---

## 2. Hypotheses from the brief — confirmed / rejected

| # | Hypothesis | Verdict | Evidence |
|---|---|---|---|
| H1 | Raw frame-level chroma, no beat-synchronous aggregation | **REJECTED** | `chords.py:278-285` averages chroma per beat window |
| H2 | No temporal smoothing / smoothing far too heavy | **PARTLY CONFIRMED — it is too WEAK, not too heavy** | Viterbi exists (`chords.py:164`), but penalty 0.06 per beat against cosine scores often spanning 0.0–0.25. Measured 2.64 segments/bar on a jazz waltz; 50 % of events shorter than one beat |
| H3 | Hop/window too large | **REJECTED (mostly)** | hop 512 @ 22.05 kHz = 23 ms; the *window* is one beat (0.43–0.72 s), which is intended |
| H4 | No tuning/reference-pitch estimation | **CONFIRMED** | `chroma_cqt(..., tuning=None)` (`chords.py:267`). librosa only applies tuning if you pass it — verified in `librosa/feature/spectral.py::chroma_cqt`, which forwards `tuning` straight into `cqt()` |
| H5 | No harmonic/percussive separation | **CONFIRMED** | no `effects.hpss` / `harmonic` call anywhere in `chords.py` |
| H6 | Stems exist but the chord stage doesn't use them | **CONFIRMED (for the default 6-stem model)** | `ui/isolate_jobs.py:1401` looks only for `no_vocals`/`other`; `htdemucs_6s` yields `drums,bass,other,vocals,guitar,piano` and `fold_other_into_guitar` can delete `other`. Real run `46b84e7b…` has `analysis_diagnostics.json → "harmony_path": ".../source.mp3"` |
| H7 | Vocabulary too small or too large | **CONFIRMED — too large *and* wrongly weighted** | 96 states for a pop product; sus4/dim/aug get zero prior; maj7 template wins on real timbres (see §3.3) |
| H8 | No key-aware prior | **CONFIRMED** | `chords.py:294` subtracts only `_EXTENSION_PRIOR`; no key, no scale, no diatonic bonus |
| H9 | Chart UI delayed relative to audio | **PARTLY CONFIRMED** | Audio clock is correct (`main.ts:343-360`); but the sheet repaints at ≤10.4 Hz (`main.ts:3094`) and the `.chord-strip` never scrolls (`style.css:1482-1488`, no `scrollIntoView` anywhere) |

Two further defects found that were not on the list:

- **H10 — meter defaults to 4/4.** `detect_beats_per_measure` returns 4 whenever the accent
  contrast is weak (`metronome.py:935-941`). The reference run is a jazz **waltz**; the analysis
  says `beats_per_measure: 4`. Every downbeat and therefore every bar line is wrong.
- **H11 — the "now" chord can disagree with the beat grid.** Chord windows come from
  `click_times_1x`, which is a *hybrid* grid: detected beats in the body plus **extrapolated**
  beats in lead-in/tail/holes (`metronome.py:616-750`). Those extrapolated beats are not
  onsets, so windows near intros can straddle a real chord change.

---

## 3. Reproduction results

All scripts are in `docs/chord-recognition/bench/` and are reproducible with
`.venv311/bin/python`. Nothing writes into the product tree.

### 3.1 Synthetic, known ground truth (6 progressions × 8 bars, 100 BPM, 4/4)

`bench/synth_bench.py` renders pad + bass + melody + drums, then optionally a "realistic" mix
(instruments +30 cents sharp, louder backbeat, vibrato lead, saturation, short reverb). It scores
with `mir_eval.chord.evaluate` (duration-weighted WCSR).

| Variant | root | majmin | sevenths | mirex |
|---|---|---|---|---|
| Current detector, ground-truth beats | **0.997** | **0.997** | 0.907 | 0.997 |
| Current detector, estimated beats | 0.992 | 0.991 | 0.902 | 0.991 |
| Realistic-only subset, current | 0.995 | 0.995 | 0.814 | 0.995 |

**This is the single most important result in the audit.** On clean, separable harmony the current
template+Viterbi decoder is essentially perfect, *including* a 30-cent detune and a saturated,
reverbed mix. The algorithm is not the bottleneck; the **representation of real music** is.

Caveat: synthetic tracks have one chord per bar, root-position voicings, no inversions, no
borrowed chords and no dense jazz harmony. They prove the decoder is sound, not that it is good
enough.

### 3.2 Real tracks (no ground truth → proxy metrics)

`bench/real_track_diag.py` and an equivalent run over three more runs. Proxies:
**diatonic** = duration-weighted share of chord events whose root+quality fit the estimated key;
**segs/bar** = over-segmentation; **vocab** = quality histogram.

| Run | Input | segs | segs/bar | diatonic | dominant qualities |
|---|---|---|---|---|---|
| `46b84e7b` Waltz for Debby (fingerstyle, 125 s, Dm, 105 BPM) | full mix (what shipped) | 145 | **2.64** | **0.57** | sus4 34, m7 29, maj7 26, 7 20 |
| same | guitar stem | 147 | 2.68 | 0.57 | sus4 33, m7 28, maj7 27 |
| same | piano stem | 100 | 1.82 | 0.82 | m7 29, 7 26, maj7 24 |
| same | bass stem | 68 | 1.24 | 0.82 | maj7 45, m7 15 |
| `50f1b1f5` metal, 253 s, ~Cm, 108 BPM | full mix | 97 | 0.85 | 0.83 | **maj7 51**, m7 24 |
| `9a18a73f` 289 s, ~Gm, 118 BPM | full mix | 146 | 1.03 | 0.44 | **maj7 59**, sus4 25 |
| `ad6e7c9f` 290 s, ~Am, 123 BPM | full mix | 185 | 1.24 | 0.58 | **maj7 123**, sus4 38 |

Reference run details: 100 % timeline coverage, no gaps, median event 0.60 s, **72/145 events
shorter than one beat**, 219 beats / 55 downbeats over 124.9 s.

**Reading of the table**

1. **`maj7` is the default wrong answer.** 53 %, 40 %, 66 % of all events on three band mixes.
   Cause: a major triad's overtones put energy on the major 7th (the 3rd harmonic of the major
   third), and the maj7 template is *rewarded* for matching it while paying only a 0.03 penalty.
2. **`sus4` is the second escape hatch** (23 % on the waltz). Template (0,5,7) overlaps both major
   and minor triads plus the perfect-fifth harmonic, and carries **no** prior penalty.
3. **~43–56 % of chord labels are outside the detected key.** A pop/jazz chart typically has
   10–20 % borrowed chords; ≥40 % means the labelling, not the song, is chromatic.
4. **Over-segmentation is real but inconsistent** (0.85–2.64 segs/bar). It is not the user's
   "too slow" symptom; see §4.
5. **Stem choice is not a universal win.** On the solo-guitar waltz, guitar ≈ mix (the guitar *is*
   the mix) and `guitar+piano+bass` did not improve. On band mixes, the harmonic sum changed the
   label distribution but did not fix the maj7 bias. So stems alone are necessary, not sufficient.

### 3.3 Beat-grid sensitivity (reference run)

Shifting the whole grid by ±¼ and ±½ beat changed the diatonic share by ≤0.02
(`bench/real_track_diag.json`). **Chord *labels* are robust to grid phase; chord *boundaries* are
not.** That is why "changes don't align with beats and bars" is a grid/meter problem, not a
detector problem.

---

## 4. Root causes, ranked by expected impact

| Rank | Cause | Evidence | Why it produces the symptom |
|---|---|---|---|
| **1** | **Template scoring is acoustically naive for real timbres** — binary templates, cosine similarity, overtones counted as chord tones, no key/vocabulary prior | 40–66 % `maj7`; 43–56 % non-diatonic; synthetic 0.99 | Wrong *symbol*, even when the *root* is right. This is the "9 in 10 chords are wrong" report |
| **2** | **Harmony input is the full mix on the default model** | `isolate_jobs.py:1401`; `analysis_diagnostics.harmony_path = source.mp3`; run has no `other.wav` | Drums + vocals + bass compete with the harmony; chroma is noisier, thirds get masked → sus4/maj7 drift |
| **3** | **Meter is assumed 4/4 when ambiguous, and the grid is used as the chord clock** | `metronome.py:935-941`; waltz stored as `beats_per_measure: 4`; 55 downbeats over a 3/4 tune | Every bar line, downbeat accent, count-in and "bar" grouping is wrong → "doesn't line up with bars" |
| **4** | **Temporal model too weak for the vocabulary size** | 0.06/beat; 72/145 events < 1 beat; 2.64 segs/bar | Flicker and spurious passing chords; a chart that is hard to read |
| **5** | **Chart surface does not follow playback** | `main.ts:3094` 96 ms throttle; no scroll in `.chord-strip`; web sheet has no active chip | The **visible** chart stays on the first bars while the song advances → "switches too slowly / lags" |
| 6 | No tuning estimation | `chords.py:267` | Minor on its own (30-cent detune still scored 0.99) but adds error on badly tuned recordings |

### Why "too slow" and "over-segmented" can both be true

Measured event rate is *fast* (2.6 chords/bar on the waltz) while the user reports *slow*. The two
are compatible: the chord **strip** is a non-scrolling horizontal list, so what the user sees is
frozen near the start of the song even though the labels underneath are changing. The "now" line
does update, at 10 Hz. Both need fixing, but they are different defects — one is model output, one
is UI follow.

---

## 5. Baseline numbers to beat (Phase 4 targets are set against these)

| Metric | Baseline (measured) | How measured |
|---|---|---|
| root WCSR, clean synthetic | 0.997 | `synth_bench.py` |
| majmin WCSR, clean synthetic | 0.997 | `synth_bench.py` |
| majmin WCSR, realistic synthetic | 0.995 | `synth_bench.py` |
| root WCSR, **real music** | **not measurable — no ground truth in repo** | blocker, see §6 |
| non-diatonic event share, real music | 0.43 – 0.56 | `real_track_diag.py` |
| segments per bar, real music | 0.85 – 2.64 | `real_track_diag.py` |
| `maj7` share of events, band mixes | 0.40 – 0.66 | same |
| events shorter than one beat | 0.50 (waltz) | `analysis.json` |
| meter correctness | 0/1 on the only 3/4 track | `analysis.json` vs known waltz |
| UI repaint rate | ≤10.4 Hz (96 ms) | `main.ts:3094` |
| chart auto-scroll | **none** | no `scrollIntoView` in `frontend/src` |
| beat-grid label sensitivity | Δdiatonic ≤0.02 for ±½ beat | `real_track_diag.py` |

---

## 6. Blockers / what is missing

1. **No labelled chord corpus in the repo.** `eval/fixtures` are MIDI→WAV synthetic; there is no
   audio + chord-annotation pair. `docs/plans/moises-parity/08-EVIDENCE-LOG.md:361` already lists
   "labelled chord accuracy corpus" as an open gap. Until one exists, real-music accuracy can only
   be reported as proxies. **Needed from the owner:** permission to add a small evaluation corpus
   (e.g. 10–20 Isophonics tracks with local audio, or 5 hand-annotated songs).
2. **Runs in `data/ui_runs` are the only real audio available.** Three of them are useful as
   regression fixtures, but they are unlabelled and one is a solo fingerstyle arrangement, which is
   not representative of band mixes.
3. The hosted API does not run analysis at all (grep of `backend/` for `chord`/`analysis` returns
   nothing), so this audit covers desktop only.

---

## 7. Files read for this audit

```
src/audio_to_tab/analysis.py        src/audio_to_tab/chords.py
src/audio_to_tab/key.py             src/audio_to_tab/metronome.py
src/audio_to_tab/tempo.py           src/audio_to_tab/sections.py
src/audio_to_tab/rhythm.py          ui/isolate_jobs.py (analysis + metronome stages)
ui/stem_mixer_component/frontend/src/main.ts (practice panel, transport clock)
ui/stem_mixer_component/frontend/src/analysis.ts
ui/stem_mixer_component/frontend/src/style.css (.chord-strip)
web/src/components/PracticeSheet.tsx
web/src/mixer/analysis.ts
tests/test_chords.py
data/ui_runs/46b84e7b-…/{analysis.json, analysis_diagnostics.json, metronome_diagnostics.json, meta.json}
docs/plans/moises-parity/{08-EVIDENCE-LOG.md,10-MOISES-UI-CRAFT.md,_work/moises-public.md}
```
