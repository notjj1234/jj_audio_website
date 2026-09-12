# Issues

Design-decision and issue history for this repo. CI and planning docs may cite IDs (for example `.github/workflows/ci.yml` comments `I-072`). If an older copy of this file is recovered, **append** new sections — never renumber IDs.

Guiding rule for isolation work: if separation is fast, stable, and clean on an **8 GB Apple Silicon CPU (no MPS)**, a high-end host is already “instant.” Bias toward that floor, not peak-GPU showcases.

**Kind key**

| Kind | Meaning |
|------|---------|
| documented tradeoff | Known limit (model, cutoff, speed vs quality). Not a forgotten bug. |
| unfixed gap | We could enforce or align this; it is not done. |
| implemented-in-code | Gap closed in code; remaining text is history / residual limits. |
| unknown | Not verified here. |

Desktop **Lite** auto-profile (speed / device / guitar from RAM/GPU, Detected/Using captions) **already shipped**. Hosted processing mode `lite` is **not** the same as desktop UI Lite.

**2026-09-08 follow-through:** I-500, I-501, I-503, I-505, I-509 are **implemented-in-code**. I-502 / I-504 / I-506 / I-507 / I-508 stay documented tradeoffs (honesty copy + Drop C HPF test; no fake clean-guitar engine).

Do **not** “fix” 8 GB Macs by enabling MPS. `MPS_MIN_RAM_GB = 12` in `src/audio_to_tab/hardware.py` exists because unified-memory OOM/swap is worse than CPU.

---

## Reserved historical IDs

These IDs appear elsewhere in the repo (CI, tests, eval, `.opencode` plans). **Do not reuse them.** Full write-ups are not reconstructed here from memory; details may live in a recovered `docs/issues.md`, `docs/issues-audit-2026-09-02.md`, or `.opencode/plans/fix-plan-2026-09-02.md`.

| ID | Where it still appears |
|----|------------------------|
| I-072 | `.github/workflows/ci.yml` (desktop-first test/lint gate) |
| I-098 | `tests/test_ui_pages.py` |
| I-104 | `eval/score_transcription.py` |
| I-200–I-252 | `.opencode/plans/fix-plan-2026-09-02.md` (desktop-tier audit). **I-227** (full-file reads) overlaps I-500 / I-501 if that audit is restored — cross-ref, do not duplicate ID 227. |

---

## Isolation performance and function (2026-09-08)

