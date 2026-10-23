# Moises desktop — agent reference

Read this before changing the desktop Isolate mixer or the Home | mix | + strip. Research only. Do not copy Moises source, assets, channel names, or menu art into the product. When you build from this note, follow `COMPETITIVE-INSPIRATION-PLAN.md`, including section 8 (design constraints). That plan, not the “Do” lines below, sets priority and interaction. Where this note is ambiguous, the deeper-pass text wins: a parent / group row does **not** sum (gain stays on the children), and substring hits for `audioworklet`, `bounce` (it was `debounceTime`), `download`, and `export` are false friends, not Moises features. Evidence sections below stay as captured; nothing was deleted.

Captured 2026-10-17 from `/Applications/Moises.app` **2.0.3** (build `2609048vfr0p5is`) with REA `rea-agents` 6.5.0. The app was not launched. `audify.node` was not disassembled. Topic split of the same notes: `README.md`, `mixer-ux.md`, `architecture.md`, `gaps-vs-audio-tools.md`, `evidence-index.md`.

Label every claim:

- **Observed** — REA graph, plist, fuse, or inventory.
- **Literal** — a short string counted in a file REA parsed. Renderer UI words are literals. Feature traces on that bundle returned no-match and do not index ordinary strings. No-match is not absence.
- **Inference** — a conclusion from those facts.
- **Unknown** — do not build a feature from this.

## What Moises is

**Observed.** Electron app (`NSPrincipalClass` `AtomApplication`), ToDesktop id `com.todesktop.220410vabqjud82`, package name `moises-desktop`, main `./out/main/index.js`. ASAR sha256 `8c244bb62ecd4725625225b8edccdc4f56bb5e9831a2e48776349979acb20827` (22,408,285 bytes). Electron Framework is arm64. Fuses: `RunAsNode` on, `EnableNodeCliInspectArguments` on, `EnableEmbeddedAsarIntegrityValidation` off, `OnlyLoadAppFromAsar` off. Helpers on disk: GPU, Plugin, Renderer. Frameworks on disk: Electron, Squirrel, Mantle, ReactiveObjC.

**Observed.** Renderer HTML title is `Moises Studio`. It mounts `#root` from one Vite bundle, `out/renderer/assets/index-CiDG_8MY.js` (1,528,413 bytes, sha256 `791aa79ee729023a10a2d39c18ba717f63dea91ea4c5de29ef0d93fec7759f00`), plus `index-bDi2iXqb.css`.

**Inference.** This is a studio host (several tools in one shell), not a native mixer. The mixer UI is inside that one bundle. Stem playback is not an IPC feature.

## Our product (do not confuse the two)

Desktop Isolate is Streamlit: `ui/pages/isolate.py`, tab strip `ui/mix_tabs_component/`, live mixer `ui/stem_mixer_component/` (Web Audio). We already have Home | mix | +, per-stem mute/solo/dB, master, mute-all, clear-solo, presets, speed/key, metronome, waveforms, and an optional synced picture (YouTube or local file). Export is “Save current mix,” not a write on every fader (`docs/ui-issues.md` I-607). The hosted `web/` mixer is a different surface. Desktop Interface Lite and hosted processing mode `lite` are different products.

## Priorities for us

### P0 — tab strip

**Observed.** Main process owns tabs. Renderer literal `electronAPI.tab` occurs 15 times. Bridge members: create, duplicate, close, closeOthers, closeRight, activate, reorder, getAll, onUpdated, showPreview, hidePreview, showContextMenu, showNewMenu. Drag: start, end, indicator, released, drop-index. New-tab menu: show, hide, ready, select, close. UI literals: `Home`, `New Tab`, `Close tab`.

**Ours.** Home, one tab per mix, plus, close. No duplicate, close-others, or drag-reorder.

**Do.** Drag-reorder, duplicate a mix, close others / close to the right. Keep Home as the separate/upload step.

### P0 — track row

**Literal (renderer).** `TrackHeader`, `TrackControlButton`, `TrackControlsToggle`, `PanControl`, `Input gain`, `No waveform data`, `isParentTrack`, plus CSS-module names for mute, solo, pan, record, `autoMute`, `waveformContainer`. Counts: `mute` 31, `solo` 8, `record` 8, `wavesurfer` 6, `AudioContext` 2, `createGain` 1, `audioworklet` 2, `WebAudio` 3. Do not count the substring `pan` (it matches unrelated words).

