# Competitive inspiration plan — Moises → Audio Tools (similar, not same)

**Superseded for scope by `docs/plans/moises-parity/04-SCOPE-CUT.md` (2026-10-23).** The competitor build in the sections below is 2.0.3 and is historical. Pan law, solo law, summing, and the rule against copying an unknown mixer law still apply. Do not treat the non-goals in section 0 as the current program.

## 0. Framing

- Competitor: Moises desktop 2.0.3 (static REA via `REFERENCE.md`). App was not launched. `FULL-TEARDOWN.md` is complementary evidence (shell vs hosted studio). Its §10 is a loading playbook to inspire, not a clone list.
- Analogy: Artcraft vs Photoshop — same job class, different product.
- Scope: desktop Isolate mixer + hosted web mixer only.
- Non-goals: clone UI/IPC/assets; VST/lyrics/mastering/voice-studio; build from Unknown.

## 1. Evidence rules used

`REFERENCE.md` is evidence, not a spec. Observed and Literal can inspire a user job. Inference stays provisional. Unknown is not a feature. Trace no-match is not absence. Desktop Isolate and hosted web stay separate products. Desktop Interface Lite and hosted processing mode `lite` stay separate. Confirmed “ours” against the files named in section 3 on 2026-10-18. Did not re-run REA.

## 2. Moises strengths (user jobs)

| Job | Moises evidence tag + ID | Why it feels strong | Notes / Unknowns |
| --- | --- | --- | --- |
| Several mixes open, switch, duplicate, close a side, reorder | Observed IPC + Inference candidate map. `ev_2e54eb001ccfb0467d561f4bbac91b8ca3ef0ac1d1bb52b3a498b47e9dc3e99d`. First-pass bridge list in `REFERENCE.md` “P0 — tab strip”. | A musician keeps more than one song in the shell and rearranges them without going home. | Wiring from button to channel is inferred, not an observed call. Do not copy the channel list. |
| Mute and solo a track | Literal `mute` / `solo` (first pass). Law Unknown. | Standard mixer row. | Solo law Unknown. Do not copy a law we did not see. |
| Set track loudness | Literal one `createGain` into `destination` (deeper pass, local scan of sha256 `791aa79e…`, module `ev_46db80d8df79d3988f0e957b315d84d68e20c71ae7c00874f35e8d6deb2f484b`). Fader scale Unknown. Trace `createGain` no-match `ev_95e31ca8b609bbc38eac74b529798c6c854e263788ba6a9b959ef2c1b89cc0bb`. | Something in the studio bundle turns level into a single output gain. | Not evidence of a per-stem fader graph. |
| Pan a track | Literal `PanControl` displayName (local scan). Trace no-match `ev_25a3f7988d232a7e89db49b406fee5fe1ac8d59fef2109cdfcd8e59e7ac5a597`. | A named pan control exists. | Pan law Unknown. |
| Fold child tracks under a parent row | Literal `isParentTrack` next to `toggleOpenButton` (local scan). | A row can collapse. | Whether the parent sums audio is Unknown. |
| See a waveform | Literal `wavesurfer` and “No waveform data” (first pass). Trace no-match `ev_40d28c5e0a6b8376e0b7945939dd98492fe8f63f8f148b486c52d040f654705a`. | Empty and filled waveform states exist as strings. | Graph of the waveform widget was not traced. |
| Hear a file at another speed | Literal `playbackRate` and `preservesPitch` on an HTML media element (local scan). Trace no-match `ev_8a70126bdcd8ffcf74d959dd4252fa2ce172ee1d27ce32dbf2aa26ad50c58c67`. | Media playback can change rate and keep pitch. | Not a semitone practice shifter. Metronome exact token ×0. |
| Watch the song while playing | Unknown. No `youtube`, `<video`, or `HTMLVideoElement`. | — | Unknown — do not plan from this. |
| Save or bounce the mix | Unknown. `export` / `download` / `bounce` tokens are false friends (deeper pass). | — | Unknown — do not plan from this. |
| Record mic or interface into the project | Observed listen `audio-capture:port` in `out/preload/webview.cjs`. `ev_01e435c65a35fb7b277d7133bee5327f05c0fa416f0e8361289212f4a1fb595a`. | Capture is off the studio bundle. | Sample rate, channel count, and `audify.node` exports Unknown. |
| Open a file into the app | Observed document types (first pass) + `import:consume` handler location inferred on `ev_2e54eb00…`. | OS can hand the app an audio file. | MIDI types are not a MIDI editor. |
| Plugins, lyrics, mastering, voice studio | Observed plugin IPC (first pass + candidate map). Menu asset names. | A bigger studio product. | Out of scope. Non-goal only. |

