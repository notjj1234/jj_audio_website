# Follow-up: where the audit and the code disagree

These are measurements from this implementation pass. The audit text was not edited.

- Stored waltz `analysis.json` has 31/145 events shorter than one beat (0.214), not the 0.50 figure in `01` §5. The file still says `beats_per_measure: 4` until that run is analysed again.
- librosa 0.11 `chroma_cqt(tuning=None)` does estimate tuning. The new detector passes `estimate_tuning * (bins_per_octave / 12)` explicitly. `chroma_cqt` has no `octwidth`; the bass chroma uses `fmin=C2` and `n_octaves=3`.
- `fold_other_into_guitar` already returned before deleting `other.wav` when guitar was missing. The unlink now also requires `guitar.wav` to be a real file.
- Phase 0 `baseline.json` clean root and majmin are 1.000. The audit's 0.997 is inside the ±0.01 gate.
- `data/ui_runs/ad6e7c9f-df76-411e-a700-4bd2b3d65d30/current_mix.wav` is digital silence. The before/after band-mix numbers for that id use a temporary sum of its stems, not that file.
- The saved beat grid for `50f1b1f5-2f38-41ea-8f2a-f31e63fddd29` is 80.75 BPM, not the audit's ~108. Comparisons use the saved beats.
- A fresh `beat_track` on the waltz source (103.4 BPM) and on `drums.wav` (69.8 BPM) both score meter 2 above meter 3. The synthetic 3/4 click fixture does return 3. The saved analysis stays at 4.
