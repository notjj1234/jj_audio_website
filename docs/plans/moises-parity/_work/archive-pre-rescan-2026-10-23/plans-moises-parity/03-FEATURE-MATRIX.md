# Feature matrix — Moises vs Audio Tools

**Purpose:** one row per user-facing capability, so nothing is silently dropped. The Moises column is
the competitor surface; the Desktop/Web columns are what this repo has today. `Decision` is a build
decision, not a judgement of importance.

**Sources:** `01-MOISES-SURFACE.md` (M) and `02-CURRENT-STATE.md` (C). Section references point at
those files. Runtime observations are from Moises 2.0.18 on 2026-10-19.

**Decision key**

| Decision | Meaning |
|---|---|
| **Defend** | We already match or beat Moises. Keep it; do not rebuild it. |
| **Match** | A real parity gap. Close it in the phase shown. |
| **Differentiate** | A wedge Moises cannot easily copy. Invest here. |
| **Defer** | Real feature, deliberately later. Not a Phase 1 blocker. |
| **Cut** | Not our product. Do not build it even later. |

**Phase key:** `P1` = Song Workbench (first release) · `P1.5` = desktop UI craft · `P1.6` = desktop
hardening/packaging · `P2` = practice parity/polish · `P3` = Studio / cloud / platform · `Never` = not
our product.

## Scoreboard (rough, from the rows below)

- **Defend now:** local/offline processing, YouTube ingest, pan, speed/key, synced picture, guitar
  separation, tab engine, export formats, no quotas, privacy, group rows, media keys. Moises is
  cloud-first; we are local-first. That is the structural advantage.
- **Closed in P1 (desktop):** BPM/key/chords/sections/lyrics display, count-in, A/B loop, tab inside
  the player, project manifest, save-what-you-hear export parity. The feature gap is no longer the
  main gap; the surface is. See `06` §Verification.
- **P1.5:** Home parity only: 240px rail, 100px action cards, 150×210 recents, 56px Files table, Home-scoped neutrals. Measurements are `10` §13. Player composition waits for P1.6.
- **P1.6:** installer/first-run model download, packaged lyrics decision, failure states, 8 GB Mac
  regression.
- **P2:** chord/lyric/section editing, capo/tuning, chord-chart export, setlists, filters/sort, web
  parity, batch, localization, deeper accessibility.
- **P3:** Studio DAW, stem/sample generation, voice conversion, mastering, Auto Mix, collaboration,
  mobile/TV, VST/AU/AAX, Moises Live-style system audio, cloud sync.
- **Never:** artist-name prompting, full text-to-song, social feed/marketplace, DRM streaming
  imports, watermarks, B2B DAW integrations. They do not serve the guitar-practice job.

---

## 1. Ingest and source

| # | Capability | Moises | Desktop | Web | Decision | Phase | Notes |
|---|---|---|---|---|---|---|---|
| 1 | Local audio upload | Yes (all) | Yes | Yes | Defend | P1 | Desktop 500 MB; web 50 MB (M §17; C §1). Local processing is the advantage. |
| 2 | Local video import + picture | Limited / not in Play | Yes | No | Defend | P1 | Desktop extracts audio and syncs local/YouTube picture (C §3). Moises Play has no picture pane. |
| 3 | YouTube search + URL | Rejects streaming links | Yes | No | Differentiate | P1 | Desktop search/download; hosted route fixed 2026-10-20 (`allow_youtube`) but hosted YouTube remains out of scope (C §10). |
| 4 | YouTube to MP3 save-only | No | Yes | No | Defend | P1 | Separate desktop page; not part of separation. |
| 5 | OS open-with / drag-drop | Yes (desktop document types) | Yes | No | Match | P1 | Desktop lands in a new Home tab (C §6). Keep it. |
| 6 | Section trim before separation | Yes (trim/select) | Yes | Yes | Match | P1 | Region picker on both (C §1). |
| 7 | Batch upload | Yes (20 files) | No | No | Defer | P2 | Serial desktop jobs make this a queue feature, not a parallel one. |
| 8 | Direct URL import (non-YouTube) | Yes (public URLs) | No | No | Defer | P2 | YouTube covers the common case; add generic URL later. |
| 9 | Cloud picker (Drive/iCloud) | Yes (mobile) | No | No | Defer | P3 | OS file picker covers local files; cloud is a sync feature. |
| 10 | Streaming-service URLs | Rejected (DRM) | Rejected | Rejected | Cut | Never | Do not build a DRM workaround. |

