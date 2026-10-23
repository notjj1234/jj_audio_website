# Architecture

Static only. Nothing here was executed. Moises source is not copied into this repo.

**Read with [FULL-TEARDOWN.md](FULL-TEARDOWN.md) §9.4.** The renderer bundle contains mixer component source, but the shipped desktop shell does not mount it. Studio UI is a hosted page.

## Stack

| Fact | Evidence | Status |
| --- | --- | --- |
| App bundle `/Applications/Moises.app` | Filesystem layout plus REA | Observed |
| Electron: `NSPrincipalClass` `AtomApplication`, `ElectronAsarIntegrity` for `Resources/app.asar` | plist `ev_fdf1916866a1193308c106bff4ecbac2ed443fb691b67754cb7108512e353b68` | Observed |
| Version 2.0.3, build `2609048vfr0p5is`, id `com.todesktop.220410vabqjud82` | same plist; package node name `moises-desktop`, version `2.0.3`, main `./out/main/index.js` in `ev_5a4a99a0…` | Observed |
| Electron Framework arm64, fuse wire version 1 | `ev_b4632266ee9f932130ad7c3d0821df5746fbdfb3d6ec6f3eb343070941f89476` | Observed |
| `RunAsNode` enabled, `EnableNodeCliInspectArguments` enabled, `EnableEmbeddedAsarIntegrityValidation` disabled, `OnlyLoadAppFromAsar` disabled | same fuse record | Observed. Not used to attach a debugger. |
| ASAR sha256 `8c244bb62ecd4725625225b8edccdc4f56bb5e9831a2e48776349979acb20827`, 22,408,285 bytes, 2439 nodes / 3069 occurrences | `open_binary` + inventory parent `ev_821d0e0379fc6925be313ea1aa8d4e1bf9acc53e0daf4adb498bb23540dbb979` | Observed |
| Helpers: GPU, Plugin, Renderer; frameworks Electron, Squirrel, Mantle, ReactiveObjC | Directory listing | Observed layout, not REA-decompiled |
| `node_modules` includes `@electron-toolkit/utils`, `@sentry/*`, `electron-updater`, `@moises-ai/plugin-server-darwin-arm64` | Inventory pages | Observed paths |
| Package dependencies named in `package.json` text: `@electron-toolkit/utils`, `@expo/sudo-prompt`, `@moises-ai/plugin-server` 0.8.23, `@sentry/electron`, `@todesktop/runtime`, `axios`, `extract-zip`. `"type": "module"`. Node `>=22.12.0` | File text of the tree REA then analyzed. The package **graph node** only retained name, version, and `main` | File observation; not a graph edge |

**Not native UI.** Hopper/Ghidra do not analyze the ASAR. The native pieces are the Electron shell and `audify.node`.

## Paths that matter

```
app.asar
  package.json
  out/main/index.js                 # electron main, 56,101 bytes
  out/main/audio-capture-host.js    # utility entry, 2,686 bytes
  out/preload/index.cjs             # contextBridge
  out/preload/webview.cjs
  out/renderer/index.html
  out/renderer/assets/index-CiDG_8MY.js   # 1,528,413 bytes, studio UI
  out/renderer/assets/index-bDi2iXqb.css
  native/rtaudio/prebuilds/darwin-arm64/audify.node
  native/rtaudio/prebuilds/darwin-arm64/librtaudio*.dylib
  native/rtaudio/prebuilds/darwin-arm64/libopus*.dylib
  resources/menu/                   # lyrics, mastering, play, sparkbars, voice-studio
app.asar.unpacked
  native/rtaudio/...                # unpacked native builds
  node_modules/@moises-ai/plugin-server*
```

Main-file sha256 after a correct slice, and the sha256 on the BrowserWindow observation, are the same: `965b14e606db812d7bb864abaa0861d954b8fe4973b7a1ea6b70c4a1454f41ec`.

## Process model

```
Electron main (out/main/index.js)
  ├─ BrowserWindow A  contextIsolation expression !0, nodeIntegration expression !1
  │     webPreferences are an object literal; preload path not recorded
  ├─ BrowserWindow B  webPreferences dynamic (contents unknown)
  ├─ utility process  service name MoisesAudioCapture
  │     module expression joins dirname + "audio-capture-host.js"
  │     literals: audify.node, rtaudio, pcm, devices
  └─ plugin server / VST host   IPC only in this pass
        channels plugin-server:* and vst-host:connection

Renderer (Vite bundle, not Electron IPC inside the bundle graph)
  HTML entry → #root
  calls electronAPI.tab (literal, 15 times)
  Web Audio literals: AudioContext, createGain, audioworklet, wavesurfer
```

Shell analysis `ev_a4fd45e52e469e27263d328a8cfa26e4aed12d7a9a8a87ad984b66fd5ccb23f9`: 2 browser windows, 2 context bridges, 62 exposed members, 53 literal IPC channels, 42 renderer transmissions all paired with main handlers, 0 dynamic channel operations, 1 utility process, 0 resolved utility entrypoints in the summary (the entry expression is on the utility node in the later trace). Sender validation observations: 0. That does not prove checks are absent.

**Inference.** `!0` / `!1` are minified `true` / `false`, so window A isolates context and does not turn on Node in the page. Preload files exist; which window loads `out/preload/index.cjs` is **not** on the BrowserWindow node (`preload_path` null, and omitted prefs are not defaults).

**Inference.** `audio-capture-host.js` is the utility module, because the service expression names that file and the file’s literals are the capture addon. REA did not mark the utility entry as resolved.

**Unknown.** `audify.node` exports. Native handoff status `requires-provider-analysis` (`ev_5a4a99a0…`). Ghidra is not configured here. No decompile was run.

## Data flow (as far as static IPC goes)

**Tabs / chrome.** Renderer `electronAPI.tab|drag|theme|window|updates|pluginServer` → literal channels → main handlers. Pairing is unique for the 42 renderer transmissions in the shell summary (no ambiguous, no unpaired literal transmissions).

**Import.** `electron.consumePendingImportFile` → `import:consume`. Document types on the plist are the OS-facing list.

**Capture.** `electron.audioCapture.open|close|listDevices|onClosed` → `audio-capture:*`, including `audio-capture:port`. Host literals say PCM and devices. **Inference:** audio samples leave the utility process through a port, not only through JSON IPC. The byte format, sample rate, and channel count are unknown.

**Plugins.** `plugin-server:*` plus `plugin:install` and `vst-host:connection`. A `MoisesPluginServer` binary is named under `node_modules/@moises-ai/plugin-server-darwin-arm64`. It was not executed or disassembled.

**Stem playback / mix.** Not in the IPC map. The renderer graph (`ev_f0edea166e00ad7c08e38342a91ec8eb769a96e9614f3ebcddd339ee47bb8b40`) parsed the bundle (174,448 AST nodes, 0 Electron findings, 0 IPC). Semantic relations are large and partial (about 34k semantic unknowns). Feature traces for UI strings returned no-match, so the mix graph (buffer → gain → destination, mute/solo law) stays unknown.

## Integrity note

`inspect_artifact` recorded 2,627 integrity contradictions (`ev_c9c162fe3fd41f7195dc2c4eb7512dcfe599d1636517b8a70f56b98fe1a33998` is the first page). Extracted members all began with the ASAR header, so those “mismatches” compare the wrong bytes to the header hash. Do not treat the app as tampered on that basis. The integrity fuse is off, so Electron is not enforcing that check anyway.