## 3. Parity matrix (Moises job × Desktop × Hosted)

| Job | Moises | Desktop (path) | Hosted (path) | Verdict |
| --- | --- | --- | --- | --- |
| Several mixes open | Observed tab IPC | Home, one tab per mix, plus, close (click and Delete). `ui/mix_tabs_component/frontend/src/main.ts` | One isolate page, no mix-tab strip. `web/src/pages/IsolatePage.tsx` | Desktop partial. Hosted absent — product decision, not an automatic port. |
| Duplicate a mix / close a side / reorder | Observed + inferred map | Those actions are absent in `main.ts` (only `home`, `plus`, `close`). | Absent | Desktop partial. Hosted absent (same decision). |
| Mute / solo | Literal, law Unknown | Solo wins over mute. `ui/stem_mixer_component/frontend/src/main.ts` `effectiveGains` | Same rule. `web/src/mixer/engine.ts` `effectiveGains`; UI `web/src/components/StemMixer.tsx` | Similar. We already picked a law. Do not swap it for an unknown Moises law. |
| Track loudness | One output gain, scale Unknown | Per-stem dB, master dB, per-stem `createGain` (`main.ts` 282, 536) | Per-stem `createGain` (`engine.ts` 357, 574), dB −25..25 | We already do this. Moises scale Unknown, so no “ahead” claim. |
| Pan | Literal name, law Unknown | No pan | No pan | Absent on both. |
| Parent / collapse row | Literal names, summing Unknown | No parent row | No parent row | Absent on both. |
| Waveform | Literal strings | SVG peaks. `main.ts` `waveformSeekHtml` | No stem waveform. Trim only: `web/src/components/RegionPicker.tsx` | Desktop similar. Hosted partial (trim only). |
| Metronome clicks | Exact token ×0. Unknown | Click synth. `ui/stem_mixer_component/frontend/src/metronomeClicks.ts` | Stem label + mute id `metronome`. `IsolatePage.tsx`, `engine.ts` `DEFAULT_MUTED_STEMS`. No click synth. | We already do this on desktop; Moises side Unknown. Hosted partial. Do not remove desktop clicks. |
| Speed / key | Media `playbackRate` / `preservesPitch` only | Rate 0.5–1.5, key −6..6. `ui/stem_mixer_component/frontend/src/practice.ts` | Same clamps. `web/src/mixer/practice.ts`, UI in `StemMixer.tsx` | Ahead. Do not remove. |
| Picture sync | Unknown | YouTube or local picture. `ui/pages/isolate.py`; `main.ts` `pictureSeekDecision` | No picture | We already do this on desktop; Moises side Unknown. Do not plan from Moises. |
| Save mix | Unknown | Save current mix, including speed and key. `main.ts` save copy. Build on save, not on every fader (`docs/ui-issues.md` I-607, implemented-in-code). | `StemMixer.tsx` `downloadMix` → `engine.ts` `bounceMix` (`OfflineAudioContext` ~848) writes `current_mix.wav`, plus a per-stem wav link. | We already do this; Moises side Unknown. Do not plan a Moises bounce. |
| Live input | Observed port listen, format Unknown | No live input | No live input | Out of scope until a product decision to record. |
| Open a file | Observed types + inferred `import:consume` | `st.file_uploader` in `ui/pages/isolate.py` | `<input type="file">` + `api.uploadAudio` in `web/src/pages/IsolatePage.tsx` | Similar for “pick a file.” Partial for “OS opens the app onto a new mix.” |
| Plugins / lyrics / mastering / voice studio | Observed IPC and menu names | None | None | Out of scope. |

