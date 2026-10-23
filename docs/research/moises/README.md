# Moises desktop — research brief

Agents: read [REFERENCE.md](REFERENCE.md) first. It is the full handoff in one file. This page is the short version.

Static look at `/Applications/Moises.app` **2.0.3** (build `2609048vfr0p5is`, 2026-10-17) so we can improve our Isolate mixer. This is not a clone list and it does not include Moises source.

## What it is

Moises desktop is an **Electron** app (Vite-style `out/main`, `out/preload`, `out/renderer`), packaged with ToDesktop. The window title in the renderer shell is **Moises Studio**. One minified renderer bundle draws the studio UI. The main process owns windows, tabs, theme, updates, a plugin server, a VST-host connection channel, and a separate **audio-capture utility process** (`MoisesAudioCapture`) that loads the `audify` native addon (`RtAudio` / Opus builds sit beside it).

**Correction (FULL-TEARDOWN §9.4).** The local renderer does **not** mount the mixer. It draws titlebar, tabs, Settings, a blank page, and the New Project menu. Mixer components in that bundle are shared library code with **no shipped CSS and no mount**. Studio, Play, Mastering, and the mixer the user sees are hosted pages in native views (`studio.moises.ai`). Read [FULL-TEARDOWN.md](FULL-TEARDOWN.md) before treating a renderer literal as an on-screen desktop control.

The shell tab chrome is driven through `electronAPI.tab`. Stem playback is **not** an IPC feature. Literal `AudioContext`, `createGain`, `audioworklet`, and `wavesurfer` appear in the bundle as shared code. A feature trace did **not** index those literals.

## What to take for our mixer

1. **P0 — tab strip.** Their shell can create, duplicate, close, close-others, close-right, reorder, preview, and context-menu a tab. Desktop Isolate now has duplicate, close others, close to the right, and reorder on Home | mix | +. Hover previews and a separate New Project product menu stay theirs.
2. **P0 — track row.** Shared-library names include pan, record, input gain, and a parent track. Desktop now has a pan slider (our equal-power law) and a disclosure group that does not sum. Record and input gain stay with live capture, which is not a current product goal.
3. **P1 — live input.** Capture is a utility process plus `audioCapture.open` / `listDevices`, not a stem fader. Only relevant if we record into a project.
4. **Do not chase** VST hosting, lyrics, mastering, or voice-studio. Those are other tools in the same shell.

Picture-sync and mix bounce were **not** established. Our video picture may already be ahead of what this pass could see.

## How to re-run (REA 6.5.0)

Tools used: `open_binary`, `inspect_plist`, `inspect_electron_fuses`, `inspect_artifact`, `inspect_analysis_view`, `analyze_javascript_application`, `trace_application_feature`, `extract_artifact`.

1. `open_binary` on `.../Moises.app/Contents/Resources/app.asar`, then `inspect_artifact` with `detail: "summary"` and `integrity_policy: "record-and-continue"`.
2. Page inventory occurrences near the end of the archive for `out/main`, `out/preload`, `out/renderer`.
3. **Do not trust `extract_artifact` bytes on this archive.** REA 6.5.0 materializes every member as a slice that starts at the ASAR header (`text_status: invalid-utf8` on `out/main/index.js`). Inventory **paths and sizes** are still usable. Electron’s embedded-ASAR integrity fuse is **disabled**, so the thousands of hash mismatches are this reader’s slices versus the header hashes, not a tamper finding.
4. Re-slice with a normal ASAR header (8-byte size pickle, then the header pickle, then file payloads at `offset`/`size`; `unpacked` files live in `app.asar.unpacked`). Keep that tree **outside the repo** (this pass used `/tmp/moises-asar-fixed`).
5. `analyze_javascript_application` on that directory, `format: "directory"`, `detail: "summary"`, `source_paths` = `package.json`, `out/main/index.js`, `out/main/audio-capture-host.js`, `out/preload/index.cjs`, `out/preload/webview.cjs`, `out/renderer/index.html`. Then a second call for `out/renderer/assets/index-CiDG_8MY.js` (raise `max_semantic_nodes_per_file`; this pass used 150000).
6. `trace_application_feature` on the shell parent for `audio-capture`, `preload`, and `BrowserWindow`. UI words inside the renderer bundle returned **no-match**. That is not proof they are absent; confirm with a literal scan of the same file REA parsed, and label it as such.

Evidence IDs and limits: [evidence-index.md](evidence-index.md). UX: [mixer-ux.md](mixer-ux.md). Stack: [architecture.md](architecture.md). Priorities: [gaps-vs-audio-tools.md](gaps-vs-audio-tools.md).

No raw REA JSON is committed. Trace dumps include minified expression nodes and are large.