**Ours.** Mute, solo (any solo mutes the rest), per-stem dB, master dB, waveforms, metronome, speed/key. No pan, record arm, or parent/child row.

**Do.** Pan, and a parent row that groups stems. Record-arm and input gain belong with live capture (P1), not offline stem playback. Do not remove our picture, metronome, or speed/key. Those were not found as Moises features.

### P1 — live input

**Observed.** Utility service `MoisesAudioCapture`. Module expression joins dirname with `audio-capture-host.js`. That file’s literals: `audify.node`, `rtaudio`, `pcm`, `devices`, `prebuilds`, `darwin-arm64`, `win32-x64`. Bridge `electron.audioCapture`: open, close, listDevices, onClosed. Channels include `audio-capture:port`. Plist mic text says recording goes into Studio projects (mic and audio interface). Native handoff `audify.node` status `requires-provider-analysis`. Adjacent dylibs: `librtaudio`, `libopus`.

**Inference.** PCM capture runs off the UI process. The port channel is likely the sample stream. Sample rate and channel count are unknown. The renderer bundle has **zero** `audioCapture` literals, so the on-screen capture page is unknown.

**Do.** Only if the product grows from “separate a file” to “record into a project.”

### P1 — open a file into a tab

**Observed.** Plist document types: mp3, mp2, wav, m4a, aac, flac, ogg, opus, wma, amr, caf, mid, midi. Bridge `electron.consumePendingImportFile` pairs with `import:consume`.

**Do.** “Open with” / drop onto a new mix tab, wired to Isolate Home. MIDI types are not a reason to add a MIDI editor.

### P2 — leave alone

VST / plugin server (`vst-host:connection`, `plugin:install`, `plugin-server:*`, literals “VST plugins are available to Studio.” / “VST plugins are disabled.”). Menu assets `lyrics`, `mastering`, `play`, `sparkbars`, `voice-studio`. Their updater, theme IPC, and window chrome.

### Unknown — do not build from these

Synced video or a YouTube picture inside Moises (no `youtube`, `<video`, or `HTMLVideoElement` literal; the word `video` occurs twice). Mix bounce (`Could not export image` is not a stem bounce; `download` ×6 and `bounce` ×1 are ambiguous). Solo law, pan law, fader scale. Whether a track is a separation stem or a recording (no `vocals` / `drums` / `guitar` literals). Which BrowserWindow loads which preload. `audify.node` exports.

## Process model

```
Electron main  out/main/index.js   sha256 965b14e606db812d7bb864abaa0861d954b8fe4973b7a1ea6b70c4a1454f41ec
  BrowserWindow A   contextIsolation expression !0, nodeIntegration expression !1
                    (!0 / !1 are minified true / false). Preload path not recorded.
  BrowserWindow B   webPreferences dynamic
  utility MoisesAudioCapture → audio-capture-host.js → audify / RtAudio, PCM
  plugin server + vst-host:connection   IPC only

Renderer  out/renderer/index.html → index-CiDG_8MY.js
  electronAPI.tab literal ×15
  Web Audio literals only (not a traced graph)
```

Shell graph: 2 windows, 2 context bridges, 62 exposed members, 53 literal IPC channels, 42 renderer transmissions all paired, 0 dynamic channels, 1 utility process. Sender-validation observations: 0. That does not prove checks are absent. The two graphs (shell and renderer) were analyzed separately. The link from bundle `electronAPI.tab` to preload handlers is an inference from the matching name.

Package dependencies seen in `package.json` text (the graph node kept only name, version, main): `@electron-toolkit/utils`, `@expo/sudo-prompt`, `@moises-ai/plugin-server` 0.8.23, `@sentry/electron`, `@todesktop/runtime`, `axios`, `extract-zip`. `"type": "module"`. Node `>=22.12.0`.

## Bridges and channels

`electron` (14 members): `audioCapture.open`, `audioCapture.close`, `audioCapture.listDevices`, `audioCapture.onClosed`, `checkVersionReleased`, `checkVersionUser`, `consumePendingImportFile`, `getVstHostConnection`, `installPlugin`, `onPausePlayback`, `setShouldPreventNavigation`, `signOut`, `updateDesktopApp`.