## 4. Opportunities (similar-not-same)

### 4.1 Desktop: more than one mix without going home

- Musician job: duplicate the current mix, close every mix except this one, and drag mixes into the order they practice.
- Why Moises feels strong: the shell owns that list (Observed IPC). The button-to-channel step is only the candidate map on `ev_2e54eb00…`.
- Our approach: extend the strip with our own actions (`duplicate`, `close_others`, `close_right`, `reorder` by drag or keyboard). Home stays the separate/upload step. Labels and layout stay the strip we already have (Home | mixes | +). This touches **three** desktop surfaces, not one: the iframe in `ui/mix_tabs_component/` (`frontend/src/main.ts`, `style.css`, then `make mix-tabs-build`), the click handler in `ui/pages/isolate.py` (`_render_moises_tab_strip`, `_close_mix_tab`), and the tab-list state in `ui/isolate_state.py` (`MIX_TAB_ACTIONS`, `close_open_mix_tab`, new helpers).
- We will NOT copy Moises channel names, drag IPC, context menus, or preview windows.
- Evidence: Observed tab operations; Inference for the member map. Effort S–M. Risk: low product-boundary; Streamlit reruns must keep tab state. Priority **P0 desktop only**. Hosted has no multi-mix shell; do not invent one in this item.

### 4.2 Both mixers: a pan knob with our law

- Musician job: move a stem left or right while practicing.
- Why Moises feels strong: a component named `PanControl` exists (Literal). The law was not recovered.
- Our approach: add a pan control on the desktop stem row (`ui/stem_mixer_component/`) and, separately, on `web/src/components/StemMixer.tsx` + `web/src/mixer/engine.ts`. Use one law we write down (equal-power or linear). Same numbers, two engines. Do not unify Desktop Lite with hosted `lite`.
- We will NOT copy `PanControl`, its CSS module, or an unseen pan law.
- Evidence: Literal name; law Unknown so the law is ours. Effort M per surface. Risk: Unknown-law risk is avoided by defining ours; desktop-vs-hosted split means two patches. Priority **P0 desktop, P1 hosted** (hosted already has per-stem gain; pan is the missing control, not a new engine).

### 4.3 Desktop: a collapsible group row that does not pretend to be a bus

- Musician job: tuck related stems (for example drums) so the row list stays short.
- Why Moises feels strong: `isParentTrack` sits next to a toggle (Literal). Summing is Unknown.
- Our approach: a disclosure row in the desktop mixer that shows or hides child stems. Gain stays on the children. No parent fader until we choose a bus on purpose.
- We will NOT copy the parent-track class names or invent a Moises subgroup mix.
- Evidence: Literal. Effort M. Risk: Unknown summing — mitigated by not summing. Priority **P1 desktop**. Hosted later only if the desktop row proves useful.

### 4.4 Desktop: OS hands a file to Isolate Home

- Musician job: double-click an audio file and land in a new mix tab.
- Why Moises feels strong: the app registers audio document types and consumes a pending import (Observed types; inferred handler).
- Our approach: desktop “open with” / drop that creates a mix tab and runs the existing Isolate upload path. MIDI types do not add a MIDI editor.
- We will NOT copy `import:consume` or the Moises document-type list verbatim into UI copy.
- Evidence: Observed plist types; Inference on handler location. Effort L (packaging). Risk: installer/document-handler scope, not the mixer graph. Priority **P1 desktop**. Hosted already uploads in the browser.

## 5. Explicit non-goals

