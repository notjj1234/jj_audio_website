# Cursor Agent Prompt — Fix Guitar Low-End / Low-E Masking on Dense Mixes

Paste the ENTIRE block below into Cursor's Agent as the full task. It is self-contained:
it explains the codebase state, the exact root cause of the user's symptom (with the
supporting evidence), names the files/functions to change, and gives a prioritized plan
with explicit verification steps. It assumes the agent has **no** prior context.

---

## Task

Improve guitar stem quality in the `audio_to_tab` engine. The PRIMARY, must-fix symptom
is this exact, reproducible behavior reported by the user:

> When the guitar is the **only** instrument playing, the isolated guitar stem is faithful
> (matches the original). But the moment **other instruments (bass/drums/keys) enter the
> mix**, the isolated solo-guitar stem becomes **muffled / buried / low-end-rolled-off**
> (the low-E string ≈82 Hz and its low harmonics weaken or vanish). Mixing only bass+guitar
> is fine; it only degrades when the music gets dense. So the problem is **not** the
> guitar-solo sections — it's the sections where other instruments compete.

The improvement must take effect in the **Tab PDF / transcription path** (`pipeline.py`),
which today uses the **weakest** separation default and therefore exhibits the symptom most
severely.

## Root cause (do not "fix" with a blunt EQ boost — it will not work)

This is **masking at separation time, inside the model**. These separation networks estimate
soft time-frequency masks; when other instruments are present, the model can lower the
guitar mask's value in the low-mid band (≈60–400 Hz) so that energy there is re-assigned to
the bass / drums stems. That guitar fundamental + low harmonics are **discarded during
inference**. Once removed:

- A post-hoc **broadband low-shelf boost cannot put the removed fundamental back** — it only
  amplifies the remnant + noise left in that band, adding mud without restoring the note.
- This is NOT a bleed problem to be filtered away; it is guitar energy the model dropped.

Therefore the real levers are (in order of impact):

1. **Use a better base separator** that does not gate the guitar's low-mid so aggressively.
   Leadership data (MVSEP guitar leaderboard / Multisong) quantifies the gap on exactly this
   kind of masking:

   | Model | Guitar SDR | Note |
   |---|---|---|
   | `htdemucs_6s` (what the **Tab path uses today**) | **5.25 dB** | worst — most low-end masking |
   | `htdemucs_ft` (4-stem, guitar in `other`) | ~8.3 dB instr | better but no guitar label |
   | **BS-RoFormer-SW** (already in `roformer.py`) | **9.05 dB** | best free 6-stem; ~4 dB better |
   | MVSep Guitar ensemble (BS-RoFormer + MelBand) | 7.51 dB | residual-based specialist |

   Wiring **BS-RoFormer-SW** (already implemented, SHA256-pinned in `roformer.py`) into the
   Tab pipeline is the single highest-value, fully free fix.

2. **Residual-aware MelBand guitar refine** (also already implemented) — feed the guitar +
   the `other` residual back through the dedicated `becruily/mel-band-roformer-guitar`
   specialist. When the residual contains part of what the 6-stem model dropped, the
   specialist can put it back. The Tab path currently does this **without the residual** (it
   throws `other` away) — a real bug to fix.

3. **Subtractive / harmonic de-bleed and restoration** (in-project, opt-in) — see the plan
   below. This is the correct replacement for "EQ boost": recover or re-support the low
   notes without fighting the model's discarded fundamental.

## Codebase state (already true — do NOT re-implement what exists)

- Shared engine in `src/audio_to_tab/` used by a Streamlit deskt/app and a FastAPI/React
  site (`backend/`).