`electronAPI` (48 members): `drag.start|end|onIndicator|onReleased|reportDropIndex`, `newTabMenu.close|onHide|onShow|ready|select`, `platform`, `pluginServer.getConnection|getStatus|onStatus|restart|start|stop`, `tab.activate|close|closeOthers|closeRight|create|duplicate|getAll|hidePreview|onUpdated|reorder|showContextMenu|showNewMenu|showPreview`, `theme.get|onChanged`, `updates.check|getState|install|onDownloaded`, `window.close|isMaximized|maximize|minimize|onMaximizedChanged`.

All 53 literal channels:

`app:set-should-prevent-navigation`, `app:update-desktop-app`, `audio-capture:close`, `audio-capture:closed`, `audio-capture:devices`, `audio-capture:open`, `audio-capture:port`, `auth:sign-out`, `desktop:pause-playback`, `drag:drop-index`, `drag:end`, `drag:indicator`, `drag:released`, `drag:start`, `import:consume`, `new-menu:close`, `new-menu:hide`, `new-menu:ready`, `new-menu:select`, `new-menu:show`, `plugin-server:connection`, `plugin-server:restart`, `plugin-server:start`, `plugin-server:status`, `plugin-server:stop`, `plugin:check-version-release`, `plugin:check-version-user`, `plugin:install`, `tab:activate`, `tab:close`, `tab:close-others`, `tab:close-right`, `tab:context-menu`, `tab:create`, `tab:duplicate`, `tab:get-all`, `tab:new-menu`, `tab:preview-hide`, `tab:preview-show`, `tab:reorder`, `tabs:updated`, `theme:changed`, `theme:get`, `updates:check`, `updates:downloaded`, `updates:get-state`, `updates:install`, `vst-host:connection`, `window:close`, `window:is-maximized`, `window:maximize`, `window:maximized-changed`, `window:minimize`.

## Paths inside the ASAR

`out/main/index.js` (56,101 bytes), `out/main/audio-capture-host.js` (2,686), `out/preload/index.cjs`, `out/preload/webview.cjs`, `out/renderer/index.html`, `out/renderer/assets/index-CiDG_8MY.js`, `native/rtaudio/prebuilds/darwin-arm64/audify.node` plus `librtaudio` and `libopus`, `resources/menu/*`. Unpacked copies of the native addon and `@moises-ai/plugin-server*` live in `app.asar.unpacked`.

## Evidence IDs

| ID | Supports |
| --- | --- |
| `ev_fdf1916866a1193308c106bff4ecbac2ed443fb691b67754cb7108512e353b68` | Info.plist |
| `ev_b4632266ee9f932130ad7c3d0821df5746fbdfb3d6ec6f3eb343070941f89476` | Electron fuses |
| `ev_821d0e0379fc6925be313ea1aa8d4e1bf9acc53e0daf4adb498bb23540dbb979` | ASAR inventory parent (2,439 nodes, 3,069 occurrences) |
| `ev_27b2845be5ce90d53cd3ef4fe65dc93925b562fcdae1f48441eae60e9744eb75` | Inventory summary, 2,627 integrity contradictions |
| `ev_9a885801fde41fed9a9d0365f742b19b3d298ef658b0570fab29e8e017ea9b18` | `out/` paths and menu icon names |
| `ev_1303704624046edc027d7eebe579f3a51128cc19088b7bfc19a2161cefb25427` | `extract_artifact` — **bad bytes**, do not use |
| `ev_f6a179ca062019ce3b6147c56cfa1d54cb1bd2415f6d089c51726f917a39b2b0` | Raw-ASAR read of main is `invalid-utf8` |
| `ev_a4fd45e52e469e27263d328a8cfa26e4aed12d7a9a8a87ad984b66fd5ccb23f9` | Shell JS graph (corrected tree) |
| `ev_e68c209a31baa04c2b2ee848c54b5d1d66745adddb7fa5aaa76952a5699dc504` | Shell summary |
| `ev_81155c7f82b5cf26d4dbf887fdef28fefb647f3a219e03a14764e05fb137962a` | Preload trace, `electronAPI` |
| `ev_3d2461cf4ba559a2db9e83c275d007b7a475a2ff70aeb1f06c8a6004808b924d` | Two `BrowserWindow`s |
| `ev_5a4a99a0c2342efc78f28b59d2e9ea87c6fa1371b5e60937771f3ee45c9d103a` | `audio-capture` trace: channels, utility, audify handoff |
| `ev_8a3f6afa08a8e6e31134240f32660950f5fe3f9954170382dc7bceabe4b46539` | `preload` trace |
| `ev_76eb70fa0b5d543458710184e883df04d554fc71fc0e485443a52221e90f45c2` | `utilityProcess` string **no-match** |
| `ev_f0edea166e00ad7c08e38342a91ec8eb769a96e9614f3ebcddd339ee47bb8b40` | Renderer graph: 174,448 AST nodes, 0 IPC findings, ~34k semantic unknowns |
| `ev_d8cded18300672c1cd7ce97f2a8fa619d24ccba24cdc567384677ab2fe3447da` | Renderer summary |
| `ev_ac5e291577dfb124c31f7e563eb2fda76814b761506e953039b2a3cd5f1827cd` | `TrackHeader` **no-match** |
| `ev_f89377b724fae536d67ff03677bc44c1c744fb7706ec389cbbb50760ec3d26bc` | `AudioContext` string **no-match** |
| `ev_f0f5127c741241b2b5125e62224934418cca55999bef4cb937e199c43f2db198` | `AudioContext` api **no-match** |
| `ev_50046ae9261de5d1569b09e206de9bfc89c7494a3bfe868a2a92e54f93ff25af` | `No waveform data` **no-match** |