- VST, plugin server, lyrics, mastering, voice-studio, updater, theme IPC, window chrome. Different product.
- Solo law, pan law, and fader scale taken from Moises. Unknown — do not plan from this. Our solo rule stays “solo wins.”
- Moises picture sync or a Moises mix bounce. Unknown. Substring hits for `audioworklet`, `bounce`, `download`, and `export` are false friends (deeper pass).
- Removing desktop picture, metronome clicks, or speed/key. We are ahead there.
- Live capture and `audify.node`. Format and exports Unknown. Only if the product later means “record into a project.”
- Unifying Desktop Interface Lite with hosted processing mode `lite`.
- Cloning the Moises tab IPC shape. Section 4.1 is the user job only.
- Rebuilding export on every fader. I-607 stays save-on-save.

## 6. Recommended planning sequence

1. Desktop tab actions across `ui/mix_tabs_component/` + `ui/pages/isolate.py` + `ui/isolate_state.py`: duplicate, close others, close to the right, reorder (drag and keyboard). Home stays put. After editing the iframe source run `make mix-tabs-build`; verify with `python -m pytest tests/test_mix_tabs_component.py tests/test_isolate_state.py -q`.
2. Desktop pan knob with a written law in `ui/stem_mixer_component/`. After editing run `make mixer-build`; verify with `python -m pytest tests/test_stem_mixer_component.py -q`.
3. Hosted pan knob in `StemMixer.tsx` / `engine.ts` using that same law. Verify with `cd web && npm test` and `cd web && npx tsc --noEmit` (CI runs neither; run them yourself).
4. Desktop collapsible group row, hide/show only. Same rebuild and verify as step 2.
5. Desktop OS open-with into Isolate Home, after the tab actions exist so the new mix has somewhere to land. Packaging scope — ask the owner before starting.

The planning pass wrote no code. Implementation follows this order; hashed `frontend/build/` output comes only from the make targets.

## 7. Open questions

- Product decision (blocks hosted tabs only): should the website grow a multi-mix strip, or stay one job per page? This plan does not add hosted tabs until that is yes.
- Product decision (blocks live input only): is “record into a project” a goal? If no, leave section 2’s capture row alone.
- Not blocking: pan law and parent summing. We define pan ourselves. The group row does not sum. More REA is not required for items 1–4.
- OS open-with (step 5) is in. The desktop app offers Open With for the audio and video types Isolate Home already accepts. It does not become the default player, and it does not register MIDI. Opening a file queues it (`AUDIO_TOOLS_PENDING_OPEN`) and Isolate Home stages a copy on a new tab. Dropping a file onto the Dock or taskbar icon is the same path. A drop onto the window interior is not a separate gesture.

## 8. Design constraints for the next implementer

These are interaction rules, not a Moises layout. Desktop is a pointer-and-keyboard app (Streamlit plus the mixer iframes). Hosted is the React mixer. Navigation and controls stay familiar. Do not restyle the mixer to look like a native Mac app, and do not copy Moises chrome.

The signature stays the stem rows (waveform, mute, solo, level). New controls sit on that row. Do not add a second visual system.

### Tabs (`ui/mix_tabs_component/`)

- Home and each mix are panes of one strip. A control inside a mix (mute, solo, level, pan) changes only that mix. State stays on the open tab in `ui/isolate_state.py`; `ui/pages/isolate.py` is what applies the action. The iframe only sends it.
- Plus, duplicate, close, close others, and close to the right are buttons, not tabs. A tab switches the pane. A button does a job.
- Tab labels are the mix name (noun), title case, at least 13 px. Truncate with the full name on hover. Do not put a verb on a tab.
- The strip scrolls when there are many mixes. Do not replace it with a menu, and do not cap the product at six mixes. Six is a native tab-view limit that does not fit this job.
- Close is not the accent button. The visible control is at least 20×20 px (28×28 preferred), with an accessible name that includes the mix title. Pressed state is visible.
- Drag reorder moves the tab in the same strip. It does not copy. Offer the same reorder from the keyboard (move left / move right). A bad drop returns the tab to where it was. Home does not drag.

