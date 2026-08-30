# Lead / Rhythm evaluation checklist

Use short, rights-cleared multitracks (local only; do not commit large audio). Place clips under `clips/` (gitignored).

**Research decisions (keep stage-1 `htdemucs_6s`; second-stage lead/rhythm path):** see [RESEARCH.md](RESEARCH.md) (local-only, gitignored).

## Stage 1 — guitar stem quality (from the mix)

Demucs quality is separate from Lead/Rhythm post-process. Measure it on rights-cleared multitracks that include an isolated guitar ground truth:

```bash
export PYTHONPATH=src:.
audio-isolate --audio /path/to/mix.wav --output ./eval/lead_rhythm/out_stage1 \
  --model htdemucs_6s --quality fast
# Compare out_stage1/guitar.wav to GT guitar (SI-SDR / SIR / listening).
# Optional: inspect out_stage1/bass_bleed_diagnostics.json (analyze_bass_bleed).
```

Pass for a stage-1 challenger: guitar SIR / listening beats stock `htdemucs_6s` on the same clips. Piano bleed and bass bleed inside the guitar band remain known limits.

### Guitar-ft A/B (stock vs `htdemucs_6s_guitar_ft`)

Stay Advanced **opt-in** until this listen pass holds. Do **not** default Full band to guitar-ft or invert the checkbox without it. Do not publish author MoisesDB SDR as product metrics.

Use three rights-cleared clips (local only, not committed):

1. Typical rock/pop full band with a clear guitar part.
2. Dense mix with piano/keys (expect residual piano in guitar — fail only if **worse** than stock).
3. Distorted guitar + bass (bleed may remain).

```bash
export PYTHONPATH=src:.
audio-isolate --audio CLIP --output ./eval/lead_rhythm/out_stock \
  --model htdemucs_6s --quality fast
audio-isolate --audio CLIP --output ./eval/lead_rhythm/out_gft \
  --model htdemucs_6s --quality fast --guitar-checkpoint htdemucs_6s_guitar_ft
```

A/B `guitar.wav` in the mixer (or SI-SDR / SIR vs guitar GT when you have it). First guitar-ft run downloads ~330 MB to `$TORCH_HOME/checkpoints/guitar_htdemucs_6s.pt`.

Cover at least: solo guitar, guitar+orchestra, guitar+bass, dense rock. Score energy bands and high-end (and SI-SDR when GT exists):

```bash
python eval/lead_rhythm/score_guitar_stage1.py \
  --dirs stock=./eval/lead_rhythm/out_stock guitar_ft=./eval/lead_rhythm/out_gft \
  --gt-guitar /path/to/gt_guitar.wav \
  --note "rock full band"
```

Each isolate run also writes `guitar_stem_quality.json` (low/mid/high-end shares, competitor overlap).

### Two-pass A/B (4-stem → 6-stem on residual)

Stay Advanced **opt-in**. About 2× wall time vs single-pass `htdemucs_6s`.

```bash
export PYTHONPATH=src:.
audio-isolate --audio CLIP --output ./eval/lead_rhythm/out_two_pass \
  --model htdemucs_6s --quality fast --two-pass
python eval/lead_rhythm/score_guitar_stage1.py \
  --dirs stock=./eval/lead_rhythm/out_stock two_pass=./eval/lead_rhythm/out_two_pass
```

Pass only if guitar SIR / listening beats stock on the same clips without a worse piano-bleed regression.

### BS-RoFormer-SW / MelBand refine / Tab PDF path A/B

The isolate path and the Tab PDF pipeline now share `model`, `guitar_refine` (residual-aware), optional guitar-ft (cache only on the tab path), and opt-in `--low-end-restore-db`.

