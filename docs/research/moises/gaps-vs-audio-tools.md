# Gaps versus this repo — 2026-10-23

Moises facts are only what [PAGE-INVENTORY.md](PAGE-INVENTORY.md) and [FEATURE-DEEP-DIVE.md](FEATURE-DEEP-DIVE.md) support. Our facts cite this repo.

## Confirmed in our code this scan

| Ours | Where |
|---|---|
| MPS gate stays 12 GB | `src/audio_to_tab/hardware.py` line 27, `MPS_MIN_RAM_GB = 12.0` |
| Home flag defaults on | `ui/design_tokens.py` lines 57–58, `AUDIO_TOOLS_UI_V2` default `1` |
| Count-in is 0, 1, or 2 bars | `ui/stem_mixer_component/__init__.py` lines 70 and 99 |
| Lead/rhythm split is off in the job | `ui/isolate_jobs.py` lines 112–113, `lead_rhythm` False |
| Tab PDF pipeline is imported | `src/audio_to_tab/pipeline.py` line 19 |

## Gaps that this scan can support

| Gap | Class | Why |
|---|---|---|
| A hosted multi-product shell (Home, Play, Studio, Mastering, Voice, Lyrics) with account login | Platform | Routes and login page observed. We are a local desktop app. Building that shell is not the practice wedge. |
| Studio DAW, real-time collaboration, voice, mastering, generation credits | Product | Routes or help text observed. Interiors not run. Still a different product. |
| VST/AAX install path | Platform | Filenames and install IPC observed. Not our practice player. |
| Live interface capture (WASAPI/ASIO) | Platform | Shipped addon observed. Not required to practise from a file. |
| Public price table | Commercial | Help links `studio.moises.ai/pricing/`. That page redirected to login. Dollar amounts were not on the articles fetched. |
| Their free-tier counter (5 uploads, 5-minute stems, first minute of chords and lyrics) | Commercial | Help text P-S6-61 through P-S6-63. We do not meter uploads. |

## Gaps the old matrix still lists, not re-opened

Chord editing, capo, setlists, batch upload, 27-stem models, and Hi-Fi tiers were not exercised. The marketing home claims 27 stem types and Hi-Fi models. That is an advertisement, not a run. Keep them as historical gaps in `docs/plans/moises-parity/03-FEATURE-MATRIX.md` with status "not re-opened", not as new measurements.

## Where we are ahead, still

Guitar tab and tab PDF exist here (`pipeline.py` importing `pdf_render`). Nothing in the analyzed Moises shell implements tab. Chord Finder and Capo Mode marketing pages do not contain the strings `guitar tab` or `tablature`. The hosted player was not opened, so "Moises has no tab" is still not a 2.1.0 proof. It remains the wedge until a logged-in player pass says otherwise.

Local processing and the 12 GB gate are ours. Moises Home in the persisted session is `studio.moises.ai`, which is not local-first.
