# Mixer and studio UX

What a user can do, from static evidence only. The app was not launched. Labels below are **observations** (REA graph or a literal in a file REA parsed), **inferences**, or **unknowns**.

**Correction.** Track-row inferences in this file describe shared bundle source. [FULL-TEARDOWN.md](FULL-TEARDOWN.md) §9.4 shows those components are not mounted by the desktop shell. The on-screen studio is hosted.

## Shell the user sees

**Observation.** `out/renderer/index.html` is the renderer entry. Its title is `Moises Studio`, and it mounts `#root` from one Vite asset, `out/renderer/assets/index-CiDG_8MY.js`, plus one CSS asset. REA resolved that HTML as the electron renderer (`electron-renderer`, mechanism `html-script-entrypoint`) in trace `ev_5a4a99a0c2342efc78f28b59d2e9ea87c6fa1371b5e60937771f3ee45c9d103a`.

**Observation.** Menu icon paths in the ASAR inventory (`ev_9a885801fde41fed9a9d0365f742b19b3d298ef658b0570fab29e8e017ea9b18`) name `lyrics`, `mastering`, `play`, `sparkbars`, and `voice-studio` (dark/light `@2x` pairs). The same three words `lyrics`, `mastering`, and `voice-studio` each occur in the renderer bundle.

**Inference.** The desktop app is a studio host with more than one tool, not only a stem mixer. Which icon is the default screen is unknown.

**Observation (plist `ev_fdf1916866a1193308c106bff4ecbac2ed443fb691b67754cb7108512e353b68`).** The bundle registers as an editor for many audio types plus `mid` / `midi`. The microphone usage text says recording goes into Studio projects (mic and audio interface).

## Tabs, Home, library chrome

**Observation (preload bridge, shell graph).** `contextBridge` key `electronAPI` exposes a `tab` object:

| Member | IPC channel |
| --- | --- |
| `create` | `tab:create` |
| `duplicate` | `tab:duplicate` |
| `close` | `tab:close` |
| `closeOthers` | `tab:close-others` |
| `closeRight` | `tab:close-right` |
| `activate` | `tab:activate` |
| `reorder` | `tab:reorder` |
| `getAll` | `tab:get-all` |
| `onUpdated` | `tabs:updated` |
| `showPreview` / `hidePreview` | `tab:preview-show` / `tab:preview-hide` |
| `showContextMenu` | `tab:context-menu` |
| `showNewMenu` | `tab:new-menu` |

Drag reporting is separate: `drag:start`, `drag:end`, `drag:indicator`, `drag:released`, `drag:drop-index`, exposed as `electronAPI.drag.*`. A new-tab menu uses `new-menu:show|hide|ready|select|close`.

**Observation (renderer literals, same file REA parsed, sha256 `791aa79ee729023a10a2d39c18ba717f63dea91ea4c5de29ef0d93fec7759f00`).** `electronAPI.tab` occurs 15 times. Short UI literals include `Home`, `New Tab`, `Close tab`. Radix-style names `Tabs`, `Tabs.List`, `Tabs.Trigger`, `Tabs.Content` are present. Trace seeds `TrackHeader`, `AudioContext`, and `No waveform data` on the renderer graph returned **no-match** (`ev_ac5e291577dfb124c31f7e563eb2fda76814b761506e953039b2a3cd5f1827cd`, `ev_f89377b724fae536d67ff03677bc44c1c744fb7706ec389cbbb50760ec3d26bc`, `ev_50046ae9261de5d1569b09e206de9bfc89c7494a3bfe868a2a92e54f93ff25af`). Those traces do not index ordinary bundle literals.

**Inference.** Home and mix-like documents are tabs managed by the main process. The renderer asks the shell to create, reorder, and preview them. A second `BrowserWindow` exists (`ev_3d2461cf4ba559a2db9e83c275d007b7a475a2ff70aeb1f06c8a6004808b924d`); whether it is the tab preview or the new-tab menu is unknown.

**Unknown.** Library as a named screen. The word `library` was not a meaningful UI literal. `SliderLibrary` in the bundle is a component name, not proof of a media library.

## Track list, mute, solo, volume

**Observation (renderer literals).** One occurrence each of `TrackHeader`, `TrackControlButton`, `TrackControlsToggle`, `PanControl`, `Input gain`, `No waveform data`. CSS-module-style names include mute, solo, pan, record, `autoMute`, `isParentTrack`, `trackControls`, `waveformContainer`. Counts in that file: `mute` 31, `solo` 8, `record` 8, `wavesurfer` 6, `AudioContext` 2, `createGain` 1, `audioworklet` 2, `WebAudio` 3. The substring `pan` is too common to count (it matches unrelated words).

**Inference.** A track row can mute, solo, pan, and arm record, and can sit under a parent track. Waveforms are a first-class empty state (“no waveform data”), and the audio engine in the page is Web Audio (context, gain, worklet) with wavesurfer present as a string. This pass did **not** recover the gain graph, solo-bus rule, or fader scale.

**Unknown.** Stem names (`vocals`, `drums`, `guitar`, and similar) do not appear as literals. Whether tracks are separation stems, recorded inputs, or both is unknown from this bundle. Per-track volume might be the gain node, a fader component whose name we did not isolate, or both.

## Video / sync

**Observation.** The renderer bundle has no literal `youtube`, `<video`, or `HTMLVideoElement`. The word `video` occurs twice, which is too weak to describe a picture.

**Unknown.** Synced video, YouTube embed, and offset. Absence of those literals is not proof the feature is missing (another chunk, or `createElement`).

## Export / save mix

**Observation.** Shell bridge `electron.consumePendingImportFile` pairs with IPC `import:consume`. A renderer literal `Could not export image` exists. `download` occurs 6 times and `bounce` once; both are ambiguous.

**Unknown.** Mix bounce, stem download, and “save current mix.” Image export failure text is not a mixdown pipeline. OS document open is supported (plist types); how a dropped file becomes a tab is only the `import:consume` channel.

## Live input (next to the mixer, not the faders)

**Observation.** Second bridge key `electron` exposes `audioCapture.open`, `audioCapture.close`, `audioCapture.listDevices`, `audioCapture.onClosed`. Channels: `audio-capture:open`, `close`, `closed`, `devices`, `port`. Utility service name `MoisesAudioCapture`. The host file’s literals include `audify.node`, `rtaudio`, `pcm`, `devices`, `prebuilds`, `darwin-arm64`, `win32-x64`.

**Inference.** The user can pick an input device and capture PCM on a utility process, with a port channel that likely carries the stream. The renderer bundle contains **zero** `audioCapture` literals, so which page calls it is unknown. It may be a window this pass did not fully connect.

**Observation.** `VST plugins are available to Studio.` and `VST plugins are disabled.` are renderer literals. Shell channels include `vst-host:connection`, `plugin:install`, `plugin-server:start|stop|status|restart`.

**Unknown.** Whether a plugin sits on a mixer track, and the enable/disable rule. Static text is not the runtime policy.
