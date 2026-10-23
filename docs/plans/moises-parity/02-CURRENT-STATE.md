# Current state — Audio Tools desktop + website (2026-10-19, delta 2026-10-20)

Inventory only. No recommendations, no roadmap. Evidence is `path:line` at the time of writing
(2026-10-19). "Desktop" = Streamlit product under `ui/`, packaged with `packaging/launcher.py`.
"Web" = React SPA under `web/` + FastAPI under `backend/`. "Engine" = shared
`src/audio_to_tab/`.

This is the source inventory for `03-FEATURE-MATRIX.md`. The qualifications in section 10 matter:
a few rows say "absent" when the code can do part of the job, and a few rows say "implemented" when
the UI cannot reach the code. Read the evidence, not just the status word.

Status legend: `implemented` = works end-to-end on at least one shipped surface;
`partial` = present but limited, surface-specific, engine-only, or not wired to a UI;
`absent` = no code path found; `unknown` = not confirmable from source.

## 0. Delta — 2026-10-20 (Phase 1 landed)

The tables below are the **2026-10-19 pre-implementation baseline**. Phase 1 changed several rows
without rewriting the whole inventory. Where this delta conflicts with a table row or a note in §10,
**this delta wins**.

| Area | 2026-10-19 baseline | 2026-10-20 status | Evidence |
|---|---|---|---|
| Analysis (BPM/key/chords/sections/lyrics) | No analysis layer | Implemented in `src/audio_to_tab/analysis.py`, `key.py`, `chords.py`, `sections.py`, `lyrics.py`; cached as `analysis.json` | `tests/test_analysis.py`, `test_chords.py`, `test_sections.py`, `test_lyrics.py`; real Waltz run |
| Practice display | No Chords/Sections/Lyrics/Tab UI | Implemented in the mixer practice panel: tabs, diagrams, click-to-seek, lyric highlight, measure view | Real Waltz UI; `tests/test_stem_mixer_component.py`; `tests/test_analysis.py` |
| Project manifest | Session-scoped run state | `project.json` per run (source, analysis/tab refs, mixer state, clamping, atomic writes) | `ui/project.py`; `tests/test_project.py` |
| Count-in / A/B loop | Both absent | Both implemented in the desktop player; section loops use the same range | Practice panel; real Waltz UI |
| Desktop mix export | Applied speed/key, no pan | Applies pan as well; center export bit-identical; hard L/R tested | `mix_stems_to_wav(..., pans=...)`; `tests/test_mixer.py` |
| Hosted YouTube typo | `allow_youtssube` → `AttributeError` | Fixed to `allow_youtube` | `backend/main.py:343`; `backend/config.py:44` |
| Packaged lyrics | Not present | Dev path works; freeze does not collect `faster_whisper` or ship the model. Decision deferred to Phase 1.6 | `05` §Phase 1.6; `06` §Verification |
| Home | Text-only recents + button rows | Functional: primary action, recents, library, Analyse/Practice, flash. **Craft is the remaining gap** | `ui/pages/home.py`; current 1440/1024 audit in `10` |
| Test count | 882 collected; `AGENTS.md` said 809 | 1030 passed, 1 skipped at the Phase 1 gate; `AGENTS.md` updated to 1030 | `pytest tests/ -q` at the Phase 1 gate |

The remaining UI gap is specified in `10-MOISES-UI-CRAFT.md` and planned in
`11-DESKTOP-UI-REDESIGN.md`. The engine is no longer the gap; the surface is.

## 1. Ingest and source handling