Ignore raw-ASAR analyses `ev_b9b7ae1d…` and `ev_c0d8c0ae…` (0 JS files parsed). `recover_javascript_sources` was unavailable. Ghidra was not configured.

## If you re-run REA

REA 6.5.0 `extract_artifact` on this ASAR writes every file as a slice that **starts at the archive header**. Inventory paths and sizes are fine. The 2,627 hash mismatches are those bad slices versus header hashes, not a tamper finding (the integrity fuse is off).

Re-slice outside the repo (this pass used `/tmp/moises-asar-fixed`, directory digest `45ad32479631200eb21e5bb2837d354fcfe57d65ecbce61be48c756d897e651c`): 8-byte size pickle, header pickle, then payloads at `offset`/`size`. `unpacked` files are in `app.asar.unpacked`. Then `analyze_javascript_application` with `format: "directory"` and `detail: "summary"`. Shell `source_paths`: `package.json`, `out/main/index.js`, `out/main/audio-capture-host.js`, `out/preload/index.cjs`, `out/preload/webview.cjs`, `out/renderer/index.html`. Renderer bundle separately; this pass set `max_semantic_nodes_per_file` to 150000. Do not commit the extracted tree or REA JSON (trace dumps contain minified expressions).

## Deeper pass — 2026-10-17

Same app on disk: **2.0.3**, build `2609048vfr0p5is`. Corrected tree `/private/tmp/moises-asar-fixed` still has directory digest `45ad32479631200eb21e5bb2837d354fcfe57d65ecbce61be48c756d897e651c` and main sha256 `965b14e606db812d7bb864abaa0861d954b8fe4973b7a1ea6b70c4a1454f41ec`. Stack inventory was not repeated. `audify.node` was not disassembled. Nothing in this section replaces the notes above.

### What changed

**Observed.** Shell graph re-parsed (`ev_1344baa7ffdd5e3d9c0fbefe978bf1af81d2a7318025e0dbb740f06779f15d4c`, summary `ev_e8839921efbfb2e1cda16f217c0d1fed02566dc534f5895cf87a8afe5ac29490`): 4 JS files, 18,470 AST nodes, 177 findings, 2 windows, 2 bridges, 62 members, 53 literal channels, 42 paired renderer transmissions, 0 dynamic channels, 1 utility. Same shape as the first shell graph.

**Observed.** `audio-capture:port` is a renderer-side `listen` in `out/preload/webview.cjs` (resolution `literal`, `ev_01e435c65a35fb7b277d7133bee5327f05c0fa416f0e8361289212f4a1fb595a`). Outgoing trace has no further edge, so the sender and the sample format stay unknown. `desktop:pause-playback` handlers in that same preload are on the `tab:create` walk (`ev_2e54eb001ccfb0467d561f4bbac91b8ca3ef0ac1d1bb52b3a498b47e9dc3e99d`), evidence state inferred. That is why the studio bundle has zero `audioCapture` literals: the capture listener is the webview preload, not `index-CiDG_8MY.js`.

