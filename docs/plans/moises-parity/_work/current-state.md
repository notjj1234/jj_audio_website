# Current-state feature matrix

Inventory only. No recommendations, no roadmap. Evidence is `path:line` at the time of writing
(2026-10-19). "Desktop" = Streamlit product under `ui/`, packaged with `packaging/launcher.py`.
"Web" = React SPA under `web/` + FastAPI under `backend/`. "Engine" = shared
`src/audio_to_tab/`.

Status legend: `implemented` = works end-to-end on at least one shipped surface;
`partial` = present but limited, surface-specific, engine-only, or not wired to a UI;
`absent` = no code path found; `unknown` = not confirmable from source.

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
| Full-file processing | Yes | Partial | Yes | partial | `ui/pages/isolate.py:2236-2263`; `web/src/pages/IsolatePage.tsx:263-291` | Desktop processes the whole file and warns on Lite; hosted clamps to the mode cap and shows a trim notice. |
| Carry audio from Tab PDF into isolation | Yes | No | n/a | partial | `ui/pages/tab_pdf.py:485-493`; `ui/pages/isolate.py:1484` | Streamlit page-switch carry-over; no hosted equivalent. |
| YouTube URL accepted by job API | n/a | Partial | n/a | partial | `backend/main.py:341-343`; `backend/config.py:44` | Route reads `settings.allow_youtssube` (typo), so any `youtube_url` job raises `AttributeError`. See contradictions. |

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
| Save current mix | Yes | Yes | Yes | partial | `ui/pages/isolate.py:1023-1058`; `web/src/components/StemMixer.tsx:272-280`; `web/src/mixer/engine.ts:873-923` | Both render a WAV. Desktop includes speed/key but not pan; web includes pan but not speed/key. |
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
| Tempo/beat tracking | Yes | Yes | Yes | implemented | `src/audio_to_tab/metronome.py:158-169`; `src/audio_to_tab/metronome.py:1112` | Tempo curve + `click_times_1x`; no BPM readout in either mixer. |
| Metronome accent | Yes | No | Yes | partial | `ui/stem_mixer_component/frontend/src/main.ts:3188-3190`; `src/audio_to_tab/metronome.py:96-100`; `src/audio_to_tab/isolate.py:905` | Desktop toolbar chip; hosted has no control. |
| Metronome rate (subdivision) | Yes | No | Yes | partial | `ui/stem_mixer_component/frontend/src/main.ts:3180-3187`; `src/audio_to_tab/metronome.py:97-99`; `src/audio_to_tab/isolate.py:906` | Desktop only. |
| Metronome sound selection | Yes | No | Yes | partial | `ui/stem_mixer_component/frontend/src/main.ts:3190-3194`; `src/audio_to_tab/metronome.py:99`; `src/audio_to_tab/isolate.py:907` | Desktop only. |
| Smart vs steady follow | Yes | No | Yes | partial | `ui/stem_mixer_component/frontend/src/main.ts:3185-3187`; `src/audio_to_tab/metronome.py:100` | Smart follows tempo changes; steady is one tempo. |
| Rebake metronome without re-tracking | Yes | No | Yes | partial | `ui/pages/isolate.py:1105-1130`; `src/audio_to_tab/metronome.py:1670-1678` | Desktop re-renders from the stored grid; no hosted equivalent. |
| Count-in | No | No | No | absent | `ui/stem_mixer_component/frontend/src/main.ts`; `web/src/components/StemMixer.tsx` | No count-in control or click pre-roll found in either mixer. |
| A/B or section loop | No | No | No | absent | `ui/stem_mixer_component/frontend/src/main.ts:118`; `web/src/mixer/engine.ts:195` | Only whole-buffer audio-element looping exists. |

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
| Chord-name detection | No | No | No | absent | `src/audio_to_tab/tab_generate.py:47-54` | Simultaneous notes are grouped for guitar voicing; no chord labels. |

## 6. Export, files, projects and persistence