| Feature | Desktop | Web | Engine | Status | Evidence (file:line) | Notes |
|---|---|---|---|---|---|---|
| Local audio upload | Yes | Yes | n/a | implemented | `ui/pages/isolate.py:2026`; `web/src/pages/IsolatePage.tsx:436`; `ui/common.py:37` | MP3/WAV/FLAC/M4A on both. Desktop uploader also accepts video. |
| Upload size cap | 500 MB | 50 MB | n/a | implemented | `.streamlit/config.toml:24`; `backend/config.py:43`; `backend/main.py:310` | Desktop cap is a local Streamlit setting; hosted cap is enforced server-side. |
| Local video upload | Yes | No | n/a | partial | `ui/pages/isolate.py:2026-2037`; `ui/pages/isolate.py:1196-1217` | MP4/MOV/WebM/MKV; audio is extracted, video is shown in the mixer. |
| YouTube search | Yes | No | Yes | partial | `ui/pages/isolate.py:373`; `src/audio_to_tab/ingest.py:325`; `web/src/trackOptions.ts:45` | Hosted copy explicitly says YouTube is desktop-only. |
| YouTube URL → audio (download only) | Yes | No | Yes | partial | `ui/pages/youtube_audio.py:64-181`; `src/audio_to_tab/ingest.py:405` | Desktop has a separate "YouTube to MP3" page; it does not separate stems. |
| YouTube preview video in mixer | Yes | No | Yes | partial | `ui/pages/isolate.py:462-587`; `src/audio_to_tab/ingest.py:456` | Search → Use downloads the video and offsets playback. |
| Section/region before separation | Yes | Yes | Yes | implemented | `ui/pages/isolate.py:2321-2350`; `web/src/pages/IsolatePage.tsx:506-594`; `web/src/components/RegionPicker.tsx:45` | Desktop uses the committed wavesurfer iframe; web uses wavesurfer directly. |
| Full-file processing | Yes | Partial | Yes | partial | `ui/pages/isolate.py:2236-2263`; `web/src/pages/IsolatePage.tsx:263-291` | Desktop processes the whole file and warns on Lite; hosted silently trims to the mode cap after a notice. |
| Carry audio from Tab PDF into isolation | Yes | No | n/a | partial | `ui/pages/tab_pdf.py:485-493`; `ui/pages/isolate.py:1484` | Streamlit page-switch carry-over; no hosted equivalent. |
| YouTube URL accepted by job API | Yes | Partial | n/a | partial | `backend/main.py:341-343`; `backend/config.py:44` | Fixed 2026-10-20: route reads `settings.allow_youtube`. Desktop YouTube ingest does not use this route. |

## 2. Separation and stem models

| Feature | Desktop | Web | Engine | Status | Evidence (file:line) | Notes |
|---|---|---|---|---|---|---|
| Demucs 4-stem (`htdemucs`) | Yes | Yes | Yes | implemented | `src/audio_to_tab/separate.py:390`; `web/src/pages/IsolatePage.tsx:105-111`; `ui/pages/isolate.py:1752` | Vocals/drums/bass/other. |
| Fine-tuned 4-stem (`htdemucs_ft`) | Yes | No | Yes | partial | `ui/pages/isolate.py:1841-1855`; `src/audio_to_tab/separate.py:26` | Desktop-only checkbox; web always uses stock models it names. |
| Demucs 6-stem guitar/piano | Yes | Yes | Yes | implemented | `ui/pages/isolate.py:1850`; `web/src/pages/IsolatePage.tsx:105-111` | Piano is labeled as heavy-bleed on both surfaces. |
| BS-RoFormer-SW guitar | Yes | Yes | Yes | implemented | `src/audio_to_tab/roformer.py:39`; `ui/pages/isolate.py:1878`; `web/src/pages/IsolatePage.tsx:102-111` | Hosted caveat names ~700 MB first download and residual bleed. |
| MelBand guitar refine | Yes | Yes | Yes | implemented | `src/audio_to_tab/roformer.py:39`; `ui/pages/isolate.py:1878`; `web/src/pages/IsolatePage.tsx:102-111` | Second-pass specialist; web exposes it as a guitar-picker option. |
| SCNet 4-stem | No | No | Yes | partial | `src/audio_to_tab/scnet.py:34`; `src/audio_to_tab/isolate.py:118,2218` | Engine/CLI path only; no desktop or hosted control. |
| Guitar-focused Demucs weights | Yes | No | Yes | partial | `ui/pages/isolate.py:1818-1834`; `src/audio_to_tab/separate.py:123` | ~330 MB, SHA256-pinned `urllib` download; opt-in checkbox. |
| Two-pass 4-stem → 6-stem guitar | Yes | No | Yes | partial | `ui/pages/isolate.py:1856-1870`; `src/audio_to_tab/isolate.py:852-855` | Opt-in; about 2× slower. |
| Cross-model guitar ensemble | Yes | No | Yes | partial | `ui/pages/isolate.py:1972-1986`; `src/audio_to_tab/isolate.py:901` | Demucs + BS-RoFormer per-band soft-max blend; opt-in. |
| Other → guitar fold | Yes | Partial | Yes | partial | `ui/pages/isolate.py:1907-1930`; `web/src/pages/IsolatePage.tsx:115-119` | Web always sends `fold_other_into_guitar`; only desktop exposes `best_effort`/`band_limited`/`full`. |
| Adaptive fold gain / spectral bleed gate | Yes | No | Yes | partial | `ui/pages/isolate.py:1920-1935`; `src/audio_to_tab/isolate.py:895-905` | Desktop-only experimental toggles. |
| Bass de-bleed / low-end restore | Yes | Yes | Yes | implemented | `ui/pages/isolate.py:904-977`; `web/src/pages/isolateSubmit.ts:29-40`; `src/audio_to_tab/isolate.py:868-895` | Web sends only these two repair fields. |
| Lead/Rhythm guitar split | No | No | Yes | partial | `backend/contracts.py:74-77`; `src/audio_to_tab/isolate.py:856-862` | API/engine opt-in; no UI on either surface. |
| Vocals & instrumental 2-stem | Yes | Yes | Yes | implemented | `ui/pages/isolate.py:1237-1284`; `web/src/pages/IsolatePage.tsx:80-95` | Hosted uses `htdemucs` + `two_stems=vocals`. |
| Track picker / emit only chosen stems | Yes | Yes | Yes | implemented | `ui/pages/isolate.py:1266-1284`; `web/src/pages/IsolatePage.tsx:438-500`; `src/audio_to_tab/isolate.py:884` | Unselected stems are discarded after separation. |
| Device / speed / quality selection | Yes | Partial | Yes | partial | `ui/pages/isolate.py:1606-1734`; `backend/capabilities.py:130-170`; `web/src/components/ProcessingModeSelect.tsx` | Desktop exposes CUDA/MPS/CPU and speed; hosted resolves device from the processing mode. |
| Lite vs Pro desktop controls | Yes | n/a | Yes | implemented | `ui/pages/isolate.py:336-341`; `ui/isolate_state.py:342`; `src/audio_to_tab/hardware.py:683` | Desktop Lite auto-picks speed/device and has its own guitar-engine resolver. |

