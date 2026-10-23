# Moises desktop — research brief (2026-10-23)

Read [PAGE-INVENTORY.md](PAGE-INVENTORY.md) and [FUNCTION-INVENTORY.md](FUNCTION-INVENTORY.md) for the row-level census. [REFERENCE.md](REFERENCE.md) is the handoff. This page is the short version.

## Artifact

Windows desktop **2.1.0**, build `261021a1gygumpb`, installed at `%LocalAppData%\Programs\moises-desktop`. The ToDesktop feed `https://download.todesktop.com/220410vabqjud82/latest.yml` returned that same build on 2026-10-23 (`releaseDate` 2026-10-21). Asar SHA-256 `e7242b3db57214f5a32ff24b4fb2e3f66d5ffabd6101381dbc4992de3d6bd284`.

The 2.0.3 macOS notes and the 2.0.18 runtime notes are historical. They are archived under `docs/plans/moises-parity/_work/archive-pre-rescan-2026-10-23/`.

## What it is

An Electron shell (ToDesktop, `package.json` main `./out/main/index.js`) whose local page is a tabbed frame. The page title is Moises Studio. Its content security policy does not allow network calls. Play, Studio, Mastering, Voice Studio, Lyric Writer, and Home are hosted routes on `studio.moises.ai`, chosen from a new-tab menu in the main process. `sparkbars` is the Studio icon name in that menu.

Capture is a utility process loading `native/capture/prebuilds/win32-x64/capture.node` (RtAudio 6.0.1, WASAPI by default). The shipped README says audify was the addon through 2.0. The process is still referred to as `MoisesAudioCapture` in main.

## What changed versus the last write-up

- Build is 2.1.0, not 2.0.3 or 2.0.18.
- Capture addon is the custom RtAudio build, not audify.
- Shell IPC is 68 literal channels and 79 bridge members (REA `ev_2015286d22cfc4a62451bbee9e1c1ca624e084e78ff6c80bf01cfaa20162ab93`), including a memory panel that the older bridge list did not center.
- Logged-in interiors were not re-walked. A fullscreen video was on the primary display. This scan did not dismiss it.
- The public sitemap is 3,041 URLs (405 English paths). Help text states a free tier of 5 uploads a month and 5-minute stems. Prices are still unpublished on the pages that loaded. Chord Finder and Capo Mode pages do not say guitar tab. The player was not opened.

## How to re-run

Use Node 22.19+, 24.11+, or 26. This machine's system Node is 20.18.0. The Cursor helper Node 24.19.0 can run the CLI. REA MCP was not registered. `rea setup` was not applied.

1. `inspect-electron-fuses` on `Moises.exe`.
2. `analyze-javascript-application` on `app.asar` with `--integrity-policy record-and-continue` and `--source-path` for `out/main/index.js`, `out/main/audio-capture-host.js`, `out/main/chunks/capture-apis-J4FdMrZ-.js`, `out/preload/index.cjs`, `out/preload/webview.cjs`, `out/renderer/index.html`.
3. Do not commit the unfiltered JSON. The package-only run was about 86 MB of JSON before filtering.
4. Walk the running app only when the user's display is free. Do not press Esc on a fullscreen video. Do not log in, upload, or purchase.

Evidence IDs: [evidence-index.md](evidence-index.md).