| Feature | Desktop | Web | Engine | Status | Evidence (file:line) | Notes |
|---|---|---|---|---|---|---|
| Export mix WAV | Yes | Yes | Yes | implemented | `ui/pages/isolate.py:3656-3660`; `web/src/components/StemMixer.tsx:272-280`; `web/src/mixer/engine.ts:1039` | Desktop writes `current_mix.wav`; web downloads a rendered WAV. |
| Export all stems | Yes | Yes | n/a | implemented | `ui/pages/isolate.py:3747-3753`; `backend/jobs/runner.py:212-218` | Desktop saves a folder; hosted builds `stems.zip`. |
| Save to chosen folder / reveal in OS | Yes | No | n/a | partial | `ui/desktop_export.py:1`; `ui/pages/isolate.py:3731` | Native file manager integration is desktop-only. |
| Per-user job history | Yes | Partial | n/a | partial | `ui/pages/isolate.py:3561`; `backend/main.py:461`; `web/src/api.ts:114` | Desktop has a floating Queue; hosted has `GET /v1/jobs` but no history page in `web/src/App.tsx:105-114`. |
| Resume an old project | No | No | No | absent | `ui/isolate_state.py:2404`; `web/src/App.tsx:105-114` | Desktop state is session-scoped; hosted routes expose no project/reopen screen. |
| Restore last-used settings | Yes | Partial | n/a | partial | `ui/isolate_state.py:2619-2662`; `web/src/components/StemMixer.tsx:238-241` | Desktop restores isolate settings; web restores only practice speed/key. |
| Cloud project library | No | No | No | absent | `backend/main.py:461-478` | Jobs are listed individually; there is no library/project model. |
| Signed artifact URLs | n/a | Yes | n/a | implemented | `backend/main.py:544-579` | Token + user id check; no public share URL. |
| Open-with / file association | Yes | No | n/a | partial | `ui/opened_audio.py:68-116`; `packaging/launcher.py:1232-1247`; `packaging/AudioTools.iss:111` | OS open-with lands in a new Home tab. |

## 7. Accounts, access, collaboration, billing

| Feature | Desktop | Web | Engine | Status | Evidence (file:line) | Notes |
|---|---|---|---|---|---|---|
| No-account / anonymous use | Yes | Yes | n/a | implemented | `backend/main.py:236-244`; `backend/main.py:216` | Desktop has no accounts; hosted mints anonymous sessions when auth is off, with per-tab anonymous JWTs in demo mode. |
| Login / session / logout | n/a | Yes | n/a | implemented | `backend/main.py:216-275`; `web/src/pages/LoginPage.tsx`; `web/src/App.tsx:106-114` | Login is routed; no self-serve registration endpoint. |
| Multi-user data isolation | n/a | Yes | n/a | implemented | `backend/main.py:480-490`; `backend/main.py:549` | Jobs and artifacts are checked against `user_id`. |
| Account deletion | n/a | Yes | n/a | implemented | `backend/main.py:280`; `backend/account.py:15`; `web/src/pages/SettingsPage.tsx:66` | Admin accounts cannot self-delete. |
| Admin user management UI | n/a | No | n/a | absent | `backend/main.py:78` | Only bootstrap admin creation; no user-admin screens/endpoints. |
| Share links / public mixes | No | No | n/a | absent | `backend/main.py:544-579` | Artifact access is signed and user-scoped; no public token or share page. |
| Real-time collaboration | No | No | n/a | absent | `web/src/App.tsx:105-114` | No presence, comments, or multi-editor state. |
| Billing / subscription / plans | No | No | n/a | absent | `backend/main.py:206-297` | Route list has auth/jobs/artifacts only; no Stripe or checkout code. |

## 8. Moises-adjacent AI extras

