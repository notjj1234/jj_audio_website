# This repo — citations checked 2026-10-23

Only files opened or grepped in this scan are cited. Older `02` prose is in the archive. If a capability is not in this table, this scan did not re-prove it.

| Capability | What the code says | Citation |
|---|---|---|
| Apple GPU memory gate | `MPS_MIN_RAM_GB = 12.0`. Requests below that do not use MPS. | `src/audio_to_tab/hardware.py:27` and the check at line 416 |
| Home visual flag | Default `AUDIO_TOOLS_UI_V2` is `1`. `0` keeps the old Home. | `ui/design_tokens.py:57-58` |
| Count-in | Mixer argument `count_in_bars` is documented as 0, 1, or 2. | `ui/stem_mixer_component/__init__.py:70` and `:99` |
| Count-in persistence | Practice state clamps `countInBars` to that range. | `ui/project.py:114-119` |
| Lead/rhythm UI | Job options set `lead_rhythm` False and mode `confident`. | `ui/isolate_jobs.py:112-113` |
| Tab PDF | The pipeline imports `render_structured_tab_pdf`. | `src/audio_to_tab/pipeline.py:19` |
| Isolate GPU copy | Isolate tells the user CUDA on Windows and MPS on Apple Silicon with the 12 GB condition in the hint string. | `ui/isolate_state.py:185` |

## Follow-up lines opened the same day

| Capability | What the code says | Citation |
|---|---|---|
| RoFormer length cap | Known RAM under 12 GB refuses RoFormer past 90 seconds. Otherwise the cap is 180 seconds. | `src/audio_to_tab/hardware.py:410-418` |
| MPS downgrade | An MPS request on a Mac without a usable MPS device, or with known RAM under 12 GB, becomes CPU. | `src/audio_to_tab/hardware.py:421-438` |
| Desktop upload size | Streamlit `maxUploadSize` is 500. | `.streamlit/config.toml:24` |
| Desktop audio types | The shared uploader list is mp3, wav, flac, and m4a. | `ui/common.py:37-52` |
| Web routes | `/login`, `/tab`, `/isolate`, `/settings`, `/legal/:docId`. No Home route. | `web/src/App.tsx:105-113` |
| API upload cap | Default `max_upload_mb` is 50. YouTube is off. Upload rate `10/minute`. Job rate `20/minute`. | `backend/config.py:43-46` |
| API duration cap | Default `max_job_duration_sec` is 300. | `backend/config.py:65` |

## Not re-audited this scan

Separator model names, YouTube ingest, export format lists, web upload limits, and the Home component's pixel output. The Home tests exist (`tests/test_home.py` mentions the flag) but were not executed in this session.

## Studio / DAW

No DAW timeline, VST host, or collaboration session was found by the searches above. That is a bounded search, not a proof the strings never appear. The product under `ui/` and `src/audio_to_tab/` that this scan touched is a local practice and separation app.
