# Gaps versus this repo

Product comparison only. The “Ours” lines below are the 2026-10-17 snapshot. **Status as of 2026-10-18** (code, not this file’s old sentences): desktop tabs duplicate, close others, close to the right, and reorder; both mixers have pan (`ui/stem_mixer_component/frontend/src/pan.ts`, `web/src/mixer/pan.ts`); desktop has a non-summing group row; OS open-with is `ui/opened_audio.py` plus packaging. [FULL-TEARDOWN.md](FULL-TEARDOWN.md) §9.4: the local Moises renderer does not mount the mixer. Do not treat the opportunities under P0 as still open.

Our desktop mixer is Streamlit Isolate: Home | mix | + (`ui/mix_tabs_component/`), and a Web Audio iframe (`ui/stem_mixer_component/`) with per-stem mute, solo, dB volume, master, presets, speed/key, metronome, and an optional synced picture. Export is “Save current mix,” not a write on every fader move. The hosted `web/` mixer is a different surface and was not the target of this comparison.

Moises 2.0.3 is an Electron studio shell. The comparable pieces are the **tab bridge** and the **track-row literals**. Live capture and VST are a different product sitting in the same app.

## P0 — tab strip

**Their model (observed).** Main-process tabs: create, duplicate, close, close others, close right, reorder, preview, context menu, new-tab menu, drag indicator. The renderer calls `electronAPI.tab`.

**Ours.** Home, one tab per mix, plus, close. Focus keys include Home/End. No duplicate, close-others, or drag-reorder in the strip.

**Opportunity.** Make the strip a project switcher: drag to reorder, duplicate a mix, close others / close to the right. Keep our Home page as the separate/upload step. Do not copy their menu art or channel names.

## P0 — track row

**Theirs (literals in the parsed renderer, not a traced audio graph).** `TrackHeader`, mute, solo, `PanControl`, record, `Input gain`, `isParentTrack`, waveform container, empty state `No waveform data`, plus `wavesurfer` / `AudioContext` / `createGain` / `audioworklet`.

**Ours.** Mute, solo (including “any solo mutes the rest”), per-stem dB, master dB, mute-all, clear-solo, waveforms, metronome row, practice speed/key, presets. No pan, no record arm, no parent/child track.

**Opportunity.** Pan on a stem, and a parent row that groups stems (for example guitar pre/refined, or drums that contain pieces), are the mixer gaps that match evidence. Record-arm and input gain belong with live capture (P1), not with offline stem playback.

**Do not drop** our picture, metronome, or speed/key to look more like this bundle. Those were not found as Moises features in this pass.

## P1 — live input

**Theirs (observed).** Utility process `MoisesAudioCapture`, `audify` / `RtAudio`, PCM literals, `audioCapture.listDevices` / `open` / `close`. Plist text says mic and interface audio go into Studio projects.

**Ours.** File or YouTube in, stems out, then mix. No interface capture into the mixer.

**Opportunity.** Only if the product grows from “separate a file” to “record into a project.” It is a new process and a native addon, not a fader. The renderer bundle never mentions `audioCapture`, so we also do not know their on-screen capture UX.

## P1 — open a file into a tab

**Theirs.** OS document types (audio + MIDI) and `import:consume` / `consumePendingImportFile`.

**Ours.** Upload and YouTube search on Isolate Home. The desktop app is not an OS document editor.

**Opportunity.** “Open with” / drop a file onto a new mix tab, wired to the same Home form. MIDI on their plist is not a reason for us to add a MIDI editor.

## P2 — leave these alone

- **VST / plugin server.** Channels and the strings “VST plugins are available to Studio” / “disabled” are a plugin host. Out of scope for the stem mixer.
- **Lyrics, mastering, voice-studio, sparkbars.** Menu assets and a few bundle literals. Other tools in their shell, not gaps in our mixer.
- **Their updater, theme IPC, and window chrome.** Desktop packaging already has its own shell (Streamlit / pywebview).

## Explicitly unknown — do not build from these

- Synced video or YouTube picture inside Moises. Our picture path may already be the further one.
- Mix bounce / “save mix” behavior. `Could not export image` is not a stem bounce. Keep our save-on-export rule (`docs/ui-issues.md` I-607).
- Solo law, pan law, and whether volume is dB. Not in the IPC graph, and the renderer trace did not reach `AudioContext`.
- Stem names and whether a track is a separation stem or a recording.
