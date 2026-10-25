# 00 — Summary

**Question asked:** users report the chord chart is wrong, switches too slowly, and does not line
up with bars. Moises appears better. Why, and what would it take to fix?

**Answer in one line:** the chord *decoder* is not broken; the *inputs, priors and metrical frame*
are, and the chart UI never scrolls — so the visible symptom is partly not a model problem at all.

---

## What was measured (not estimated)

| Finding | Number | Source |
|---|---|---|
| Decoder accuracy on clean synthetic harmony | majmin WCSR **0.997** | `bench/synth_bench.py` |
| Same, detuned + saturated + reverbed | **0.995** | same |
| Real band mixes labelled `maj7` | **40 / 53 / 66 %** of events | `bench/real_track_diag.py` |
| Chord labels outside the detected key | **43–56 %** | same |
| Segments per bar (over-segmentation) | **0.85 – 2.64** | same |
| Events shorter than one beat (waltz) | **50 %** | `analysis.json` |
| Meter on the only 3/4 track | **wrong — stored as 4/4** | `metronome.py:935-941` |
| Chord stage cost | **0.37 s per 125 s audio** | measured this session |

The synthetic result is the pivot: an algorithm scoring 0.997 on clean harmony is not the reason
charts are wrong. The failure appears only on real timbres and real meters.

## Three root causes, ranked

1. **Acoustic scoring is naive for real timbres.** 96 binary templates, unweighted tones, cosine
   similarity, and a prior of `0.03` that is meaningless because scores are never normalised. A
   major triad's 3rd harmonic lands on the major 7th, so `maj7` wins — which is exactly the 40–66 %
   measured. `sus4` is the second escape hatch (23–34 %) because it too is unpenalised.
   — `src/audio_to_tab/chords.py:29-70,294`
2. **The chord stage analyses the full mix, not the harmony stems.** `htdemucs_6s` produces no
   `no_vocals`, `fold_other_into_guitar` can delete `other.wav`, so `isolate_jobs.py:1396-1408`
   falls through to `source.mp3` — confirmed in the reference run's `analysis_diagnostics.json`.
3. **The metrical frame defaults to 4/4 and the chart never scrolls.** The waltz is barred as 4/4
   (`metronome.py:935-941`), so every downbeat, bar line, count-in and section boundary is wrong;
   and `.chord-strip` has no `scrollIntoView` (`style.css:1482-1488`), so the *visible* chart freezes
   near the start while the labels underneath do change. "Too slow" and "too many chords" are both
   true because they are different defects.

## What Moises actually does (verified, public sources)

Three display levels (easy/medium/advanced) over **one** chord timeline; the public API returns a
`chordMap` whose annotations carry **multiple chord classes at once** (Complex Jazz / Simple Jazz /
Complex Pop / Simple Pop) plus bass — so the levels are renderings, not three detections. Charts
export as web link, iReal Pro or MusicXML, lyrics-aligned, with key/tempo/time signature in the
header, and are editable per chord. No accuracy number is published anywhere; every claim is
marketing. `02` records 27 behaviours and 13 unknowns, with the exact URL for each.

## The plan

Five phases, no new dependencies, each independently shippable:

0. harness (baseline reproducible)
1. harmony source + tuning + HPSS **(biggest win per hour)**
2. weighted templates, z-normalised scores, real priors, stronger decoder, 3 display levels
3. meter and key (two-pass, bass tie-break)
4. chart document + rAF follow + scroll + web highlighting
5. MusicXML / text export
6. *optional, gated:* BTC scorer — MIT code, but training-data provenance undocumented

**Targets:** `maj7` ≤ 20 % (from 40–66), non-diatonic ≤ 25 % (from 43–56), 0.6–1.2 segs/bar (from
0.85–2.64), meter 1/1 on 3/4, synthetic majmin ≥ 0.99 (no regression). Real WCSR stays **unmeasurable**
until 5 tracks are hand-annotated — that is the one thing the owner must approve.

**Cost:** the chord stage is 0.3 % of realtime today. Performance is not an argument for delay.

---

Read in order: `01` audit → `02` competitor → `03` state of the art → `04` plan.
Bench scripts are reproducible: `bench/synth_bench.py`, `bench/real_track_diag.py`.
