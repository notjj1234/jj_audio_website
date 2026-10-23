# Moises Desktop 2.0.3 — full teardown (agent deep pass)

Complement to [REFERENCE.md](REFERENCE.md). This pass answers: **what the app is made of, how
each surface is structured, where every button sits, how it loads so smoothly, and what was
literally used to build it.** Static analysis only — the app was not launched. No Moises source
was cloned or copied; quoted strings are UI literals used as identifiers.

Labels: **Observed** (bytes/hashes on disk or parsed structure) · **Literal** (exact string
counted in a file) · **Inference** (conclusion from those facts) · **Unknown** (runtime-only).

> **Correction to earlier notes (important).** REFERENCE.md inferred the mixer UI lives in the
> locally rendered bundle. Deeper pass: the local renderer mounts **only** the titlebar/tab
> strip, Settings, a blank page, and the New Project menu window. The mixer/track/waveform
> components exist in the bundle as **shared source with the hosted studio** but are **not
> mounted** by the desktop shell — their CSS is absent from the shipped stylesheet (proof in
> §9.4). The actual Studio, Play, Mastering, and mixer UI are the **hosted web app** loaded in
> native `WebContentsView`s from `studio.moises.ai`.

## 1. Artifact identity

| Item | Value |
|---|---|
| App | `/Applications/Moises.app` — **2.0.3**, build `2609048vfr0p5is` |
| Bundle id | `com.todesktop.220410vabqjud82` (ToDesktop) |
| `app.asar` | sha256 `8c244bb62ecd4725625225b8edccdc4f56bb5e9831a2e48776349979acb20827`, 22,408,285 B |
| `out/main/index.js` | sha256 `965b14e606db812d7bb864abaa0861d954b8fe4973b7a1ea6b70c4a1454f41ec`, 56,101 B |
| `out/renderer/assets/index-CiDG_8MY.js` | sha256 `791aa79ee729023a10a2d39c18ba717f63dea91ea4c5de29ef0d93fec7759f00`, 1,528,413 B |
| `out/renderer/assets/index-bDi2iXqb.css` | sha256 `8db0403eafea5972833dc2dd1223fcebc8225dd4eb9697c470d1b4b82e0baf5a`, 705,966 B |
| Mach-O `Contents/MacOS/Moises` | sha256 `656bc2bf6e534131ebba8eea9b3ef7103de4a8eb0b987f3f4b5b8442b98a3298` (arm64) |
| `package.json` | name `moises-desktop`, `"type":"module"`, node `>=22.12.0`, pnpm 10.28.2 |
| Updater | `app-update.yml`: provider generic, `https://download.todesktop.com/220410vabqjud82`, channel `latest`, cache dir `moises-desktop-updater` |

Working tree for this pass: `/private/tmp/moises-asar-fixed` (re-sliced ASAR from the earlier
pass; directory digest `45ad3247…` unchanged). Pretty-printed copies used for reading:
`/tmp/moises-pretty.js` (esbuild, 14,607 lines) and `/tmp/moises-main-pretty.js` (1,696 lines).
No REA MCP server in this session; this pass is esbuild + node + grep static analysis of the
same verified bytes. REA evidence IDs from REFERENCE.md remain valid.

## 2. What Moises Desktop actually is

**Observed.** A **native Electron shell around a hosted web app**:

```
Main process  out/main/index.js
 ├─ BrowserWindow (frameless, 1260×800)          ← local renderer = CHROME ONLY
 │   ├─ local renderer  out/renderer/index.html   (titlebar + tabs + settings + blank)
 │   ├─ WebContentsView "home" tab  → studio.moises.ai/home?client=desktop
 │   ├─ WebContentsView per "webview" tab → studio.moises.ai/<route>?client=desktop
 │   └─ WebContentsView (lazy) #new-menu         ← transparent
 ├─ BrowserWindow preview (tab hover)             ← transparent, 296×186, no preload
 ├─ child process  MoisesPluginServer             ← VST/plugin host, ws://127.0.0.1
 ├─ utilityProcess MoisesAudioCapture             ← audify/RtAudio PCM capture
 └─ Tray + app menu + global updater
```

**Literal (local renderer root).** The entire local UI is one React tree:
`render #new-menu ? <NewTabMenu> : <AppShell>`; `AppShell` = titlebar/tab strip +
`pageId` switch → `settings` (Settings page) | `blank` (empty state) | `home`/`webview`
(renders **null** — a native view covers the area). Everything else in the 1.5 MB bundle is
**shared code with the web studio** that the shell never mounts.

**Inference.** "How it feels smooth" is therefore two layers: (a) the **shell** keeps every
tab's web content alive in native views (§10), and (b) the **hosted studio app** (React +
Radix Themes, same component library as the bundle's dead code) does its own UI work remotely —
not statically inspectable from this artifact.

## 3. Methods of the deep pass (re-runnable)