### Pan and level

- Pan is a horizontal slider. Silence or full left is the leading end. Full right is the trailing end. Center is zero and easy to hit. Show the value in text (for example “L 20”, “C”, “R 20”), not by color alone.
- Moving the thumb changes the sound while it moves. Do not wait for save.
- The slider adjusts this stem against the others. It does not change the Mac or browser system volume, and it does not answer play/pause media keys.
- Hosted uses the same law and the same words. On a narrow screen, put the value under the slider instead of clipping it. Touch target at least 44×44 px on the hosted page.

### Group row

- A group is a disclosure triangle on the leading edge of a row, not a second fader. The label is the group name. The triangle points leading when closed and down when open. Children indent under it.
- Several groups may each have a triangle. Do not use one disclosure button for the whole mixer.

### Already on the row

- Mute and solo stay visible as letters or words, not as color alone. Do not restyle them to match Moises.
- Save stays an explicit action. Do not move the only save control to the bottom edge of a long stem list where a short window cuts it off.
- dB readouts and tab titles stay at least 13 px. No thin or light weight under that size. Text on the row needs 4.5:1 against its background. Do not ship a new color until that ratio is measured.

## 9. Gap matrix after FULL-TEARDOWN (2026-10-18)

Facts from `FULL-TEARDOWN.md`. Build calls stay in this plan. Unknown is not a feature.

| Job | Source | Ours | Verdict |
| --- | --- | --- | --- |
| Duplicate, close others, close right, reorder | Teardown §5.4; plan §4.1 | `ui/mix_tabs_component/frontend/src/main.ts`; handlers in `ui/pages/isolate.py` | Already |
| Pan control | Teardown §9.3 name only; law unknown | `pan.ts` both mixers; equal-power is ours | Already |
| Group / parent row, no sum | Teardown §9.3 `isParentTrack`; summing unknown | Desktop disclosure in `main.ts` `groupHtml`; no parent fader | Already |
| Open a file into a new mix | Teardown §13 | `ui/opened_audio.py`, launcher, macOS plist, Windows Open With. Not default player. No MIDI | Already |
| Mute, solo, level | Plan §3 | Both mixers; solo wins | Already |
| One audible mix | Teardown §10.8 | One mixer iframe. Switching mixes replaces it, so two mixes do not play together | Already |
| Same mix stays mounted across reruns | Plan / `mixer_component_key` | Key is stable per run (`ui/isolate_state.py`). A Streamlit rerun of that run does not remount | Already |
| Switch back to another mix with no re-decode | Teardown §10.1 (native views stay alive) | A different run gets a new component key, so the iframe remounts and decodes again | Out of scope. Keeping decoded stems for every open tab is their multi-view shell. It would hold extra PCM against the 8–16 GB desktop floor. Not an Electron port |
| Hover preview, cross-window drag, New Project menu of five products | Teardown §6–§7 | Our strip has no preview window and one Isolate product | Out of scope (chrome / other products) |
| Dark window until ready, short chrome animations | Teardown §10.4–§10.6 | Streamlit + pywebview shell | Out of scope (their window chrome) |
| Session restore of remote URLs | Teardown §5.8 | Open tabs live in the Streamlit session, not a `tabs.json` of hosted routes | Out of scope (their hosted-tab model) |
| Live capture | Teardown §11 | None | Stop and ask |
| VST / lyrics / mastering / voice studio / Play | Teardown §7, §12 | None | Stop and ask |
| Hosted multi-mix strip | Plan §7 | `web/src/pages/IsolatePage.tsx` is one job | Stop and ask |
| Bake pan into the saved desktop mix | Not in teardown (bounce unknown) | Playback pans; `mix_stems_to_wav` does not | Stop and ask |
| Pan law, parent sum, solo law, fader scale, capture format | Teardown §17 | Our solo rule and pan law stay ours | Unknown — do not build |
