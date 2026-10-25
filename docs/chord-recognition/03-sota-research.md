# 03 — State of the art: chord, key, beat, and what is legally usable

**Status:** literature + repository survey, 2026-10-25. Numbers in §3 are **author-reported and
not re-run here**; each row says which dataset it came from. Licence verdicts in §7 were checked
against the repository/PyPI/Zenodo metadata, not against marketing copy.
**Companion:** `01-current-system-audit.md` (our measured baseline) and
`02-moises-behaviour-spec.md` (what the competitor exposes).

---

## 1. "Chord recognition" is five separable problems

Most of the disappointment in chord features comes from treating this as one model. It is five
stages, each with its own state of the art and its own failure signature:

| # | Stage | State of the art | Our current stage | Our measured failure |
|---|---|---|---|---|
| 1 | Front end (what the model sees) | CQT or log-mel, tuned, harmonic/percussive-separated, sometimes bass-separated | `chroma_cqt(tuning=None)` on the full mix | max: 30-cent detune survived, so front end is *adequate*, not the main bug |
| 2 | Acoustic scoring (frame → chord) | learned (CNN/CRNN/transformer) | 96 binary templates, cosine | **`maj7` 40–66 %, `sus4` 23 %** |
| 3 | Temporal decoding (frames → segments) | learned end-to-end, or CRF/HMM/Viterbi with tuned priors | Viterbi, penalty 0.06/beat | 2.64 segs/bar; 50 % of events < 1 beat |
| 4 | Metrical frame (beats, downbeats, meter) | Beat This! (2024) | librosa + accent heuristic, defaults to 4 | waltz stored as **4/4** |
| 5 | Rendering (symbol, level, spelling, chart) | doc model + poly-label classes (Moises) | flat symbol, one vocabulary | no easy/medium/advanced, no export |

Our synthetic result (`01` §3.1: majmin WCSR 0.997) says stages 2–3 are *implemented correctly*.
The real-music proxies say stage 2's **acoustic model** is wrong for real timbres and stage 4 is
wrong for non-4/4. That ordering is what makes the plan cheap: the expensive-looking stage
(decoding) is already fine.

---

## 2. Metrics, and why WCSR alone will lie to us

`mir_eval.chord.evaluate` (MIT, 0.8.2 installed) reports duration-weighted recall over several
alphabets: `root`, `majmin`, `sevenths`, `mirex`, plus per-quality breakdowns.

**WCSR is a duration ratio, so it rewards exactly the mistakes our users complain about:**

| Error | WCSR cost | User cost |
|---|---|---|
| `C` detected as `Cmaj7` for the whole bar | **zero** on `root`, full bar lost on `majmin`/`mirex` | "that chord is wrong" |
| chord flickers `C → Csus4 → C` inside one bar | ~zero (durations cancel) | "chart jumps around / unreadable" |
| correct chords, boundaries 300 ms late | near zero | "doesn't line up with the beat" |
| 3/4 song barred as 4/4 | **invisible** — WCSR has no bar concept | "bars are wrong" |

So the harness must report, alongside WCSR: **wrong-quality-right-root rate**, **segments per
bar**, **share of events shorter than one beat**, **median segment duration**, **beat-boundary
error (ms)**, and **meter correctness**. Our bench already computes most of these
(`bench/real_track_diag.py`); the plan (`04`) promotes them to first-class gates.

---

## 3. Methods, and the numbers their authors report