## 2. Separation and guitars

| # | Capability | Moises | Desktop | Web | Decision | Phase | Notes |
|---|---|---|---|---|---|---|---|
| 11 | 2-stem vocals/instrumental | Yes | Yes | Yes | Defend | P1 | Already. |
| 12 | 4-stem vocals/drums/bass/other | Yes | Yes | Yes | Defend | P1 | Already. |
| 13 | 6-stem guitar/piano | Yes | Yes | Yes | Defend | P1 | Piano is heavy-bleed on both (C §2). |
| 14 | Guitar specialist / refine / ensemble | Yes (guitar sub-stems) | Yes | Partial | Defend | P1 | RoFormer, MelBand refine, ensemble, fold, low-end repair (C §2). This is our strongest engine area. |
| 15 | Acoustic/electric/lead/rhythm guitar splits | Yes (Pro) | Engine only | No | Differentiate | P2 | `lead_rhythm.py` exists but no UI; acoustic/electric are not separate models. Pair with tab. |
| 16 | 27-stem catalogue (kick/snare/toms/hats/cymbals, backing/female/male vocals, brass/reeds/woodwind) | Yes (Pro) | No | No | Defer | P3 | Expensive model catalogue; not required for guitar practice. Revisit only if users ask. |
| 17 | Hi-Fi separation models | Yes (Pro) | Quality options, no tier | No | Defer | P2 | Quality R&D, not a blocker. Keep the local quality knobs. |
| 18 | Custom multi-track separation | Yes (Pro) | Track picker only | Track picker only | Defer | P2 | We can emit chosen stems; arbitrary target models are a later engine project. |
| 19 | Multimedia stems (dialogue/soundtrack/FX) | Yes (Pro) | No | No | Cut | Never | Not the music-practice job. |
| 20 | Re-separate without re-upload | Yes (paid) | Yes (re-run run dir) | Partial | Match | P1 | The run directory already holds the source; add a clear "re-separate" action. |
| 21 | Stem editor / split an existing stem | Yes (Studio) | No | No | Defer | P3 | DAW feature. |
| 22 | Tuning read / 432 Hz fix | Yes (Premium) | Engine helpers only | No | Defer | P2 | `tuning.py` exists; expose after the practice player. |
| 23 | Progress / cancel / retry | Yes | Yes | Partial | Defend | P1 | Serial desktop queue with retry (C §2). |

## 3. Practice player and mixer