```bash
export PYTHONPATH=src:.
audio-isolate --audio CLIP --output ./eval/lead_rhythm/out_baseline \
  --model htdemucs_6s --quality fast
audio-isolate --audio CLIP --output ./eval/lead_rhythm/out_roformer \
  --model bs_roformer_sw --quality fast
audio-isolate --audio CLIP --output ./eval/lead_rhythm/out_refine \
  --model bs_roformer_sw --quality fast --guitar-refine
audio-isolate --audio CLIP --output ./eval/lead_rhythm/out_restore \
  --model htdemucs_6s --quality fast --low-end-restore-db 3
python eval/lead_rhythm/score_guitar_stage1.py \
  --dirs baseline=./eval/lead_rhythm/out_baseline \
         roformer=./eval/lead_rhythm/out_roformer \
         refine=./eval/lead_rhythm/out_refine \
         restore=./eval/lead_rhythm/out_restore \
  --gt-guitar /path/to/gt_guitar.wav \
  --note "high-gain solo + bass"
```

Focus on `low_band_energy_share`, `competitor_overlap` (bass must not explode), and SI-SDR when GT exists. Then score transcription recall on a low-E fixture with `eval/score_transcription.py` through `run_pipeline` (`PipelineConfig.model` / `guitar_refine` / `low_end_restore_db` / `sub_bass_debleed`).

### Dense-mix recovery A/B (subtractive de-bleed + harmonic restore)

Use a **dense high-gain solo clip with bass/drums present** (not a solo section). Stay Advanced **opt-in** until listening + metrics pass.

```bash
export PYTHONPATH=src:.
audio-isolate --audio CLIP --output ./eval/lead_rhythm/out_stock \
  --model htdemucs_6s --quality fast
audio-isolate --audio CLIP --output ./eval/lead_rhythm/out_roformer \
  --model bs_roformer_sw --quality fast
audio-isolate --audio CLIP --output ./eval/lead_rhythm/out_roformer_refine \
  --model bs_roformer_sw --quality fast --guitar-refine
audio-isolate --audio CLIP --output ./eval/lead_rhythm/out_roformer_recover \
  --model bs_roformer_sw --quality fast --guitar-refine --low-end-recovery
# Or explicit stages:
audio-isolate --audio CLIP --output ./eval/lead_rhythm/out_debleed \
  --model htdemucs_6s --quality fast --sub-bass-debleed
audio-isolate --audio CLIP --output ./eval/lead_rhythm/out_debleed_restore \
  --model htdemucs_6s --quality fast --sub-bass-debleed --low-end-restore-db 3
python eval/lead_rhythm/score_guitar_stage1.py \
  --dirs stock=./eval/lead_rhythm/out_stock \
         roformer=./eval/lead_rhythm/out_roformer \
         roformer_refine=./eval/lead_rhythm/out_roformer_refine \
         roformer_recover=./eval/lead_rhythm/out_roformer_recover \
         debleed=./eval/lead_rhythm/out_debleed \
         debleed_restore=./eval/lead_rhythm/out_debleed_restore \
  --gt-guitar /path/to/gt_guitar.wav \
  --note "dense high-gain + bass/drums"
```

Each run writes `low_end_recovery_diagnostics.json` when de-bleed or restore is enabled. Pass when `low_band_energy_share` improves vs stock/refine without exploding `competitor_overlap` (bass bleed). Then compare transcription recall on low-E riffs:

```bash
python eval/score_transcription.py --help
# Run run_pipeline with PipelineConfig(sub_bass_debleed=True, low_end_restore_db=3, ...)
# against baseline stock htdemucs_6s on the same clip.
```

RoFormer guitar needs `bs-roformer-infer` in the same venv. guitar-ft on Tab PDF uses cache only (no runtime download).

## Stage 2 — Lead / Rhythm post-process

### Binary pass (challenger vs current DSP)

Listeners can tell lead from rhythm on:

1. a **hard-panned** two-guitar clip, **and**
2. a **mild-pan** two-guitar clip (`mix_type=mild_pan`),

**better than** today’s `split_lead_rhythm_guitar` (spatial / pitch-rescue / midside / register / forced-emit).

Centered same-register overlap (`centered_overlap`) is **not** a pass gate.

Prefer **label correctness + SI-SDR + listening**. Always-emit makes `split_recall` near 1.0 and is **not** a quality metric.

### Synthetic smoke clips

```bash
export PYTHONPATH=src:.
python eval/lead_rhythm/make_synthetic_clips.py \
  --write-manifest eval/lead_rhythm/manifest.json
python eval/lead_rhythm/score_lead_rhythm.py --no-basic-pitch --note "synthetic smoke"
# or: make eval-lead-rhythm
```