1. Pretty-print both bundles: `npx esbuild@0.21.5 <file> --format=esm --outfile=/tmp/…`.
2. String/enumeration extraction via small node scripts (no exec of app code).
3. Targeted greps on pretty output; CSS module families extracted with
   `\._([A-Za-z0-9]+)_([a-z0-9]{5})_\d+`.
4. Cross-check with REFERENCE.md evidence IDs; nothing was deleted from earlier notes.

## 4. Process & surface inventory

### 4.1 Windows and views

| Surface | Kind | Preload | Notes |
|---|---|---|---|
| Main window | `BrowserWindow` | `out/preload/index.cjs` | `frame:false`, `titleBarStyle:"hidden"`, traffic lights `{x:12,y:12}` (macOS), win32 `titleBarOverlay {color:"#141414",symbolColor:"#909090",height:40}`, `backgroundColor:"#141414"`, `show:false` until `ready-to-show`, min 480×320 |
| Tab content | `WebContentsView` | `out/preload/webview.cjs` | one per tab; `contextIsolation:true`, `sandbox:true`, `focusOnNavigation:false`; optional `webSecurity:false` per tab; bounds `{x:0, y:40, w, h-40}` |
| New Project menu | `WebContentsView` (one per window, lazy) | `index.cjs` | loads `renderer/index.html#new-menu` when first opened; transparent bg; full content-area bounds; `send`-driven show/hide; `new-menu:ready` handshake + pending buffer |
| Tab hover preview | `BrowserWindow` | none | `frame:false, transparent:true, backgroundColor:"#00000000", alwaysOnTop:true, skipTaskbar:true, resizable:false, focusable:false, hasShadow:false`, `setIgnoreMouseEvents(true)`; loads a self-contained `data:text/html` card |
| Sign-in popup | `BrowserWindow` (window.open) | none | 500×700 (min 420×520), white bg, `autoHideMenuBar` |
| Studio app | remote pages | — | `studio.moises.ai` (prod) / `studio-stage.moises.ai` (dev), both with `?client=desktop` |

### 4.2 Utility/child processes

| Process | Entry | Purpose |
|---|---|---|
| `MoisesAudioCapture` (`utilityProcess.fork`) | `out/main/audio-capture-host.js` (2,686 B) | RtAudio capture; PCM over `MessagePort` (§11) |
| `MoisesPluginServer` (`child_process.spawn`) | `@moises-ai/plugin-server` executable (v0.8.23) | VST hosting + plugin bridge (§12.2) |

### 4.3 Bridge surfaces (from earlier REA + re-verified strings)

- `window.electron` (webview preload): `checkVersionReleased/User`, `installPlugin`,
  `updateDesktopApp`, `setShouldPreventNavigation`, `consumePendingImportFile`,
  `getVstHostConnection`, `signOut`, `onPausePlayback`, `audioCapture.{listDevices,open,close,onClosed}` —
  plus a raw `audio-capture:port` listener that relays the `MessagePort` to the page (§11.3).
- `window.electronAPI` (chrome preload): `tab.*` (create/close/closeOthers/closeRight/activate/
  reorder/duplicate/getAll/onUpdated/showPreview/hidePreview/showContextMenu/showNewMenu),
  `drag.*` (start/end/onIndicator/onReleased/reportDropIndex), `newTabMenu.*`
  (ready/select/show/hide/onShow/onHide/close), `window.*` (minimize/maximize/close/isMaximized/
  onMaximizedChanged), `theme.*` (get/onChanged), `updates.*` (check/getState/install/onDownloaded),
  `pluginServer.*` (getConnection/getStatus/onStatus/restart/start/stop), `platform`,
  `audioCapture.*`.

## 5. The tab system (core of the shell)

### 5.1 Tab model and page types

**Observed.** Tab record: `{ id, title, pageId, icon, url, disableWebSecurity }`, ids from a
monotonic counter. `pageId` ∈ `home | webview | settings | blank`. `#d(tab)` — "has native
content" — is true for `webview`, and for `home` only when it has a URL. Home is special:
max one per window, pinned index 0, not closable, not draggable.

### 5.2 Route table — which hosted page becomes which tab

**Observed** (main, route matcher):

| Tab title | Icon | URLs matched | "New project" URL |
|---|---|---|---|
| Play | `play` | `/play`, `/play/*`, `/library*`, `/upload/split*` | `/upload/split/3` (in Home) |
| Home | `home` | `/home`, `/home/*` | — |
| Studio | `sparkbars` | `/studio*`, `…/daw/…` | `/studio/new` |
| Mastering | `mastering` | `/mastering*`, `/upload/master*` | `/mastering/upload` (in Home) |
| Voice Studio | `voice-studio` | `/voice-studio*` | `/voice-studio/upload` (in Home) |
| Lyric Writer | `lyrics` | `/lyrics*`, `/lyric-writer*` | `/lyrics/new` |
| Setlist | `setlist` | `/setlist*` | — |