| # | Capability | Moises | Desktop | Web | Decision | Phase | Notes |
|---|---|---|---|---|---|---|---|
| 24 | Per-stem volume (dB) | Yes | Yes | Yes | Defend | P1 | Both mixers. |
| 25 | Mute / solo | Yes | Yes | Yes | Defend | P1 | Solo wins; keep our law. |
| 26 | Master volume | Yes | Yes | Yes | Defend | P1 | Both. |
| 27 | Pan | Not in Play | Yes | Yes | Defend | P1 | Equal-power; Moises Play lacks it (C §3). |
| 28 | Group / parent row | Not documented in Play | Yes (desktop) | No | Defend | P1 | Desktop disclosure, no parent fader (C §3). |
| 29 | Waveforms | Yes | Yes | No | Match | P2 | Desktop has per-stem peaks; web has a seek slider. Add web waveform in P2. |
| 30 | Seek / transport | Yes | Yes | Yes | Defend | P1 | Both. |
| 31 | Speed change without pitch change | Yes (free-capped) | Yes | Yes | Defend | P1 | SoundTouch worklet; no artificial cap. |
| 32 | Pitch/key shift | Yes (free ±2) | Yes | Yes | Defend | P1 | Desktop/web ±6; no artificial cap. |
| 33 | Smart metronome (tempo curve) | Yes | Yes | Partial | Defend | P1 | Engine + desktop controls; hosted only a muted stem (C §10). |
| 34 | Metronome accent / subdivision / sound | Yes (Premium) | Yes | No | Match | P2 | Desktop already; port to web. |
| 35 | Count-in | Yes (4 free / 16 paid) | Yes (1/2 bars) | No | **Match** | **P1 done** | Desktop mixer count-in; web has no count-in. Verified in the practice panel. |
| 36 | A/B loop / section loop | Yes | Yes (region + section) | No | **Match** | **P1 done** | Desktop A/B region loop + section loop; web only whole-buffer loop. |
| 37 | Loop region before separation | Yes | Yes | Yes | Defend | P1 | Region picker. |
| 38 | Synced picture / video | Not in Play | Yes | No | Defend | P1 | Desktop picture with offset; keep. |
| 39 | Mix presets (karaoke/acapella/etc.) | Yes | Yes | Yes | Match | P1 | Fixed solo maps; fine. |
| 40 | Save current mix | Yes | Yes (pan/speed/key/mute/solo/master) | Partial (omits speed/key) | **Match** | **P1 desktop / P2 web** | Desktop pan export fixed in P1; center remains bit-identical, hard L/R tested. Web export still omits speed/key; P2 must fix it and add a visible “exports at original speed/key” warning until then. |
| 41 | Media keys / OS transport | Likely | Yes | Yes | Defend | P1 | Both. |
| 42 | Background / wake behavior | Likely | Yes | Yes | Defend | P1 | Both keep playing across hide (C §3). |
| 43 | Spacebar play/pause | Likely | Yes | Unknown | Match | P2 | Desktop only; add on web if missing. |
| 44 | Per-stem meters / clip indicators | Some | No | No | Defer | P2 | Nice polish, not core. |
| 45 | Metronome track show/hide | Yes | Yes | Partial | Match | P1 | Desktop already; web has a muted stem. |

## 4. Analysis and display

| # | Capability | Moises | Desktop | Web | Decision | Phase | Notes |
|---|---|---|---|---|---|---|---|
| 46 | BPM detection + readout | Yes | Yes (`analysis.bpm`) | Partial | **Match** | **P1 done** | Real Waltz: 105.47 BPM high confidence; Home shows `105.5 BPM`. Web does not show it yet. |
| 47 | Key detection + readout | Yes | Yes (`analysis.key`) | No | **Match** | **P1 done** | Real Waltz: Dm high confidence; chord-histogram + chroma fallback. |
| 48 | Chord detection | Yes (free first minute) | Yes (draft) | No | **Match** | **P1 done (draft)** | Real Waltz: 145 draft chords; zero-new-dependency CQT/template/Viterbi path. Accuracy is not certified; UI labels “Draft chords.” |
| 49 | Chord diagrams / chord shapes | Yes | Yes | No | **Match** | **P1 done** | Inline SVG diagrams in the Chords tab; capo display read-only. |
| 50 | Chord editing | Yes | No | No | Defer | P2 | Read-only + regenerate first. |
| 51 | Chord difficulty (easy/advanced) | Yes (Premium) | No | No | Defer | P2 | Voicing simplification after editing. |
| 52 | Capo mode | Yes | No | No | Defer | P2 | Guitar wedge; needs chord engine first. |
| 53 | Sharps/flats notation | Yes | No | No | Defer | P2 | Small preference. |
| 54 | Section detection | Yes | Yes (`analysis.sections`) | No | **Match** | **P1 done** | Real Waltz: 7 sections; minimum 8s; heuristic labels. Editable later. |
| 55 | Section editing / rename | Yes (Premium) | No | No | Defer | P2 | After detection. |
| 56 | Lyrics transcription | Yes (30+ languages) | Partial (dev; packaged deferred) | No | **Match** | **P1 dev / P1.6 packaging** | `faster-whisper` small, pinned local model; real Japanese excerpt produced 7 lines with word timestamps. Freeze does not collect it; packaged decision is P1.6. |
| 57 | Word-level lyric sync | Yes | Partial (dev) | No | **Match** | **P1 dev** | Word spans and click-to-seek verified with injected real lines; packaged availability follows 56. |
| 58 | Lyrics editing | Yes | No | No | Defer | P2 | Read-only first. |
| 59 | Beat/bar grid | Yes | Yes (measure view) | Partial | **Match** | **P1 done** | Chord grid + tab measure view; beat/bar display in the practice panel. |
| 60 | Vocal pitch / melody view | No | No | No | Cut | Never | Not needed for the guitar job. |
| 61 | Drum transcription / drum tab | No | No | No | Cut | Never | Out of scope. |
| 62 | Bass tab | No | No | No | Defer | P2 | Guitar tab first; bass is a natural extension. |