`make_synthetic_clips.py` writes `mild_pan_example/` (required binary-pass case), hard-pan, mono, centered overlap, and double-track under `clips/`, plus optional `gt_lead.wav` / `gt_rhythm.wav` for SI-SDR.

## Threshold defaults (tune after listening)

| Constant | Default | Module |
|----------|---------|--------|
| `SEPARABILITY_FLOOR` | 0.22 | spatial |
| `ROLE_MARGIN_MIN` | 0.18 | spatial/midside/register role gate |
| `REGISTER_SEPARABILITY_FLOOR` | 0.28 | STFT register candidate |
| `MIDSIDE_SEPARABILITY_FLOOR` | 0.22 | Mid/Side candidate |
| `MIDSIDE_SIDE_RATIO_MIN` | 0.04 | Side/Mid RMS floor (rejects mono) |
| `SPECTRAL_SEPARABILITY_FLOOR` | 0.55 | spectral diagnostics only |
| `SPECTRAL_ROLE_MARGIN_MIN` | 0.28 | only if `--lr-allow-spectral-emit` |
| Spatial balance min | 0.12 | same |
| Spatial corr max | 0.92 | spatial (always-allowed ceiling) |
| Spatial corr relaxed max | 0.985 | spatial, only with pitch-divergence evidence (see below) |
| Pitch divergence min | 3.0 semitones | spatial, mild-pan evidence gate |
| Pitch confidence min | 0.08 | spatial, mild-pan evidence gate |
| Analyze window | 90 s | Basic Pitch (first + last window) |

### Env / CLI overrides (eval only)

| Env | CLI |
|-----|-----|
| `ATT_LR_SEPARABILITY_FLOOR` | `--lr-separability-floor` |
| `ATT_LR_ROLE_MARGIN_MIN` | `--lr-role-margin-min` |
| `ATT_LR_ALLOW_SPECTRAL_EMIT` | `--lr-allow-spectral-emit` |
| `ATT_LR_REGISTER_SEPARABILITY_FLOOR` | — |
| `ATT_LR_SPECTRAL_SEPARABILITY_FLOOR` | — |
| `ATT_LR_ANALYZE_WINDOW_SEC` | — |
| `ATT_LR_SPATIAL_CORR_RELAXED_MAX` | — |
| `ATT_LR_PITCH_DIVERGENCE_SEMITONES_MIN` | — |
| `ATT_LR_PITCH_CONFIDENCE_MIN` | — |

### Policy (2026-07-17, updated)

- Prefer **spatial** L/R candidates when the stereo gate passes.
- Else try **midside** (Mid/Side — centered lead + wide rhythm) before register.
- Else try **register** (STFT low/high soft masks) before spectral.
- **Spectral (HPSS)** is diagnostics-only: never emits Lead/Rhythm unless `allow_spectral_emit` (quarantine — HPSS ≠ Lead/Rhythm).
- **Always emit** `lead_guitar` + `rhythm_guitar` whenever a Demucs `guitar` stem exists (best-effort). Low-confidence / forced emits set `forced_emit` / `low_confidence` in diagnostics; labels may be inaccurate.
- Long HPSS/register tails are **silence-padded**, never duplicated mono into both streams.
- Quality presets affect Demucs only; Lead/Rhythm post-process is independent of quality.
- Threshold changes require a new row in [RESULTS.md](RESULTS.md) (local-only, gitignored).
- Demucs itself never produces two guitar stems — Lead/Rhythm is always post-process on the single `guitar` stem.

### Mild-pan pitch-divergence rescue (2026-07-17, new)

Root cause: raw L/R sample correlation of two *independent* sources panned
(p, 1-p) is `2p(1-p) / (p^2 + (1-p)^2)` — it climbs toward 1.0 as panning
approaches center regardless of how different the content is (e.g. two
independent tones panned 55/45 already correlate ~0.98). A single
`SPATIAL_CORR_MAX` ceiling can't distinguish that from a duplicated-mono
guitar (corr → exactly 1.0), so most real two-guitar mixes — which are rarely
hard-panned — were previously rejected before role classification ever ran.