## 3. Mixer and playback

| Feature | Desktop | Web | Engine | Status | Evidence (file:line) | Notes |
|---|---|---|---|---|---|---|
| Multi-stem synchronized playback | Yes | Yes | n/a | implemented | `ui/stem_mixer_component/frontend/src/main.ts:159-165`; `web/src/mixer/engine.ts:725-760` | Web Audio graph; one shared SoundTouch on the master bus. |
| Per-stem volume in dB | Yes | Yes | n/a | implemented | `ui/stem_mixer_component/frontend/src/main.ts:73-100`; `web/src/mixer/engine.ts:40-45` | −25…+25 dB on both. |
| Mute / solo | Yes | Yes | n/a | implemented | `ui/stem_mixer_component/frontend/src/main.ts:100`; `web/src/mixer/engine.ts:45-70` | Solo wins over mute on both. |
| Master volume | Yes | Yes | n/a | implemented | `ui/stem_mixer_component/frontend/src/main.ts:77-100`; `web/src/components/StemMixer.tsx:346` | Included in both gain calculations. |
| Stereo pan | Yes | Yes | n/a | implemented | `ui/stem_mixer_component/frontend/src/main.ts:159-163`; `web/src/components/StemMixer.tsx:162-164`; `web/src/mixer/pan.ts` | Equal-power law; desktop and web are separate implementations kept in sync by convention. |
| Mix presets (All/Karaoke/Acapella/Drums+Bass) | Yes | Yes | n/a | implemented | `ui/stem_mixer_component/frontend/src/main.ts:2313-2317`; `web/src/components/StemMixer.tsx:220-233` | Presets are solo maps, not level snapshots. |
| Waveform display | Yes | No | n/a | partial | `ui/stem_mixer_component/frontend/src/main.ts:1127-1140`; `ui/pages/isolate.py:676` | Desktop draws per-stem peaks; web has a seek slider only (`web/src/components/StemMixer.tsx:327-341`). |
| Seek / transport | Yes | Yes | n/a | implemented | `ui/stem_mixer_component/frontend/src/main.ts:237-245`; `web/src/components/StemMixer.tsx:327-341` | — |
| Video picture synced to audio | Yes | No | n/a | partial | `ui/stem_mixer_component/frontend/src/main.ts:202`; `ui/pages/isolate.py:1196-1217` | Local or YouTube video, with offset; hosted has no video pane. |
| Metronome click playback | Yes | Partial | Yes | partial | `ui/stem_mixer_component/frontend/src/main.ts:3152-3195`; `web/src/mixer/engine.ts:19` | Hosted only has a `metronome.wav` stem, default-muted, with no click controls. |
| Per-stem download | Yes | Yes | n/a | implemented | `ui/pages/isolate.py:1183-1184`; `web/src/components/StemMixer.tsx:566-570` | WAV per stem. |
| Save current mix | Yes | Yes | Yes | partial | `ui/pages/isolate.py:1023-1058`; `web/src/components/StemMixer.tsx:272-280`; `web/src/mixer/engine.ts:873-923` | Desktop now includes speed/key **and pan**; center export bit-identical. Web still includes pan but not speed/key (P2). |
| Media Session / OS transport | Yes | Yes | n/a | implemented | `ui/stem_mixer_component/frontend/src/main.ts:1724-1806`; `web/src/mixer/engine.ts:925-1004` | Both publish metadata and handlers. |
| Wake hooks (no soft-pause on hide) | Yes | Yes | n/a | implemented | `ui/stem_mixer_component/frontend/src/main.ts:202,875`; `web/src/mixer/engine.ts:289-291` | Kept in sync by hand between the two mixers. |
| Group / parent stem row | Yes | No | n/a | partial | `ui/stem_mixer_component/frontend/src/main.ts:2869-2915`; `ui/isolate_state.py:3628` | Only for re-separated `parent::child` stems; does not sum. Hosted mixer has no group row. |
| Spacebar play/pause | Yes | Unknown | n/a | partial | `ui/stem_mixer_component/frontend/src/main.ts:3538-3542` | Desktop global keydown; no equivalent found in the hosted mixer. |