## 5. Tab and guitar workflow

| # | Capability | Moises | Desktop | Web | Decision | Phase | Notes |
|---|---|---|---|---|---|---|---|
| 63 | Guitar tab generation | **No** | Yes | Yes | **Differentiate** | **P1** | Existing Basic Pitch → tab pipeline (C §5). |
| 64 | Tab PDF export | **No** | Yes | Yes | **Differentiate** | **P1** | Existing `pdf_render.py`; no Moises equivalent. |
| 65 | On-screen tab synced to playhead | **No** | Yes (measure view) | No | **Differentiate** | **P1 done** | Tab measure view with current/next measure; real Waltz has 55 measures. |
| 66 | Fretboard / tuning display | Chord diagrams only | Yes (diagrams + tab) | No | **Match** | **P1 done** | Standard tuning shown in chord diagrams/tab; capo/tuning presets remain P2. |
| 67 | Capo / alternate tuning presets | Yes | No | No | Defer | P2 | After chord/capo engine. |
| 68 | Tab editing | No | No | No | Defer | P2 | User corrections would improve trust; not first release. |
| 69 | MIDI export | Yes (Studio) | Yes (tab page) | Yes (tab page) | Defend | P1 | Surface the existing MIDI download in the player. |
| 70 | MusicXML export | Yes (Studio) | No | No | Defer | P3 | DAW/notation feature. |
| 71 | Bass / drum tab | No | No | No | Defer | P2 | Extension, not wedge. |

## 6. Export

| # | Capability | Moises | Desktop | Web | Decision | Phase | Notes |
|---|---|---|---|---|---|---|---|
| 72 | Mix WAV | Yes | Yes | Yes | Match | P1 | Fix save-what-you-hear first. |
| 73 | Stems (all/selected) | Yes | Yes | Yes | Defend | P1 | Both. |
| 74 | Per-stem export | Yes | Yes | Yes | Defend | P1 | Both. |
| 75 | MP3 / M4A / FLAC / OGG | Yes | Yes | WAV only | Defend (desktop) | P2 | Desktop `EXPORT_FORMATS` already has all; web catches up in P2. |
| 76 | 48 kHz / 24-bit WAV | Yes (Pro) | Source-rate WAV | Source-rate WAV | Defer | P2 | Add explicit render settings if users ask. |
| 77 | Chord chart export | Yes (Play export) | No | No | **Match** | **P2** | Live Moises export dialog has Chord Chart; public help center lags. |
| 78 | Tab PDF | **No** | Yes | Yes | **Differentiate** | **P1** | Keep. |
| 79 | Metronome track export | Yes (paid) | Yes (stem) | Partial | Defend | P1 | Desktop already. |
| 80 | MIDI | Yes (Studio) | Yes | Yes | Defend | P1 | Surface it. |
| 81 | DAWproject / Ableton Set | Yes (Studio) | No | No | Defer | P3 | DAW feature. |
| 82 | Video export | Yes (mobile) | No | No | Cut | Never | Not our product. |
| 83 | Watermark | No | No | No | Cut | Never | Never add one. |
| 84 | Export time limits | Yes (Free 1 min) | No | No | **Cut** | **Never** | Local exports stay unlimited. |

## 7. Library, projects, cloud