- The **isolate path** (engine `src/audio_to_tab/isolate.py`, UI `ui/pages/isolate.py`, UI
  state `ui/isolate_state.py`, backend job `backend/jobs/runner.py`) is ALREADY fully wired
  with all quality backends:
  - `src/audio_to_tab/roformer.py`: **BS-RoFormer-SW** (id `bs_roformer_sw`, 6-stem, weights
    `enerjazzer/BS-ROFO-SW-Fixed`, SHA256-pinned urllib download) and **MelBand-RoFormer
    Guitar** (id `melband_roformer_guitar`, `becruily/mel-band-roformer-guitar`).
  - `src/audio_to_tab/separate.py`: **htdemucs-6s-guitar-ft** in-process (id
    `htdemucs_6s_guitar_ft`, `adityalakhani/htdemucs-6s-guitar-ft/guitar_htdemucs_6s.pt`,
    SHA256-pinned).
  - `isolate.py` already has: `fold_other_mode` (`full`/`best_effort`/`band_limited`,
    `FOLD_GUITAR_BAND_LOW_HZ = 82.0`), `FoldOtherDiagnostics`, `analyze_bass_bleed`,
    `GuitarStemQualityDiagnostics` (`GUITAR_HIGH_END_HZ = 4000.0`), opt-in bass-bleed HPF
    mitigation, checkpoint/resume, `effective_demucs_segment`, and optional `guitar_refine`
    that DOES pass the residual: `run_guitar_refine(guitar, guitar, residual_path=<other>, ...)`.
  - `ui/isolate_state.py` exposes `guitar_roformer` / `guitar_roformer_refine` with graceful
    downgrade. Optional extras: `[demucs]`, `[roformer]` (`bs-roformer-infer>=0.1.5`),
    `[separator]` (`audio-separator>=0.39.1`).

- **THE GAP (your main job):** the **Tab PDF pipeline** does not use any of this.
  - `src/audio_to_tab/pipeline.py`: `PipelineConfig` (lines ~32-48) has NO `model`,
    `guitar_checkpoint`, `guitar_refine`, `demucs_segment`, `demucs_jobs`, `fold_other_mode`,
    or residual options. `run_pipeline` calls
    `separate_guitar_stem(work_audio, stem_path, device=..., quality=...)` (lines ~139-144)
    → defaults to stock **`htdemucs_6s`** (the masking-prone 5.25 dB model).
  - `src/audio_to_tab/separate.py` `separate_guitar_stem` (lines ~225-331) writes ONLY the
    guitar WAV to `out` and discards the temp dir → the `other` residual (and every other
    stem) is lost. Its `guitar_refine` path calls `run_guitar_refine(out, out, device=...)`
    with `residual_path=None` → a WEAK refine vs. the isolate path.
  - `ui/pages/tab_pdf.py` (lines ~165-173) and `backend/jobs/runner.py` (lines ~65-75) build
    that same `PipelineConfig` with no backend knobs.

## Constraints (security / dependency / licensing discipline)

1. Weights are fetched with **urllib + explicit SHA256 pins** cached under
   `torch_cache_dir()` / `separator_cache_dir()`. **Do NOT add `huggingface_hub`** as a hard
   dep. Any NEW checkpoint must have a SHA256 pin or be disallowed.
2. Do NOT add new hard runtime deps. New backends go behind existing optional extras
   (`[roformer]`, `[separator]`, `[demucs]`) or a new optional extra — never required by
   default. Always graceful-degrade (log + fall back) when an optional backend is missing.
3. **Licensing:** the `enerjazzer/BS-ROFO-SW-Fixed` checkpoint shows **License: unknown** on
   HuggingFace, and `becruily/mel-band-roformer-guitar` is a community Megaphone-sourced
   model. These are acceptable for the user's **personal/internal use** (already the project's
   posture). Do NOT re-license, claim commercial redistribution rights, or remove provenance
   comments for these checkpoints. The BS-RoFormer *architecture* is MIT (lucidrains) and
   ZFTurbo's training repo is MIT — cite those when adding comments. Keep the existing
   "do not publish author/MoisesDB SDR" rule in all eval docs.
4. Respect documented tradeoffs: `BASS_BLEED_HPF_CUTOFF_HZ = 60.0` is a partial mitigation
   that hurts tunings below Drop-D; never make it on by default or present it as a fix.
   Anything labeled diagnostic stays diagnostic.
5. Preserve CPU-friendly defaults: `demucs_jobs` default 1 (avoid OOM on 8–16 GB desktop);
   `effective_demucs_segment` clamps `htdemucs_6s` to ≤7s. Reuse these.
6. Match existing style: typed dataclasses like `isolate.py`; diagnostics persisted as
   `*_diagnostics.json`; no new comments unless needed; tests in `tests/`.

## In-repo work (do FIRST — no downloads needed beyond existing pinned weights)