## 4. Practice and timing tools

| Feature | Desktop | Web | Engine | Status | Evidence (file:line) | Notes |
|---|---|---|---|---|---|---|
| Speed change without pitch change | Yes | Yes | n/a | implemented | `ui/stem_mixer_component/frontend/src/main.ts:368-384`; `web/src/components/StemMixer.tsx:390`; `web/src/mixer/practice.ts` | Shared SoundTouch worklet approach on both; independent rate. |
| Pitch/key shift in semitones | Yes | Yes | n/a | implemented | `ui/stem_mixer_component/frontend/src/main.ts:368-373`; `web/src/components/StemMixer.tsx:414-420` | Transposition only; no key detection. |
| Speed/key persistence | Yes | Yes | n/a | implemented | `ui/stem_mixer_component/frontend/src/main.ts:1827-1844`; `web/src/components/StemMixer.tsx:238-241` | Desktop uses session storage; web saves practice settings. |
| Tempo/beat tracking | Yes | Yes | Yes | implemented | `src/audio_to_tab/metronome.py:158-169`; `src/audio_to_tab/metronome.py:1112`; `src/audio_to_tab/analysis.py` | Tempo curve + `click_times_1x`; desktop Home/practice shows BPM. Web still has no readout. |
| Metronome accent | Yes | No | Yes | partial | `ui/stem_mixer_component/frontend/src/main.ts:3188-3190`; `src/audio_to_tab/metronome.py:96-100`; `src/audio_to_tab/isolate.py:905` | Desktop toolbar chip; hosted has no control. |
| Metronome rate (subdivision) | Yes | No | Yes | partial | `ui/stem_mixer_component/frontend/src/main.ts:3180-3187`; `src/audio_to_tab/metronome.py:97-99`; `src/audio_to_tab/isolate.py:906` | Desktop only. |
| Metronome sound selection | Yes | No | Yes | partial | `ui/stem_mixer_component/frontend/src/main.ts:3190-3194`; `src/audio_to_tab/metronome.py:99`; `src/audio_to_tab/isolate.py:907` | Desktop only. |
| Smart vs steady follow | Yes | No | Yes | partial | `ui/stem_mixer_component/frontend/src/main.ts:3185-3187`; `src/audio_to_tab/metronome.py:100` | Smart follows tempo changes; steady is one tempo. |
| Rebake metronome without re-tracking | Yes | No | Yes | partial | `ui/pages/isolate.py:1105-1130`; `src/audio_to_tab/metronome.py:1670-1678` | Desktop re-renders from the stored grid; no hosted equivalent. |
| Count-in | No | Yes (1/2 bars) | No | implemented | `ui/stem_mixer_component/frontend/src/main.ts`; practice panel | Added in Phase 1. Desktop only; web has no count-in. |
| A/B or section loop | No | Yes (region + section) | Partial (whole buffer) | implemented | `ui/stem_mixer_component/frontend/src/main.ts`; practice panel | Desktop region loop and section loop added in Phase 1. Hosted still loops the whole buffer only. |

## 5. Transcription, tab, MIDI, PDF