Fix (spatial method only, `lead_rhythm.py`): when correlation exceeds
`SPATIAL_CORR_MAX` but stays under `SPATIAL_CORR_RELAXED_MAX`, compute each
channel's dominant spectral peak ("predominant pitch" proxy — no split
required, same idea as the pitch-confidence features used by solo/rhythm
guitar classifiers in Foulon et al. 2013 and Pati & Lerch 2017). If the two
channels' peaks diverge by at least `PITCH_DIVERGENCE_SEMITONES_MIN`
semitones with reasonable confidence, admit the pair and construct its two
streams via a pitch-informed harmonic mask (centered on the two detected
peaks) instead of the amplitude-only L/R-dominance heuristic, which degenerates
at near-center panning. Identical/near-identical channels always show zero
divergence for this spatial rescue (they may still emit via midside/register
under **best_effort** emit mode only).

## Cases

| Case | Expect (confident default) |
|------|--------|
| Hard-panned lead L / rhythm R | `outcome=lead_rhythm`, correct labels, `method=spatial` |
| Mild/no hard pan, genuinely distinct lead + rhythm | `outcome=lead_rhythm`, `method=spatial`, pitch-divergence evidence |
| Centered lead + wide-panned rhythm | Prefer `method=midside`; emit Lead+Rhythm |
| Mono or highly correlated L/R single guitar | `outcome=ambiguous`, no LR WAVs; combined Guitar kept |
| Centered overlapping lead+rhythm (dead center, L≡R) | `outcome=ambiguous` (confident); best_effort may force emit with warning |
| Double-tracked wide rhythm (same part, mild pan, same pitch) | Usually ambiguous (confident); best_effort may force emit |
| Intermittent lead over continuous rhythm | Emit when margin OK |
| Register-separated mono dual parts | May emit via `method=register` when gates pass |
| 4-stem model (no guitar) | skipped; no lead/rhythm |
| Demucs guitar bleed | May lower confidence → skip emit (confident) or forced emit (best_effort) |

## Automated scorer

```bash
cp eval/lead_rhythm/manifest.example.json eval/lead_rhythm/manifest.json
# add local WAVs under eval/lead_rhythm/clips/...
# or generate synthetics: python eval/lead_rhythm/make_synthetic_clips.py --write-manifest eval/lead_rhythm/manifest.json
export PYTHONPATH=src:.
python eval/lead_rhythm/score_lead_rhythm.py --note "baseline"
python eval/lead_rhythm/score_lead_rhythm.py --emit-mode confident --note "confident policy"
python eval/lead_rhythm/score_lead_rhythm.py --emit-mode best_effort --note "legacy always-emit"
# or
make eval-lead-rhythm
```

Metrics written to `RESULTS.md` (local-only, gitignored):

- **Split precision** — among emits, fraction with `gt_parts=2`
- **Split recall** — among `gt_parts=2`, fraction emitted (also by `mix_type`)
- **Ambiguous rate on gt≤1** — fraction correctly refused (target → 1.0 under confident emit)
- **Label correctness** — among emits with `gt_lead` set
- **Mean SI-SDR** — when manifest includes `gt_lead_wav` + `gt_rhythm_wav` (best of two role permutations)

## Synthetic proxy results (historical)

See earlier 2026-07-17 sine proxies; re-validate with real multitracks via the scorer above.

**2026-08-24 update — confident emit (default):** Lead/Rhythm WAVs are written
only when separability and role gates pass. Low-confidence cases write
`guitar_split_diagnostics.json` with `outcome=ambiguous` and keep combined
Guitar. Pass `--lead-rhythm-mode best_effort` (CLI), `lead_rhythm_mode:
best_effort` (API), or the desktop advanced checkbox to restore legacy
always-emit behavior.

**2026-07-17 update — Mid/Side candidate:** Mid/Side targets centered lead +
wide-panned rhythm (common mix layout). Detected Instruments default-checks
Lead Guitar and Rhythm Guitar only when those WAVs exist.

## Manual procedure (full mix → Demucs → split)

```bash
export PYTHONPATH=src:.
audio-isolate --audio /path/to/clip.wav --output ./eval/lead_rhythm/out --model htdemucs_6s --quality fast --lead-rhythm-mode best_effort
cat ./eval/lead_rhythm/out/guitar_split_diagnostics.json
```