### 1. Wire quality backends + residual into the Tab PDF pipeline (highest value)
- Extend `PipelineConfig` in `pipeline.py` with: `model` (default `htdemucs_6s`),
  `guitar_checkpoint` (default None), `guitar_refine` (default False), `demucs_segment`,
  `demucs_jobs`, and a `fold_other_mode` equivalent for the tab path.
- Change `run_pipeline` so it retains the `other` residual (and ideally all 6 stems) so
  `guitar_refine` can use a residual-aware MelBand refine exactly like the isolate path:
  `run_guitar_refine(guitar, guitar, residual_path=<other>, device=...)`.
- Fix `separate_guitar_stem` in `separate.py`: keep its signature backward-compatible (add
  optional params with defaults), but (a) when `model` is a RoFormer model, collect ALL
  stems (don't return only guitar), and (b) make its `guitar_refine` call pass the residual
  when one is available.
- Surface new options in `ui/pages/tab_pdf.py` (e.g. a "Separation quality / model" selector
  that only shows RoFormer/MelBand/guitar-ft when the backend is installed — reuse
  `is_roformer_backend_available` / `is_guitar_refine_available` from `roformer.py` and
  `is_demucs_available` from `separate.py`).
- Surface them through the backend path: `backend/jobs/runner.py`, `backend/contracts.py`,
  and the API route/contract JSON so the website Tab PDF job can select the model.
- Add tests in `tests/`: (a) `PipelineConfig` carries the new fields and defaults are
  unchanged-by-default; (b) `separate_guitar_stem` passes a residual to `run_guitar_refine`
  when present (mock the real backends); (c) the UI state helper normalizes/downgrades the
  tab-path selection exactly like `ui/isolate_state.py::normalize_guitar_track_selection`.
  Update `tests/test_isolate_state.py` only if behavior of existing state helpers changes.

### 2. Correct low-end recovery: harmonic support + subtractive de-bleed (NOT a naive shelf)
Background from the audio literature: for low-pitched notes, **listeners reconstruct a
missing fundamental from its overtone series** (the 2nd harmonic of low-E ≈165 Hz, 3rd ≈247
Hz, 4th ≈330 Hz). So the right restoration is to **preserve/boost the low-mid *harmonics***
of the guitar so the low note stays audible, and to **remove the actual bled bass content**
(subtractively) rather than boost a band blindly. Implement BOTH as opt-in, default-off, with
diagnostics:

- **Subtractive bass de-bleed (priority):** for the `guitar` stem, estimate the sub-band
  (< ~150 Hz) overlap with the `bass` stem (and optionally the drums stem's low band) across
  time using a short-window STFT/spectral mask or an envelope-gated subtraction, and subtract
  a scaled copy from the guitar's low band. This removes the *real* bled content the model
  left behind instead of boosting it. Model it on the existing `analyze_bass_bleed` +
  `fold_other_into_guitar` style. Add a `LowEndRecoveryDiagnostics` dataclass persisted as
  `low_end_recovery_diagnostics.json` recording pre/post low-band share and the RMS removed.
- **Harmonic support (secondary):** an opt-in gentle boost centered on the guitar's low-mid
  harmonics (e.g. a low/upper-bass shelf peaking ~120–200 Hz, NOT a sub boost below ~60 Hz),
  gated behind a config field (e.g. `low_end_restore_db`, default 0 = off) so A/B eval stays
  apples-to-apples. Use `scipy.signal` like `_bandpass_audio` / `_highpass_rms`.
- Wire both into BOTH the isolate path (`isolate.py`) and the tab path (`pipeline.py`), plus
  UI toggles in `ui/pages/tab_pdf.py` and `ui/pages/isolate.py`.
- The mitigation HPF (`bass_bleed_mitigation`) is NOT a replacement — keep it opt-in and
  separate.

### 3. Guitar-ft as the tab/transcription default when cached (no download at runtime)
`guitar-ft` (htdemucs_6s_guitar_ft) uses the same architecture/weights as stock Demucs and
is "better calibrated for clean highs to distorted lows". When it is NOT in the torch cache,
do NOT download at runtime — fall back to stock `htdemucs_6s` and log a hint. Only opt in
via the new config field. This is a no-download improvement only when the checkpoint exists.

### 4. (Optional, after 1–3) Ensemble the low-end across two separators
The proven MVSEP "dedicated guitar" trick: run BS-RoFormer-SW to get stems, then run the
MelBand guitar specialist on guitar+residual, and **blend** the low-mid of the specialist's
guitar with the 6-stem guitar. Add as an opt-in mode with diagnostics and A/B. Do not claim
it restores harmonics above the guitar's own range.

## Optional: one external model for full fundamental recovery (after in-repo work)

The in-repo work reduces masking and restores low-end harmonic support, but **full
fundamental recovery from a dense high-gain mix may still need a different separator**. Do
this ONLY after 1–3, choosing ONE path behind the existing optional extras, SHA256-pinned:

1. **BS-RoFormer-SW as the tab separator** — already implemented in `roformer.py`; the work
   is purely wiring it through `pipeline.py` + `separate_guitar_stem` (item 1). Expected best
   low-end guitar behavior (~9.05 dB vs 5.25 dB). Requires `[roformer]`.
2. and/or **becruily MelBand guitar refine WITH residual** — also already implemented; reuse
   `run_guitar_refine` with the retained `other` residual exactly like the isolate path.

Do NOT add alternative un-verified community checkpoints lacking a SHA256 pin. If you need an
additional quantifiable verification resource, you MAY add an optional extra `[eval]` that
brings in `mir_eval` (already used by `eval/score_transcription.py`) — but do not change
default-install deps.

## External resources to reference (free; not required if 1–3 suffice)

- **MVSEP (mvsep.com)** — free leaderboard + online "Guitar Extractor"; documents BS-RoFormer-SW
  at 9.05 dB guitar SDR and the ensemble ("filtered sources from other stems") you replicate
  in item 4. Their weights are community mirrors of what `roformer.py` already pins.
- **`bs-roformer-infer`** / `python-audio-separator` — free, already optional deps.
- **MSST (Music Source Separation Toolbox)** and `pgotta/Stemmy` — free GitHub multi-source
  "Extended" mode (heavier) as a reference for dense-mix multi-instrument cases; not required.
- **guitar-ft weights** — free, already in-repo.

## Verification checklist (run what applies)

- `python -m pytest tests/ -x -q` — the full suite must stay green.
- New/updated tests for: `PipelineConfig` new fields; `separate_guitar_stem` residual
  retention; low-end recovery default-off behavior; optional-backend downgrade (tab path).
- Before/after A/B on a **dense high-gain solo clip with bass/drums present** (this is the
  failing case — NOT a solo section):
  - `audio-isolate --audio CLIP --output out_stock --model htdemucs_6s --quality fast`
  - `audio-isolate --audio CLIP --output out_roformer --model bs_roformer_sw --quality fast`
  - `audio-isolate --audio CLIP --output out_roformer_refine --model bs_roformer_sw --quality fast --guitar-refine`
  - `audio-isolate --audio CLIP --output out_roformer_recover --model bs_roformer_sw --quality fast --guitar-refine --low-end-recovery`
  - Score with:
    `python eval/lead_rhythm/score_guitar_stage1.py --dirs stock=out_stock roformer=out_roformer roformer_refine=out_roformer_refine roformer_recover=out_roformer_recover [--gt-guitar GT.wav]`
  - Focus on `low_band_energy_share` and (if GT given) `si_sdr`; confirm recovery raises
    low-band presence without exploding `competitor_overlap` for bass.
- Transcription-level: `eval/score_transcription.py` on a low-E / low-riff fixture — compare
  recall/precision baseline vs best backend. The muffled case should show notably better
  low-note recall (notes in the 40–120 Hz MIDI range) after the fix.
- Optional end-to-end: run `pipeline.py` with the new backend options and confirm BOTH the
  guitar stem and the residual are produced and the refine uses the residual.

## Definition of done

- Tab PDF pipeline supports the better backends (model selector: htdemucs_6s / guitar-ft /
  BS-RoFormer-SW / +MelBand refine) and a residual-aware MelBand refine.
- `separate_guitar_stem` no longer discards the residual needed for a residual-aware refine.
- Opt-in low-end recovery (subtractive de-bleed + harmonic support) exists in BOTH isolate
  and tab paths, default OFF, with persisted diagnostics, and demonstrably improves low-note
  transcription recall on a dense-mix clip.
- Optional-backend graceful degradation everywhere; CPU defaults preserved.
- Tests green; A/B scores recorded (stage-1 + transcription); licensing provenance preserved.
- No `huggingface_hub` dependency; no new hard deps; any new checkpoint SHA256-pinned.
