# Feature matrix — 2026-10-23

Row numbers match the archived matrix so `13-PARITY-DELTA.md` can account for each one. The Moises behavior cell from 2026-10-20 is historical unless this scan column says the fact was re-seen.

**Scan:** `CONFIRMED` re-seen on 2.1.0 at the scope in the evidence cell. `HIST` not re-opened; do not quote the old Moises cell as a current measurement. Every `HIST` row cites archived `03-FEATURE-MATRIX.md` and the logged-in blocker in `14-RESCAN-OPEN-QUESTIONS.md` (player page P-S2-08 was not entered). Rows that name another id below use that id instead.

**Decision** is unchanged from the archive unless `04-SCOPE-CUT.md` moves the row. Phase names: P1 practice core, P1.5 Home, P1.6 player/packaging, P2 practice depth, P3 other products, Never.

| # | Capability | Scan | Decision | Phase | Evidence |
|---|---|---|---|---|---|
| 1 | Local audio upload | HIST | now | P1 | P-S2-03 not opened |
| 2 | Local video import | HIST | now | P1 | P-S2-08 not opened |
| 3 | YouTube search | HIST | now | P1 | not re-opened |
| 4 | YouTube to MP3 | HIST | now | P1 | not re-opened |
| 5 | OS open / drag-drop | CONFIRMED | now | P1 | F-057 `import:consume` |
| 6 | Trim before separation | HIST | now | P1 | P-S2-03 not opened |
| 7 | Batch upload | HIST | later | P2 | not re-opened |
| 8 | Generic URL import | HIST | later | P2 | not re-opened |
| 9 | Cloud picker | HIST | later | P3 | not re-opened |
| 10 | DRM streaming URLs | HIST | never | Never | not re-opened |
| 11 | 2-stem | HIST | now | P1 | marketing mentions separation; not run |
| 12 | 4-stem | HIST | now | P1 | P-S6-01 marketing |
| 13 | 6-stem guitar/piano | HIST | now | P1 | P-S6-01 marketing |
| 14 | Guitar specialist | HIST | now | P1 | not re-opened |
| 15 | Lead/rhythm splits | HIST | later | P2 | our flag `ui/isolate_jobs.py:112` |
| 16 | 27-stem catalogue | HIST | later | P3 | P-S6-01 says "27 stem types"; not run |
| 17 | Hi-Fi models | HIST | later | P2 | P-S6-01 marketing |
| 18 | Custom multi-track | HIST | later | P2 | help mentions custom upload; body not read |
| 19 | Dialogue/FX stems | HIST | never | Never | not re-opened |
| 20 | Re-separate | HIST | now | P1 | not re-opened |
| 21 | Stem editor | HIST | later | P3 | P-S2-04 interior not opened |
| 22 | Tuning / 432 Hz | HIST | later | P2 | not re-opened |
| 23 | Progress / cancel | HIST | now | P1 | not re-opened |
| 24 | Per-stem volume | HIST | now | P1 | P-S2-08 not opened |
| 25 | Mute / solo | HIST | now | P1 | P-S2-08 not opened |
| 26 | Master volume | HIST | now | P1 | P-S2-08 not opened |
| 27 | Pan in Play | HIST | now | P1 | not re-opened; do not invent a law |
| 28 | Group row | HIST | now | P1 | not re-opened |
| 29 | Waveforms | HIST | later | P2 | not re-opened |
| 30 | Seek / transport | HIST | now | P1 | P-S2-08 not opened |
| 31 | Speed without pitch | HIST | now | P1 | not re-opened |
| 32 | Pitch shift | HIST | now | P1 | not re-opened |
| 33 | Smart metronome | HIST | now | P1 | help blurb only |
| 34 | Metronome accent | HIST | later | P2 | not re-opened |
| 35 | Count-in | HIST | now | P1 | our code `ui/stem_mixer_component/__init__.py:99`; Moises not re-opened |
| 36 | A/B loop | HIST | now | P1 | not re-opened |
| 37 | Loop before separation | HIST | now | P1 | not re-opened |
| 38 | Synced picture | HIST | now | P1 | not re-opened |
| 39 | Mix presets | HIST | now | P1 | not re-opened |
| 40 | Save current mix | HIST | now | P1 | not re-opened |
| 41 | Media keys | HIST | now | P1 | not re-opened |
| 42 | Background playback | HIST | now | P1 | not re-opened |
| 43 | Spacebar | HIST | later | P2 | not re-opened |
| 44 | Meters | HIST | later | P2 | not re-opened |
| 45 | Metronome track | HIST | now | P1 | not re-opened |
| 46 | BPM | HIST | now | P1 | not re-opened |
| 47 | Key | HIST | now | P1 | not re-opened |
| 48 | Chords | HIST | now | P1 | not re-opened |
| 49 | Chord diagrams | HIST | now | P1 | not re-opened |
| 50 | Chord editing | HIST | later | P2 | not re-opened |
| 51 | Chord difficulty | HIST | later | P2 | not re-opened |
| 52 | Capo | HIST | later | P2 | not re-opened |
| 53 | Sharps/flats | HIST | later | P2 | not re-opened |
| 54 | Sections | HIST | now | P1 | not re-opened |
| 55 | Section editing | HIST | later | P2 | not re-opened |
| 56 | Lyrics transcription | HIST | now | P1 | route P-S2-07; quality not run |
| 57 | Word-level lyrics | HIST | now | P1 | not re-opened |
| 58 | Lyrics editing | HIST | later | P2 | not re-opened |
| 59 | Beat grid | HIST | now | P1 | not re-opened |
| 60 | Vocal pitch view | HIST | never | Never | not re-opened |
| 61 | Drum tab | HIST | never | Never | not re-opened |
| 62 | Bass tab | HIST | later | P2 | not re-opened |
| 63 | Guitar tab generation | HIST | now | P1 | local bundle needle scan found no `guitar`; hosted player not opened. Our PDF import `src/audio_to_tab/pipeline.py:19` |
| 64 | Tab PDF | HIST | now | P1 | same as 63 |
| 65 | On-screen tab | HIST | now | P1 | P-S2-08 not opened |
| 66 | Fretboard | HIST | now | P1 | not re-opened |
| 67 | Capo presets | HIST | later | P2 | not re-opened |
| 68 | Tab editing | HIST | later | P2 | not re-opened |
| 69 | MIDI | HIST | now | P1 | not re-opened |
| 70 | MusicXML | HIST | later | P3 | not re-opened |
| 71 | Bass/drum tab | HIST | later | P2 | not re-opened |
| 72 | Mix WAV | HIST | now | P1 | not re-opened |
| 73 | Stems export | HIST | now | P1 | not re-opened |
| 74 | Per-stem export | HIST | now | P1 | not re-opened |
| 75 | Compressed formats | HIST | now | P2 | not re-opened |
| 76 | 48 kHz / 24-bit | HIST | later | P2 | not re-opened |
| 77 | Chord chart export | HIST | later | P2 | not re-opened |
| 78 | Tab PDF export | HIST | now | P1 | same as 63 |
| 79 | Metronome export | HIST | now | P1 | not re-opened |
| 80 | MIDI export | HIST | now | P1 | not re-opened |
| 81 | DAWproject | HIST | later | P3 | not re-opened |
| 82 | Video export | HIST | never | Never | not re-opened |
| 83 | Watermark | HIST | never | Never | not re-opened |
| 84 | Export time limits | HIST | never | Never | not re-opened |
| 85 | Library / recents | CONFIRMED | now | P1 | P-S2-01 route and persisted Home tab. Interior not opened. |
| 86 | Search / filter | HIST | later | P2 | not re-opened |
| 87 | Setlists | HIST | later | P2 | not re-opened |
| 88 | Queue | HIST | later | P2 | not re-opened |
| 89 | Cloud sync | HIST | later | P3 | hosted origin only |
| 90 | Per-device state | HIST | now | P1 | `tabs.json` exists; behavior not compared |
| 91 | Versions / undo | HIST | later | P3 | not re-opened |
| 92 | Share links | HIST | later | P3 | not re-opened |
| 93 | Storage quotas | HIST | now | P1 | not re-opened |
| 94 | Delete / recover | HIST | later | P2 | not re-opened |
| 95 | Real-time sessions | HIST | later | P3 | P-S6-01 marketing sentence |
| 96 | Roles / chat | HIST | later | P3 | not re-opened |
| 97 | Comments | HIST | later | P3 | not re-opened |
| 98 | Offline | HIST | now | P1 | shell entry is hosted; offline claim not tested |
| 99 | Collaborative setlists | HIST | later | P3 | not re-opened |
| 100 | Stem generation | HIST | later | P3 | P-S6-05 help text |
| 101 | Sample generation | HIST | later | P3 | not re-opened |
| 102 | Prompt controls | HIST | later | P3 | not re-opened |
| 103 | Audio or MIDI return | HIST | later | P3 | not re-opened |
| 104 | Voice conversion | HIST | later | P3 | P-S2-06 route only |
| 105 | Custom voice | HIST | later | P3 | not re-opened |
| 106 | AI mastering | HIST | later | P3 | P-S2-05 route only |
| 107 | Auto Mix | HIST | later | P3 | not re-opened |
| 108 | Amp modeler | HIST | later | P3 | not re-opened |
| 109 | AI mix controls | HIST | later | P3 | not re-opened |
| 110 | Timeline | CONFIRMED | later | P3 | P-S2-04 route exists. Timeline itself not opened. |
| 111 | Buses | HIST | later | P3 | interior not opened |
| 112 | Clips | HIST | later | P3 | interior not opened |
| 113 | Automation | HIST | later | P3 | interior not opened |
| 114 | MIDI editor | HIST | later | P3 | interior not opened |
| 115 | Instruments / VST | HIST | later | P3 | F-058 connection channel; UI not opened |
| 116 | Comping | HIST | later | P3 | interior not opened |
| 117 | Recording | HIST | later | P3 | F-065 capture channel; not run |
| 118 | DAW export | HIST | later | P3 | interior not opened |
| 119 | Plugin server | HIST | later | P3 | F-038 through F-042 |
| 120 | Desktop apps | CONFIRMED | now | P1 | Windows 2.1.0 inspected |
| 121 | Web app | HIST | later | P2 | P-S3-01 login only |
| 122 | iOS / Android | HIST | later | P3 | S5 blocked |
| 123 | iPad / TV / visionOS | HIST | never | Never | marketing names iPad; TV not seen |
| 124 | VST/AU/AAX plugin | CONFIRMED | later | P3 | P-S2-10 filenames and F-054 |
| 125 | Moises Live | CONFIRMED | later | P3 | P-S6-50 marketing page. Desktop-only, on-device, offline. Not installed. |
| 126 | Fender / LUNA | HIST | never | Never | not re-opened |
| 127 | Public API | HIST | never | Never | help mentions B2B purchases; no API spec read |
| 128 | Offline processing | CONFIRMED | now | P1 | Home tab URL is `studio.moises.ai`. Our gate `hardware.py:27` |
| 129 | Privacy / no upload | HIST | now | P1 | Moises Home is hosted. Our local path not re-audited beyond the gate. |
| 130 | Localization | HIST | later | P2 | locale list on P-S6-01; our UI not re-audited |
| 131 | Accessibility | HIST | later | P2 | not re-opened |
| 132 | Themes | HIST | now | P1 | F-049 channel; colors not measured |
| 133 | Free-tier limits | CONFIRMED | never | Never | Help text P-S6-61 and P-S6-63: 5 uploads a month. P-S6-62: 5-minute stems, first minute for metronome, chords, and lyrics. Not a quota response. Do not copy the cap into our app. |
| 134 | Subscription | HIST | later | P3 | P-S6-04 names Premium and Pro; prices unknown |
| 135 | Commercial rights | HIST | now | P1 | not re-opened |
| 136 | Training opt-out | HIST | now | P1 | FAQ says they do not train on user data. Policy text, not a control we used. |
| 137 | Data retention | HIST | now | P1 | not re-opened |
| 138 | Artist-name prompting | HIST | never | Never | not re-opened |
| 139 | Text-to-song | HIST | never | Never | not re-opened |
| 140 | Social feed | HIST | never | Never | not re-opened |
| 141 | Home hierarchy | HIST | next | P1.5 | not remeasured |
| 142 | Home table | HIST | next | P1.5 | not remeasured |
| 143 | Recents rail | HIST | next | P1.5 | not remeasured |
| 144 | Sidebar | HIST | next | P1.5 | not remeasured |
| 145 | Player composition | HIST | later | P1.6 | not remeasured |
| 146 | Practice sheet | HIST | later | P1.6 | not remeasured |
| 147 | Popovers | HIST | next | P1.5 | not remeasured |
| 148 | Empty states | HIST | next | P1.5 | not remeasured |
| 149 | Keyboard / focus | HIST | next | P1.5 | shell accelerators Control+Tab observed as strings |
| 150 | Responsive | HIST | next | P1.5 | not remeasured |
| 151 | Typography | HIST | next | P1.5 | not remeasured |
| 152 | Motion | HIST | next | P1.5 | not remeasured |
| 153 | Consistency | HIST | next | P1.5 | not remeasured |

New rows N1–N7 are in `13-PARITY-DELTA.md`, not renumbered into this table.
