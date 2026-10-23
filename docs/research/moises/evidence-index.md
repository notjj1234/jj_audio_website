# Evidence index

REA `rea-agents` **6.5.0**. Session looked at `/Applications/Moises.app`. No runtime attach, no Frida, no Ghidra (`not_configured`). `audify.node` was not disassembled.

Claims in the other notes cite these IDs. A **no-match** trace is not evidence of absence.

## Identity

| ID | Tool | What it supports |
| --- | --- | --- |
| `ev_fdf1916866a1193308c106bff4ecbac2ed443fb691b67754cb7108512e353b68` | `inspect_plist` | Electron plist, version 2.0.3, document types, mic usage text |
| `ev_b4632266ee9f932130ad7c3d0821df5746fbdfb3d6ec6f3eb343070941f89476` | `inspect_electron_fuses` | arm64 Electron Framework fuses; integrity fuse off; inspect arguments on |
| `open_binary` result (no separate evidence id in the ack) | `open_binary` | ASAR format, sha256 `8c244bb62ecd4725625225b8edccdc4f56bb5e9831a2e48776349979acb20827` |

## Inventory (paths and sizes only)

| ID | Tool | What it supports |
| --- | --- | --- |
| `ev_821d0e0379fc6925be313ea1aa8d4e1bf9acc53e0daf4adb498bb23540dbb979` | `inspect_artifact` parent | Full inventory, `record-and-continue` |
| `ev_27b2845be5ce90d53cd3ef4fe65dc93925b562fcdae1f48441eae60e9744eb75` | summary view | 2439 nodes, 3069 occurrences, 2627 integrity contradictions |
| `ev_e57490dbd0c72854d38c524a44b75c5fd8bad6c41c880d12b7df627561b672a2` | occurrences page 0 | `.npmrc`, `assets`, `build`, `native/rtaudio`, start of `node_modules` |
| `ev_9a885801fde41fed9a9d0365f742b19b3d298ef658b0570fab29e8e017ea9b18` | occurrences at offset 3029 | `out/main`, `out/preload`, `out/renderer`, `package.json`, menu icon names |
| `ev_c9c162fe3fd41f7195dc2c4eb7512dcfe599d1636517b8a70f56b98fe1a33998` | integrity page | Sample contradictions (`.npmrc`, icon, entitlements plist) |
| `ev_1303704624046edc027d7eebe579f3a51128cc19088b7bfc19a2161cefb25427` | `extract_artifact` | Extraction root under `$TMPDIR`. **Bytes are wrong** (each file starts with the ASAR header). Do not analyze that tree. |

## Shell graph (corrected tree, then REA)

Directory `/tmp/moises-asar-fixed` (not in git). REA digest of that directory: `45ad32479631200eb21e5bb2837d354fcfe57d65ecbce61be48c756d897e651c`.

| ID | Tool | What it supports |
| --- | --- | --- |
| `ev_a4fd45e52e469e27263d328a8cfa26e4aed12d7a9a8a87ad984b66fd5ccb23f9` | `analyze_javascript_application` parent | `package.json`, main, audio-capture host, both preloads, renderer HTML. 4 JS files parsed, 18,470 AST nodes, 2 windows, 62 bridge members, 53 channels |
| `ev_e68c209a31baa04c2b2ee848c54b5d1d66745adddb7fa5aaa76952a5699dc504` | summary view of that parent | Counts above; coverage partial because other files were not selected |
| `ev_81155c7f82b5cf26d4dbf887fdef28fefb647f3a219e03a14764e05fb137962a` | `trace_application_feature` | Preload module outgoing: `electronAPI` tab/drag/theme/window/updates/pluginServer and their channels |
| `ev_3d2461cf4ba559a2db9e83c275d007b7a475a2ff70aeb1f06c8a6004808b924d` | trace `BrowserWindow` | Two constructions. Window A: `contextIsolation` `!0`, `nodeIntegration` `!1`. Window B: dynamic webPreferences |
| `ev_5a4a99a0c2342efc78f28b59d2e9ea87c6fa1371b5e60937771f3ee45c9d103a` | trace `audio-capture` | 53 channels, utility `MoisesAudioCapture`, `audify.node` handoffs, package node, renderer HTML entry |
| `ev_8a3f6afa08a8e6e31134240f32660950f5fe3f9954170382dc7bceabe4b46539` | trace `preload` | Same channel set; 4 seed matches |
| `ev_76eb70fa0b5d543458710184e883df04d554fc71fc0e485443a52221e90f45c2` | trace `utilityProcess` | **no-match** (the code uses another spelling). Utility fact comes from the audio-capture trace instead |
| `ev_e502c03db622b4059126bfee85adcda5fcbee763c35220bc74f8a66fa4c2ba5e` | module item | One `audio-capture-host.js` node is only the `node:path` import. The file was still parsed (shell stats) |
| `ev_f6a179ca062019ce3b6147c56cfa1d54cb1bd2415f6d089c51726f917a39b2b0` | module item on the **broken** ASAR analysis `ev_c0d8c0ae…` | `out/main/index.js` `text_status: invalid-utf8` when read from the ASAR directly |

Bridge member lists (62 = 14 on `electron` + 48 on `electronAPI`) are properties of the context-bridge nodes inside `ev_5a4a99a0…`.

## Renderer graph

| ID | Tool | What it supports |
| --- | --- | --- |
| `ev_f0edea166e00ad7c08e38342a91ec8eb769a96e9614f3ebcddd339ee47bb8b40` | `analyze_javascript_application` | Bundle only. 1 file, 1,528,413 bytes, 174,448 AST nodes, 0 Electron IPC findings, partial semantic graph |
| `ev_d8cded18300672c1cd7ce97f2a8fa619d24ccba24cdc567384677ab2fe3447da` | summary view | Those counts |
| `ev_ac5e2915…`, `ev_f89377b7…`, `ev_50046ae9…`, `ev_f0f5127c…` | traces | `TrackHeader`, `AudioContext` (string and api), `No waveform data`: **no-match** |

Renderer file sha256 `791aa79ee729023a10a2d39c18ba717f63dea91ea4c5de29ef0d93fec7759f00`. UI words (`TrackHeader`, `PanControl`, `Input gain`, `No waveform data`, `electronAPI.tab` ×15, `wavesurfer` ×6) are **literal counts in that file**, not trace hits. Label them that way.

## Failed or unused routes

- First `analyze_javascript_application` calls on the raw ASAR (`ev_b9b7ae1d…`, `ev_c0d8c0ae…`) read the files as invalid UTF-8 and parsed 0 JS files. Ignore them for behavior.
- `recover_javascript_sources` is unavailable (needs Wakaru on Linux).
- Native providers cannot open an ASAR. `audify.node` stays a handoff.
- Renderer and shell were analyzed as **two** graphs. Edges from `electronAPI.tab` in the bundle to the preload handlers were not linked by REA. The link is an inference from matching names plus the literal `electronAPI.tab` in the bundle.

## Unknowns still open

- Which `BrowserWindow` loads which preload.
- Capture sample rate, channel count, and the page that calls `audioCapture` (0 hits in the renderer bundle).
- Mute/solo/pan law and the Web Audio graph.
- Video sync and mix bounce.
- `audify.node` exports.
- Behavior of lyrics / mastering / voice-studio beyond icon names and short literals.