| Feature | Desktop | Web | Engine | Status | Evidence (file:line) | Notes |
|---|---|---|---|---|---|---|
| Audio → MIDI transcription | Yes | Yes | Yes | implemented | `src/audio_to_tab/pipeline.py:246`; `ui/pages/tab_pdf.py:470-477`; `web/src/pages/TabPage.tsx:140-143` | Basic Pitch-based; MIDI file is downloadable on both. |
| Guitar tab generation | Yes | Yes | Yes | implemented | `src/audio_to_tab/tab_generate.py:35-41`; `ui/pages/tab_pdf.py:456-463`; `web/src/pages/TabPage.tsx:133-139` | Guitar only; standard tuning, max fret 15. |
| Tab PDF | Yes | Yes | Yes | implemented | `src/audio_to_tab/pdf_render.py:120-170`; `ui/pages/tab_pdf.py:456`; `web/src/pages/TabPage.tsx:133-139` | Structured PDF with tuning/tempo footer. |
| ASCII tab (.tab) download | Yes | No | Yes | partial | `ui/pages/tab_pdf.py:464-469`; `backend/main.py:121` | Hosted artifact type exists but the Tab page does not link it. |
| Tempo override for transcription | Yes | No | Yes | partial | `ui/pages/tab_pdf.py:294-300`; `src/audio_to_tab/pipeline.py:72` | Desktop Pro advanced setting only. |
| Onset/frame threshold controls | Yes | No | Yes | partial | `ui/pages/tab_pdf.py:301-303`; `backend/contracts.py:53-54` | Desktop Pro only; hosted sends defaults. |
| Mix-aware filtering toggle | Yes | Partial | Yes | partial | `ui/pages/tab_pdf.py:289-292`; `backend/contracts.py:51` | Desktop Pro toggle; hosted always sends `true` by default. |
| Max-duration limit for tab job | Yes | Yes | Yes | implemented | `ui/pages/tab_pdf.py:162-170`; `backend/contracts.py:50` | Desktop exposes seconds; hosted defaults to 90. |
| Tab accuracy warning | Yes | Yes | n/a | implemented | `ui/pages/tab_pdf.py:444`; `web/src/pages/TabPage.tsx:54-61` | Both call the output a demo / not finished. |
| Drum or bass tab | No | No | No | absent | `src/audio_to_tab/pipeline.py:246-289` | Pipeline renders guitar tab only. |
| Chord-name detection | Yes | Yes (draft) | No | implemented (draft) | `src/audio_to_tab/chords.py`; `analysis.py` | CQT chroma + templates + Viterbi; 145 draft chords on the real Waltz run. Accuracy not certified; UI labels “Draft chords.” |

## 6. Export, files, projects and persistence

| Feature | Desktop | Web | Engine | Status | Evidence (file:line) | Notes |
|---|---|---|---|---|---|---|
| Export mix WAV | Yes | Yes | Yes | implemented | `ui/pages/isolate.py:3656-3660`; `web/src/components/StemMixer.tsx:272-280`; `web/src/mixer/engine.ts:1039` | Desktop writes `current_mix.wav`; web downloads a rendered WAV. |
| Export all stems | Yes | Yes | n/a | implemented | `ui/pages/isolate.py:3747-3753`; `backend/jobs/runner.py:212-218` | Desktop saves a folder; hosted builds `stems.zip`. |
| Save to chosen folder / reveal in OS | Yes | No | n/a | partial | `ui/desktop_export.py:1`; `ui/pages/isolate.py:3731` | Native file manager integration is desktop-only. |
| Per-user job history | Yes | Partial | n/a | partial | `ui/pages/isolate.py:3561`; `backend/main.py:461`; `web/src/api.ts:114` | Desktop has the Queue plus the Home library/recents; hosted has `GET /v1/jobs` but no history page. |
| Resume an old project | Yes | No | No | partial | `ui/isolate_state.py:2404`; `ui/project.py`; `web/src/App.tsx:105-114` | Desktop now writes `project.json` and can reopen a saved run; hosted routes expose no project/reopen screen. |
| Restore last-used settings | Yes | Partial | n/a | partial | `ui/isolate_state.py:2619-2662`; `web/src/components/StemMixer.tsx:238-241` | Desktop restores isolate settings; web restores only practice speed/key. |
| Cloud project library | No | No | No | absent | `backend/main.py:461-478` | Jobs are listed individually; there is no library/project model. |
| Signed artifact URLs | n/a | Yes | n/a | implemented | `backend/main.py:544-579` | Token + user id check; no public share URL. |
| Open-with / file association | Yes | No | n/a | partial | `ui/opened_audio.py:68-116`; `packaging/launcher.py:1232-1247`; `packaging/AudioTools.iss:111` | OS open-with lands in a new Home tab. |

## 7. Accounts, access, collaboration, billing