| Year | Method | Representation / decoder | Reported result | Dataset | Note |
|---|---|---|---|---|---|
| 2010– | NNLS-Chroma + Chordino | hand templates + HMM | — | — | GPL; still the reference "classical" baseline |
| 2016–19 | CNN, CNN+CRF, CRNN | CQT frames, CRF/HMM head | CNN+CRF best on most metrics in the BTC comparison | 471 songs | the pre-transformer ceiling |
| **2019** | **BTC** (Park et al., ISMIR) | CQT → bi-directional transformer, **single training phase, no HMM/CRF** | **root 83.8 %, maj-min 71.8 %, MIREX 65.5 %**, sevenths 80.8 %, tetrads 75.9 % (5-fold CV) | 221 Isophonics + 65 Robbie Williams + 185 Billboard-derived = 471 songs | MIT code; 170-chord large vocabulary mode |
| 2019 | BTC+CRF | same + CRF | 83.9 / 83.1 / 83.5 / 80.7 / 75.7 / 70.7 / 64.8 | same | CRF adds ~nothing; the transformer already segments |
| 2023–24 | Beat/downbeat: **Beat This!** | mel spectrogram → conv+transformer, **no DBN** | SOTA beat/downbeat F1 "despite using no DBN"; GTZAN downbeat F1 ≈ 87.8 (Table 2) | 16 datasets incl. GTZAN test | MIT code **and** MIT weights; `pip install beat-this` |
| 2026 | Pseudo-label + distillation (DAFx26) | BTC teacher → BTC / 2E1D students on 1 000 h unlabeled audio | student "surpasses the teacher across all metrics", large gains on rare qualities | — | shows BTC is now a *teacher*, not the frontier |
| 2026 | Event-based sequence modelling with oversegmentation minimisation | event decoder + SPLIT | beats BTC on WCSR **and** segmentation quality | — | directly targets our #1 visible symptom |

Two cautions before anyone quotes this table:

1. **Cross-paper numbers are not comparable.** Different train/test splits, different label
   alphabets (25 vs 170 chords), different handling of "no chord". BTC's 71.8 % maj-min and a
   2026 paper's "85 %" can both be true and mean different things. Compare *our* pipeline against
   *our* harness, on one fixed split, always.
2. **The frontier moved past BTC in 2026**, but the frontier is also less packaged. BTC is the last
   model with a small, well-understood, MIT-licensed reference implementation and a citable
   baseline. That is why it is the candidate, not because it is the best.

What actually changed between 2019 and 2026 is not the architecture family; it is (a) better
front ends and augmentation, (b) pseudo-labelling to escape annotation scarcity, and (c) **explicit
segmentation objectives**. Our problem is (c) plus priors, which is why the plan fixes those first.

---

## 4. Which SOTA component attacks which of our root causes

| Our root cause (`01` §4) | SOTA component that fixes it | Fix without a neural model? |
|---|---|---|
| 1. Template acoustics (maj7/sus4 bias) | learned acoustic model (BTC et al.) | **partly** — overtone-aware template weights, key prior, quality prior |
| 2. Harmony input = full mix | source separation (we already run Demucs) | **yes** — wiring bug, not a model gap |
| 3. Meter defaults to 4 | Beat This! downbeats; or multi-hypothesis meter scoring | **yes** — score 2/3/4/6 candidates against accent evidence |
| 4. Weak temporal model | event-based decoders; CRF; tuned Viterbi | **yes** — penalty + minimum duration + metrical prior |
| 5. Chart doesn't follow | — (product engineering) | **yes** |

Only root cause 1 needs a learned model to be *fully* solved. Everything else is engineering we
already have the pieces for. That is the single most important conclusion of this survey.

---

## 5. Beat / downbeat / meter

- **Beat This!** (Foscarin, Schlüter, Widmer; ISMIR 2024, arXiv 2407.21658) is the current
  practical choice: beats **and downbeats**, no DBN, trained across 16 datasets including time
  signature changes — which is precisely our waltz failure. Code MIT (`CPJKU/beat_this`, 444
  stars), weights MIT, `beat-this` on PyPI (1.1.0).
- **madmom is not usable commercially.** Repo licence reports `NOASSERTION`, and its DBN is
  patented and licensed for non-commercial use only (third-party packaging notes this explicitly).
  Anything that imports madmom's DBN inherits that constraint. Avoid, including as a "just for
  evaluation" dependency in shipped code.
- **Third-party speed datapoint:** a Rust port reports the reference Python model at ~5.1 s for a
  4:32 track on CPU (≈53× realtime). **[UNVERIFIED on our hardware]** but the order of magnitude
  says a beat model is affordable next to Demucs.