Record wall time for Demucs vs post-process (progress lines).

## Known Demucs limitation: bass bleed into the guitar stem (2026-07-17)

Distorted/overdriven bass and electric guitar share heavily overlapping
spectral and timbral characteristics (harmonic distortion pushes bass energy
up into guitar-like frequency/harmonic ranges), which Demucs's training data
does not always disambiguate cleanly. This is confirmed as a known, inherent
limitation of Demucs-family separation — a maintainer discussion on the
official repo (facebookresearch/demucs, issue #291, "Guitar/Synth is
splitting") states there is "no easy solution" short of training dedicated
per-instrument models on curated datasets ("a hell of a challenge"), which is
explicitly out of scope for this project (no model training, no new
dependencies). Only `htdemucs_6s` is affected in this repo because it is the
only supported model that produces a `guitar` stem at all; `htdemucs_ft` is
the fine-tuned *4-stem* model (vocals/drums/bass/other) and never separates
out guitar, so this specific failure mode does not apply to it (guitar content
simply stays inside "other," unseparated).

**What was implemented — a diagnostic, plus an opt-in partial mitigation, not
a fix:**

- `analyze_bass_bleed()` in `src/audio_to_tab/isolate.py` measures the
  `guitar` stem's RMS energy share below `BASS_BLEED_LOW_BAND_HZ` (250 Hz) and
  flags it (`bass_bleed_diagnostics.json`, same dataclass +
  `to_dict()`/`write_json()` pattern as `LeadRhythmDiagnostics`) when that
  share is anomalously high (`BASS_BLEED_ENERGY_SHARE_FLOOR = 0.65`, calibrated
  against synthetic clean-guitar vs. bled-guitar fixtures in
  `tests/test_isolate.py`). It cannot distinguish bled-in bass from a guitar
  tone that is legitimately bass-heavy — the reason string says so explicitly.
- An optional high-pass filter (`IsolateConfig.bass_bleed_mitigation`, default
  **off**) attenuates the guitar stem below `BASS_BLEED_HPF_CUTOFF_HZ` (60 Hz)
  when flagged. Testing against synthetic fixtures (a clean guitar chord with
  a modest low-E fundamental vs. the same chord plus heavy sub-80 Hz bleed)
  showed this cutoff — chosen below standard tuning's lowest fundamental
  (open low E ≈82.4 Hz) and Drop D (≈73.4 Hz) — measurably reduces the
  bled fixture's low-band energy share while leaving the clean fixture's RMS
  and low-band share almost unchanged (see
  `test_apply_bass_bleed_mitigation_reduces_bleed_without_damaging_clean_signal`).
  It is still only a **partial** reduction: bleed harmonics above the cutoff,
  and bleed that overlaps the guitar's own playable range, are untouched. It
  is also a real tradeoff for guitars tuned lower than the cutoff (Drop C
  ≈65.4 Hz, 7-string low B ≈61.7 Hz, Drop A, etc.) — those fundamentals would
  themselves be attenuated. There is no cutoff that is safe for every tuning,
  which is exactly why this stays opt-in and off by default.
- Both are surfaced through the same progress-message mechanism as the
  Lead/Rhythm diagnostics (`on_progress("bass_bleed", ...)`), and the
  Streamlit UI (`ui/pages/isolate.py`) shows a warning with the diagnostic's
  reason string after a run when flagged, so a user sees an explanation
  instead of a silent mislabel.

**What was not implemented, and why:** a real fix would require re-training or
fine-tuning a source-separation model on curated bass/guitar data — explicitly
excluded by this project's constraints (no new dependencies, no model
training/fine-tuning/downloading). Spectral gating or more aggressive
frequency-domain suppression was considered but rejected: because bled bass
harmonics overlap the guitar's own playable frequency range, any filter
strong enough to remove most of the bleed would also remove legitimate guitar
content, which contradicts the "never damage legitimate low-end guitar
content" requirement for this mitigation. The conservative, clearly-labeled
high-pass filter above is the bounded, honest mitigation implemented instead.