| Feature | Desktop | Web | Engine | Status | Evidence (file:line) | Notes |
|---|---|---|---|---|---|---|
| Chord detection / chord chart | No | No | No | absent | `src/audio_to_tab/tab_generate.py:47-54` | Simultaneous notes are grouped for tab voicing; no chord-name estimator. |
| Lyrics / transcription | No | No | No | absent | `src/audio_to_tab/transcribe.py:1` | Basic Pitch note transcription only; no speech-to-text or lyric alignment. |
| Key detection | No | No | No | absent | `src/audio_to_tab/metronome.py:158-169` | Engine tracks tempo/beats, not key; no detected-key display. |
| BPM detection / display | Partial | Partial | Yes | partial | `src/audio_to_tab/metronome.py:158-169` | Beat grid is computed; neither UI shows a BPM number. |
| Drum transcription / drum tab | No | No | No | absent | `src/audio_to_tab/pipeline.py:246-289` | Pipeline transcribes guitar pitch; drums are a separation stem only. |
| Mastering / loudness matching | No | No | No | absent | `src/audio_to_tab/mixer.py` | Export mixes stems and applies gain; no mastering or loudness target. |
| Voice conversion / vocal tuning | No | No | No | absent | `src/audio_to_tab/isolate.py:905` | Separation/repair stages only; no pitch correction or timbre conversion. |
| Live input / recording | No | No | No | absent | `ui/pages/isolate.py:2026` | Input path is file upload, video, or YouTube; no capture or record-arm. |
| VST / plugin hosting | No | No | No | absent | `packaging/audio_tools.spec` | No plugin scanner or host in the desktop freeze. |
| AI mix assistant / auto-mix | No | No | No | absent | `ui/stem_mixer_component/frontend/src/main.ts:2313-2317` | Presets are fixed solo maps, not generated mixes. |
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
| Internationalization | No | No | No | absent | `web/src/App.tsx:105-114`; `ui/app.py:1` | No locale files or language switch on either surface. |

## Known contradictions / stale docs

- **Tab-strip actions are implemented in state but not wired.** `duplicate_open_mix_tab`
  (`ui/isolate_state.py:1994`), `close_other_open_mix_tabs` (`:1952`), and
  `close_right_open_mix_tabs` (`:1975`) exist and are unit-tested, but `ui/pages/isolate.py`
  imports only `move_open_mix_tab` (`:101-107`, used at `:4436`). The iframe emits only
  `home|plus|focus|close|reorder` (`ui/mix_tabs_component/frontend/src/main.ts:282-284`), so
  duplicate / close-others / close-right are unreachable from the UI.
- **Docs claim those actions ship.** `docs/research/moises/README.md:17` says "Desktop Isolate
  now has duplicate, close others, close to the right"; `REFERENCE.md:245` and
  `COMPETITIVE-INSPIRATION-PLAN.md:151` repeat it, and `COMPETITIVE-INSPIRATION-PLAN.md:97`
  lists them as a completed edit. `REFERENCE.md:209` still calls them a "Real gap", and
  `COMPETITIVE-INSPIRATION-PLAN.md:36` correctly says only `home`, `plus`, `close` exist —
  the same documents contradict themselves.
- **YouTube job route has a typo.** `backend/main.py:343` reads
  `settings.allow_youtssube`; `backend/config.py:44` defines `allow_youtube`. Any job request
  carrying `youtube_url` raises `AttributeError` instead of the intended 403.
- **Test count in `AGENTS.md` is stale.** It says 809 tests (`AGENTS.md:46`); current
  collection is 882 (`.venv311/bin/python -m pytest tests/ --collect-only -q`).
- **TypeScript does not currently typecheck.** `cd web && npx tsc --noEmit` reports 8 errors:
  missing Node types in `src/App.test.ts` (3), impossible `AudioContextState` comparison and
  `playsInline` on `HTMLAudioElement` in `src/mixer/engine.ts` (176, 197, 509), and two unused
  symbols (256, 664). CI does not run `tsc`, so this is invisible in green builds.
- **Mix export surfaces bake different state.** Desktop `_build_current_mix`
  (`ui/pages/isolate.py:1023-1058`) applies speed/key but has no pan parameter; hosted
  `bounceMix` (`web/src/mixer/engine.ts:873-923`) applies pan and gains but not speed/key.
  Both therefore export a mix that differs from what the user hears when those controls are
  active.
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