- If we do *not* adopt Beat This!, the minimum viable fix is multi-hypothesis meter scoring: for
  each candidate meter *m* ∈ {2,3,4,6}, fold the beat-accent series at period *m* and pick the
  period with the highest normalised contrast, **with a prior toward 4 only as a tie-break**, never
  as the default. `metronome.py:935-941` currently does the opposite.

---

## 6. Key detection

Key is a 24-way problem (12 tonics × major/minor) and is *easier* than chords; the literature
converged decades ago on pitch-class-distribution correlation:

- **Krumhansl–Schmuckler** profiles correlated against a duration-weighted chroma vector is still
  the standard non-neural method, and is what `music21` (BSD-3) implements.
- **Essentia**'s KeyExtractor is AGPL-3.0 → unusable in a hosted product without releasing source.
- **madmom** key detector → same non-commercial DBN caveat.
- **Best fit for us:** keep the chord-histogram estimator we already have (`key.py:65-123`), but
  (a) weight by *duration and metrical position*, (b) use the detected **bass** root to break
  relative major/minor ties (the relative minor's tonic is the vi; the bass tells you which is
  home), and (c) correlate against Krumhansl profiles as a second opinion, reporting confidence as
  the margin between the top two keys rather than an absolute score.

Key accuracy is not separately measurable in our repo today (no key ground truth), but it is
*derived* from chords, so improving chords improves key for free. Do not build a key model first.

---

## 7. Datasets and licences — read this before adding fixtures

| Dataset | Content | Licence | Audio included? | Usable for us? |
|---|---|---|---|---|
| **Isophonics** (Beatles 171, Queen 20, Carole King 12, Zweieck 18) | chord + key + beat annotations | research use | **no** (copyright) | **evaluation only, never vendored** |
| **McGill Billboard** | 890 songs, expert chord annotations | annotations CC-ish, audio licensed | no | evaluation only |
| **CoCoPops** (Billboard + RS200 subset) | harmonic + melodic transcriptions, humdrum/CSV | **CC-BY-4.0** | no | best *annotation* licence; still needs our own audio |
| **ChoCo** | 20 000+ timed chord annotations, 18 sources, unified Harte syntax | **CC BY-NC-SA 4.0** | mostly no | **NC — do not use in a commercial eval fixture**; useful for research comparison only |
| Robbie Williams (used by BTC) | 65 songs | research | no | evaluation only |
| RWC | 100 pop songs, studio audio | paid licence | yes | only if purchased |

**Consequence for the plan:** we cannot commit a labelled corpus to this repo. The realistic
options, in order of legal cleanliness:

1. **Hand-annotate 5 songs we already host** (or 5 royalty-free tracks) → commit only our own
   annotations + a checksum manifest, not the audio. Fully clean, small, reproducible by the owner.
2. Use Isophonics/CoCoPops annotations **locally** for a one-off calibration run, report the
   numbers in a doc, and never commit audio or annotations. Clean enough for R&D, not for CI.
3. Buy RWC. Expensive, probably not worth it at this stage.

Option 1 is what `04` specifies. **Do not let a benchmark block the product fixes** — the proxy
metrics in `01` §3.2 are already enough to prove the maj7/sus4/meter problems and to prove they
went away.

---

## 8. Candidate architectures for this codebase

| Option | What it is | Expected gain | Effort | New deps / weights | Licence risk | Verdict |
|---|---|---|---|---|---|---|
| **A. Template-v2** | keep `chords.py`; fix priors, vocabulary, HPSS, tuning, bass, decoder, meter | kills maj7/sus4 bias, halves over-segmentation, fixes 3/4 | **1–2 days** | none | none | **do first** |
| **B. BTC** | replace scoring+decoding with 170-chord transformer | largest symbol accuracy gain, especially jazz vocabulary | 3–5 days + packaging | torch (already), ~100 MB weights, new weight-fetch path | **code MIT; training-data provenance unclear** — flag, don't hide | second, behind a flag |
| **C. 2E1D / ChordMini** | 2026 compact dual-encoder | comparable to BTC, newer | 3–5 days | same as B | MIT code, 25 stars → **young, unproven** | watchlist |
| **D. Beat This!** | replace beat/downbeat tracking | fixes meter + downbeats properly | 2–3 days | `beat-this` + weights | MIT code + MIT weights → **cleanest ML dependency available** | do if A's meter fix is insufficient |

