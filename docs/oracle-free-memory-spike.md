# Oracle Always Free — Demucs memory spike

- Date: 2026-07-29
- Host arch: `arm64`
- Python: `3.11.9`
- Torch: `2.13.0` (ok=True)
- Demucs import ok: `True`
- Model: `htdemucs_6s`, quality flags: shifts=0 overlap=0.25, device=cpu
- Verdict: **PASS**

Peak RSS stayed under ~10 GiB for measured clips. Short-clip lite profile on Oracle Free is plausible with single-flight jobs and swap.

**Caveat:** clips were synthetic stereo tones (not dense music mixes). Real songs and Lead/Rhythm post-process may use more RAM; keep `ATT_MAX_JOB_DURATION_SEC≤90`, `ATT_SINGLE_FLIGHT_JOBS=true`, and add 4–8 GB swap on the VM.

| Duration (s) | Peak RSS (GiB) | Elapsed (s) | Exit |
|-------------:|---------------:|------------:|-----:|
| 60 | 1.74 | 29.5 | 0 |
| 90 | 1.88 | 39.5 | 0 |
| 120 | 1.93 | 47.8 | 0 |

Pass criterion: peak &lt; 10.0 GiB. Fail: peak ≥ 11.0 GiB or OOM/nonzero exit.
Parent process max RSS (self, KiB, informational): 295370752