| # | Capability | Moises | Desktop | Web | Decision | Phase | Notes |
|---|---|---|---|---|---|---|---|
| 85 | Local library / recents | Cloud library | Yes (project manifest) | Partial | Defend | P1 done / P1.5 UI | Runs have `project.json`; Home lists recents + library. P1.5 replaces the button stack with a real table/rail. |
| 86 | Search / filter / sort | Yes | Search only | No | Match | P2 | P1.5 keeps search and the visual table; filters/sort are still P2 features. Do not ship inert controls. |
| 87 | Setlists | Yes | No | No | Defer | P2 | Local setlists first; sharing later. |
| 88 | Queue / play-all | Yes (mobile) | No | No | Defer | P2 | Practice convenience. |
| 89 | Cloud cross-device sync | Yes | No | No | Defer | P3 | Optional; never required to practise. |
| 90 | Per-device edit state | Yes (weakness) | Local run state | Local session | **Defend** | P1 | Project manifest fixes this locally; sync later. |
| 91 | Project versions / undo | Yes (Studio) | No | No | Defer | P3 | DAW feature. |
| 92 | Share links / public mixes | Setlists | No | No | Defer | P3 | Needs auth/cloud. |
| 93 | Storage quotas | Plan-based | Local disk | Server disk | **Defend** | P1 | No artificial project cap. |
| 94 | Delete / recover | Permanent | Local delete | Job delete | Match | P2 | Add confirmation/undo where cheap. |

## 8. Collaboration

| # | Capability | Moises | Desktop | Web | Decision | Phase | Notes |
|---|---|---|---|---|---|---|---|
| 95 | Real-time Studio sessions | Yes | No | No | Defer | P3 | Separate product; go/no-go after P2. |
| 96 | Roles / presence / cursors / chat | Yes | No | No | Defer | P3 | Same. |
| 97 | Comments / version history | Yes | No | No | Defer | P3 | Same. |
| 98 | Offline resilience | Claimed (Studio) | Yes (local) | No | Defend | P1 | Local-first wins by construction. |
| 99 | Collaborative setlists | Yes (7 people) | No | No | Defer | P3 | After cloud sync. |

## 9. AI Studio / generation

| # | Capability | Moises | Desktop | Web | Decision | Phase | Notes |
|---|---|---|---|---|---|---|---|
| 100 | Stem generation | Yes (credits) | No | No | Defer | P3 | Buy/partner a model; do not train from scratch. |
| 101 | Sample generation | Yes | No | No | Defer | P3 | Same. |
| 102 | Prompt / reference / creative control | Yes | No | No | Defer | P3 | Same. |
| 103 | Audio or MIDI return | Yes | Partial (tab MIDI) | Partial | Defer | P3 | Generation MIDI is different from transcription MIDI. |
| 104 | Voice conversion | Yes (40–50+ voices) | No | No | Defer | P3 | Separate product/partner. |
| 105 | Custom voice model | Yes (Studio) | No | No | Defer | P3 | Rights/consent heavy. |
| 106 | AI mastering | Yes (Auto/Advanced/Reference) | No | No | Defer | P3 | Partner or deferred. |
| 107 | Auto Mix | Yes (Studio) | Presets only | Presets only | Defer | P3 | Our presets are fixed solo maps, not AI. |
| 108 | Amp modeler / NAM / TONE3000 | Yes (Studio) | No | No | Defer | P3 | Guitar-relevant, but a separate amp-sim product. |
| 109 | AI mix controls (presence/pan/reverb) | Yes | No | No | Defer | P3 | Studio feature. |

## 10. Studio / DAW

| # | Capability | Moises | Desktop | Web | Decision | Phase | Notes |
|---|---|---|---|---|---|---|---|
| 110 | Timeline / arrangement | Yes (Studio) | No | No | Defer | P3 | This is a different product. |
| 111 | Tracks / groups / buses / sends / returns | Yes | Group row only | No | Defer | P3 | Our group row is a disclosure, not a bus. |
| 112 | Audio/MIDI clips, split/trim/fade | Yes | No | No | Defer | P3 | DAW. |
| 113 | Automation | Yes | No | No | Defer | P3 | DAW. |
| 114 | MIDI editor | Yes | No | No | Defer | P3 | DAW. |
| 115 | Instruments / effects / VST3 | Yes | No | No | Defer | P3 | DAW. |
| 116 | Comping / take lanes | Yes | No | No | Defer | P3 | DAW. |
| 117 | Recording / monitoring | Yes | No | No | Defer | P3 | DAW. |
| 118 | DAWproject / Ableton export | Yes | No | No | Defer | P3 | DAW. |
| 119 | Plugin server / VST/AU/AAX | Yes (Pro) | No | No | Defer | P3 | Separate plugin product. |