The pragmatic sequence is **A → measure → D if meter still fails → B only if symbol accuracy is
still the top complaint after A**. Option A costs no new dependency and no new licence surface,
which matters because this repo has an explicit rule about SHA256-pinned weight downloads
(`AGENTS.md`) and a 1030-test suite that mocks torch.

**Why not fine-tune our own model now?** No labelled data (§7), no annotation budget, and our
synthetic corpus is one-chord-per-bar — training on it would bake in the same assumptions we are
trying to remove.

---

## 9. What "good" looks like numerically

Published references to calibrate targets, not to copy:

- BTC on 471 songs: maj-min **71.8 %**, root **83.8 %**. A mature commercial product is plausibly
  in that band or above on pop; nobody credible publishes 95 %+ on real mixed music.
- Our synthetic 99.7 % is **not** evidence we are near SOTA — it is evidence the decoder is sound.
- A realistic target after Option A on *our* proxies: `maj7` share ≤ 20 % (from 40–66 %),
  non-diatonic ≤ 25 % (from 43–56 %), segs/bar 0.6–1.2 (from 0.85–2.64), meter 1/1 on 3/4 fixtures
  (from 0/1). Those are set in `04` §6 with the exact baseline each one replaces.

---

## 10. References

Primary sources, all retrieved 2026-10-25:

- BTC paper: https://arxiv.org/abs/1907.02698 (ISMIR 2019). Table 1 numbers and the 471-song
  corpus read from the HTML full text; vocabulary definition (170 chords = 12 × 14 qualities +
  X + N) quoted from §4.1.
- BTC code: https://github.com/jayg996/BTC-ISMIR19 — GitHub API reports `license.spdx_id = MIT`.
- BTC weights: https://zenodo.org/records/3527886 (record exists; **weight licence not stated on
  the record — treat as [UNVERIFIED]**).
- Beat This!: https://arxiv.org/abs/2407.21658 (ISMIR 2024); code
  https://github.com/CPJKU/beat_this (`MIT`, 444 stars); PyPI `beat-this` 1.1.0; spectrogram+annotation
  release https://zenodo.org/records/13922116.
- DAFx26 distillation paper: https://arxiv.org/abs/2602.19778 — BTC as teacher; student surpasses
  teacher on seven `mir_eval` metrics.
- Event-based / oversegmentation paper: https://arxiv.org/abs/2604.24386 — reports beating BTC on
  WCSR and segmentation quality.
- ChordMini (2E1D): https://github.com/ptnghia-j/ChordMini — `MIT`, 25 stars at time of check.
- madmom: https://github.com/CPJKU/madmom — licence `NOASSERTION`; DBN patent/non-commercial
  constraint noted by an independent packaging project.
- Essentia: https://github.com/MTG/essentia — `AGPL-3.0`.
- music21: https://github.com/cuthbertLab/music21 — `BSD-3-Clause`.
- mir_eval: PyPI 0.8.2, `MIT`. librosa: PyPI 1.0.0 current, `ISC` (we run 0.11.0).
- ChoCo: https://github.com/smashub/choco (20K+ annotations); Zenodo record 7193888 declares
  **CC BY-NC-SA 4.0**.
- CoCoPops: https://ismir2023program.ismir.net/poster_104.html — **CC-BY-4.0**.
- Harte et al., chord syntax: https://ismir2005.ismir.net/proceedings/1080.pdf — the annotation
  grammar the datasets and `mir_eval` share.