| Feature | Desktop | Web | Engine | Status | Evidence (file:line) | Notes |
|---|---|---|---|---|---|---|
| Account required | No | No | n/a | implemented | `backend/main.py:236-244`; `backend/main.py:216` | Hosted mints anonymous sessions when auth is off; demo mode uses per-tab anonymous JWTs. |
| Login / session / logout | n/a | Yes | n/a | implemented | `backend/main.py:216-275`; `web/src/pages/LoginPage.tsx`; `web/src/App.tsx:106-114` | Login is routed; no self-serve registration endpoint. |
| Multi-user data isolation | n/a | Yes | n/a | implemented | `backend/main.py:480-490`; `backend/main.py:549` | Jobs and artifacts are checked against `user_id`. |
| Account deletion | n/a | Yes | n/a | implemented | `backend/main.py:280`; `backend/account.py:15`; `web/src/pages/SettingsPage.tsx:66` | Admin accounts cannot self-delete. |
| Admin user management UI | n/a | No | n/a | absent | `backend/main.py:78` | Only bootstrap admin creation; no user-admin screens/endpoints. |
| Share links / public mixes | No | No | n/a | absent | — | No share token, public page, or embed. |
| Real-time collaboration | No | No | n/a | absent | — | No presence, comments, or multi-editor state. |
| Billing / subscription / plans | No | No | n/a | absent | — | No Stripe/checkout/subscription code found. |

## 8. Moises-adjacent AI extras

| Feature | Desktop | Web | Engine | Status | Evidence (file:line) | Notes |
|---|---|---|---|---|---|---|
| Chord detection / chord chart | Yes | Yes (draft) | No | implemented (draft) | `src/audio_to_tab/chords.py`; practice panel | Draft chords in the player; accuracy not certified. |
| Lyrics / transcription | Yes | Partial (dev) | No | implemented (dev) | `src/audio_to_tab/lyrics.py`; practice panel | `faster-whisper` small, pinned local model; real Japanese excerpt produced 7 lines with word timestamps. Packaged freeze deferred to Phase 1.6. |
| Key detection | Yes | Yes | No | implemented | `src/audio_to_tab/key.py`; `analysis.py` | Real Waltz: Dm high confidence; Home shows the key. |
| BPM detection / display | Partial | Yes | Yes | implemented | `src/audio_to_tab/analysis.py`; `metronome.py` | Desktop Home/practice shows BPM; hosted still has no readout. |
| Drum transcription / drum tab | No | No | No | absent | — | Only stem separation for drums. |
| Mastering / loudness matching | No | No | No | absent | — | Mix export has a limiter, not mastering. |
| Voice conversion / vocal tuning | No | No | No | absent | — | No pitch correction or timbre conversion. |
| Live input / recording | No | No | No | absent | — | No capture, device enumeration, or record-arm code. |
| VST / plugin hosting | No | No | No | absent | — | No plugin scanner or host. |
| AI mix assistant / auto-mix | No | No | No | absent | — | Presets are fixed solo maps, not generated mixes. |
| Stem-aware guitar transcription | Yes | Yes | Yes | implemented | `src/audio_to_tab/pipeline.py:246-289`; `ui/pages/tab_pdf.py:350-360` | Transcription runs on the guitar stem when separation is on. |

## 9. Platform, performance, packaging, deployment

| Feature | Desktop | Web | Engine | Status | Evidence (file:line) | Notes |
|---|---|---|---|---|---|---|
| Native desktop window | Yes | n/a | n/a | implemented | `packaging/launcher.py:1001-1008,1092` | pywebview window on Windows/macOS; browser fallback only on unsupported platforms. |
| Desktop installers | Yes | n/a | n/a | implemented | `.github/workflows/desktop-release.yml:46-64`; `packaging/make_app.sh`; `packaging/AudioTools.iss` | Windows CPU/CUDA/both and macOS arm64/x64, unsigned. |
| Offline desktop use | Yes | No | n/a | partial | `packaging/launcher.py:797-817` | Local Streamlit + models on disk; first model download needs internet. |
| Hosted deployment stack | n/a | Yes | n/a | implemented | `docker-compose.yml:2-74`; `Dockerfile` | Caddy + FastAPI + Postgres + Redis + MinIO + arq worker. |
| GPU / Apple-silicon acceleration | Yes | Yes | Yes | implemented | `src/audio_to_tab/hardware.py:416-437`; `backend/capabilities.py:94-107` | CUDA, MPS, CPU; device list is GPU-first. |
| MPS RAM gate (≥12 GB) | Yes | Yes | Yes | implemented | `src/audio_to_tab/hardware.py:27,416-437`; `tests/test_hardware.py` | Below 12 GB, MPS is not offered. |
| Serial isolation jobs / RAM pressure | Yes | Partial | n/a | partial | `ui/isolate_jobs.py`; `src/audio_to_tab/hardware.py:24`; `backend/capabilities.py:112` | Desktop runs one isolate job at a time; hosted can run multi-flight unless configured. |
| Duration caps | No hard cap | Yes | n/a | partial | `backend/capabilities.py:36-38,144-153`; `ui/pages/isolate.py:2236` | Hosted: lite 60 s, fast CPU 90 s, balanced/high up to `max_job_duration_sec` (300 s default). Desktop does not clamp. |
| Edition resolution (`cpu`/`cuda`/`both`) | Yes | n/a | Yes | implemented | `src/audio_to_tab/edition.py`; `packaging/audio_tools.spec:143-155`; `.github/workflows/desktop-release.yml:170` | Release writes `edition.txt` into the freeze and asserts it matches the env var. |
| Theme / appearance | Yes | Yes | n/a | implemented | `ui/pages/settings.py:10-45`; `web/src/components/ThemeSelector.tsx` | Both have theme selection; web can import/export a theme JSON. |
| Internationalization | No | No | No | absent | — | No locale files or language switch. |