**Observed.** Renderer re-parse (`ev_981b32d0a71080b39dae414e904f7e03e6b1865281a92db35a9c82e51f63fa0f`, summary `ev_c1cb3ff14b6c221705b3a4a2b081e6108624d273a613e0e30e0a9d340f006c4c`) read the same bundle (module item `ev_46db80d8df79d3988f0e957b315d84d68e20c71ae7c00874f35e8d6deb2f484b`, sha256 `791aa79ee729023a10a2d39c18ba717f63dea91ea4c5de29ef0d93fec7759f00`, 174,448 AST nodes, 0 exports). The semantic graph was dropped: every family retained 0 relations because the graph exceeded the parent result budget. Traces on that parent are no-match and are not absence.

**Inference.** Forty-two `maps_to` edges on `ev_2e54eb00…` bind a bridge member to a channel string. Every one is `resolution: candidate`, evidence state inferred, confidence high. The channel string is an exact match. The wiring is not an observed call. `contextBridge` as an API seed was no-match (`ev_888ed8c6ba50c637107b94c64947ac49cb84a7add259780caba925dc05bd5b6b`) even though the bridge nodes exist.

Candidate pairs (inference only):

- `electron.audioCapture.open|close|listDevices` → `audio-capture:open|close|devices`
- `electron.checkVersionReleased|checkVersionUser` → `plugin:check-version-release|plugin:check-version-user`
- `electron.consumePendingImportFile` → `import:consume`
- `electron.getVstHostConnection` → `vst-host:connection`
- `electron.installPlugin` → `plugin:install`
- `electron.setShouldPreventNavigation` → `app:set-should-prevent-navigation`
- `electron.signOut` → `auth:sign-out`
- `electron.updateDesktopApp` → `app:update-desktop-app`
- `electronAPI.drag.start|end|reportDropIndex` → `drag:start|end|drop-index`
- `electronAPI.newTabMenu.close|ready|select` → `new-menu:close|ready|select`
- `electronAPI.pluginServer.getConnection|getStatus|restart|start|stop` → `plugin-server:connection|status|restart|start|stop`
- `electronAPI.tab.activate|close|closeOthers|closeRight|create|duplicate|getAll` → `tab:activate|close|close-others|close-right|create|duplicate|get-all`
- `electronAPI.tab.hidePreview|showPreview|showContextMenu|showNewMenu|reorder` → `tab:preview-hide|preview-show|context-menu|new-menu|reorder`
- `electronAPI.theme.get` → `theme:get`
- `electronAPI.updates.check|getState|install` → `updates:check|get-state|install`
- `electronAPI.window.close|isMaximized|maximize|minimize` → `window:close|is-maximized|maximize|minimize`

Six `sends` edges add `pairing_basis: unique-exact-literal-channel` and name `out/main/index.js` operation `on` (still inferred): `tab:preview-hide`, `tab:preview-show`, `new-menu:ready`, `new-menu:close`, `new-menu:select`, `drag:drop-index`.

Channels with no `maps_to` edge: `audio-capture:closed`, `audio-capture:port`, `desktop:pause-playback`, `drag:indicator`, `drag:released`, `new-menu:hide`, `new-menu:show`, `tabs:updated`, `theme:changed`, `updates:downloaded`, `window:maximized-changed`. Listener members (`onClosed`, `onPausePlayback`, `onIndicator`, `onReleased`, `onHide`, `onShow`, `onStatus`, `onUpdated`, `onChanged`, `onDownloaded`, `onMaximizedChanged`) and `platform` are not in the candidate map. Do not invent those pairs.

### Playback literals the graph could not trace

Traces no-match: `createGain` API `ev_95e31ca8b609bbc38eac74b529798c6c854e263788ba6a9b959ef2c1b89cc0bb`, `wavesurfer` `ev_40d28c5e0a6b8376e0b7945939dd98492fe8f63f8f148b486c52d040f654705a`, `AudioWorklet` API `ev_5108164d8aca640d412401464ddc673eb407a35587373665af4b6038ee852c1a`, `PanControl` `ev_25a3f7988d232a7e89db49b406fee5fe1ac8d59fef2109cdfcd8e59e7ac5a597`, `preservesPitch` `ev_8a70126bdcd8ffcf74d959dd4252fa2ce172ee1d27ce32dbf2aa26ad50c58c67`.

**Literal (local exact-token scan of the file REA hashed above, not a graph fact).** The first-pass counts are substrings. Exact tokens on the same bytes:

