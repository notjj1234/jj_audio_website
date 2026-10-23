# Moises 2.1.0 teardown

This replaces the 2.0.3 teardown as the current note. The old text is in `docs/plans/moises-parity/_work/archive-pre-rescan-2026-10-23/research-moises/FULL-TEARDOWN.md`.

## 1. Identity

| Field | Value | Evidence |
|---|---|---|
| Version | 2.1.0 | `package.json` in the asar; exe ProductVersion |
| Build | `261021a1gygumpb` | `tdBuildId`; exe FileVersion; update feed |
| Platform scanned | win32-x64 | This host |
| Asar | 60,980,590 bytes, 6,711 files | Header parse plus REA E-PKG |
| Current on the feed | Yes, on 2026-10-23 | latest.yml |

## 2. Fuses

E-FUSES. Integrity validation is off, so a hash mismatch does not by itself mean Electron will refuse to boot. Cookie encryption is off. Node CLI inspect arguments are honored if the process is started with them. The running processes were not started with an inspect port by this scan.

## 3. Windows

REA: 2 browser windows, 2 explicit web preference objects. Constructions were not dumped as source in the summary view. Preload paths `../preload/index.cjs` and `../preload/webview.cjs` are strings in main. INFERRED: one window is the shell and one class of view is the hosted page. The exact `webPreferences` flags were not re-printed. Do not copy the 2.0.3 `contextIsolation` note forward as a 2.1.0 observation.

## 4. Bridge

Two `contextBridge.exposeInMainWorld` calls.

- `electronAPI`: tabs, new menu, memory panel, drag, window, plugin server, updates, auth, theme, platform.
- `electron` (webview): plugins, desktop update, navigation guard, import, VST host, sign-out, auth state, pause, audio capture.

Full method list: [FUNCTION-INVENTORY.md](FUNCTION-INVENTORY.md). 68 methods named. REA counted 79 members. 11 unnamed in the summary.

Sender-validation observations: 0. That is not a finding that handlers skip checks. REA's limitation says arbitrary call side effects were not evaluated.

## 5. Routes

The new-tab menu in main pairs labels with paths:

| Label | Paths | Icon string |
|---|---|---|
| Studio | `/studio/new`, `/studio` | `sparkbars` |
| Play | `/upload/split/3`, `/play`, `/upload/split` | `play` |
| Home | `/home` | `home` |
| Mastering | `/mastering/upload`, `/mastering`, `/upload/master` | `mastering` |
| Voice Studio | `/voice-studio/upload`, `/voice-studio` | `voice-studio` |
| Lyric Writer | `/lyrics/new`, `/lyrics`, `/lyric-writer` | `lyrics` |

Host prefix observed in the live session for Home: `https://studio.moises.ai`. The code also contains `https://studio-stage.moises.ai`.

## 6. Capture

`audio-capture-host.js` loads `capture.node` from the unpacked tree. Windows default API is WASAPI (`capture-apis` map). ASIO is available on `win32-x64` and is refused with `device-busy` if a stream is already open. The README in `app.asar.unpacked/native/capture/README.md` is the vendor's own description of RtAudio 6.0.1 patches and of audify's removal after 2.0. This scan did not record audio.

## 7. Plugins

`@moises-ai/plugin-server` 0.8.40. Main looks for a free loopback port and reports startup failure strings. Plugin filenames observed: Stems and Studio and Mastering, as AAX, and Studio and Mastering as VST3 and `.component`. Download host `https://plugins.moises.ai`. A menu string says "Enable VST plugins". Nothing was installed.

## 8. Updates and auth

Update feed is the ToDesktop URL in section 1. Channels `updates:get-state`, `updates:check`, `updates:install`, `updates:downloaded`. Auth channels `auth:is-signed-in`, `auth:changed`, `auth:sign-out`, `auth:state`. The logged-out web login offers Google, Facebook, Apple, X, and email. Not submitted.

## 9. Renderer bundle

`index-C76vPLoN.js` is 1,724,942 bytes. It was not semantically analyzed. A literal count found no `player2`, `guitar`, `chord`, or `studio.moises`. It did contain `memory-panel` and the product icon names. INFERRED: the bundle is shell chrome. That inference is bounded by the needle list. It does not prove a string is absent under a different spelling.

## 10. What a later session must open

Logged-in Home, Play, `/player2`, Studio, Mastering, Voice Studio, Lyric Writer, and a HAR that redacts tokens. Until then, sections 5's interiors stay unknown.
