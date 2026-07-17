# Lead/Rhythm eval results

_No real multitrack run recorded yet. Copy `manifest.example.json` → `manifest.json`, add rights-cleared clips under `clips/`, then:_

```bash
export PYTHONPATH=src:.
python eval/lead_rhythm/score_lead_rhythm.py --note "baseline after spectral quarantine"
# or: make eval-lead-rhythm
```

## Gate

Do not change `SEPARABILITY_*` / `ROLE_*` (or `LeadRhythmThresholds` defaults) without re-running the suite and appending a dated summary row below.

## Runs

| date | note | n | split_precision | split_recall | ambiguous_ok_gt≤1 | label_correctness |
|------|------|---|-----------------|--------------|-------------------|-------------------|
| — | awaiting first local corpus | — | — | — | — | — |