When a webview navigates, main re-derives icon/title from this table (`did-navigate` →
`oe(url)` → matched route; page `<title>` preferred via `Le(title,url)`). "Realm" key for
dedupe = `origin + pathname(no trailing /) + daw-hash`; pages ending in `/new` are realm-less
so "New project" tabs never dedupe onto an existing tab.

### 5.3 Creation, dedupe, activation

- **createTab** default `{title:"New Tab", pageId:"blank", icon:"file"}`. For `webview` +
  URL: if another window already shows the same realm (excluding this tab), **activate that**
  instead of creating a duplicate (`preferWinId` first; excludes home tabs).
- New views **start loading immediately on creation** (`loadURL` in `#m`), even when the tab
  is not active. Views are attached to the window's contentView and then toggled with
  `setVisible(active)` — see §10.
- **activateTab** only flips `activeTabId`, updates visibility, focuses; no reload.
- **Blank page** (never given a URL) renders the local empty state: app icon + "New Tab".
- **Home tab** created at window birth with `studio.moises.ai/home?client=desktop`; "Go to
  Home" menu/`Cmd+T` re-activates it, or reloads `/home` if it had navigated elsewhere.

### 5.4 Lifecycle operations

| Op | Behavior (Observed) |
|---|---|
| `closeTab` | Refuses for home and for the **last non-home** tab (window keeps ≥1 content tab); otherwise guard-check, remove, free view, activate `min(index, len-1)` |
| `closeActiveTab` | If active is home or missing → closes the **window** (`Cmd+W` on Home exits the window) |
| `duplicateTab` | Clones the underlying webContents (`webContents.clone()` + `reload()`), inserted right after; falls back to fresh `loadURL` |
| `detachTab` | Moves tab to a new window at cursor `{x-200, y-20}` (blocked if it's the last non-home tab) |
| `transferTab` | Cross-window drag drop at index; auto-closes source window if it has no non-home tabs left |
| `closeOtherTabs` / `closeTabsToRight` | Always preserve the home tab |
| `reorderTab` | Home pinned; reorder index 0 clamps to 1 |
| `cycleTab` | Ctrl+Tab / Ctrl+Shift+Tab |
| `activateTabByIndex` | Cmd/Ctrl+1…9 (9 = last) |
| `closeSessionTabs` | Sign-out: clears guards, collapses each window to home, loads `/auth/login` |

### 5.5 Tab context menu (Observed)

Home tab → single item "Go to Home". Other tabs → **Duplicate Tab**, **Detach to New Window**
(enabled if >1 non-home), separator, **Close Tab** (`CmdOrCtrl+W`), **Close Other Tabs**
(enabled if >1), **Close Tabs to the Right** (enabled if not last).

### 5.6 Keyboard/menu shortcuts (Observed)

App menu: File — Go to Home `Cmd+T`, New Window `Cmd+N`, Open Audio… `Cmd+O`, Close Tab
`Cmd+W`, Close Window `Shift+Cmd+W`; Settings… `Cmd+,`; View — Reload `Cmd+R`, Force Reload
`Shift+Cmd+R`, DevTools `Alt+Cmd+I` (mac) / `Ctrl+Shift+I`, zoom `Cmd+0/+/-`, fullscreen;
Tabs — Next/Previous `Ctrl+Tab` / `Ctrl+Shift+Tab`, `Cmd+1…9`.

### 5.7 Guards ("unsaved changes") and audio coordination

- Webviews can call `setShouldPreventNavigation(true)` → main marks that webContents
  **guarded**. Close-tab, close-window, `will-navigate`, and quit then show a native dialog
  **"Unsaved Changes — You have unsaved changes. Are you sure you want to leave?"** (`Yes`/`No`);
  re-entrancy protected per window.
- `audio-state-changed` on any tab that becomes `audible` → main sends
  **`desktop:pause-playback`** to all other in-app webContents. One audible tab at a time by design.

### 5.8 Session persistence (restore on relaunch)

**Observed.** File: `<userData>/tabs.json`, `{version:1, windows:[{bounds, maximized, tabs:
[{title,pageId,icon,url}], activeIndex}]}`.
- Written debounced **500 ms** after changes; deleted on clean quit, sign-out, and restart-install.
- Only "valid" tabs saved: in-app URLs, excluding `/new` pages. Home tab saved by URL too.
- Restore: windows with saved bounds (only if intersecting a display), all tabs recreated and
  **preloaded immediately**; active tab re-activated last. If nothing restorable → one fresh window.
- Window `bounds` saved un-maximized; `maximized` flag re-applied.

## 6. Tab strip UI anatomy (button placement, exact metrics)

All **Observed** in `index-bDi2iXqb.css` (the only CSS that ships for the shell — 6 modules,
§9.4) and the titlebar JSX.

```
┌─ titlebar (40px, bg #1a1a1a, 1px bottom border #2a2a2a, z-100) ─────────────┐
│ (macOS traffic lights 12,12)  78px pad ──► tabs … [+]     … windowControls │
└──────────────────────────────────────────────────────────────────────────────┘
```

- `.titlebar` — `height: var(--titlebar-height)` = **40px**.
- `.dragRegion` — `-webkit-app-region: drag`, `padding-left: 78px` on macOS (traffic-light gap).
- `.tabsContainer` — `no-drag`, `align-items:flex-end`, `gap:1px`, `padding:4px 4px 0`,
  horizontal scroll, `scrollbar-width:none`.
- **Tab** — height **36px** (bottom-aligned in the 40px bar, so tabs hang flush with content),
  `max-width:200px`, `padding:0 12px`, `gap:8px`; active = `background: var(--bg)` +
  `color: var(--text)`; inactive `var(--text-secondary)` (#888). Home tab `padding:0 14px`.
- Tab order: **color icon (14px) → title (12px/500, ellipsis) → close button** (18×18,
  radius 4, `opacity:0` until hover; middle-click also closes; Enter activates).
- **New tab [+] button** — 28×28, radius 6, margin-left 2px, opens the New Project menu below it.
- `.crossDragSpacer` — animated spacer used during cross-window drags:
  `transition: width .2s cubic-bezier(.2,0,0,1)`.
- Dragged tab becomes a `.floating` clone following the pointer; on drop it plays a **settle**
  animation (left position interpolated to the slot), `.released` fades it out.
- `.windowControls` — visible on Windows/Linux only (`display:none` under `.platform-darwin`);
  buttons 46px wide, full height. macOS uses native traffic lights (`titleBarOverlay` on win32).
- Icon accent colors (per tab type, e.g. home `--aqua-9 #00dae8`, mixer `#2dd4bf`, mastering
  `--purple-11`, lyrics `--tomato-11`) — these colors also feed the tab preview and drag ghost.
- Shell font: `-apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif`,
  `user-select:none`, transitions `.15s ease`, radius 8.
- Blank page: centered icon + "New Tab" (`.blank` flex column, gap 12).

### 6.1 Tab hover preview (a flagship smoothness feature)

Flow (**Observed**):
1. Hover starts a timer: **450 ms**; if a preview was hidden within the last **400 ms**, the
   delay drops to **75 ms** (hover warm-up).
2. Renderer sends `tab:preview-show {requestId, tabId, bounds, meta{accent, iconSvg}}`.
3. Main creates/updates a **transparent always-on-top window** (260×150 content + 18px
   padding), positions it under the tab (work-area clamped), and **captures the tab's live
   frame** via `webContents.beginFrameSubscription` (first frame, 1 s timeout) — for local
   pages it waits two rAFs (≤100 ms) and crops the 40px titlebar first.
4. Frame is resized to **520px** (`quality:"good"`), encoded **JPEG q76**, sent as a data URL;
   a per-tab thumbnail cache (`Map`) avoids re-capture.
5. Card layout: 28px header strip (14px colored tab icon + 11.5px title), body with 34px
   glyph fallback; thumbnail fades in over the gradient with `opacity 100ms`; card itself
   animates `pop 130ms cubic-bezier(.2,0,0,1)` (opacity+scale .96). Source comment notes the
   animation deliberately runs *from* hidden without fill-mode ("a hidden window does not tick
   animations … can strand the card at opacity 0").
6. Hides on mouse-out, `Esc`-equivalent blur, window blur, or tab close. Wayland sessions
   disable previews entirely. Accent color is sanitized (`/^[\w#().,%\s+\/-]{1,64}$/`,
   fallback `#10b981`); icon markup is only ever their own fixed icon set, never page data.

### 6.2 Cross-window tab drag

**Observed.** Pointer down on a non-home tab → 5px threshold → floating preview window (bare
card = the same preview window chrome with `titlebar:true`) + main-process loop at **30 ms**:
- follows cursor, computes target window (window under cursor excluding source),
- sends `drag:indicator {show, localX, tab}` to the target renderer, which renders the drop
  gutter (`.crossDragSpacer` animates tab widths out of the way) and reports the drop index,
- marks "released" when the cursor leaves the source titlebar strip (+24px margin) — target
  shows the "add to this window" state,
- release: **transfer** into target at index, **detach** into a new window at cursor when
  released over empty desktop, else **reorder** in place (bias: swap after 75% of a tab's
  width to the right, 25% to the left).

## 7. New Project menu (⌘+ plus button)

**Observed.** A **separate transparent WebContentsView** per window, loading the same
renderer with `#new-menu` and `document.body.classList.add("transparent")`, created lazily on
first open. Main sends `new-menu:show {anchor, items}`; items (**5**):

| Item | Opens (via `new-menu:select` → main) |
|---|---|
| Studio | new Studio tab at `/studio/new?client=desktop…` |
| Play | **reuses Home tab** (`/upload/split/3`) |
| Mastering | Home tab (`/mastering/upload`) |
| Voice Studio | Home tab (`/voice-studio/upload`) |
| Lyric Writer | new tab (`/lyrics/new`) |

Panel: width **236px**, `padding:6px`, `background: var(--neutral-2)`, bottom corners radius
16 (`0 0 16px 16px` — it hangs from the titlebar), `animation: _appear_ .11s cubic-bezier(.2,0,0,1)`,
positioned at the [+] button anchor (+6px below). Items: 56px tall, gap 16, **48×48 icon tile**
(radius 12, `neutral-alpha-3`), 11px-neutral label; hover changes bg/text. Keyboard: ↑/↓ cycle,
Enter select, Esc close; click-away (backdrop) closes; `blur` on the window also hides it.

## 8. Settings page (local React)

**Observed.** Centered column, max-width 700, padding 40/32. Contains exactly:

1. **"Enable VST plugins"** toggle — drives the plugin server (start/stop) with live status
   detail; disabled while starting/stopping; error text inline.
2. **"Moises Desktop" updater row** — version; button cycles
   Check for updates → Checking… → "You're up to date." / failure message; when a version is
   downloaded: **"Restart & install"** (primary style).
3. **Debug** (`<details open>`) — status dot + pill (Stopped/Starting…/Running/Stopping…/Failed),
   Start / Stop / Restart buttons, `Port / Process / Version / Uptime` dl, and an **Output log**
   (last 60 lines, stderr styled red, auto-scrolled). Note text: "The server runs in the main
   process and keeps running when every window is closed. Use the menu bar icon to reach it or
   to quit."

Row style: `background: var(--surface)` (#1e1e1e), 1px border, radius 8. Buttons 13px/500,
`padding:8px 18px`, radius 6. Status dot has `_pulse_` keyframes (opacity .35 at 50%).

## 9. The renderer bundle internals (what was literally used)

### 9.1 Framework and application stack

| Layer | Finding | Evidence |
|---|---|---|
| React | **19.x** | `useOptimistic`, `useActionState`, `useFormStatus`, `use(` wrapper, `Activity` component, `Suspense`/`SuspenseList` exports; StrictMode root |
| Mount | `createRoot(#root).render(<StrictMode><Theme appearance:"dark">…)` | bundle tail |
| Design system | **Radix Themes** — `Theme(accentColor:"cyan", appearance:"dark", panelBackground:"solid")`; full component set present: Avatar, Badge, Blockquote, Callout, Card, Checkbox, Code, Container, DataList, Dialog, Flex, Grid, Heading, HoverCard, Inset, Popover, Progress, RadioCards, RadioGroup, ScrollArea, Section, SegmentedControl, Select, Separator, Skeleton, Slider, Table, Tabs, Text, TextArea, TextField, Tooltip, Theme, `rt-r-*` responsive utilities (5,281 hits), `rt-skeleton-pulse`, `rt-spinner-leaf-fade`, progress variants |
| UI primitives | Radix UI primitives (displayName inventory: Dialog/AlertDialog/ContextMenu/DropdownMenu/Popover/Popper/Select/ScrollArea/Slider/Switch/Tabs/Toast/Tooltip/HoverCard/Checkbox/Radio/Collapsible/AspectRatio/Avatar/Progress/ToggleGroup/RovingFocus/DismissableLayer/FocusScope/Presence/Slot/VisuallyHidden/Collection) |
| State | immer (×7 internal strings); signals-style reactive state (`signal/computed/effect`) inside the wavesurfer wrapper; **no Redux** (`@@redux` 0 hits), **no TanStack Query** (0 hits) |
| Drag & drop (studio code) | Draggable/Droppable/Sortable types + `TreeOrder`/`ReversedTreeOrder` drop strategies + Pointer/RightClick sensors (library not conclusively identified from minified code) |
| Scroll/editor icon | `excalidraw` icon exists in the icon set (tab icon map) |
| i18n | identity provider pattern `i18n = { _: (s) => s }` — desktop chrome strings are hardcoded English; the 54 `.lproj` dirs in Resources are empty Electron stubs |
| Errors | `Minified React error #` strings (prod React) |

### 9.2 Icon set (Observed literals)

`home, file, music, mixer, settings, waveform, folder, star, globe, server, excalidraw,
sparkbars, play, mastering, voice-studio, lyrics, setlist` + UI glyphs: `KeysIcon, Strings,
Music, More Icon, Settings Icon, CloseIcon, Lock, SparkBars, Lyrics, Mastering, Waveform, Plus,
Star, Minus, User Voice, Check, Moises Play Icon`. Tab-color map listed in §6.

### 9.3 Mixer components present in the bundle (shared with studio; **not mounted locally**)

**Observed definitions** (displayNames): `TrackHeader`, `TrackControlButton`,
`TrackControlsToggle`, `InputLevelMeter`, `InstrumentSelect`, `InstrumentSelectCard`,
`PanControl`, `TextField`, `PreviewCard`. Anatomy of `TrackHeader`:

- Row height **81px** default; `compact` mode hides the controls row; `isParentTrack` renders a
  disclosure (children in `.group` when open; **children are real nested tracks**).
- Header line order: `[▸/▾ expand]` (parent only) → `[instrument icon button]` (opens
  InstrumentSelect popover, `side:"bottom", align:"start"`) → **track name** → right-aligned
  **`R` record | `M` mute/auto-mute | `S` solo** (single letters - observed map `record:"R",
  mute:"M", autoMute:"M", solo:"S"` with tooltips incl. shortcut hints) → `⋯` menu.
- Record button click opens a **popover (360px)**: `Source` device `Select` (+ channel select),
  `Input Level` meter, empty state `"No device options."` (right-click opens it too).
- Controls row (non-compact): **InputLevelMeter** (horizontal slider + volume + double-click
  reset) and **PanControl** (`minValue:-1, maxValue:1`).
- All inner controls stop propagation of pointer/mouse/touch events (track select is on the row).
- Stem instrument icons: `Vocals, Drums, Electric Guitar, Acoustic Guitar, Bass, Piano, Keys,
  Strings, Music`.

**Tempo & key panel** (shared): BPM stepper −/+ with clamped range **30–200** (defaults to 30 on
invalid; Enter/blur commit), tempo-marking label from a 19-entry table
(Larghissimo→Prestissimo), Time Signature selects `2…16` / `2,4,8,16`, Root Key select of **24**
values (`C…B`, `Cm…Bm`), sparkle-marked AI-detected fields (`✦`, `--ai-chars` var),
`"Detecting…"` state + **AI Re-detect** button (solid cyan), "Last time detected: …".

### 9.4 Dead-code proof (why we know the shell doesn't render the mixer)

**Observed.** The shipped CSS contains **only six CSS-module families**:

| Family | Classes | Belongs to |
|---|---|---|
| `3ydxf` | 36 | Settings page |
| `iih9f` | 10 | Tab strip |
| `1gppu` | 8 | Titlebar / window controls |
| `1gwmd` | 6 | Blank page |
| `qh1z3` | 5 | New Project menu |
| `4gyus` | 2 | App shell (app/content) |

Track/mixer/preview-card module classes (`_track_mbec5_*`, `_button_e3u0i_*`, `_previewCard_1pkng_*`,
`_waveformContainer_*`, `_skeleton_1pkng_*`, `_pan_mbec5_*`) exist as **JS literals but have zero
CSS rules** and zero mount sites (`TrackHeader` symbol: 2 references = definition + displayName
only). The root page switch renders `settings`/`blank`/null only. → The desktop shell shows
**remote studio pages**; the mixer components ship as unsplit shared-library code.

## 10. "Why it loads so smoothly" — the shell playbook

1. **Views stay alive.** Every tab's `WebContentsView` is created with its URL loading
   immediately and stays attached to the window; switching tabs only toggles `setVisible` —
   no reload, no spinner, instant switch.
2. **Session restore = preload at launch.** All saved tabs are recreated and loading before
   you interact; the active one is simply revealed.
3. **Hover previews from live frames** (`beginFrameSubscription`, 520px JPEG q76, cached per
   tab) with a **450→75 ms warm-up** — previews feel instant on rapid tab scanning.
4. **Window never flashes white**: `backgroundColor:"#141414"`, `show:false` until
   `ready-to-show`; chrome is dark from frame zero.
5. **Native overlays, not iframes** — web content runs in separate processes (parallel load,
   crash isolation); the 40px chrome is trivial local DOM.
6. **Micro-animations tuned short** with one curve: menus `.11s`, preview pop `.13s`,
   generic `.15s`, drag spacer `.2s`, all `cubic-bezier(.2,0,0,1)`; the preview card is
   deliberately animate-from-hidden (no fill-mode) to avoid stuck-opacity bugs in a hidden
   window.
7. **Optimistic/lean UI toolbox**: Radix Themes `Skeleton` (pulse keyframes), spinners,
   progress bars for the hosted app's loading states; Radix primitives handle focus/scroll-lock
   so overlays never jank the page.
8. **Audio never fights audio**: only one tab may be audible (`audio-state-changed` →
   `desktop:pause-playback` broadcast).
9. **Drag feels live**: 30ms cursor polling, transform-only floating tab, width transitions
   for the reorder gutter.
10. **Zero-cost chrome bundling**: one JS + one CSS file, no runtime chunk fetches
    (modulepreload not needed), fonts are system fonts.

## 11. Audio capture pipeline (record input)

**Observed** in `audio-capture-host.js` + main manager:

- Utility process `MoisesAudioCapture` loads `audify.node` (RtAudio) from
  `app.asar.unpacked/native/rtaudio/prebuilds/<darwin-arm64|win32-x64>/`; other platforms warn
  "native capture is unavailable".
- API map: `coreaudio=1, asio=6, wasapi=7, directsound=8`.
- `devices` → RtAudio device list filtered to `inputChannels>0` with id/name/sampleRates/
  preferredSampleRate/isDefaultInput (per-request `requestId` protocol).
- `open {deviceId, channels, firstChannel=0, sampleRate, frameSize=256, api}` →
  `openStream(… FLOAT32, sampleRate, 256, "moises-capture-<id>", cb, null, SCHEDULE_REALTIME, errCb)`
  → returns `{channels, firstChannel, sampleRate, frameSize, latencyFrames}`.
- PCM callback copies each buffer into a fresh Float32Array and sends
  **`{t:"pcm", seq, samples}` through a `MessageChannelMain` port** — not IPC serialization.
  The webview preload re-posts it into the page as
  `window.postMessage({type:"moises-desktop:audio-capture-port", …}, origin, [ports])`.
- Sessions are keyed by renderer webContents; `close` stops the stream; sessions auto-shutdown
  the process after idle (30s); `closed`/`failed` messages returned to the caller.
- Sender validation: capture channels accept calls only from **studio** URLs
  (`/studio/*`, daw, etc.).

## 12. Plugin stack (VST host + DAW plugins)

### 12.1 DAW plugin installer

- Products: **STEMS / STUDIO / MASTERING**; formats **AU / AAX / VST3**.
- Files: `Stems|Studio|Mastering .vst3/.component/.aaxplugin`. Service:
  `https://plugins.moises.ai/<PRODUCT>/` + `info.json` per product (version, per-platform zip).
- Install flow: fetch info.json → download zip → `extract-zip` to temp → **sudo-prompt**
  shell copy (`mkdir -p; rm -rf; mv` on macOS; `robocopy` on Windows) into:
  - macOS: `/Library/Audio/Plug-Ins/VST3`, `…/Components`, `/Library/Application Support/Avid/Audio/Plug-Ins`
  - win32: `C:\Program Files\Common Files\VST3`, `…\Avid\Audio\Plug-Ins`
- Installed-version bookkeeping: `<userData>/version.json`; user version verified by checking
  each expected plugin file still exists.

### 12.2 In-app plugin server (VST hosting)

- Executable: `@moises-ai/plugin-server` 0.8.23 (`serverExecutablePath()`), spawned with
  `--exit-on-stdin-close --port <n> --token <t> --allowed-origins moises.ai,moises.com,*.moises.ai,*.moises.com,*.moises.localhost --no-open-browser`.
- Port: default **6647** (env `MOISES_VST_HOST_PORT` overrides), probe/listen on 127.0.0.1;
  fallback to a random free port (5 tries).
- Connection for the page: `ws://127.0.0.1:<port>/?token=<token>` (token is a static string in
  the main bundle).
- Status model `{state: stopped|starting|running|stopping|error, port, pid, version, startedAt,
  error, log}`; stdout/stderr captured into a **60-line ring buffer with `token=[redacted]`**;
  60s stop grace, 5s start grace; `vst-host:connection` IPC resolves after the server leaves
  starting/stopping.
- Tray + Settings both expose start/stop; status broadcast to all windows
  (`plugin-server:status`).

## 13. File open / import flow

- **OS "Open with" / drag onto Dock**: handled from `process.argv` (and `second-instance`
  argv), filters to the 13 known extensions, queues until the renderer's import listener is
  ready, then opens `studio.moises.ai/studio/new?client=desktop&desktopImport=1` (a Studio tab
  or reuse) and parks the file keyed by that webContents.
- **File → Open Audio…** (`Cmd+O`): native `showOpenDialog` — title "Open Audio", button
  "Open", `multiSelections`, filters from the extension table.
- Extension→kind table: **audio** = mp3, mp2, wav, m4a, aac, flac, ogg, opus, wma, amr, caf;
  **midi** = mid, midi (Info.plist document types match, Editor/Default).
- **Max size 1.5 GB**; over → `"{name} is too large to open"`; read errors surfaced.
- The studio pulls the file via `import:consume` → main reads it into a Buffer and returns
  `{file: {name, kind, data}}` (one-shot; entry deleted on consume).
- macOS `will-download`: auto-saves to `~/Downloads` with ` (n)` uniquification and reveals in
  Finder when done.

## 14. Shell behaviors, tray, theme, updater, telemetry

- **Theme**: `theme:get` from `nativeTheme.shouldUseDarkColors`; live broadcast `theme:changed`;
  tray icon swaps dark/light (@2x PNGs, `nativeImage` scaleFactor 2).
- **Tray**: tooltip "Moises — VST plugins <state>"; menu = version (disabled) · Show/Hide
  Moises App · "New Project" header + 5 product items with themed icons · VST status +
  "Enable VST plugins" checkbox (start/stop) · "Desktop Settings…" · "Quit Moises Desktop".
  Non-macOS left-click opens Settings. Tray lives after all windows close (non-macOS stays
  resident).
- **UA / identity**: UA suffix `MoisesDesktop-2.0.3-<platform>` appended to every webContents;
  AUMID `ai.moises.studio`; dock icon set; single-instance lock with argv import.
- **Updater**: `@todesktop/runtime` autoUpdater, `checkForUpdates({source:"settings-page",
  disableUpdateReadyAction:true})`; `updates:downloaded` broadcast → Settings shows
  "Restart & install"; native confirm "A new version is available, do you want to restart &
  install?"; before restart/quit: session file + guards cleared. Smoke-test mode flagged.
- **Telemetry**: `@sentry/electron` main init with DSN
  `https://REDACTED@o418792.ingest.sentry.io/REDACTED`.
- **Before-quit**: blocked once to confirm guarded tabs, then unguards, deletes `tabs.json`,
  shuts down capture + plugin server, quits.

## 15. Security model (what's enforced, statically visible)

- **Sender validation on every sensitive IPC**: helper checks `event.senderFrame.url` is
  `https://` on `moises.ai` / `*.moises.ai`; rejects with `{error:true,message:"Not allowed"}`
  + console warning. Audio-capture channels are stricter (studio URLs only).
- Sandbox + contextIsolation on every BrowserWindow and WebContentsView; `nodeIntegration:false`.
- `window.open` policy: auth/payment popups allowed in a fixed 500×700 window; external
  domains → `shell.openExternal` (denied in-app); in-app URLs → **dedupe** to the existing
  tab/window for that realm, else new tab (supports `background-tab` disposition); everything
  else denied. `outlivesOpener` for in-app popups.
- Home tab will-navigate: off-domain navigations are prevented and opened in the system browser.
- Guard dialogs gate data loss (tab close, window close, navigation, quit).
- Preview: accent sanitized, icon markup strictly theirs; plugin logs redact the token.
- For comparison, `E`-series evidence (earlier pass): ASAR integrity fuse off, `OnlyLoadAppAsar`
  off (which is what made this re-slicing pass possible; not a tamper finding).

## 16. Shared-code details worth archiving (from the studio-unshared code in the bundle)

Kept for completeness because the components are byte-identical candidates for the hosted app:

- **wavesurfer** (v7-line API: `WaveSurfer.create`, `getState()`, signal-based reactive state,
  `WebAudioPlayer` with **one `GainNode` per instance** — `muted` implemented as
  `gainNode.disconnect()/connect(destination)`; `setSinkId`; `playbackRate` with pause/replay;
  `stopAt(t)`; sample defaults `waveColor:#999 progressColor:#555 cursorWidth:1 fillParent
  interact autoScroll autoCenter sampleRate:8000`).
- **Preview card list** (stem previews): per-stem wavesurfer, `backend: "WebAudio"` on Safari /
  `"MediaElement"` elsewhere, `normalize:true, barWidth:2, barHeight:1, height:40`; role
  "option" listbox; skeleton state while loading (`_skeleton_1pkng_`); `autoRepeat` option.
- **Stem "handoff" sync** (the wavegroup): playing a card pauses the previously active one,
  seeks the new one to the old's current time (`syncTime`), resumes if it had been playing,
  tracks `lastPlayed/active/isPlaying` in shared state; `play` reuses stored seek time on
  quick switches (`skipPauseFor`). This is how stem switching stays in time.
- **MediaElement vs WebAudio detection**: `/((?!chrome|android).)*safari/i` UA test flips
  backend (Safari bug workaround).

## 17. Unknowns (do not build from these)

- Hosted studio app internals (studio.moises.ai bundles) — not in this artifact; remote pages
  were not fetched. Any "skeleton/spinner" UX inside the studio is runtime/network territory.
- `disableWebSecurity:true` per-tab usages (flag plumbed everywhere; actual caller unknown).
- `audify.node` native exports beyond the host wrapper; capture sample-format negotiation.
- Whether the mixer components are ever mounted (e.g. a future desktop studio) — today: no.
- Runtime-only: actual preview frame quality/perf, drag feel, capture latency on device.

## 18. Evidence summary for this pass

| Fact | Source |
|---|---|
| Route table, tab model, window options, IPC list, guards, session store | `out/main/index.js` @ 965b14e6… (pretty `/tmp/moises-main-pretty.js`) |
| Shell JSX/CSS metrics, theme config, icons, dead-code inventory | `index-CiDG_8MY.js` @ 791aa79e…, CSS @ 8db0403e… |
| Preview window HTML/CSS, drag loop, plugin spawn args, capture IPC | main pretty lines 20–95, 180–330, 1186–1470 |
| Audio capture internals | `out/main/audio-capture-host.js` (ASAR) |
| Webview bridge incl. MessagePort relay | `out/preload/webview.cjs` |
| Earlier REA evidence (fuses, plist, ASAR graph) | REFERENCE.md evidence IDs |

Re-run recipe: §3 (same tree digest `45ad3247…`; do not commit extracted tree or these temp
files — they contain minified source).

---

*Pass date: 2026-10-18. Static only; app not launched. Complements [REFERENCE.md](REFERENCE.md)
(which stays authoritative for product-priority guidance); where this file contradicts an
earlier inference, this file's byte-level evidence wins and REFERENCE.md should be read with
§9.4 of this document in mind.*