## 11. Platform and integrations

| # | Capability | Moises | Desktop | Web | Decision | Phase | Notes |
|---|---|---|---|---|---|---|---|
| 120 | macOS / Windows desktop | Yes | Yes | n/a | Defend | P1 | Our installers exist. |
| 121 | Web app | Yes | n/a | Yes | Match | P2 | Our web is thinner; port the practice player after desktop. |
| 122 | iOS / Android | Yes | No | No | Defer | P3 | Desktop priority. |
| 123 | iPad / TV / visionOS | Yes | No | No | Cut / Defer | Never* | TV/visionOS are not the product; iPad is a later companion if mobile happens. |
| 124 | VST/AU/AAX plugin | Yes (Pro) | No | No | Defer | P3 | Separate product. |
| 125 | Moises Live (system audio) | Yes (free) | No | No | Defer | P3 | Interesting desktop adjacency; separate product. |
| 126 | Fender / LUNA integrations | Yes (B2B) | No | No | Cut | Never | B2B deals, not consumer app. |
| 127 | Public API | B2B only | No | Internal API | Cut | Never | Do not build a public API before the product is stable. |
| 128 | Offline processing | No (cloud) | Yes | No | **Defend** | P1 | Structural advantage. |
| 129 | Privacy / no upload | No (cloud) | Yes | No | **Defend** | P1 | Structural advantage. |
| 130 | Localization | 33 languages | No | No | Defer | P2 | English first; add UI strings when the workflow stabilizes. |
| 131 | Accessibility | Unknown | Partial | Partial | Match | P1.5/P2 | P1.5 adds keyboard/focus/contrast/table semantics; P2 deepens screen-reader/zoom coverage. |
| 132 | Themes | Dark | Yes | Yes | Defend | P1 | Keep Tyrian Nocturne as default; other presets must remain legible. |

## 12. Business and trust

| # | Capability | Moises | Desktop | Web | Decision | Phase | Notes |
|---|---|---|---|---|---|---|---|
| 133 | Free-tier processing limits | 5/month, 5 min, first-minute gating | None | Hosted mode caps only | **Cut** | **Never** | Do not copy artificial scarcity. |
| 134 | Subscription / billing | Yes | No | No | Defer | P3 | Only if cloud/AI costs require it. |
| 135 | Commercial rights | User owns outputs | User owns local files | User owns files | Defend | P1 | State it plainly. |
| 136 | Training opt-out | Yes | Local by default | Hosted policy needed | Defend | P1 | Local processing is the strongest opt-out. |
| 137 | Data retention | 60 days free | Local until delete | Job retention | Defend | P1 | Local control. |
| 138 | Artist-name prompting | Blocked | No | No | Cut | Never | Do not build. |
| 139 | Full text-to-song | No | No | No | Cut | Never | Not our product. |
| 140 | Social feed / marketplace | No | No | No | Cut | Never | Not our product. |

## 13. Experience quality (Phase 1.5)

These are not new features. They are the craft rows that decide whether the features feel like a
product. The reference and tokens are in `10-MOISES-UI-CRAFT.md`; the build plan is `11`.