- `createGain` ×1, beside `audioContext`, `gainNode`, `connect`, `destination`. `GainNode` ×0, `StereoPannerNode` ×0, `createStereoPanner` ×0, `OfflineAudioContext` ×0, `AudioWorklet` ×0, `getUserMedia` ×0, `MediaRecorder` ×0.
- `audioworklet` ×2 sits in a `modulepreload` switch with `paintworklet`, `serviceworker`, `sharedworker`, and `worker`. That is not an audio worklet graph.
- `preservesPitch` ×1 sits on `media.playbackRate`. `playbackRate` also appears as a media-element getter next to `volume`, `muted`, and `seeking`.
- `PanControl` ×1 is a React `displayName`. `isParentTrack` sits next to `toggleOpenButton` and CSS `_pan_`.
- Whole word `video` ×4: an HTML tag switch (`iframe` / `object` / `embed` / `video` / `audio`), a CSS `where video`, and `canPlayType` next to the same `gainNode`. Still no `youtube`, `<video`, or `HTMLVideoElement`.
- Whole word `export` hits are CommonJS `exports`. Whole word `download` ×1 is an HTML attribute case; other substring hits are `updates.onDownloaded`. The single `bounce` hit is `debounceTime`.

**Inference.** The studio bundle shows one gain into `destination`, a named pan component, and a parent row that can toggle open. It does not show a per-stem gain graph, a pan law, a solo law, an audio worklet, or a mix bounce. Speed/pitch here is HTML media `playbackRate` / `preservesPitch`, not a practice shifter.

### Feature matrix

Moises cells use the labels above. Our cells are the current repo, not a plan.

| Feature | Moises | Desktop Isolate | Hosted web |
| --- | --- | --- | --- |
| Tabs | Observed IPC create, duplicate, close, close others, close right, reorder, drag (`ev_2e54eb00…` candidate map) | Home, one mix tab, plus, close. `ui/mix_tabs_component/frontend/src/main.ts` | No mix-tab strip. Upload is `web/src/pages/IsolatePage.tsx` |
| Mute | Literal `mute` (first pass). Law unknown | Any-solo wins, else mute. `ui/stem_mixer_component/frontend/src/main.ts` `effectiveGains` | Same rule. `web/src/mixer/engine.ts` `effectiveGains`; UI `web/src/components/StemMixer.tsx` |
| Solo | Literal `solo`. Law unknown | Solo wins over mute. Same `effectiveGains` | Same `effectiveGains` |
| Volume | Literal one `createGain` to `destination` (local scan). Fader scale unknown | Per-stem dB and master dB; `createGain` at `main.ts` 282 and 536 | Per-stem `createGain` at `web/src/mixer/engine.ts` 357 and 574. dB range −25..25 |
| Pan | Literal `PanControl` displayName (local scan). Law unknown. Trace no-match | No pan | No pan |
| Parent tracks | Literal `isParentTrack` plus `toggleOpenButton` (local scan). Audio grouping unknown | No parent row | No parent row |
| Waveform | Literal `wavesurfer` and `No waveform data` (first pass). Trace no-match | SVG peaks. `main.ts` `waveformSeekHtml` | No stem waveform. Trim uses wavesurfer in `web/src/components/RegionPicker.tsx` |
| Metronome | Exact token ×0. Unknown | Click synth. `ui/stem_mixer_component/frontend/src/metronomeClicks.ts` | Stem label only. `web/src/pages/IsolatePage.tsx`. Engine can mute id `metronome` (`engine.ts` `DEFAULT_MUTED_STEMS`). No click synth |
| Speed / key | Literal `playbackRate` and `preservesPitch` on an HTML media element (local scan). Not a semitone shifter | Rate 0.5–1.5, key −6..6. `ui/stem_mixer_component/frontend/src/practice.ts` | Same clamps. `web/src/mixer/practice.ts`. UI in `StemMixer.tsx` |
| Picture / video sync | Unknown. No `youtube` or `<video`. `video` hits are a tag switch, CSS, and `canPlayType` | YouTube or local picture, offset, drift. `ui/pages/isolate.py`; sync in `main.ts` `pictureSeekDecision` | No picture |
| Save / export | Unknown. `export` / `download` / `bounce` tokens are not a stem bounce (local scan) | Save current mix, including speed and key. `main.ts` save copy. `docs/ui-issues.md` I-607 | `StemMixer.tsx` `downloadMix` writes `current_mix.wav` via `engine.bounceMix` (`OfflineAudioContext` at `engine.ts` 848) plus a per-stem wav link |
| Live input | Observed listen on `audio-capture:port` in `webview.cjs` (`ev_01e435c6…`). Format unknown. `audify.node` exports unknown | No live input | No live input |
| File open | Observed `import:consume` on `out/main/index.js` (handler location inferred, `ev_2e54eb00…`). Plist types in the first pass | `st.file_uploader` in `ui/pages/isolate.py` | `<input type="file">` and `api.uploadAudio` in `web/src/pages/IsolatePage.tsx` |
| Plugins | Observed `plugin-server:*`, `plugin:install`, `vst-host:connection` (first pass and candidate map) | None | None |