## Known contradictions / stale docs

- **Tab-strip actions are implemented in state but not wired.** `duplicate_open_mix_tab`
  (`ui/isolate_state.py:1994`), `close_other_open_mix_tabs` (`:1952`), and
  `close_right_open_mix_tabs` (`:1975`) exist and are unit-tested, but `ui/pages/isolate.py`
  imports only `move_open_mix_tab` (`:101-107`, used at `:4436`). The iframe emits only
  `home|plus|focus|close|reorder` (`ui/mix_tabs_component/frontend/src/main.ts:282-284`), so
  duplicate / close-others / close-right are unreachable from the UI.
- **Docs claim those actions ship.** `docs/research/moises/README.md:17` says "Desktop Isolate
  now has duplicate, close others, close to the right"; `REFERENCE.md:245` and
  `COMPETITIVE-INSPIRATION-PLAN.md:151` repeat it. `COMPETITIVE-INSPIRATION-PLAN.md:36`
  correctly says only `home`, `plus`, `close` exist — the same document contradicts itself.
- **YouTube job route typo — resolved 2026-10-20.** `backend/main.py:343` now reads
  `settings.allow_youtube` (`backend/config.py:44`). Desktop YouTube ingest does not use this route.
- **Test count in `AGENTS.md` was stale.** It said 1026 tests before the 2026-10-20 update; the
  Phase 1 gate is **1030 passed, 1 skipped**. `AGENTS.md` now says 1030. Keep it in sync when adding
  tests.
- **TypeScript does not currently typecheck.** `cd web && npx tsc --noEmit` reports 8 errors:
  missing Node types in `src/App.test.ts` (3), impossible `AudioContextState` comparison and
  `playsInline` on `HTMLAudioElement` in `src/mixer/engine.ts` (176, 197, 509), and two unused
  symbols (256, 664). CI does not run `tsc`, so this is invisible in green builds.
- **Mix export surfaces still bake different state.** Desktop `_build_current_mix`
  (`ui/pages/isolate.py:1023-1058`) now applies speed/key **and pan**; hosted `bounceMix`
  (`web/src/mixer/engine.ts:873-923`) applies pan and gains but not speed/key. The web export still
  differs from what the user hears when speed/key are active; P2 must fix it or warn visibly.
- **Metronome parity is overstated if read from the shared engine.** The engine and desktop
  have accent/rate/sound/follow and rebake (`src/audio_to_tab/metronome.py`,
  `ui/pages/isolate.py:1105-1130`); hosted only exposes `metronome.wav` as a default-muted stem
  (`web/src/mixer/engine.ts:19`). No hosted click controls exist.
- **`docs/ui-issues.md:26` I-602** still describes an "Advanced options" `<details>` and a
  `readAdvancedOpen` helper in `web/src/pages/IsolatePage.tsx`; neither symbol exists in the
  current file. The row is marked `implemented-in-code`, so treat it as history rather than a
  description of today's UI.
- **`docs/ui-issues.md:24` I-600 and `:28` I-604** describe a missing Tab PDF warning and a
  missing file-only note; both are present now (`web/src/pages/TabPage.tsx:54-61`,
  `web/src/trackOptions.ts:45`). They are resolved rows whose prose still reads as open gaps.

## 10. Verification notes and qualifications

These are the places where a status word in the tables above would mislead an implementer. The code
was checked again on 2026-10-19 while writing this section.

1. **"Resume an old project" is partly present.** Desktop Home lists local isolate runs and
   `open_saved_run()` reopens the mixer from the run directory (`ui/pages/home.py:115-124`,
   `ui/common.py:163-188`), and Phase 1 added a `project.json` manifest (`ui/project.py`). What is
   still missing is a cross-device/cloud project model and a portable export/import. Treat desktop as
   **partial/implemented locally**, not absent.
