# Moises function inventory — 2026-10-23

Chains below are from the shipped preload and main sources that REA parsed (`ev_2015286d22cfc4a62451bbee9e1c1ca624e084e78ff6c80bf01cfaa20162ab93`). They were **not executed** in a visible window. Runtime result of each call is UNKNOWN unless noted. Blocker: fullscreen on the primary display, and hosted pages require login.

REA summary for that evidence: 140 IPC operations, 68 literal channels, 0 dynamic channels, 54 renderer transmissions all paired, 51 main handlers, 35 renderer listeners, 2 context-bridge APIs, 79 exposed members, 2 browser windows, 1 utility process, 0 sender-validation observations.

The 79-versus-68 gap: 68 methods are named in the two preloads. REA's member count is 79. The other 11 members were not listed in the summary view. **Unresolved: 11 bridge members.**

## T1 — shell bridge methods

`electronAPI` in `out/preload/index.cjs` (SHA-256 `c5650c0d6a45331bdd57c3fd8ef011bab31cf90109116b9596206c4f316b714f`).

| ID | Action | Channel | Kind |
|---|---|---|---|
| F-001 | Create tab | `tab:create` | invoke |
| F-002 | Close tab | `tab:close` | invoke |
| F-003 | Activate tab | `tab:activate` | invoke |
| F-004 | Reorder tabs | `tab:reorder` | invoke |
| F-005 | Duplicate tab | `tab:duplicate` | invoke |
| F-006 | Close other tabs | `tab:close-others` | invoke |
| F-007 | Close tabs to the right | `tab:close-right` | invoke |
| F-008 | Read tabs | `tab:get-all` | invoke |
| F-009 | Tab context menu | `tab:context-menu` | invoke |
| F-010 | New-product menu | `tab:new-menu` | invoke |
| F-011 | Show tab preview | `tab:preview-show` | send |
| F-012 | Hide tab preview | `tab:preview-hide` | send |
| F-013 | Tabs changed | `tabs:updated` | on |
| F-014 | New menu ready | `new-menu:ready` | send |
| F-015 | New menu select | `new-menu:select` | send |
| F-016 | New menu close | `new-menu:close` | send |
| F-017 | New menu show | `new-menu:show` | on |
| F-018 | New menu hide | `new-menu:hide` | on |
| F-019 | Memory panel ready | `memory-panel:ready` | send |
| F-020 | Memory panel close | `memory-panel:close` | send |
| F-021 | Memory panel open | `memory-panel:open` | invoke |
| F-022 | Memory panel show | `memory-panel:show` | on |
| F-023 | Memory panel hide | `memory-panel:hide` | on |
| F-024 | Memory auto-open | `memory-panel:auto-open` | on |
| F-025 | Memory icon visibility | `memory-icon:visible` | on |
| F-026 | Memory chrome state | `memory-chrome:state` | invoke |
| F-027 | Consume memory auto-open | `memory-chrome:consume-auto-open` | invoke |
| F-028 | Drag start | `drag:start` | invoke |
| F-029 | Drag end | `drag:end` | invoke |
| F-030 | Drag drop index | `drag:drop-index` | send |
| F-031 | Drag indicator | `drag:indicator` | on |
| F-032 | Drag released | `drag:released` | on |
| F-033 | Minimize | `window:minimize` | invoke |
| F-034 | Maximize | `window:maximize` | invoke |
| F-035 | Close window | `window:close` | invoke |
| F-036 | Is maximized | `window:is-maximized` | invoke |
| F-037 | Maximized changed | `window:maximized-changed` | on |
| F-038 | Plugin server status | `plugin-server:status` | invoke and on |
| F-039 | Plugin server start | `plugin-server:start` | invoke |
| F-040 | Plugin server stop | `plugin-server:stop` | invoke |
| F-041 | Plugin server restart | `plugin-server:restart` | invoke |
| F-042 | Plugin server connection | `plugin-server:connection` | invoke |
| F-043 | Update state | `updates:get-state` | invoke |
| F-044 | Check for updates | `updates:check` | invoke |
| F-045 | Install update | `updates:install` | invoke |
| F-046 | Update downloaded | `updates:downloaded` | on |
| F-047 | Is signed in | `auth:is-signed-in` | invoke |
| F-048 | Auth changed | `auth:changed` | on |
| F-049 | Get theme | `theme:get` | invoke |
| F-050 | Theme changed | `theme:changed` | on |
| F-051 | Platform value | none | `process.platform` exposed, no IPC |

`window.electron` in `out/preload/webview.cjs` (SHA-256 `ca97c93b63dc95a005d52f1aa426a5bb78ed9bff224b6cc67c125910c2b4d993`). This bridge is for hosted pages.