### Already ours, real gaps, leave alone

**Already ours.** Desktop and hosted both mute, solo (solo wins), and set per-stem plus master dB with a real per-stem `createGain`. Both have speed and key. Desktop also has the tab strip, waveforms, metronome clicks, and a synced picture. Hosted already bounces the current mix to a wav. Neither product is missing a gain engine.

**Real gap.** Desktop tabs do not duplicate, close others, close to the right, or drag-reorder. Those Moises channels are observed IPC, and the member-to-channel step is only the candidate map above. A pan control and a collapsible parent row exist as names in the Moises bundle. The pan law and whether the parent sums audio are unknown, so the gap is the control, not a copied law. OS “open with” into a tab is `import:consume`; our upload paths already open a file, they do not register as the document handler.

**Do not build.** VST, the plugin server, lyrics, mastering, and voice-studio. Do not add live capture unless the product is meant to record into a project; the port listener does not say sample rate or channel count. Do not remove our picture, metronome, or speed/key. Do not treat `audioworklet`, `bounce`, `download`, or `export` substring hits as features. Solo law, pan law, fader scale, and `audify.node` exports stay unknown.

### New evidence

| ID | Supports |
| --- | --- |
| `ev_981b32d0a71080b39dae414e904f7e03e6b1865281a92db35a9c82e51f63fa0f` | Renderer graph, semantic relations dropped |
| `ev_c1cb3ff14b6c221705b3a4a2b081e6108624d273a613e0e30e0a9d340f006c4c` | Renderer summary, 174,448 AST nodes, 0 findings |
| `ev_46db80d8df79d3988f0e957b315d84d68e20c71ae7c00874f35e8d6deb2f484b` | Renderer module item, same sha256 as the first pass |
| `ev_95e31ca8b609bbc38eac74b529798c6c854e263788ba6a9b959ef2c1b89cc0bb` | `createGain` API **no-match** |
| `ev_40d28c5e0a6b8376e0b7945939dd98492fe8f63f8f148b486c52d040f654705a` | `wavesurfer` **no-match** |
| `ev_5108164d8aca640d412401464ddc673eb407a35587373665af4b6038ee852c1a` | `AudioWorklet` API **no-match** |
| `ev_25a3f7988d232a7e89db49b406fee5fe1ac8d59fef2109cdfcd8e59e7ac5a597` | `PanControl` **no-match** |
| `ev_8a70126bdcd8ffcf74d959dd4252fa2ce172ee1d27ce32dbf2aa26ad50c58c67` | `preservesPitch` **no-match** |
| `ev_1344baa7ffdd5e3d9c0fbefe978bf1af81d2a7318025e0dbb740f06779f15d4c` | Shell graph, second pass |
| `ev_e8839921efbfb2e1cda16f217c0d1fed02566dc534f5895cf87a8afe5ac29490` | Shell summary |
| `ev_2e54eb001ccfb0467d561f4bbac91b8ca3ef0ac1d1bb52b3a498b47e9dc3e99d` | `tab:create` walk: 42 candidate `maps_to` edges, webview handlers |
| `ev_888ed8c6ba50c637107b94c64947ac49cb84a7add259780caba925dc05bd5b6b` | `contextBridge` API **no-match** |
| `ev_01e435c65a35fb7b277d7133bee5327f05c0fa416f0e8361289212f4a1fb595a` | `audio-capture:port` listen in `webview.cjs` |

## Additional REA pass — 2026-10-18

Same file on disk. The app was not launched. No product code was changed. Nothing in this section replaces the notes above.