2. **Tab-strip duplicate / close-others / close-right are unreachable, not shipped.** The state
   helpers exist and are tested (`ui/isolate_state.py:1952`, `:1975`, `:1994`), but
   `ui/pages/isolate.py` imports only `move_open_mix_tab` (`:107`), and the iframe emits only
   `home`, `plus`, `focus`, `close`, and `reorder` (`ui/mix_tabs_component/frontend/src/main.ts:270-285`).
   Do not claim these actions work. Either wire them or leave them out of the first release.
3. **Save-what-you-hear is fixed on desktop, still false on web.** Desktop `_build_current_mix`
   (`ui/pages/isolate.py:1023-1058`) now applies speed/key and pan; center export is bit-identical and
   hard L/R is tested. Hosted `bounceMix` (`web/src/mixer/engine.ts:873-923`) applies pan/gain but not
   speed/key. Fix web speed/key in Phase 2 with a visible “exports at original speed/key” warning
   until then.
4. **The hosted YouTube typo is fixed (2026-10-20).** `backend/main.py:343` now reads
   `settings.allow_youtube`; `backend/config.py:44` defines it. Do not expand hosted YouTube in
   Phase 1/1.5.
5. **`web/` does not typecheck today.** `cd web && npx tsc --noEmit` reports 8 errors in
   `App.test.ts` and `mixer/engine.ts` (missing Node types, an impossible `AudioContextState`
   comparison, `playsInline`, and two unused symbols). CI does not run `tsc`. Fix these before
   touching the web mixer, and keep the check green after.
6. **BPM/beat tracking, key, chords, sections, and lyrics now have an analysis layer.** The engine
   writes `analysis.json`; the desktop Home/practice panel displays BPM, key, chords, sections,
   lyrics, and tab. Web display remains Phase 2. The analysis is a draft, not a certified model; see
   `01` §17 and `06` §Verification.
7. **Count-in and A/B loop are implemented on desktop.** The region loop and section loop work in the
   practice player; count-in is a 1/2-bar control. Hosted still has only whole-buffer looping. The
   earlier "genuinely absent" note is the 2026-10-19 baseline.
8. **Metronome parity is desktop-only.** Desktop has accent, rate, sound, smart/steady follow, and
   rebake; hosted only has a default-muted `metronome.wav` stem. Do not describe the hosted mixer as
   having metronome controls.
9. **The mixer is already ahead of Moises Play in several places.** Desktop/web have speed and key,
   pan, group rows (desktop), a synced picture (desktop), and a save-on-demand mix. Moises Play has
   volume, mute/solo, speed, pitch, smart metronome, and no visible pan/EQ/comp. Do not rebuild these
   controls; extend the existing mixer and fix the export mismatch.
10. **The library is local, not cloud.** Home has recents, a searchable local library, and a queue;
    the hosted side has per-user jobs but no history page. There is no cross-device sync, share link,
    collaboration, billing, or subscription code. Those are Phase 3+ decisions, not Phase 1 blockers.
11. **The UI is functional but not crafted.** The current Home at 1440 is a 300px sidebar plus a
    980px content block; at 1024 the block still starts at x=380 and clips. All text is amber, the
    library is a stack of 74px buttons, and Streamlit's developer promo overlays the page. This is the
    Phase 1.5 target, not a feature gap. See `10` §2–3.

## 11. What this means for the plan

- **The engine is not the gap anymore.** Separation, guitar refinement, metronome, tab generation,
  chord/key/BPM/section/lyrics analysis, and PDF rendering exist. Phase 1.5 closes the **surface
  craft** gap: hierarchy, Home library, shell, player composition, states, 1024/900, accessibility.
- **Do not rebuild the mixer.** Extend the existing iframe; keep the stem rows, pan law, solo rule,
  wake hooks, and save-on-save contract. Phase 1.5 may recompose the chrome, not the audio graph.
- **Keep save-what-you-hear honest.** Desktop now bakes speed/key/pan; web still omits speed/key. Do
  not add more export controls until the web warning/fix lands in Phase 2.
- **Analysis is an artifact, not a live computation.** Run it once after separation, cache it in the
  run directory with a schema version and model versions, and let the player read it. Never run
  Whisper or chord inference on every Streamlit rerun.
- **Tab is already built; integrate it.** The tab PDF pipeline exists on both surfaces. Phase 1
  reuses it on the isolated guitar stem and shows the tab in the player; Phase 1.5 makes the measure
  view legible, not a second transcription stack.