| ID | Action | Channel | Kind |
|---|---|---|---|
| F-052 | Plugin version, release | `plugin:check-version-release` | invoke |
| F-053 | Plugin version, user | `plugin:check-version-user` | invoke |
| F-054 | Install plugin | `plugin:install` | invoke |
| F-055 | Update desktop from page | `app:update-desktop-app` | invoke |
| F-056 | Prevent navigation | `app:set-should-prevent-navigation` | invoke |
| F-057 | Consume pending import | `import:consume` | invoke |
| F-058 | VST host connection | `vst-host:connection` | invoke |
| F-059 | Start VST host | `plugin-server:start` then `plugin-server:connection` | invoke |
| F-060 | Sign out | `auth:sign-out` | invoke |
| F-061 | Set auth state | `auth:state` | send |
| F-062 | Pause playback | `desktop:pause-playback` | on |
| F-063 | Capture capabilities | `audio-capture:capabilities` | invoke |
| F-064 | List capture devices | `audio-capture:devices` | invoke |
| F-065 | Open capture | `audio-capture:open` | invoke |
| F-066 | Close capture | `audio-capture:close` | invoke |
| F-067 | Capture closed | `audio-capture:closed` | on |
| F-068 | Capture devices changed | `audio-capture:devices-changed` plus `audio-capture:watch` | on / invoke |

T1 discovered 68, classified 68, runtime-executed 0. Blocker on every runtime cell: window not walked.

## T2 — integrations

The 68 channel names are the Channel column of F-001 through F-068, plus `audio-capture:port` which the capture host posts and which is not a preload method. That set is 68 names if `plugin-server:status` is one channel used as both invoke and listener, and `audio-capture:port` replaces the double-count. REA's literal channel count is 68. The names above plus `audio-capture:port` are the named set. A name-by-name join against REA's channel list was **not** exported (the summary view has counts only). **Unresolved: proof that the 68th REA channel is exactly `audio-capture:port`.**

| ID | Integration | Evidence |
|---|---|---|
| F-069 | `https://studio.moises.ai` | OBSERVED in main and in the persisted Home tab |
| F-070 | `https://studio-stage.moises.ai` | OBSERVED literal in main. Not requested. |
| F-071 | `https://plugins.moises.ai` | OBSERVED literal in main |
| F-072 | ToDesktop feed `https://download.todesktop.com/220410vabqjud82/latest.yml` | OBSERVED 200, version 2.1.0, build `261021a1gygumpb` |
| F-073 | Sentry ingest | OBSERVED host in main. Key redacted. Not called. |
| F-074 | Login with Google, Facebook, Apple, X | OBSERVED buttons. Not clicked. |
| F-075 | Capture utility `parentPort` messages `devices`, `open`, `close`, `watch` | OBSERVED in `audio-capture-host.js` |
| F-076 | Page message `moises-desktop:audio-capture-port` | OBSERVED in webview preload |

No authenticated XHR, WebSocket, or SSE was captured. Those rows are not invented.

T2 discovered 76 rows (68 channels represented by F-001–F-068 and F-075/F-076 covering the utility, plus F-069–F-074). Classified 76. Live responses: only F-072.

## T3 — modules

Counting method: `function` keywords plus `=>` tokens. This is an inventory of syntax tokens, not a named export table. REA `statistics.modules` was 0 for the shell parse.

| Module | Bytes | Token count | REA parsed | Named analysis |
|---|---:|---:|---|---|
| `out/main/index.js` | 66147 | 414 | yes | IPC and route literals read. Other functions not named. |
| `out/main/audio-capture-host.js` | 5211 | 37 | yes | Host protocol read. |
| `out/main/chunks/capture-apis-J4FdMrZ-.js` | 659 | 9 | yes | API map read. WASAPI default on win32. ASIO and CoreAudio present. |
| `out/preload/index.cjs` | 4105 | 79 | yes | Full bridge read. |
| `out/preload/webview.cjs` | 1961 | 24 | yes | Full bridge read. |
| `out/renderer/index.html` | 936 | 0 | metadata | Full file read. |
| `out/renderer/assets/index-C76vPLoN.js` | 1724942 | 3885 | **no** | Needle scan: `player2` 0, `guitar` 0, `chord` 0, `studio.moises` 0. `sparkbars` 2, `mastering` 2, `voice-studio` 2, `lyrics` 2, `memory-panel` 5. |
| `node_modules` and other asar files | 6510 files outside the shell selection | UNKNOWN | no | Inventory only. `relevant_files` 6516 includes the selection. |
| `native/capture/prebuilds/win32-x64/capture.node` | 592896 | UNKNOWN | no | README read. Binary not decompiled. |
| `MoisesPluginServer.exe` | 7794688 unpacked | UNKNOWN | no | REA integrity contradiction. Bytes untrusted against the asar hash. |

Shell token total 414+37+9+79+24 = **563**, all inside files REA parsed. Renderer tokens **3885**, analyzed **0**.

✅ [S1 shell] pages 12/12, functions 68/68 T1, blocked runtime 68
