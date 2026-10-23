# Moises desktop architecture — 2.1.0

Evidence: E-FUSES and E-SHELL in [evidence-index.md](evidence-index.md). Channel names: [FUNCTION-INVENTORY.md](FUNCTION-INVENTORY.md). Routes: [PAGE-INVENTORY.md](PAGE-INVENTORY.md).

## Stack

| Piece | Observed |
|---|---|
| Product | `moises-desktop` 2.1.0, `tdBuildId` `261021a1gygumpb` |
| Packaging | ToDesktop runtime `^2.1.4`, app id `220410vabqjud82` |
| Electron entry | `out/main/index.js`. Imports include `BrowserWindow`, `WebContentsView`, `dialog`, `screen`. |
| Local UI | `out/renderer/index.html` plus `assets/index-C76vPLoN.js` and `index-D1VDwdG1.css`. Title `Moises Studio`. |
| Preloads | `out/preload/index.cjs` exposes `electronAPI`. `out/preload/webview.cjs` exposes `electron` for hosted pages. |
| Dependencies in package.json | `@electron-toolkit/utils`, `@expo/sudo-prompt`, `@moises-ai/plugin-server` 0.8.40, `@sentry/electron`, `@todesktop/runtime`, `axios`, `extract-zip` |
| Node engines | `>=22.12.0` declared in package.json |

## Process model

Observed processes while the app was open: several `Moises` processes and one `MoisesPluginServer`. A hidden JUCE window belonged to the plugin server. REA counted 2 browser windows and 1 utility process in the shell sources. The utility entry path was not resolved (`resolved_utility_entrypoints` 0). The capture host uses `process.parentPort`, which is the utility-process parent channel.

Fuses on `Moises.exe` (observed): `EnableNodeCliInspectArguments` enabled, `EnableEmbeddedAsarIntegrityValidation` disabled, `OnlyLoadAppFromAsar` disabled, `EnableCookieEncryption` disabled, `RunAsNode` enabled. Fuse state does not prove the running process was started with a debugger. This scan did not attach one.

## Hosted versus local

The local HTML CSP is `default-src 'none'` and `connect-src 'self'`. A comment in that file says the page holds `window.electronAPI` and nothing but the bundle may run in it. Product routes (`/home`, `/play`, `/studio`, `/mastering`, `/voice-studio`, `/lyrics`) are strings in the main process, not in the renderer bundle (needle scan: `studio.moises` count 0 in the renderer JS).

Persisted session: one tab whose URL was `https://studio.moises.ai/home?client=desktop`, and one `player2` webview. The player id is omitted.

`studio-stage.moises.ai` is a literal. It was not requested.

## IPC and storage

Shell state is written to `tabs.json` under `%AppData%\Roaming\Moises`. IndexedDB directories exist for `https_studio.moises.ai_0` and `https_studio1.moises.ai_0`. What `studio1` is was not established. Cookies and Local Storage were not read.

There is one REA integrity contradiction, on the unpacked plugin-server executable. Those bytes are untrusted against the hash stored in the asar. The asar file hash itself matches the hash REA recorded.

## What this file does not claim

Mixer DSP, stem models, and Studio's DAW internals are not in the local bundle's analyzed files. They were not executed.