| ID | Severity | Area | Surface | File:symbol | Symptom | Evidence | Low-end impact | Kind | Direction (research only) |
|----|----------|------|---------|-------------|---------|----------|----------------|------|---------------------------|
| I-500 | High | performance | desktop | `ui/pages/isolate.py:_render_region_controls` | Lite used to look like “whole song” while silently capping at **90 s**. | Hosted Auto/`lite` still hard-caps **60 s / 90 s** (API quotas). | Runtime/RAM on long files. | implemented-in-code | Lite defaults to **full file** like Pro; **no silent clamp**. Visible warning when &gt; 90 s + one-click **Safer: first 90 s**. Honesty over hidden override. |
| I-501 | High | performance | engine | `hardware.py:roformer_max_audio_sec`; `roformer.py:_refuse_long_roformer_audio` | Long RoFormer jobs OOM/swap: full-track `result`/`counter` plus mix tensor. | PyTorch MPS OOM on 8 GB unified memory. | Pro/forced RoFormer on long audio. | implemented-in-code | Duration/RAM gate: ram &lt; 12 GB → 90 s, else 180 s. Full-track alloc remains inside the cap. No MPS below 12 GB. MLX out of scope. |
| I-502 | High | guitar function | engine | `src/audio_to_tab/isolate.py`; Lite/Pro help copy | Guitar stem still has bass/drum/cymbal/vocal bleed. | Demucs README / guitar-ft card. | Lite 8 GB **must** use Demucs. | documented model-level tradeoff | Honesty copy: do not promise clean guitar. Fold defaults unchanged. |
| I-503 | Med | performance | engine | `hardware.py:apply_recommended_cpu_threads`; `separate.py:run_demucs` | Demucs could use all logical cores / E-cores. | Thread cap was RoFormer-only. | Contention on Lite Demucs. | implemented-in-code | Shared thread helper on RoFormer, guitar-ft, frozen in-process Demucs; subprocess `OMP`/`MKL`/`TORCH_NUM_THREADS`. |
| I-504 | Med | guitar / tuning | engine | `isolate.py` `BASS_BLEED_HPF_CUTOFF_HZ = 60` | Opt-in HPF can thin deep-drop fundamentals. | Drop D kept; Drop C / 7-string / Drop A not. | Quality, not RAM. Lite HPF off. | documented tradeoff | HPF stays opt-in. Drop C fixture test + mixer caption added. |
| I-505 | Med | policy | desktop vs web | `backend/capabilities.py:recommended_mode`, `device_options` | Hosted Auto used to stay CPU Fast on ≥12 GB MPS Macs. | Desktop already Balanced/MPS at the 12 GB gate. | 8 GB: both CPU. | implemented-in-code | Hosted Auto aligns with ≥12 GB MPS gate (`balanced`/`mps`). 8 GB: `fast_cpu`, MPS hidden. Single-flight still `lite`. |
| I-506 | Med | guitar/piano | engine | Lite/Pro piano help | Keys in the guitar stem, or keys vanishing when fold skips `other`. | Demucs piano artifacts. | Quality only. | documented upstream limitation | Piano is not a Lite outcome; picker warns Demucs piano is unreliable. |
| I-507 | Med | quality vs speed | desktop Lite | `QUALITY_SHIFTS` (`fast=0`, `balanced=1`) | Lite Faster is weaker than Pro Balanced on the same Demucs model. | Demucs `--shifts` cost. | Intentional wall-clock bias. | documented speed/quality tradeoff | Faster stays the floor default; Lite band help says Faster ≠ Balanced quality. |
| I-508 | Med | guitar function | engine (upstream) | `lead_rhythm.py` (not default) | Lead + rhythm + acoustic collapse to one guitar stem. | guitar-ft / MelBand cards. | Same ceiling as I-502. | documented model limit | Lead/rhythm stays non-default; guitar card says one guitar track. |
| I-509 | Med | performance | website | `ProcessingModeSelect.tsx`; `IsolatePage.tsx` | Select hid Auto and remapped it to Balanced. | API Auto existed; SPA bypassed it. | Low-end web users missed 60/90 s caps. | implemented-in-code | Isolate defaults to `auto`; Auto is the first select option; helper text uses Auto’s resolved device/cap. |

### Not filing (already mitigated or out of scope)

- Lite auto speed/device/guitar + Detected/Using captions — shipped.
- MPS below 12 GB — keep gated. Raising `PYTORCH_MPS_HIGH_WATERMARK_RATIO` to force MPS on 8 GB is an OOM/swap risk.
- `demucs_jobs=1` / `demucs_segment≈8` clamped to 7 s for HTDemucs — keep. Upstream Hybrid Transformer max segment is **7.8 s**.
- Stem presence labels — UX only; Demucs still computes the full stem set.
- Tab PDF, auth, visual polish — out of this audit.

### Web sources (opened for this audit)

- https://github.com/facebookresearch/demucs — 6s guitar/piano; `--shifts` cost; CPU ~1.5× duration; HTDemucs segment ≤7.8 s
- https://huggingface.co/adityalakhani/htdemucs-6s-guitar-ft — remaining bleed on metal, piano, multi-guitar
- https://discuss.pytorch.org/t/mps-backend-out-of-memory/183879 — 8 GB MPS OOM
- https://www.runlocalai.co/errors/mps-backend-out-of-memory — unified-memory watermark ([uncertain] on the exact % vs current macOS)
- https://github.com/0ji54n/guitar_backingtrack — MelBand guitar still bleeds
- facebookresearch/demucs issue **#291** — cited in `isolate.py` (page not fetched for this write-up)
