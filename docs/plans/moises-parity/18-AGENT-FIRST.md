# Agent first — what is left

Read this before any other plan. The user wants the remaining planned work finished. Phases 1, 1.5, and 1.6 are done. Phase 2 is partly done. Phase 3 has not started.

Do one slice, then stop and name the next slice. Do not start Phase 3 until every Phase 2 row below is done. Do not build a row in the never list.

## Already done

- Phase 1 practice core is in the tree: analysis display, count-in, loop, tab, and the desktop player. The old three-song checklist was not run again.
- Phase 1.5 Home is done. `AUDIO_TOOLS_UI_V2=0` still falls back to the old Home.
- Phase 1.6 player layout is done. Plan: `15-PHASE-1.6-PLAN.md`.
- Phase 2 chord edit and capo are done. Plan: `16-PHASE-2-CHORDS.md`. Type a symbol on one chip. Capo is fret 0–11. Fret 0 says "No capo". The sounding name stays. The diagram uses the shape transposed down by that many frets.
- Phase 2 local setlists are partly done. Plan: `17-PHASE-2-SETLISTS.md`. Create, add, and filter work. The file is `data/ui_runs/setlists.json`. The browser gets ids and tokens, never file paths.

## Rules that stay in force

- Guitar tab, tab/PDF export, and local-first processing are the product. The practice player is the battlefield. Studio, voice, mastering, plugins, and capture are Phase 3.
- Do not raise `MPS_MIN_RAM_GB` (12.0 in `src/audio_to_tab/hardware.py`).
- Do not edit `ui/stem_mixer_component/frontend/src/pan.ts` or `web/src/mixer/pan.ts`.
- Desktop isolation stays serial (`ui/isolate_jobs.py`). Desktop Interface Lite is not hosted `lite`.
- Pixels in `10-MOISES-UI-CRAFT.md` are our spec, not a Moises 2.1.0 measurement.
- Do not log into Moises, upload private audio, or buy a plan.
- No new dependency. No commit, push, or PR unless this conversation asks.
- Rebuild the mixer with `powershell -File scripts/dev.ps1 mixer-build`. Rebuild Home with `powershell -File scripts/dev.ps1 home-build`. Do not hand-edit `frontend/build/`.
- Python is `.venv311\Scripts\python.exe`. Write the failing test first.
- Stop and ask before deleting a file, adding a dependency, or changing a database schema.
- If a slice has no chosen behavior in the code or in these plans, ask one question and do not invent a second model.
- After UI work, check the flow in the browser at 1440, 1280, 1024, and 900. Stop the temporary Streamlit process afterward.

## Next slice

Finish the setlist screen, then the website player. The website player was not started.

Setlist store can already remove a song (`ui/setlists.py` `remove_song`). Home cannot. Add, on the existing Home screen:

- Remove one song from the selected setlist.
- Rename a setlist.
- Delete a setlist.

Keep paths out of the iframe. A blank rename stays "Setlist". Deleting a list does not delete the songs from the library. Rebuild Home. Extend `tests/test_setlists.py`. Do not start sharing.

## Phase 2 after that

Do these in order. One slice per session.

1. **Website player.** The site is FastAPI `backend/` plus React `web/`. Bring the practice player there: play, stems, speed, key, chords, capo, sections, lyrics, and tab. Auth already exists (JWT, refresh cookie `att_refresh`). Logout currently does not revoke the refresh token; fix that in this slice if the player requires a signed-in session. Do not copy the desktop Streamlit iframe.
2. **Batch queue.** Matrix rows 7 and 88. A queue of local songs, still one separation at a time. Do not start a second isolate worker.
3. **8** Generic URL import. Ask how a non-YouTube URL should be saved before coding. YouTube audio already exists.
4. **15** Lead/rhythm splits. The flag is `ui/isolate_jobs.py`. Finish the split the flag already points at. Do not add a new model.
5. **17** Hi-Fi models. Ask which installed model is the Hi-Fi choice. Do not download a new one inside the slice.
6. **18** Custom multi-track upload. Extra local tracks into an existing song. No cloud picker.
7. **22** Tuning / 432 Hz. A listen control. Do not retune the exported master unless the user picks that.
8. **29** Waveforms on the desktop player.
9. **34** Metronome accent.
10. **43** Spacebar play/pause in the desktop player. Do not steal the key while a text field is focused.
11. **44** Meters.
12. **51** Chord difficulty. Ask what the levels mean before coding.
13. **53** Sharps/flats spelling. Capo and chord edit already force sharp names (`PC_NAME` in `analysis.ts`). This slice is the spelling switch.
14. **55** Section editing.
15. **58** Lyrics editing.
16. **62** Bass tab.
17. **67** Capo presets. Separate from the fret dropdown in `16`.
18. **68** Tab editing.
19. **71** Bass/drum tab. Drum tab as its own product is in the never list. This row is bass tab plus a drum staff only if the user confirms the drum half. Ask before the drum half.
20. **76** 48 kHz / 24-bit export.
21. **77** Chord chart export.
22. **86** Library filters beyond the Home search box. Search already exists.
23. **94** Delete and recover a library song. Deleting a setlist is the earlier slice. This row is the song itself.
24. **130** Localization. Ask which language is first.
25. **131** Accessibility pass on Home and the player. Keyboard, focus, names, and contrast. No new visual system.