| # | Capability | Moises | Desktop today | Web | Decision | Phase | Notes |
|---|---|---|---|---|---|---|---|
| 141 | Visual hierarchy / composition | No Home H1. Section headings 18/26. One cyan card icon | H1 44/52.8 weight 700. All text `#F6AD49` | Thin | **Match Home** | **P1.5** | Numbers: `10` §13. No page title on Home. |
| 142 | Home library table | 56px rows. Columns Title, Type, Created, Duration. Type and Duration hide by 1024 | 74px buttons plus a 132×74 action | No | **Match Home** | **P1.5** | Our columns: Title, Created, action. See `10` §13.8. |
| 143 | Recents rail | 150×210 cards, 12px gap, horizontal scroll, no snap | Equal columns. At 1024 they are about 100×80 and wrap to ~4 lines | No | **Match Home** | **P1.5** | Fixed 150×210. Do not scroll-snap. |
| 144 | Shell / sidebar | 240px rail at 1440, 1280, 1024, and 900. Nav row 216×36 | 300px rail, nav 260×28, active weight 600 | No | **Match Home** | **P1.5** | There is no 216px rail. 216 is the row width. |
| 145 | Player composition | Not re-measured 2026-10-21 | Current mixer | Thin | **Later** | **P1.6** | Moved out of the Home parity gate. |
| 146 | Practice sheet | Not re-measured 2026-10-21 | Tabs in the mixer | No | **Later** | **P1.6** | Moved out of the Home parity gate. |
| 147 | Popovers / dialogs | Home filter menu was not captured | Inline controls | No | **Home menu only** | **P1.5** | Home menu contract is `11` §12.8. Player popovers wait. |
| 148 | Empty / loading / error states | Home empty/loading/error `[unverified]` | `st.info` / `st.spinner` / `home_flash` | Thin | **Match (our copy)** | **P1.5** | Copy is specified in `11` §12.8 because Moises’ Home empty state was not exercised. |
| 149 | Keyboard / focus | Search outline-style none | Some Streamlit rings. Nav active weight 600 | Partial | **Match plus a ring** | **P1.5** | We add a 2px `#E9EEF5` ring. That is a deliberate correction. |
| 150 | Responsive 1024/900 | Rail stays 240. Rails clip and scroll. No page scrollbar | Rail stays 300. Page also does not scrollbar. Recents squash | No | **Match Home** | **P1.5** | 2026-10-21: current Home does **not** clip the H1 or Tab PDF off the page. |
| 151 | Typography / color tokens | Articulat, neutrals, `#75EBF5` on the first card icon | Satoshi, all-amber, `#192542` | Thin | **Home-scoped** | **P1.5** | Satoshi stays. Neutrals are Home-only. Global Tyrian tokens do not change. |
| 152 | Motion | Card 0.15s. Nav 0.2s and 0.28s | Button transition 160ms in `home.py` | Thin | **Match Home** | **P1.5** | Use the measured durations. Reduced motion zeros them. |
| 153 | Design consistency | One Home surface | 60px Streamlit header. Promo text was absent on 2026-10-21 | Thin | **Home only** | **P1.5** | Player and Isolate stay on the current theme until P1.6. |

## What the matrix says

1. **We are not starting from zero.** The separator, guitar refinement, mixer, speed/key, pan,
   picture, metronome, tab, and PDF are already built. The gap is analysis + a player that shows it.
2. **The fastest credible parity win is the analysis layer.** BPM/key/chords/sections/lyrics turn the
   existing mixer into a practice tool. None of it requires a DAW.
3. **The wedge is tab.** Moises has chords and chord charts; it has no tab generation and no tab PDF.
   Put tab in the player and make it the first thing a guitarist sees.
4. **The export mismatch is a trust bug.** Desktop now bakes speed/key/pan into “Save current mix”.
   The hosted `bounceMix` still omits speed/key, so do not claim web export parity until that is
   fixed or visibly warned.
5. **Studio is a different company-sized product.** The matrix keeps every Studio row, but none of it
   is Phase 1. The go/no-go is after the practice product is shipped.

## Assumptions and unknowns

- Moises' Play player may have hidden pan/EQ/comp controls behind an options menu; the runtime pass did
  not open every menu. The public help center says it does not. Treat "no pan in Play" as observed for
  the visible row, not a universal claim.
- Moises' Studio plan limits (projects, collaborators, session length) are not public. We do not need
  them for Phase 1.
- Our web mixer is behind desktop. The user's priority is desktop; web parity is P2, not a blocker.
- The chord/lyrics model choices are not final. `06-PHASE-1-PLAN.md` makes the first task a measured
  spike, not a guess.