**Observed.** `/Applications/Moises.app` is still **2.0.3**, build `2609048vfr0p5is`, bundle id `com.todesktop.220410vabqjud82` (`ev_5de8df69d34d4b8c4ec3dc5d35e42fd975bbca387d2ff799202560146299c329`). `app.asar` is still sha256 `8c244bb62ecd4725625225b8edccdc4f56bb5e9831a2e48776349979acb20827`, 22,408,285 bytes (`ev_b4fdd2b294e003540dd6206109e4bb2cc97103c87023f9ed27a73b5f5d20029e`, parent `ev_ef930cb8ecdec6aced82744dea7f9b327754a84a1f8a0c2c941c06b334a80943`). Electron fuse evidence is the same record as the first pass (`ev_b4632266ee9f932130ad7c3d0821df5746fbdfb3d6ec6f3eb343070941f89476`): `EnableEmbeddedAsarIntegrityValidation` off, `OnlyLoadAppFromAsar` off, `EnableNodeCliInspectArguments` on. Mach-O `Contents/MacOS/Moises` sha256 `656bc2bf6e534131ebba8eea9b3ef7103de4a8eb0b987f3f4b5b8442b98a3298` (arm64).

**Observed.** Document types are the same thirteen extensions (mp3, mp2, wav, m4a, aac, flac, ogg, opus, wma, amr, caf, mid, midi). Each entry is `CFBundleTypeRole` `Editor` and `LSHandlerRank` `Default` (`ev_5de8df69…`). The plist also stores `ElectronAsarIntegrity` for `Resources/app.asar`, algorithm SHA256, hash `115091fa1bdb581aa52de673834d13053cc166c21f73dc0c362f4f50a9e63826`. That string is not the whole-file sha256 above.

**Observed.** Direct `analyze_javascript_application` on the ASAR, `integrity_policy` `record-and-continue`, six shell paths only, parsed **0** JavaScript files (`invalid_utf8_files` 6, `parsed_javascript_files` 0, 2,448 files unselected). Coverage is partial. The summary view lists 2,634 integrity limitations and omits 2,612 of them. This is the same raw-ASAR read problem as the first pass. The corrected tree was not rebuilt. Zero parsed files is not “the mixer is gone.”

**Inference.** The archive bytes match the 2026-10-17 capture, so the earlier shell graph, candidate channel map, and renderer token scan still describe this build. The embedded plist hash and the whole-file hash are different measurements. With the integrity fuse off, that difference is not a tamper finding. What the embedded hash covers is unknown.

**No new Observed musician job.** Tabs, pan, a parent/group row, mute/solo/gain, and open-with are already in the sections above. This pass did not see a new channel, a pan law, a parent sum, a solo law, or a mix bounce.

**Ours, compared only.** Desktop Isolate now has the jobs the plan already accepted from those notes: tab duplicate, close others, close to the right, and reorder; a pan slider whose law is ours; a disclosure group that does not sum; and OS open-with into a new Home tab. Our document list is the Home uploader’s audio and video types, rank Alternate, and it does not include MIDI. Moises’s Editor/Default rank and its MIDI types stay Moises. Do not copy that rank, those extra audio types, or a MIDI editor.

**Unknown — still do not build from these.** Pan law, whether a parent row sums, solo law, fader scale, `audify.node` exports, sample format on `audio-capture:port`. Camera, Bluetooth, and the short “audio capture” usage strings are in the plist (`ev_5de8df69…`); whether a screen uses them is unknown.

| ID | Supports |
| --- | --- |
| `ev_5de8df69d34d4b8c4ec3dc5d35e42fd975bbca387d2ff799202560146299c329` | Info.plist again: version, document roles, embedded ASAR hash |
| `ev_b4632266ee9f932130ad7c3d0821df5746fbdfb3d6ec6f3eb343070941f89476` | Same fuse record as the first pass |
| `ev_ef930cb8ecdec6aced82744dea7f9b327754a84a1f8a0c2c941c06b334a80943` | ASAR analysis parent; bytes marked untrusted; 0 JS files parsed |
| `ev_b4fdd2b294e003540dd6206109e4bb2cc97103c87023f9ed27a73b5f5d20029e` | Summary of that parent |

## Teardown correction — 2026-10-18

`FULL-TEARDOWN.md` §9.4 supersedes the inference that the local renderer mounts the mixer. The shell draws tabs and settings. Studio pages are hosted. Mixer names in the bundle are unmounted shared source. This note does not delete the Evidence IDs above. What to build stays in `COMPETITIVE-INSPIRATION-PLAN.md`, including the §9 gap matrix.