Matrix row 75 (compressed export) is already marked now. Do not reopen it unless a test shows the export is missing.

## Bugs to fix before Phase 3

These are not new products. Fix them after the Phase 2 rows, or sooner if a slice touches the same file.

- Windows open-with drops `file://` video paths in `ui/opened_audio.py`. `tests/test_opened_audio.py::test_argv_keeps_audio_and_video_and_declines_midi` failed on Windows. MIDI must stay declined.
- `tests/test_account_delete.py::test_delete_me_endpoint_for_anonymous` uses the `SessionLocal` imported at module load, so the follow-up read can hit `./data/app.db` instead of the temp database.
- Refresh tokens are not stored or revoked. Logout in `backend/main.py` only deletes the browser cookie.
- Mix and Speed & Key use the same absolute position and can cover each other.
- A Streamlit rerun while a chord symbol is mid-typing can rebuild the input from the last saved symbol.
- Installer model download was left out of `15` and has no slice. Ask before adding a downloader.
- Packaged lyrics were deferred and were not part of the 1.6 layout. Ask before bundling a lyrics model.

## Phase 3

Start only after Phase 2 and the bug list. One product per session. These were a go/no-go, and the user has now said to finish them too. Still ask one question when the product has no chosen behavior in this repo.

- **9** Cloud file picker
- **16** 27-stem catalogue
- **21** Stem editor
- **70** MusicXML
- **81** DAWproject export
- **89** Cloud sync
- **91** Versions / undo
- **92** Share links
- **95** Real-time sessions
- **96** Roles / chat
- **97** Comments
- **99** Collaborative setlists. Local setlists stay the desktop feature. This row is sharing.
- **100** Stem generation
- **101** Sample generation
- **102** Prompt controls
- **103** Audio or MIDI return from generation
- **104** Voice conversion
- **105** Custom voice
- **106** AI mastering
- **107** Auto Mix
- **108** Amp modeler
- **109** AI mix controls
- **110** Studio timeline
- **111** Buses
- **112** Clips
- **113** Automation
- **114** MIDI editor
- **115** Instruments / VST inside Studio
- **116** Comping
- **117** Recording
- **118** DAW export
- **119** Plugin server
- **122** iOS / Android
- **124** VST / AU / AAX plugin
- **125** A Live-style on-device player. Do not install Moises Live.
- **134** Subscription. Do not copy Moises prices or the free-tier cap.
- **N3** WASAPI/ASIO capture utility
- **N4** Google, Facebook, Apple, X, and email login

## Do not build

Matrix rows 10, 19, 60, 61, 82, 83, 84, 123, 126, 127, 133, 138, 139, 140. Also N1 memory panel, N2 sparkbars, N5 video-recording marketing, N6 generation credits, and N7 the unknown `studio1` host. Reasons are in `04-SCOPE-CUT.md` and `13-PARITY-DELTA.md`.

## Where the decisions live

| Question | File |
|---|---|
| Row verdicts | `03-FEATURE-MATRIX.md` |
| now / later / never | `04-SCOPE-CUT.md` |
| Phase order | `05-ROADMAP.md` |
| Player layout | `15-PHASE-1.6-PLAN.md` |
| Chord and capo | `16-PHASE-2-CHORDS.md` |
| Setlists | `17-PHASE-2-SETLISTS.md` |
| Blocked research | `14-RESCAN-OPEN-QUESTIONS.md` |
