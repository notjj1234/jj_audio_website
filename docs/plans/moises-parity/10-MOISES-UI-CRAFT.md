# Moises UI craft — runtime reference and the Tyrian Nocturne direction

**2026-10-21 Home parity:** §13 supersedes every Home measurement, token, and layout rule in §1.2, §1.5, §1.6, §2.1–§2.3, §4, and §5.1–§5.5. Player notes in §1.3 were not re-measured on this pass. The Home decision is in §13.3.

**Status:** reference + design direction for Phase 1.5 (desktop UI craft). Not shipped. No code
changes are made by this document.
**Date:** 2026-10-20
**Surface:** desktop (`ui/`) first. The website is a later copy; do not edit `web/` or `backend/`
for this phase.
**Related:** `08-EVIDENCE-LOG.md` §11 has the capture inventory and labels. `11-DESKTOP-UI-REDESIGN.md`
turns this direction into file-level tasks.

## 0. Why this document exists

Phase 1 is functionally complete: Home can start a separation, show analysis, and open the practice
player. The remaining problem is not a missing feature. It is **craft**:

- Home looks like a Streamlit demo, not a product.
- Every piece of text is the same amber; the eye has no path.
- The library is a stack of large buttons, not a table.
- At 1024×768 the page clips horizontally.
- The player is capable but crowded; Speed & Key, practice, and transport compete for the same
  attention.

The user asked for one more Moises reverse-engineering pass focused on **UI**, and for the plan
bundle to become a real desktop redesign plan. This document is the reference half. It answers:

1. What does Moises actually do visually, measured rather than guessed?
2. What does our desktop do today, measured rather than described from memory?
3. Which of those differences are worth closing, and which are brand differences we should keep?
4. What is the concrete design direction — tokens, composition, states, and rules?

It is deliberately not a feature plan. Chord editing, capo, setlists, filters, and web parity are
still Phase 2 items. The UI phase makes the existing product feel finished.

### Evidence labels

| Label | Meaning |
|---|---|
| **observed** | Read from the running app with Chrome DevTools Protocol (DOM, computed styles, screenshots) or from the repo source. |
| **bundle-observed** | A label/string exists in a shipped bundle, but the control was not exercised. Not used for UI claims here. |
| **inferred** | A pattern extrapolated from observed screens; not a direct measurement. |
| **unknown** | Not verified in this pass. Do not turn it into a requirement. |

The Moises pass was read-only: no separation, upload, export, purchase, rename, or delete was
triggered. Screenshots and raw DOM stayed in `/tmp`. Personal library titles are not repeated in this
repo. The installed app was Moises 2.0.18 on macOS.

---

## 1. The reference: what Moises does visually

### 1.1 The overall impression

Moises is **quiet, dark, and compact**. The app gets out of the way of the audio:

- A near-black neutral canvas, not a branded blue.
- One saturated accent (cyan) used for the product's identity, the waveform, and the current state.
- Soft neutral surfaces separated by 1px borders, not heavy shadows.
- Small type, tight rows, and a lot of information per screen.
- A fixed player shell: the song identity and transport stay put; the practice surface changes.
- Empty states are plain and honest: “Not detected” rather than an illustration or a fake control.

The craft is not in decoration. It is in **alignment, density, and a single signal color**.

We should not copy the neutrals or the cyan. Our identity is Tyrian blue + amber. We should copy the
discipline.

### 1.2 Library / Home (2026-10-20 pass — superseded)

The numbers in this subsection are the 2026-10-20 pass. Do not build from them. The 2026-10-21 re-measure is §13.

Measured layout:

| Element | Observed value |
|---|---|
| Sidebar | 240–241px, dark rail, logo at top, product groups |
| Header | 76px |
| Nav item | 216×36px, padding 8px 12px, radius 6px |
| Section label | 12px/16px, letter-spacing 1.5px, uppercase |
| Product cards | 4 across at 1024, icon + label, compact |
| Recents cards | ~171×164px, artwork area, title below, horizontal rail |
| Table row | 56px |
| Thumbnail | 48px, radius 4px |
| Buttons | 32px high, radius 6px |
| Table data | Title + subtitle, created date, kebab menu |
| Filters | All / Play / Studio / Mastering / Voice Studio, plus search, filter, sort icons |

Observed patterns:

- The page title is **not** a giant hero. “Home” is the active sidebar item; the content starts with
  product tiles.
- Product tiles are equal-weight entry points. Recents get artwork and a horizontal rail. The library
  is a real table with columns and row actions.
- The table has a count-free, quiet header; controls sit on the right, aligned with the content edge.
- The sidebar uses icons and grouping; it reads as navigation, not a form.
- At 1024, the Home content still fits. The fifth recent card is clipped at the viewport edge, but the
  rail is scrollable; it is not squashed into six equal columns.
- There is no framework chrome, no “deploy” button, no developer promo.

What is worth taking:

- **Compact table rows** with title + subtitle, metadata column, and a row action.
- **Recents as a horizontal rail** with a stable card width, not a responsive column squeeze.
- **Sidebar as navigation**: icons, 40px rows, a grouped hierarchy, a quiet footer.
- **One accent** and neutral text levels.
- **No page hero** when the user already knows what the product is.

What is not worth taking:

- The near-black/cyan palette; ours is Tyrian/amber.
- Their “Not detected” dead end without an explanation; ours should explain why.
- Their accidental card clipping at 1024; use scroll affordance and snap instead.
- Their small metadata at low contrast; keep 12px but meet 4.5:1.

### 1.3 Player (observed at 1260×760)

Measured layout:

| Element | Observed value |
|---|---|
| Left stem rail | 280px |
| Splitter | 8px |
| Canvas | 980px at 1260px viewport |
| Fixed top timeline/annotation area | 132px |
| Tracks viewport | 531px |
| Bottom transport | 96px |
| Stem row | 80px |
| Transport buttons | 48×48px, radius 12px |
| Project cover | 56×56px |
| Footer columns | 379 / 398 / 379px |

Observed structure, top to bottom:

1. **Annotation lanes** — Chords, Sections, Lyrics — across the top, with a ruler and bar numbers.
2. **Waveform/stem stage** — each stem has a colored waveform; the left rail has volume, M/S, and a
   record/arm control. Empty lanes say “Not detected.”
3. **Practice sheet** — a large bottom panel. In the observed chord-chart state it is ~342px high,
   with bar-number gutters, 4 beat cells per bar, chord symbols, and a white active-beat cell. The
   active playhead is a white vertical line with a triangle marker.
4. **Transport** — left project block, centered play cluster, right tempo/key and view toggles.
   Timecode sits under the transport. The player bar has three columns at 1260.
5. **Secondary controls** — metronome, count-in, loop/A-B, export, stems picker are icons/pills, not
   a wall of sliders. Tempo & Key, Count-in, Smart Metronome, Stems, and Export open popovers/dialogs.

Observed interaction patterns:

- The current beat is a **filled cell** (white in Moises). It is the strongest state in the practice
  surface.
- The current chord has a shape/diagram; the chart is the main workspace, not a small tab.
- Sections and lyrics are **lanes** on the timeline and also list views in the practice sheet.
- The transport is fixed; the practice surface can be opened, closed, and resized without losing the
  playhead.
- At 1024×768 the transport becomes two rows: transport above metadata. The layout remains usable.
- At 900×700 the left rail compresses to ~210px and the player still works. This is the responsive
  floor worth matching.
- Hover actions are secondary; the primary transport and current state are always visible.

What is worth taking:

- **Fixed player shell**: identity, transport, and practice surface have stable regions.
- **Bottom practice sheet** with tabs, not a panel that pushes the stems around unpredictably.
- **Timeline annotation lanes** for Chords/Sections/Lyrics.
- **A real current-beat cell**, not just a text label.
- **Compact popovers** for tempo/key, count-in, metronome; a dialog only for export/stems.
- **Two-row transport at 1024**.
- **Primary controls visible; secondary controls in menus**.

What is not worth taking:

- White as the active-beat color. We will use amber, our signal color.
- Cyan waveform gradients; ours is amber on Tyrian.
- The exact 280/132/531/96 dimensions; use them as a reference, not a contract.
- Their hidden/absent-state handling; ours will be more informative.
- Their font (Articulat is licensed; we have Satoshi).
- Their icon set/assets; use our own inline SVG or Material Symbols consistently.

### 1.4 Popovers and dialogs (observed)

| Surface | Observed behavior | Design lesson |
|---|---|---|
| Tempo & Key | A popover with BPM/key values and controls; compact, anchored to the footer pill. | Frequently used values belong in a compact pill + popover, not permanent sliders. |
| Count-in | A popover with 4/8/16 bars and a clear on/off state. | Put it next to transport, not in a settings page. |
| Smart Metronome | A popover with enable, sound, and follow controls. | Keep advanced click options out of the main transport. |
| Stems picker | A dialog with grouped stem targets and a primary action. | Group by instrument family; do not show a flat list of 27. |
| Export | A dialog with Mix/Tracks/Chord Chart tabs, formats, sample rate, and include options. | A dialog is right when there are choices and a commit action. |

The pattern is consistent: **popover for a small adjustment, dialog for a task with a commit**.

### 1.5 Type, color, spacing (observed)

Moises token sample (computed styles / screenshot sampling):

| Role | Value |
|---|---|
| Library background | `#101213` |
| Player background | `#111313` |
| Canvas | `#121213` |
| Surface | `rgba(202, 224, 250, 0.08)` / `#2B2F33` |
| Border | `rgba(203, 221, 242, 0.12)` |
| Primary text | `#EDEEF0` / `#FFFFFF` |
| Secondary text | `rgba(216, 233, 254, 0.49)` |
| Muted text | `rgba(203, 223, 247, 0.38)` |
| Accent (UI) | `#78F7FF` |
| CTA | `#00D8E2` |
| Waveform | `#00D1E1` → `#00B1F8` gradient |
| Active metronome | `#FFC53D` with `#111113` text |
| Font | “Articulat” (licensed; do not copy) |
| Body | 16px/24px, weight 400, 0.32px tracking |
| Page title | 28px/36px, weight 500, −0.21px tracking |
| UI text | 14px/20px |
| Metadata | 12px/16px |

Observations:

- The accent is used for **identity and current state**, not for every label.
- Text hierarchy is carried by **neutral value**, not by tinting all text.
- The player uses a **yellow** active metronome state, distinct from the cyan product accent. That is
  a functional state color, not a second brand color.
- The page title is 28px; the library is dense; the type scale is deliberately restrained.

### 1.6 Responsive behavior (observed)

| Viewport | What happens |
|---|---|
| 1260×760 | Player: 280px rail, 980px canvas, 132px top, 531px tracks, 96px bottom; Home: 5 recent cards, table below. |
| 1024×768 | Player footer becomes two rows (transport above metadata); Home product cards remain 4 across; recents rail clips the fifth card but scrolls; table remains a table. |
| 900×700 | Player rail ~210px; still usable. Home still scrolls rather than overflowing the page. |

The important part is not the exact breakpoint. It is that **the page never develops a horizontal
scrollbar**, and the primary action remains visible.

### 1.7 What we will not copy

- The near-black + cyan palette. Our brand is Tyrian blue + amber; cloning Moises would make a
  competitor clone with worse recognition.
- The Articulat font, logo, icon assets, illustrations, or any licensed asset.
- Their exact product-card / recents / table markup. We will design our own composition.
- Their paywall, upsell, credit, or “Free” badges. We have no quotas.
- Their “Not detected” dead end. Our empty states must say **why** and what the user can do.
- Their accidental 1024 clipping. Our recents rail must show a scroll affordance and snap; the page
  itself must not clip.
- Their very low-contrast metadata. Keep 12px, but pass 4.5:1.
- Their single-purpose dark theme only. We keep our theme presets, but the default is Tyrian.

---

## 2. The current desktop UI — evidence

### 2.1 The 1440 view (2026-10-20 pass — superseded)

The clip story in §2.1–§2.2 was not reproduced on 2026-10-21. Current Home numbers are §13.12.

Captured at 1440×1000 with a headless Chrome CDP session against the running Streamlit app
(`/tmp/audio-tools-home-live.png`; not committed because it contains local library titles).

What the screenshot shows:

- A 300px Streamlit sidebar with Home / Audio Isolation / YouTube to MP3 / Tab PDF (demo) /
  Settings, an Interface radio group, and a demo caption.
- A 44px amber H1 “Audio Tools (CPU)”, a one-line amber caption, then three equal-weight 74px buttons:
  “Learn a song”, “Save from YouTube”, “Tab PDF”.
- Three caption lines under the buttons, outside the clickable area.
- A “Recents” section with six 150×74 text buttons; titles wrap to 2–5 lines, ages sit under them.
- A “Library” section with a search input, then 74px full-width rows. Each row is a button with the
  title and age concatenated; the analysis line is a caption below the button; a separate 74px
  Practice/Analyse button sits to the right.
- A Streamlit developer promo overlay (“Help agents write better apps / Install”) over the content.
- The whole page is `#192542`; all text is `#F6AD49` at full or reduced opacity.

The page is functional, but it reads as a **developer demo** rather than a music product.

### 2.2 The 1024 view — the release blocker

Captured at 1024×768 (`/tmp/audio-tools-home-1024.png`; not committed).

At 1024:

- The sidebar stays 300px.
- The main content still begins at x=380 and is 980px wide. It does not reflow to the 724px
  remaining viewport.
- The H1 is visibly cut off: “Audio Tools (C…”.
- The three action buttons extend past the right edge; the “Tab PDF” card is clipped.
- The six-recent grid compresses into ~100px columns. Titles wrap to 4–5 lines, the cards have
  uneven heights, and the ages detach from their cards.
- The Streamlit promo covers the title and part of the primary action.
- “Library” begins below the fold; the user must scroll before seeing the actual library.

This is not a small polish issue. At the most common 13-inch laptop width, the Home screen is
**unusable**. Phase 1.5 must treat 1024 as a first-class design width, not a fallback.

### 2.3 Measured current styles

From the running Home at 1440×1000:

| Element | Current value |
|---|---|
| Body / sidebar background | `#192542` |
| Body / sidebar text | `#F6AD49` |
| Font | Satoshi 16px/25.6px, weight 400 |
| Sidebar | 300px wide |
| Nav item | 238×28px, 16px/32px, weight 600, active bg `#2A4467`, radius 6px |
| H1 | 44px/52.8px, weight 700, amber, width 980px, x=380 |
| Primary action | 316×74px, radius 14px, bg `#2A4467`, 1px amber border (`rgba(246,173,73,0.35)`), 16px/20px |
| Recent card | 150×74px, same button style |
| Library row | 832×74px, same button style |
| Practice/Analyse | 132×74px, same button style |
| Analysis caption | 14px, amber, aligned at x=380 |
| Main content | 980px wide at 1440; x=380 |

Contrast is not the main failure: amber `#F6AD49` on Tyrian `#192542` measures **7.94:1**. Amber at
70% opacity measures **4.57:1**; at 60% it drops to **3.74:1**. The problem is that **every role uses
the same hue**, so contrast and size are doing all the hierarchy work. That is why the page feels
flat even though it is readable.

Satoshi's bundled faces are 300/400/500/700/900. The current nav uses weight **600**, which the
browser must synthesize. Phase 1.5 uses only **400/500/700**; avoid 300 and 900 as well, and never
faux 600.

### 2.4 What is actually good and must survive

- **Satoshi**, bundled offline. It is distinctive and already loaded by the shell and mixer.
- **Tyrian blue + amber**. It is a recognizable identity; do not replace it with Moises cyan.
- **The local-only promise**. “Everything stays on this computer” is a real differentiator.
- **The simple three-action Home**. The information architecture is right; the composition is wrong.
- **One-click Practice** on an analysed run.
- **The existing mixer capability**: per-stem volume, mute/solo, pan, speed/key, metronome, count-in,
  A/B loop, picture, save mix.
- **The practice tabs** (Chords/Sections/Lyrics/Tab) and the in-player tab measure.
- **Keyboard shortcuts** (`L`, `C`), `aria-live` status, and the reduced-motion branches already in
  the code.

Phase 1.5 is a **recomposition and token pass**, not a rewrite of the audio engine or the workflow.

### 2.5 Current player inventory

The player is a custom iframe (`ui/stem_mixer_component/frontend/`). It is not a Streamlit form. The
current structure is:

1. `.mixer-header` — track title + status + load bar.
2. `.mixer-transport` — Play/Stop/Restart, time, seek, master volume, Speed & Key sliders.
3. `.mixer-master` — presets, Mute all, Reset mix, Clear solo, Show video.
4. `.mixer-practice-panel` (`<details open>`) — Practice summary, loop/count-in toolbar, tabs, body.
5. `.mixer-stage` — video pane and stem rows.

This order is the source of the crowding:

- Speed & Key is permanent, wide, and sits inside the transport.
- The practice panel comes **before** the stage, so opening it pushes the stems down.
- The panel uses a native `<details>` disclosure, not the product’s tab/sheet language.
- Master, presets, and destructive actions form a button row between transport and stage.
- At 1024, the transport has too many controls for one row and no defined wrap behavior.

The audio engine and event wiring are solid; the **regions and hierarchy** are wrong. The redesign
should move the practice panel below the stage, make Speed & Key a compact popover, move master into
the stem rail header, and put presets/reset in a compact menu. None of that needs an audio-graph
change.

---

## 3. HIG audit: what a senior reviewer would flag

The Apple HIG is written for native apps, but the principles translate to a Streamlit/Electron shell.
The relevant pages are Layout, Typography, Color, Lists and Tables, Sidebars, Popovers, Dark Mode,
Loading, Focus and Selection, Accessibility, Designing for macOS, and the cross-platform translation
guide. The audit below is scoped to what this desktop app controls.

| Lens | Current finding | Target |
|---|---|---|
| **Visual hierarchy** (Layout) | H1 44px, every action 74px, every text amber. The primary action does not dominate. | 28px page title; one primary card; two secondary actions; 14px UI text; 12px meta; amber reserved for action/signal. |
| **Layout / responsiveness** (Layout) | Main content fixed at 980px from x=380; 1024 clips. | 12-column grid inside the remaining width; no horizontal page scroll at 900–1440. |
| **Typography** (Typography) | 16px/25.6px UI, 44px H1, faux 600, long line lengths. | 14px/20px UI, 28px/34px page title, 12px/16px meta, 400/500/700 only; 60–75ch max for prose. |
| **Color** (Color) | One hue for headings, body, actions, nav; opacity used as hierarchy; 60% amber fails contrast. | Three neutral text levels + one amber signal + functional status colors; no text below 4.5:1. |
| **Lists and tables** (Lists and tables) | Library is 74px buttons; title+age concatenated; no columns, headers, or row actions. | A real table: 56px rows, headers, title/subtitle, analysis, updated, action; keyboard/table semantics. |
| **Sidebars** (Sidebars) | 300px, text-only, 28px rows, a radio group competing with navigation. | 240px (216px at 1024/900), icons, 40px rows, active indicator, compact mode switch in the footer. |
| **Popovers** (Popovers) | Speed & Key and count-in are permanent inline controls; some actions are free-floating. | Compact pills/popovers for tempo/key, count-in, metronome; dialog only for export/stems. |
| **Dark mode** (Dark Mode) | Dark-only, but surfaces are one flat blue; borders/inputs are Streamlit defaults. | Layered Tyrian surfaces, neutral text, semantic borders, visible focus; respect the selected theme. |
| **Loading** (Loading) | Spinners and full-page reruns; async analysis uses `st.spinner`; no skeletons. | Immediate shell + skeleton rows; stage progress for jobs; no blank page; `aria-live` status. |
| **Focus / keyboard** (Focus and selection) | Global focus ring exists on some Streamlit buttons, but the library is 40 tab stops; rows are buttons. | Roving table focus or clear tab order; visible 2px ring; Enter/Space; Esc closes; shortcuts documented. |
| **Accessibility** (Accessibility) | Repeated “Practice”/“Analyse” labels lack song context; table semantics absent; search label hidden; icon-only controls need labels. | Contextual `aria-label`, real table semantics, visible label or `aria-label`, 32px pointer / 44px touch targets, reduced motion. |
| **macOS / desktop fit** (Designing for macOS) | Large fixed canvas ignores window resizing; app feels like a web page in a window. | Responsive at 900/1024/1280/1440; preserve window state; pointer/keyboard first; no hover-only primary actions. |
| **Content** (writing) | “File · …”, “Not analysed yet”, “isolate”, “stems” in first-run copy. | “Song”, “parts”, “Practice”, “Analyse”; explain once; no developer jargon on Home. |
| **Craft** (design lead) | Default Streamlit promo, radio dots, and a help bubble break the fiction. | No framework chrome in the packaged app; every visible pixel belongs to the product. |

### 3.1 The findings that matter most

**Critical**

1. **1024 horizontal overflow.** The page clips the title and primary action. Fix before any color
   polish.
2. **Framework chrome is visible.** The “Help agents write better apps” promo and default Streamlit
   header/menu make the desktop app look like a dev preview. Remove them from packaged builds.
3. **No hierarchy.** All text is amber; the primary action is the same size as the secondary actions.
   The first-time user does not know where to start.

**High**

4. **The library is not a table.** Six songs require scanning six 74px buttons and detached captions;
   forty songs would be unusable.
5. **Recents collapse instead of scrolling.** Six equal columns at 1024 produce 4–5-line titles and
   uneven cards.
6. **The sidebar is too wide and too plain.** 300px of text-only navigation; 240px with icons would
   give the content 60px back and read as navigation.
7. **Speed & Key, master, presets, and practice all compete in the player.** The transport has no
   single visual center.
8. **The practice panel is above the stage.** Opening chords pushes the stems down; the player does
   not have a stable practice surface.
9. **No loading skeletons or stage progress on Home.** Analysis is a blocking spinner.
10. **No table/keyboard semantics.** Repeated action labels and 40 tab stops are an accessibility
    debt.

**Medium**

11. **Type is too large and loose for a desktop tool.** 16px/25.6px and 44px H1 read as a landing
    page, not a workspace.
12. **Satoshi 600 is synthesized.** Use 400/500/700.
13. **Universal `scale(0.97)` on every button** feels toy-like; use background/border shifts and
    reserve scale for small icon controls.
14. **Muted amber below 70% fails contrast.** Use neutral secondary/muted tokens instead of opacity.
15. **No visual identity in the library.** Text-only rows feel like a file manager.
16. **No queue/status at a glance.** Running jobs can be below the fold.
17. **The Interface Lite/Pro radio is a form control in the navigation rail.** Make it a compact
    two-segment switch.
18. **The brand is in the page title, not the sidebar.** Move product/edition to the rail; use the
    page title for the user's task.
19. **Recent ages are verbose and detached.** Put age in the card meta, not a separate caption.
20. **No selected/last-opened state.** The user cannot see which project they were just in.

### 3.2 The design response in one sentence

> Keep the Tyrian blue and amber, but turn the amber into a **single signal** that marks the action,
> the current beat, and the playhead — and let parchment text, layered blue surfaces, and compact
> rows carry everything else.

---

## 4. Design direction — Tyrian Nocturne: Signal & Stage

**2026-10-21:** this section is not the Home visual system. Home tokens, type, and color are §13. The player direction below is deferred to Phase 1.6.

### 4.1 Thesis

**Tyrian Nocturne** is a dark, warm, analog practice room. The surfaces are deep Tyrian blue, the
text is warm parchment, and a single amber signal runs through the product: the primary action, the
waveform, the playhead, the current beat, the active lyric line, the current tab measure. The rest is
quiet.

The name is already used by the current theme. Phase 1.5 keeps the name and gives it a real system.

**Three words:** local, quiet, in time.

**One-line art direction:** a stage at night, lit by one amber lamp.

### 4.2 The signature: the Signal

The amber signal is the product's most recognizable element. It appears in exactly these places:

1. The primary CTA (`Choose a song`, `Separate`, `Save mix`).
2. The current beat cell in the chord grid.
3. The playhead and the played portion of the waveform.
4. The active nav indicator and the active tab underline.
5. The active lyric line's 2px left rule and the current word.
6. The current tab measure border.
7. The focus ring (`#FFD58A`, 2px, 2px offset).
8. The running-job pulse (a 6px dot, not a glowing button).

It does **not** appear on body text, metadata, every heading, every border, or every icon. If
everything is amber, nothing is.

### 4.3 The second motif: the Stage edge

Surfaces get a 1px top highlight, like light catching the front edge of a stage:

```css
background:
  linear-gradient(180deg, rgba(255, 255, 255, 0.045), transparent 28px),
  var(--surface);
border: 1px solid var(--border-subtle);
```

This gives depth without glassmorphism, gradients everywhere, or heavy shadows. It is subtle enough
to survive at 1× and 2× displays.

### 4.4 The third motif: six strings

A six-line hairline motif can appear in the primary card and empty states: six 1px lines, 6px apart,
fading from amber at 18% to transparent. It is a guitar nod, not a decorative pattern. Use it once per
screen at most. Do not put it behind text or on every card.

### 4.5 Color tokens

The palette deepens the current Tyrian blue instead of replacing it. `#192542` remains a mid-surface;
the root goes darker so amber and parchment can breathe.

| Token | Value | Use |
|---|---|---|
| `--bg-root` | `#0C1428` | App background |
| `--bg-rail` | `#101B33` | Sidebar / left rail |
| `--bg-canvas` | `#121F3A` | Main canvas |
| `--bg-surface` | `#182747` | Cards, table, panels |
| `--bg-raised` | `#1F3157` | Hover, popovers, transport |
| `--bg-hover` | `#263B66` | Row hover, secondary button hover |
| `--bg-active` | `#2E4676` | Selected row, pressed surface |
| `--border-subtle` | `rgba(244, 237, 224, 0.08)` | Default card/table borders |
| `--border-default` | `rgba(244, 237, 224, 0.14)` | Inputs, buttons |
| `--border-strong` | `rgba(244, 237, 224, 0.24)` | Hover, focused container |
| `--text-primary` | `#F4EDE0` | Titles, values, active text |
| `--text-secondary` | `#C3CFDF` | Body, secondary labels |
| `--text-muted` | `#94A3B8` | Metadata, placeholders, inactive |
| `--text-disabled` | `#64748B` | Disabled only; never information |
| `--text-inverse` | `#0C1428` | Text on amber/light fills |
| `--accent` | `#F6AD49` | Primary action, signal, current state |
| `--accent-hover` | `#FFC266` | Primary hover |
| `--accent-press` | `#D9902F` | Primary press |
| `--accent-soft` | `rgba(246, 173, 73, 0.14)` | Active nav/tab background |
| `--accent-border` | `rgba(246, 173, 73, 0.45)` | Selected outline |
| `--focus-ring` | `#FFD58A` | Keyboard focus |
| `--selection` | `rgba(246, 173, 73, 0.22)` | Text selection |
| `--success` | `#6FCF97` | Success icon/fill (dark text) |
| `--warning` | `#F2C14E` | Warning icon (not body text) |
| `--danger` | `#EB6A6A` | Error/destructive (dark text) |
| `--info` | `#7FB3E8` | Informational (dark text) |
| `--waveform-idle` | `#20365C` | Unplayed waveform |
| `--waveform-played` | `#F6AD49` | Played waveform |
| `--waveform-bg` | `#0A1224` | Waveform well |
| `--chord-cell` | `#1B2B4D` | Inactive chord cell |
| `--chord-cell-active` | `#F6AD49` | Current beat cell |
| `--chord-cell-empty` | `#162442` | Empty beat cell |

Contrast checks (WCAG 2.x, sRGB):

| Pair | Ratio | Verdict |
|---|---:|---|
| `#F4EDE0` on `#0C1428` | 15.73:1 | pass |
| `#C3CFDF` on `#182747` | 9.37:1 | pass |
| `#94A3B8` on `#1F3157` | 5.01:1 | pass for 12px |
| `#F6AD49` on `#0C1428` | 9.59:1 | pass |
| `#0C1428` on `#F6AD49` | 9.59:1 | pass |
| `#C3CFDF` on `#2E4676` | 5.91:1 | pass |
| `#94A3B8` on `#2E4676` | 3.63:1 | **do not use muted text on active blue** |
| `#64748B` on `#182747` | 3.11:1 | disabled only |
| `#F4EDE0` on `#F6AD49` | 1.64:1 | **never** |

Rules:

- Body/meta on active blue uses `--text-primary` or `--text-secondary`, never `--text-muted`.
- `--text-muted` passes on `--bg-surface` (5.77:1) and `--bg-raised` (5.01:1), but fails on
  `--bg-hover` (4.31:1) and `--bg-active` (3.63:1). On hover/selected rows, switch metadata to
  `--text-secondary` or keep the row background at `--bg-surface`.
- On amber fills, use `--text-inverse`; never parchment.
- Status is never conveyed by color alone: include an icon or text.
- Do not use `opacity` to create a text hierarchy. Use the tokens.

### 4.6 Surface and elevation

| Level | Token | Use | Shadow |
|---|---|---|---|
| 0 | `--bg-root` | App | none |
| 1 | `--bg-canvas` | Main content | none |
| 2 | `--bg-surface` | Cards, table, sheet | `0 1px 0 rgba(255,255,255,0.04)` inset top |
| 3 | `--bg-raised` | Hover, popover, transport | `0 12px 32px rgba(3, 8, 18, 0.28)` |
| 4 | `#233963` | Dialog | `0 24px 64px rgba(3, 8, 18, 0.55)` |

No backdrop-filter except the video overlay if needed. No glass panels. No neon glows.

### 4.7 Typography

Satoshi is the UI face. Tablature uses the system monospace stack; no new font dependency.

| Token | Size / line | Weight | Tracking | Use |
|---|---|---|---|---|
| `display` | 32/38 | 700 | −0.02em | Rare brand moment / empty-state title |
| `h1` | 28/34 | 700 | −0.015em | Page title |
| `h2` | 20/28 | 700 | −0.01em | Section title |
| `h3` | 16/24 | 500 | −0.005em | Card title, panel title |
| `body-lg` | 16/24 | 400 | 0 | Reading copy, empty states |
| `body` | 14/20 | 400 | 0 | UI body, table title |
| `body-strong` | 14/20 | 500 | 0 | Row title, emphasis |
| `meta` | 12/16 | 500 | 0.01em | Metadata, time, counts |
| `label` | 11/14 | 700 | 0.08em | Uppercase section labels |
| `numeric` | 12/16 | 500 | 0.01em | BPM, time, bar numbers; `font-variant-numeric: tabular-nums` |
| `mono` | 12/18 | 400 | 0 | Tablature; `ui-monospace, SFMono-Regular, Menlo, Consolas, monospace` |

Rules:

- Never use weight 600; Satoshi has no 600 face in the bundled set. Use 500 or 700.
- Page title max 28px on desktop. The old 44px H1 is retired.
- UI body is 14/20; use 16/24 only for reading paragraphs and empty-state copy.
- Line length for prose: 60–75ch.
- Uppercase labels only for section labels and small status; never for long copy.
- Japanese/English titles: `overflow-wrap: anywhere` only when needed; prefer a 2-line clamp with
  ellipsis and a tooltip/title attribute for the full title.

### 4.8 Spacing, radii, sizes

| Token | Value |
|---|---|
| `space-1` … `space-8` | 4, 8, 12, 16, 20, 24, 32, 40px |
| `space-9` | 48px |
| `space-10` | 64px |
| `radius-xs` | 4px (chips, thumbs) |
| `radius-sm` | 6px (inputs, small buttons) |
| `radius-md` | 8px (buttons, table rows) |
| `radius-lg` | 12px (cards, popovers) |
| `radius-xl` | 16px (primary card, dialogs) |
| `radius-pill` | 999px (status pills only) |
| Sidebar | 240px ≥1100; 216px 900–1099 |
| Header | 64px |
| Nav row | 40px |
| Table row | 56px |
| Button | 32px small / 36px default / 40px primary / 48px transport |
| Icon button | 32px (44px touch target via padding) |
| Input | 36px |
| Focus ring | 2px + 2px offset |

Spacing rules:

- Page padding: 32px ≥1280, 24px 1024–1279, 20px 900–1023.
- Section spacing: 32px between major sections; 16px between header and content; 12px between rows.
- Card padding: 20–24px; table cell padding: 12px 16px.
- Do not use `st.columns` for the Home composition. Use a 12-column CSS grid with `minmax(0, 1fr)`.
- Every flex/grid child that contains text gets `min-width: 0` to prevent overflow.

### 4.9 Icons

- Use **Material Symbols Rounded** in the Streamlit shell (already available) and **inline SVG** in the
  components, matching 1.5–1.75px stroke at 16/20px.
- One icon family per surface. Do not mix emoji, Material, and custom glyphs in the same row.
- Icon-only buttons need `aria-label` and a tooltip on hover/focus.
- Icons are never the only label for a primary action; pair with text on Home and in dialogs.
- Do not use the Moises icon set or copy their glyphs.

### 4.10 Motion

| Token | Value | Use |
|---|---|---|
| `motion-fast` | 120ms `cubic-bezier(0.22, 1, 0.36, 1)` | Hover, focus, color |
| `motion-base` | 180ms `cubic-bezier(0.22, 1, 0.36, 1)` | Popover, tab, row |
| `motion-sheet` | 240ms `cubic-bezier(0.22, 1, 0.36, 1)` | Practice sheet open/close |
| `motion-page` | 180ms ease-out | Page content fade/slide 4px, optional |

Rules:

- No bounce, no spring, no looping animation except the running-job pulse (1.6s, opacity only).
- No `transform: scale()` on every button. Use background/border color; scale only 32px icon buttons
  on press (`0.96`) if it feels right.
- Respect `prefers-reduced-motion: reduce`: remove transforms, sheet slides, and pulse; keep instant
  state changes.
- The playhead is functional motion; it is not animated by CSS, it follows audio time.

### 4.11 Voice

- **Product name:** Audio Tools. **Edition:** CPU / CUDA / Both. **Version:** quiet, in About.
- **User words:** song, parts/stems, mix, practice, tab, key, tempo. Avoid “isolate”, “artefact”,
  “manifest”, “job” on Home.
- **Verbs:** Learn, Practice, Separate, Analyse, Save, Export.
- **Tone:** calm, specific, local. No hype, no “AI magic”, no exclamation marks.
- **British spelling** is already in the UI: “Analyse”, “analysed”, “practise” (verb). Keep it
  consistent. Buttons use “Practice” (noun/feature).
- **Empty states** say what is missing and why, not “Oops!”.
- **Errors** say what survived and what to do next. Never blame the user.

---

## 5. Screen specs

**2026-10-21:** Home specs in §5.1–§5.5 are superseded by §13. Do not build the 28px page title, the 216px rail, or the 168px recent cards.

### 5.1 The shell

**Goal:** the app frame should disappear. The sidebar is navigation; the main area is the workspace.

- Sidebar 240px (216px at 900–1099), `--bg-rail`, 1px right border `--border-subtle`.
- Brand block at top: “Audio Tools” 18/24 700, edition/version 12/16 muted, 20px padding. A 2px amber
  vertical rule to the left of the wordmark is optional; do not add a logo illustration.
- Nav rows 40px, 12px horizontal padding, 8px gap, icon 18px, label 14/20 500. Active: `--accent-soft`
  background, amber text, 2px amber left indicator; hover: `--bg-raised`; focus: 2px `--focus-ring`.
- Mode switch at the bottom: label `Interface` 11/14 700 uppercase muted; a 2-segment control
  `Lite | Pro` 32px high; the selected segment is `--accent` with `--text-inverse`, the other is
  transparent. A short caption “Lite picks speed automatically.” 12/16 muted on hover/help.
- Footer: `Local only · No uploads` 12/16 muted with a small dot; version in About, not in the rail.
- Hide: Streamlit header, deploy button, footer, status widget, the “Help agents write better apps”
  promo, and any “Made with Streamlit” chrome. Keep a single, product-owned loading indicator.
- Collapse control: visible on hover/focus, 32px; at 1024 the rail remains open by default; the user
  can collapse it. Do not auto-collapse and shift the layout during a job.
- Page content starts at y=0 under a 64px custom top bar. The component owns the top bar; the
  Streamlit header is hidden.

At 1024, the rail is 216 and the main content gets 808px. At 900, the rail is 216 and the content
gets 684px; the table switches to its compact mode.

**Implementation note:** the 300px Streamlit sidebar is not a design choice; it is the default. A
short shell spike must prove that a CSS width override and a full-bleed component work without a gap
or overlap. If the override is unstable, keep the rail at 280 and reduce page padding; do not ship a
broken full-bleed illusion.

### 5.2 Home — 1440 layout

```
┌──────────────────────┬─────────────────────────────────────────────────────────────┐
│ Audio Tools          │ LOCAL WORKSPACE                    ● Local   [Queue 2]      │ 64
│ CPU · 0.1.5          │ Your music, ready to play.                                  │
│                      │ Separate, analyse, and practise — everything stays here.    │
│ ▸ Home               │                                                             │
│   Audio Isolation    │ ┌────────────────────────────────┐ ┌───────────────────────┐ │
│   YouTube to MP3     │ │ START HERE                     │ │ Save from YouTube     │ │
│   Tab PDF            │ │ Learn a song                   │ │ Save a public video   │ │
│   Settings           │ │ Drop in a song. We separate... │ │ as audio. No upload.  │ │
│                      │ │ [Choose a song →]   ~~~~~~~~~~ │ │ [Save audio]          │ │
│ ─────────────────    │ └────────────────────────────────┘ ├───────────────────────┤ │
│ Interface            │                                    │ Tab PDF               │ │
│ [ Lite | Pro ]       │                                    │ A rough guitar tab... │ │
│                      │                                    │ [Open Tab PDF]        │ │
│ ● Local only         │ Recents                              View library →      │
│   No uploads         │ [card] [card] [card] [card] [card] →                       │
│                      │                                                             │
│                      │ Library                              6 songs  [Search...]  │
│                      │ Song                    Analysis          Updated   ···   │
│                      │ [art] Title             105 BPM · Dm · 7  2 mo ago  [Practice]│
│                      │       File · 4:12                                           │
└──────────────────────┴─────────────────────────────────────────────────────────────┘
```

Grid:

- Content width max 1200px; page padding 32px.
- Action deck: 12-column grid; primary card spans 7 columns; secondary stack spans 5 columns (two
  cards, 84px each + 12px gap). The primary card is 176px high; secondary cards are 84px high.
- Recents: 5 cards at 168px + 16px gap, horizontal rail with `overflow-x: auto`, scroll snap, and a
  fade mask on the right edge. The rail is 156px high.
- Library: header row 40px, then 56px rows. The table is inside a surface with 1px border and 12px
  radius; header uses `--text-muted` 11/14 uppercase.
- Top bar: 64px, transparent/canvas, brand eyebrow left, status/queue right. The page title sits
  below it, not inside the top bar.
- Primary card: `--bg-surface`, 16px radius, 24px padding, 1px border, stage-edge highlight. Eyebrow
  “START HERE” amber 11/14 700. Title 24/30 700. Copy 14/20 secondary, max 52ch. CTA 40px amber with
  dark text. A six-string/signal motif in the lower-right, `aria-hidden`.
- Secondary cards: `--bg-canvas` or transparent, 12px radius, 16px padding, 1px border. Icon 20px
  amber, title 16/24 700, copy 13/18 muted (but `--text-muted` passes on surface), action as a
  text+arrow link or 32px ghost button. They must not use the amber fill; only the primary CTA does.
- Section headers: `Recents` / `Library` 20/28 700; right-side action 12/16 500 muted with hover
  primary. Count next to Library 12/16 muted.

### 5.3 Home — 1024 layout

```
┌──────────────┬──────────────────────────────────────────────────────┐
│ Audio Tools  │ LOCAL WORKSPACE              ● Local   [Queue]       │
│              │ Your music, ready to play.                          │
│ ▸ Home       │                                                      │
│   Audio ...  │ ┌──────────────────────────────────────────────────┐ │
│   YouTube    │ │ START HERE                                       │ │
│   Tab PDF    │ │ Learn a song                                     │ │
│   Settings   │ │ Copy + [Choose a song →]                         │ │
│              │ └──────────────────────────────────────────────────┘ │
│              │ ┌───────────────────────┐ ┌────────────────────────┐ │
│              │ │ Save from YouTube     │ │ Tab PDF                │ │
│              │ └───────────────────────┘ └────────────────────────┘ │
│              │ Recents                    View library →           │
│              │ [card] [card] [card] →                              │
│              │ Library                    6 songs  [Search...]     │
│              │ Song / Analysis / Practice                          │
│              │ [art] Title            105 BPM · Dm · 7  [Practice]  │
└──────────────┴──────────────────────────────────────────────────────┘
```

Rules:

- Rail 216px; page padding 24px; content 760px.
- Primary card full width; secondary actions in a 2-column row below it.
- Recents rail shows 3 full cards and a partial fourth (scroll affordance); no 6-column squeeze.
- Table hides the `Updated` column; the age moves under the title or into the analysis meta.
- Table row remains 56px; analysis wraps to two lines if needed; action is 32px.
- No horizontal page scroll. The recents rail is the only horizontal scroll on Home.
- H1 24/30 at this width; body 14/20.

### 5.4 Home — 900 layout

- Rail 216; padding 20; content 664px.
- Primary card full width; secondary actions stack one per row or stay 2-up if each is ≥300px.
- Recents rail shows 2 full cards + partial third.
- Table becomes a **stacked row**: title + meta on the left; analysis chips below; action at the right;
  `Updated` is hidden. Row height 72px (two lines), not 56.
- Player entry from a row still one click.
- If the viewport is below 900, show a product-owned “Audio Tools needs a little more room” panel with
  the current window size and a “Continue anyway” link? The desktop app should set a 1024×700 minimum
  window size; 900 is the graceful floor. Do not spend effort below 900.

### 5.5 Home components

#### Primary action card

| Property | Spec |
|---|---|
| Size | 7 columns, min-height 176px |
| Surface | `--bg-surface`, radius 16, border subtle |
| Eyebrow | `START HERE`, 11/14 700, amber, 0.08em |
| Title | `Learn a song`, 24/30 700 |
| Copy | 14/20 secondary, max 52ch |
| CTA | `Choose a song` 40px, amber fill, dark text, arrow icon |
| Secondary hint | `or drop a file on the window` 12/16 muted (only if drop is actually supported; otherwise omit) |
| Motif | six-string/signal, `aria-hidden`, lower-right |
| Hover | border `--accent-border`, surface lightens one step; no lift/shadow |
| Focus | focus ring on CTA; the card itself is not a button |

#### Secondary action card

| Property | Spec |
|---|---|
| Size | 5 columns, 84px high (two stacked) |
| Surface | `--bg-canvas`, radius 12, border subtle |
| Icon | 20px amber (YouTube download / tab) |
| Title | 16/24 700 |
| Copy | 13/18 muted, one line if possible |
| Action | `Save audio` / `Open Tab PDF` as a 32px ghost/text button |
| Hover | border strong, background `--bg-surface` |
| Focus | ring on action |

#### Recent card

| Property | Spec |
|---|---|
| Size | 168×156px, radius 12, surface |
| Art | 168×92 signal motif generated from the run ID; no fake album art |
| Title | 14/20 500, 2-line clamp |
| Meta | 12/16 muted: `105 BPM · Dm` |
| Status | 24px chip: `Ready` / `Draft` / `Needs analysis` |
| Action | whole card opens the mixer; a 28px play/open icon appears on hover/focus |
| Hover | border strong, surface lightens; no lift |
| Focus | 2px ring; Enter opens |
| Age | optional, 12/16 muted, right-aligned in the meta row |

#### Library table

| Column | Width | Content |
|---|---|---|
| Song | `minmax(0, 1fr)` | 40px signal thumb + title 14/20 500 + subtitle 12/16 muted |
| Analysis | 220px | `BPM · Key · N sections` as 12/16, or status chip |
| Updated | 110px | `2 mo ago` 12/16 muted |
| Actions | 120px | `Practice` 32px primary-ghost, plus 28px kebab |

- Header 40px, `--text-muted`, 11/14 700 uppercase; sort affordance on Updated only if sorting exists.
- Row 56px, border-bottom subtle; hover `--bg-hover`; last row no border.
- Selected/last-opened row: `--accent-soft` background and a 2px amber left indicator.
- Whole row click opens the mixer, except the action cell. Use a real `<table>` with `<th>`/`<td>`
  and a row-level link/button; do not nest buttons in a button.
- At 1024, hide Updated; at 900, stack Analysis under the title and keep the action at the right.
- Search: 36px, 240px, leading icon, visible `aria-label="Search songs"`, placeholder `Search songs`;
  results count updates. No filter/sort controls in Phase 1.5; those are P2 features. Reserve the
  visual space, but do not ship inert controls.

#### Queue / activity

- Top-bar pill: `● Local` when idle; `● 1 running · 2 queued` amber when working; `● Needs attention`
  danger when failed.
- Click opens a 320px drawer (right side, below the top bar, surface/raised, radius 12, shadow).
- Rows: 56px, title, stage, progress bar 4px, cancel/retry icon buttons. `aria-live="polite"` on the
  summary, not on every progress tick.
- The drawer is read-only except cancel/retry; it reuses existing job actions.
- While a job runs, the pill pulses only its 6px dot (opacity 1→0.45→1, 1.6s); no full-button glow.
- If the Streamlit version cannot update the component live, provide a `Refresh` control and a
  “last updated” 12/16 muted; do not fake progress.

#### Empty / loading / error states

| State | Copy | Visual |
|---|---|---|
| No songs | `No songs yet` / `Choose a song to separate. It will appear here with its key, chords, and tab.` | Six-string motif, primary `Choose a song`, secondary `Save from YouTube` |
| No search results | `No songs match “{query}”.` / `Clear search` | Search icon, quiet; do not show the full empty illustration |
| Loading library | 3 skeleton rows 56px + 2 skeleton recents | Shimmer only if >300ms; reduced-motion static |
| Analysing | Row status `Analysing…` + stage; action disabled | Amber dot + progress; no full-page spinner |
| Analysis failed | `Analysis couldn’t finish. Your stems are safe.` / `Try again` + `Details` | Danger icon + inline banner, not a toast |
| Missing tab | `No tab for this run.` / `Re-run with guitar separation.` | Quiet note in the Tab panel |
| No lyrics | `No lyrics for this song.` + reason (`This separation has no vocal stem` / `The local lyrics model is not installed`) | No retry button unless a real action exists |

### 5.6 Player

**Target shell at 1440×900:**

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ ← Library   Song title · File · 4:12                          Saved  [⋯]    │ 56
├──────────────┬───────────────────────────────────────────────────────────────┤
│ STEMS        │ Chords   Sections   Lyrics            [bar ruler]             │ 120
│ [Guitar  ▸]  │ ───────────────────────────────────────────────────────────── │
│  Guitar      │ waveform / playhead                                           │ 120
│  Vocals      │                                                               │
│  Drums       │ ┌───────────────────────────────────────────────────────────┐ │
│  Bass        │ │ Chords | Sections | Lyrics | Tab            [expand]      │ │ 320
│  Piano       │ │  1        2        3        4                             │ │
│  Other       │ │ [G7] [ ] [ ] [ ]   [C] [ ] [ ] [ ]   ...                  │ │
│  Metronome   │ └───────────────────────────────────────────────────────────┘ │
├──────────────┴───────────────────────────────────────────────────────────────┤
│ [1.00× · Key 0]     ⏮  ▶  ⏭   0:29 / 1:10   [metro] [loop] [count-in] [Export]│ 88
└──────────────────────────────────────────────────────────────────────────────┘
```

Regions:

- **Header 56px:** back to library (32px icon + label), title 14/20 500, source/format 12/16 muted,
  saved state 12/16 muted, overflow 32px. No giant cover art.
- **Stem rail 280px (240 at 1024, 210 at 900):** header `Stems` 11/14 700 uppercase + master volume
  compact; rows 72px; group rows 36px. Each row: instrument icon 16, name 14/20 500, M/S 24px,
  volume slider 4px, pan value 12/16, overflow 28px. Muted/soloed states use amber; no color-only
  state.
- **Timeline 120px:** annotation lanes for Chords/Sections/Lyrics, 28px each, with 12px labels on the
  left; bar ruler 24px; playhead 1px `--focus-ring` with a 7px triangle at top. Empty lanes say
  `Not detected` in 12/16 muted, not a blank strip.
- **Waveform 120px:** one combined practice waveform or per-stem rows; played `--waveform-played`,
  idle `--waveform-idle`, background `--waveform-bg`; current time bubble on hover; loop region
  `--accent-soft` with 2px amber handles.
- **Practice sheet 320px (280 at 1024; 240 at 900):** bottom sheet with a 4px drag handle, 40px tab
  bar, 280px body. Tabs: Chords, Sections, Lyrics, Tab. Default open on desktop; at 900 default
  collapsed with a `Practice` pill in the transport. Do not use a native `<details>` triangle.
- **Transport 88px:** three columns 220 / 1fr / auto. Left: speed/key pill + loop/count-in status.
  Center: previous, play 48px amber circle, next; time 12/16 tabular under. Right: metronome, loop,
  count-in, practice toggle, export. At 1024, two rows: transport/time first, tools second; height
  112px.
- **Practice controls:** Speed & Key moves to a 32px pill `1.00× · Key 0` that opens a popover with
  two sliders, values, reset. Count-in and metronome get 32px pills/popovers. Master moves to the stem
  rail header. Presets/reset/mute-all move to a 32px `⋯` menu or a compact chip row under the rail
  header; no permanent row of five buttons.

**Chord grid spec:**

- Bar-number gutter 32px; 4 beats per bar; 4 bars per row at ≥1280; 2 bars per row at 1024; 1 bar per
  row at 900 if needed.
- Cell height 56px; gap 4px; radius 6px; inactive `--chord-cell`; empty `--chord-cell-empty`; active
  `--chord-cell-active` with `--text-inverse`.
- Chord symbol 16/20 700; beat number 10/12 500 muted; bar number 12/16 numeric muted.
- Current chord diagram 72×84px in a side panel or above the grid; do not make every cell a diagram.
- Draft warning: `Draft chords — a starting point; verify by ear.` 12/16 muted with an info icon.
- Click a cell to seek; double-click to loop the bar (existing section loop code, no new feature).
- Empty state: `No chords found.` + `Re-run analysis.`; do not show an empty grid.

**Sections / Lyrics / Tab:**

- Sections: rows 44px, time 12/16 numeric, label 14/20 500, active amber left rule, loop icon 28px;
  total duration 12/16 muted. Click seeks.
- Lyrics: line 32px min, active 16/24 500 primary with 2px amber left rule; inactive 14/20 muted; word
  highlight amber; click seeks. If no lyrics, show the reason, not a retry that cannot work.
- Tab: measure grid, 6 string lines, current measure 2px amber border, previous/next labels 12/16,
  monospace 12/18, PDF link 32px ghost. Horizontal scroll only inside the tab panel; no page scroll.
  Confidence warning; `No tab for this run` state.

**Dialogs/popovers:**

- Tempo & Key popover: 320px, title 16/24 700, BPM/key values 20/28 numeric, sliders, reset; anchored
  to the speed/key pill.
- Count-in popover: 240px, Off/1 bar/2 bars as 3 segmented options, current state; anchored to the
  count-in pill.
- Metronome popover: 280px, on/off, sound, accent, follow; anchored to the metronome pill.
- Stems picker: 560px dialog, grouped instrument families, checkboxes, primary `Separate` 40px.
- Export: 560px dialog, tabs Mix / Stems / Tab, format/rate, include count-in/metronome, primary
  `Export` 40px, secondary `Cancel`. Show the honest note when the export differs from playback.
- Dialog overlay `rgba(3,8,18,0.72)`, 16px radius, 24px padding, 24px title, 32px close. Focus trap;
  Esc closes; return focus to the trigger.

### 5.7 Isolate (separation) screen

The Home redesign must not dead-end into a default Streamlit form. Scope the Isolate pass to the
chrome, not every advanced control:

- Page header 28/34 `Audio Isolation`; subline `Separate a song into stems. Everything stays on this
  computer.` 14/20 secondary.
- Upload surface: 100%×160px, dashed 1px border, radius 16, surface; icon 24, `Drop an audio or video
  file` 16/24 500, `or choose a file` 14/20 muted, supported formats 12/16 muted. Style the existing
  `stFileUploader`; do not build a new uploader in Phase 1.5.
- Region picker below, with a 12px caption `Choose the part to process` and the existing component
  styled with tokens.
- Advanced options: one collapsed `Advanced` disclosure, 40px header; do not show a wall of controls
  before the primary action.
- Primary `Separate` 40px amber, secondary `Cancel` 36px ghost; disabled state clear.
- Progress panel: 4 stages (`Reading`, `Separating`, `Analysing`, `Tab`), each 28px with a status
  icon; current stage amber; thin 4px progress bar; elapsed 12/16 numeric; one sentence
  `Keep this window open while it works.` Do not show a full-page spinner.
- Queue panel: same activity rows as Home, 56px, below the form at 1024 and to the right at ≥1280.
- The `Home | mix | +` tab strip stays, restyled to 40px with an amber active underline.

### 5.8 Settings / theme

- Keep theme presets, but make the default `Tyrian Nocturne` and show a 3-swatch preview per preset
  (background/surface/accent), not a bare select.
- Interface Lite/Pro moves to the sidebar footer as a 32px segmented switch; Settings repeats it with
  a one-line explanation and a link to the hardware profile.
- Do not add an app-specific light/dark toggle as a primary control; the OS/appearance theme is a
  preference, not a workflow. Keep the existing theme setting if the app already exposes it.
- About: version, edition, licenses, “Local only”. No account/avatar.

---

## 6. Component inventory

| Component | Variants | Sizes | States | Notes |
|---|---|---|---|---|
| Button | primary, secondary, ghost, danger, icon | 32/36/40/48 | default, hover, press, focus, disabled, loading | Primary is amber fill + dark text; only one per region. |
| Icon button | plain, ghost | 28/32 | hover, focus, pressed, disabled | Tooltip + `aria-label`. |
| Text input | search, form | 36 | default, focus, error, disabled | Leading icon for search; visible/aria label. |
| Select | compact | 32/36 | default, focus, open, disabled | Native select styled; no custom listbox in P1.5. |
| Slider | volume, seek, speed, key | 4px track | default, hover, focus, disabled | 14px thumb; numeric value beside; `aria-valuetext`. |
| Toggle / checkbox | switch, checkbox | 32×18 / 16 | off, on, focus, disabled | Do not use color alone; label. |
| Segmented control | Interface, count-in, tabs | 32/40 | selected, hover, focus | Amber selected; no pill overload. |
| Chip | status, preset | 24/28 | neutral, active, danger | 12/16 500; text always present. |
| Card | primary, secondary, recent | 168×156 / 84 | default, hover, focus, selected | One border, one radius, stage-edge highlight. |
| Table row | library, queue | 56/72 | default, hover, selected, focus, disabled | `<table>` semantics; no nested buttons. |
| Popover | tempo, count-in, metronome | 240–320 | open, closed | Anchored; Esc; focus return. |
| Dialog | export, stems | 560 | open, closed, busy | Focus trap; overlay; primary/secondary. |
| Banner | info, warning, error, success | full width | static, dismissible | Inline; not a toast for errors. |
| Toast | save, copy, minor | 320 | auto-dismiss 4s | Only confirmations; `aria-live`. |
| Skeleton | row, card, table | 56/156 | shimmer, static | Reduced motion stops shimmer. |
| Playhead | timeline, waveform | 1px + 7px triangle | moving, dragging | Functional; no CSS animation. |
| Chord cell | inactive, active, empty | 56px high | default, hover, current, focus | Active amber; tabular. |
| Chord diagram | 72×84 | — | static | Inline SVG; `role=img` + label. |
| Stem row | full, compact | 72/56 | default, hover, muted, soloed, focused | M/S 24px; volume 4px; pan in overflow at 210. |
| Transport | one-row, two-row | 88/112 | playing, paused, disabled | One visual center: play. |
| Practice sheet | open, collapsed, resizing | 240–360 | open, closed, dragging | Tabs; handle; no native details. |

---

## 7. Interaction and accessibility contract

### 7.1 Keyboard

| Key | Context | Action |
|---|---|---|
| `Tab` / `Shift+Tab` | Global | Move focus in DOM order; visible ring on every interactive element. |
| `Enter` / `Space` | Buttons, rows, cards | Activate. Space on a row toggles? No: Enter opens; Space plays only when the player has focus. |
| `Esc` | Popover/dialog/menu | Close and return focus to the trigger. |
| `Space` | Player, not in an input | Play/pause. |
| `L` | Player, not in an input | Toggle A/B loop. |
| `C` | Player, not in an input | Cycle count-in off/1/2. |
| `←` / `→` | Waveform focused | Seek 5s (existing behavior if present). |
| `↑` / `↓` | Table focused | Move row focus (roving tabindex) if implemented; otherwise Tab through rows. |
| `/` | Home | Focus search. |
| `?` | Global | Shortcuts help (P2 if not already present). |

Rules:

- Do not make the whole Home page a tab trap. The table can use a roving tabindex: one row is tabbable,
  arrow keys move selection, Enter opens. If that is too large for P1.5, keep one tab stop per row but
  give each action a contextual `aria-label`.
- Every icon-only control has `aria-label` and a visible tooltip on hover/focus.
- `aria-live="polite"` on the playback status, job summary, and save confirmation. Do not announce
  every progress tick.
- Use `aria-current="page"` on the active nav item; `aria-selected` on tabs; `role="tabpanel"` on the
  practice body.
- Sliders have accessible names and `aria-valuetext` (e.g., “−6 dB”, “1.05×”, “Key +2”).

### 7.2 Focus

- `:focus-visible` ring: 2px `--focus-ring`, 2px offset, 2px radius.
- Never use `outline: none` without a replacement.
- On dark/amber fills, the ring is parchment or dark? Use `--focus-ring` on dark; on amber, use
  `--text-inverse` 2px outer ring for contrast.
- When a popover/dialog opens, focus the first meaningful control; when it closes, return to the
  trigger.
- Do not auto-focus search on page load (it steals keyboard from the player); `/` focuses it.

### 7.3 Targets and pointer

- Pointer targets: 28px minimum, 32px preferred; transport 48; primary 40.
- Touch/pen: 44px minimum via padding on icon buttons; the app is desktop-first but the web copy will
  inherit.
- Hover is never the only way to reach an action. Row actions are visible on hover/focus; the kebab
  is always present at 28px, or the primary action is always visible.
- Drag handles (practice sheet, stem rail, video) have a 12px hit area and `role="separator"` with
  keyboard arrow support if feasible; otherwise provide a menu alternative.

### 7.4 Contrast and color

- All text ≥4.5:1 against its actual background; large text ≥3:1.
- Do not use `--text-muted` on `--bg-active` (3.3:1); use secondary.
- Status chips use text + icon, not color alone.
- Waveform/playhead are not the only time indicator; the timecode is always visible.
- The current beat is also announced by the current chord label; do not rely on the amber fill alone.
- Test with a grayscale screenshot: hierarchy should still work.

### 7.5 Motion and loading

- Skeletons appear immediately; if content loads <300ms, they can be replaced without a flash.
- Progress is stage-based, not a fake percentage. If the backend only gives a percentage, show it; if
  not, show indeterminate stripes + stage text.
- `prefers-reduced-motion`: no sheet slide, no pulse, no skeleton shimmer, no button scale.
- Do not block the page with a full-screen spinner for a local action; use an inline progress panel.

### 7.6 Screen reader

- Home: `main` landmark, `h1`, `nav`, table with caption/headers; row action labels include the song
  title.
- Player: `region` labels for Stems, Timeline, Practice, Transport; `aria-live` status; current chord
  and section announced at a sane interval (not every frame).
- Dialogs: `role="dialog"`/`aria-modal`, labelled by title; focus trap.
- Images/SVGs: decorative `aria-hidden`; chord diagrams `role="img"` with `aria-label="G7 chord diagram"`.
- Tablature: provide a text alternative “Measure 12, standard tuning, frets …” or a download link; do
  not rely on ASCII art alone.

---

## 8. Content and copy

### 8.1 Terminology

| Use | Avoid | Why |
|---|---|---|
| Song | File, track, asset | The user's mental model. |
| Parts / stems | Isolate, separation output | “Stems” is fine in the player; “parts” on Home. |
| Practice | Jam, play-along | Direct. |
| Analyse | Detect, infer, process | Matches the existing UI and British spelling. |
| Tab | Transcription, notation | Guitarists say tab. |
| Key, tempo/BPM | Pitch class, beat grid | Plain language. |
| Local only / on this computer | Offline-first, on-device | Clear privacy promise. |

### 8.2 Microcopy

- Primary: `Learn a song` / `Choose a song`.
- Secondary: `Save from YouTube` / `Save audio`; `Tab PDF` / `Open Tab PDF`.
- Library: `Search songs`; `No songs match “{query}”.`
- Analysis: `Analysing…` / `Ready` / `Needs analysis` / `Analysis couldn’t finish.`
- Practice: `Draft chords — a starting point; verify by ear.`
- Lyrics: `No lyrics for this song.` + reason.
- Tab: `No tab for this run.` + `Re-run with guitar separation.`
- Export: `Save current mix` / `Save all tracks`; show the difference in one line.
- Errors: what survived + next step + `Details` disclosure. No raw exceptions on the surface.

### 8.3 Do not say

- “Oops”, “Uh oh”, “Something went wrong” without a next step.
- “AI-powered” on every surface; the product is a practice tool, not a model demo.
- “Free tier”, “credits”, “upgrade” — we have no quotas.
- “Isolate” on Home; it is the internal page name.
- “File ·” as a title prefix. Use an icon/chip.
- “Not analysed yet” alone; use `Needs analysis` + the Analyse action.

---

## 9. Acceptance criteria and visual QA

### 9.1 The bar

Phase 1.5 is done when a first-time user can open the desktop app at 1024×768 and:

1. See the product name, the primary action, and at least one recent song without horizontal
   scrolling or clipped text.
2. Recognise “Learn a song” as the primary action in under two seconds.
3. Scan the library and tell which songs are ready, which need analysis, and which are running.
4. Open a song with one click and see the player’s transport, stems, and practice surface without
   overlapping controls.
5. Use the app with the keyboard alone, with a visible focus ring at every step.
6. Resize between 900 and 1440 without a horizontal page scrollbar or overlapping content.
7. See no Streamlit promo, default header, deploy button, or framework branding.

### 9.2 Visual QA matrix

| Viewport | Home | Player | Isolate |
|---|---|---|---|
| 1440×900 | 5 recents, 4-column table, action deck 7/5 | 280 rail, 320 sheet, one-row transport | form + right queue |
| 1280×800 | 5 recents, 4-column table | 280 rail, 300 sheet | form + right queue or below |
| 1024×768 | 3 recents + scroll, table hides Updated, action deck stacked | 240 rail, 280 sheet, two-row transport | form + queue below |
| 900×700 | 2 recents + scroll, stacked table row, action deck single column | 210 rail, 240 sheet or collapsed, two-row transport | form + queue below |

For each: empty library, 6 songs, 40 songs, long English title, long Japanese title, analysis missing,
analysis running, analysis failed, no lyrics, no tab, 2-stem and 6-stem runs.

### 9.3 Automated checks

- `pytest tests/ -q` (full suite) and targeted Home/design-token tests.
- `ruff check src/audio_to_tab`.
- `npx tsc --noEmit` in each changed component.
- `make home-build` / `make mixer-build`; committed build assets present.
- `python scripts/check_ui_tokens.py` (new) for contrast and required token keys.
- No `web/` or `backend/` diff.
- `git diff --check` for whitespace.

### 9.4 Manual checks

- Keyboard-only pass on Home and player.
- 200% browser zoom at 1024; no clipping.
- `prefers-reduced-motion` on; no sheet slide/pulse/scale.
- Grayscale screenshot; hierarchy still readable.
- Screen reader labels for table rows, transport, tabs, sliders.
- Real Waltz run: Home → Practice → Chords/Sections/Lyrics/Tab → loop/count-in → export.
- Real 2-stem run; real 6-stem run; long Japanese title.
- No console errors; no failed asset requests; no layout shift after fonts load (font-display:
  swap/optional, but the shell already bundles Satoshi).

---

## 10. What this phase is not

- Not a new audio engine, separation model, analysis algorithm, or export path.
- Not a new feature: no chord/lyric editing, capo, tuning, setlists, filters, batch, cloud, accounts,
  collaboration, Studio/DAW, VST, mobile.
- Not a web redesign. `web/` and `backend/` stay untouched.
- Not a Moises clone. No cyan/black palette, no Articulat, no copied assets or layouts.
- Not a new component framework. The Home component is vanilla TypeScript + Vite, reusing
  `streamlit-component-lib`, like the existing mixer.
- Not a reason to change pan/solo/summing laws, the metronome contract, wake hooks, or export
  semantics.

---

## 11. Unknowns and evidence limits

- **Populated Moises lyrics view:** no project with populated lyrics was found; the open projects
  showed “Not detected.” The lyrics layout here is **inferred** from the feature and the observed
  empty state. Do not cite it as observed.
- **Motion timings:** Moises motion was not measured frame-by-frame; our timings are design choices,
  not copied values.
- **Hover/pressed tokens:** some computed styles were sampled from screenshots; exact Moises hover
  colors/timings are unknown.
- **Fonts:** Articulat is licensed and not in this repo; Satoshi remains ours.
- **Audio quality/latency:** not measured in this pass; this is a visual/UI document.
- **Current app screenshot permissions:** OS `screencapture` failed; the current Home screenshots
  came from headless Chrome CDP. The player screenshots are from the Moises runtime pass. Raw captures
  contain personal library data and stay in `/tmp`; they are not committed.
- **Streamlit DOM stability:** the shell CSS targets Streamlit test IDs. A Streamlit upgrade may break
  selectors. Phase 1.5 must include a visual smoke test after any Streamlit bump; the component
  itself should not depend on Streamlit internals.
- **1024 full-bleed component:** not yet proven in the actual Streamlit shell. The shell spike is a
  Gate 0 task; if it fails, fall back to a native layout for the shell and keep the custom component
  only for the table/action deck.

---

## 12. Source map

| Question | File |
|---|---|
| Moises feature surface | `01-MOISES-SURFACE.md` |
| Runtime evidence and labels | `08-EVIDENCE-LOG.md` |
| Current code inventory | `02-CURRENT-STATE.md` |
| Feature decisions | `03-FEATURE-MATRIX.md` |
| Phase order and gates | `05-ROADMAP.md` |
| Phase 1 implementation history | `06-PHASE-1-PLAN.md` |
| Agent prompts | `07-BUILD-PROMPT.md` |
| UI implementation plan | `11-DESKTOP-UI-REDESIGN.md` |
| Current Home | `ui/pages/home.py` |
| Global shell/theme CSS | `ui/app.py`, `ui/theme_presets.py` |
| Shared component theme | `ui/iframe-theme.css` (copied into each component) |
| Mixer CSS/TS | `ui/stem_mixer_component/frontend/src/style.css`, `main.ts` |
| Mixer practice panel | same `main.ts` (practice rendering/toolbar) |
| Mix tabs strip | `ui/mix_tabs_component/frontend/src/main.ts`, `style.css` |
| Region picker | `ui/region_picker_component/frontend/src/` |
| Fonts | `ui/fonts/satoshi.css`, `ui/satoshi_font.py` |

**Bottom line (2026-10-21):** Home follows the measured Moises geometry and neutrals in §13. The product name, logo, Satoshi, and original icons stay ours. Global Tyrian/amber tokens stay in place until a separate approval. The player is not part of this Home pass.

---

## 13. 2026-10-21 Home parity pass

This section is the Home source of truth. A later implementation agent should not reopen Moises to re-derive these numbers. Player, mixer, and Isolate visuals are out of scope here.

### 13.1 Source

| Fact | Value | ID |
|---|---|---|
| App | Moises desktop, `/Applications/Moises.app` | E-HOME-001 |
| Version | `CFBundleShortVersionString` 2.0.18, `CFBundleVersion` `261013w3pv02l1x` | E-HOME-001 |
| Stack | Electron 43.4.1, Chrome 150.0.7871.224, UA `MoisesDesktop-2.0.18-darwin` | E-HOME-001 |
| Platform | macOS, arm64, device-pixel ratio 2 | E-HOME-001 |
| Date | 2026-10-21 | E-HOME-001 |
| Screen | `https://studio.moises.ai/home?client=desktop` inside the desktop shell | E-HOME-001 |
| Fuse | `EnableNodeCliInspectArguments` enabled. Read-only layout CDP only. No source, stylesheet, SVG, or image was copied into the repo | E-HOME-001 |
| Units | CSS pixels. Screenshots and raw dumps stayed in `/tmp` | E-HOME-001 |

The native window at launch was 1260×760. The four requested viewports were then applied with layout emulation at device-pixel ratio 1 so the CSS pixel grid is the measurement. The native ratio remains 2.

### 13.2 Annotated anatomy

Top to bottom, there is no page H1. “Home” is the active sidebar row.

1. **Rail, 240px, full viewport height.** Logo lockup, collapse glyph, nav groups, footer.
2. **Action-card rail.** Five product cards, 100px tall, horizontal, with 24px circular scroll buttons.
3. **Recents.** 18/26 heading, then a horizontal rail of 150×210 cards.
4. **Files.** 18/26 heading, pill filters, a 315×32 search field, 32×32 filter and sort buttons, then a 56px table. The document’s scroll height equals the viewport. The table is taller than the viewport, so the file list scrolls inside the page.

Sidebar order, top to bottom: logo, Home, group label PRODUCTS, Play, Studio, Mastering, Voice Studio, Lyric Writer, group label SETLISTS, New Setlist, further collection rows, then a footer with Downloads, Upgrade Plan, and an account row whose badge reads “Free”.

### 13.3 Parity vs brand

Assumption, taken from the request and not re-asked: Home parity outranks the earlier Tyrian Nocturne Home direction. The player and the global presets do not move in this phase.

| Decision | What it means |
|---|---|
| Home-scoped visual system | Layout, density, placement, type scale, surfaces, and states in this section apply to the desktop Home and its shell while `AUDIO_TOOLS_UI_V2` is on |
| Name and logo | Keep “Audio Tools” and the existing app icon. Do not draw the Moises mark or wordmark |
| Type | Satoshi, already bundled. Do not add Articulat or any other font |
| Icons | Original filled icons. Do not add an icon package and do not copy Moises paths |
| Global tokens | Do not change `ui/theme_presets.py` or the mixer palette in this phase. Home overrides live in the flag stylesheet and the Home component |
| Player | Stays on the current Tyrian/amber mixer until Phase 1.6. That mismatch is accepted |

Deliberate deviations from Moises:

- Three action cards (Learn a song, Save from YouTube, Tab PDF), not five Moises products. Same card height, radius, gap, icon size, and label style.
- No Upgrade, Free badge, Downloads, setlists, or paywall.
- Sidebar does not list products that are also the cards. It lists Home, Audio Isolation, YouTube to MP3, Tab PDF, Settings, then the Lite/Pro switch and the edition caption.
- YouTube’s trademark logo is not used. The card and nav icon are a generic save glyph.
- Section-label color is lifted so it clears 4.5:1. The measured Moises muted label does not.
- Focus is a visible 2px ring. The measured search field uses `outline-style: none`.
- Collapsed rail width was not observed. Collapse hides the rail (0px) instead of inventing an icon-rail width.
- Filter-menu, row-menu, empty-library, loading, and error visuals were not captured. The contracts in `11` §12 are ours, marked as such.
- Card icon accent `#75EBF5` was measured on the first action card only. Other card icon colors are `[unverified]`. We use that cyan on the Learn card icon only, inside Home. Secondary card icons are `#E9EEF5`.

### 13.4 Geometry at 1440×1000

Document scroll size equals the viewport. No page-level horizontal scroll. ID E-HOME-002.

| Element | x | y | w | h |
|---|---:|---:|---:|---:|
| Rail | 0 | 0 | 240 | 1000 |
| Logo button | 24 | 26 | 113 | 32 |
| Collapse glyph | 200 | 34 | 16 | 16 |
| Home row | 12 | 74 | 216 | 36 |
| First action card | 273 | 24 | 218 | 100 |
| Recents heading | 273 | 156 | — | 26 |
| First recent card | 273 | 194 | 150 | 210 |
| Files heading | 273 | 441 | 36 | 26 |
| Selected “All” pill | 333 | 438 | 40 | 32 |
| Search wrap | 1007 | 438 | 315 | 32 |
| Filter button | 1334 | 438 | 32 | 32 |
| Sort button | 1378 | 438 | 32 | 32 |
| Table | 253 | 488 | 1169 | 2872 (inner; viewport clips it) |
| Header row and body row | — | — | — | 56 |

Gaps at 1440: action cards 12px (503 − 273 − 218). Recent cards 12px (435 − 273 − 150). Five action cards, all fully inside the viewport; the fifth ends at 1410. Seven recent cards were in the rail and all fully inside; the seventh ends at 1395. Card count follows the library. Sizes do not.

Content origin is x=273, which is 33px past the rail. The table starts further left, at x=253.

Action-card width is fluid: `(inner width − 12 × (n − 1)) / n`, height fixed at 100. At 1440, n=5 produced 218.

### 13.5 The other three viewports

Rail stays 240. It does not auto-collapse. ID E-HOME-003, E-HOME-004, E-HOME-005.

| Viewport | Content origin | Action cards | Recents | Files table |
|---|---|---|---|---|
| 1280×900 | x=273 | 186×100, five, none clipped. Fifth ends at 1250 | 150×210. Six full. Seventh at x=1245 is clipped. Rail `scrollWidth` 1130, `clientWidth` 985, `overflow-x: auto`, `scroll-snap-type: none` | x=253, w=1009. Columns: select 14, Title flex, Type 116, Created 116, Duration 116, spacer 28, kebab 12 |
| 1024×768 | x=253 | 185×100. Three full. Fourth at x=845 is clipped. Fifth is offscreen. Same overflow, no snap | Four full (last full ends at 889). Fifth at x=901 is clipped | Type, Duration, and the select column measure 0×0. Title and Created remain. Row height stays 56 |
| 900×800 | x=253 | 154×100. Three full. Fourth at x=752 is clipped | Same card size. Four full, fifth clipped. `clientWidth` 637 | Same hidden columns as 1024. Created stays 116px |

The origin switch is between 1128 (still x=273) and 1120 (x=253). ID E-HOME-009. Implement the switch at `max-width: 1124px`: above it, main padding-left is 33px; at and below it, 13px. Rail width does not change.

Page `scrollWidth` equals the viewport at all four sizes. Clipping is inside the horizontal rails and the file list, not a page scrollbar.

At 900 the chip row still ends near x=674 while the search wrap is x=479, w=315, so those boxes overlap. Stacking order is `[unverified]`. Our toolbar must not overlap; see `11` §12.

### 13.6 Logo lockup

Measured on the Moises button. Recreate the box, not the artwork. ID E-HOME-007.

| Piece | Box | Notes |
|---|---|---|
| Button | 24, 26, 113×32 | Transparent background |
| Mark slot | 24, 33.5, 32×17 | SVG |
| Mark glyph | 32, 34, 16×16 | Nested SVG, color about `rgb(237, 238, 240)` |
| Wordmark slot | 64, 35.9, 73×12.3 | 8px after the 32px mark slot |

Audio Tools lockup, same boxes: existing 16×16 icon in the 32×17 slot, 8px gap, the words “Audio Tools” in Satoshi 14px/20px weight 500, color `#EDEEF0`, clipped to the 32px row. No Moises paths.

### 13.7 Navigation

| Item | Spec | ID |
|---|---|---|
| Row | 216×36, x=12, padding `8px 12px`, gap 12, radius 6 | E-HOME-006 |
| Label | 14px/20px, weight 400, Satoshi in our build. Moises used Articulat | E-HOME-006 |
| Icon | 16×16 filled SVG, no stroke, white on the active row. Home icon box was 24, 84 | E-HOME-007 |
| Active row | Background `rgba(202, 224, 250, 0.08)`, text `rgba(239, 246, 255, 0.97)` | E-HOME-006 |
| Inactive row | Transparent, text `rgba(225, 236, 249, 0.75)` | E-HOME-006 |
| Group label | 12px/16px, weight 500, uppercase, letter-spacing 1.5px, color `rgba(203, 223, 247, 0.38)` | E-HOME-006 |
| Transition | `0.2s ease` and `0.28s cubic-bezier(0.4, 0, 0.2, 1)` | E-HOME-006 |
| Footer account | 12px/16px, color `rgba(216, 233, 254, 0.49)`, letter-spacing 0.03px | E-HOME-006 |

Group labels fail contrast (§13.11). Our label color is the lifted token, not the measured alpha.

### 13.8 Action cards, recents, files

Action card, ID E-HOME-002 and E-HOME-006:

- Background `#17191C`, radius 8, shadow none, padding 0 on the button, transition 0.15s.
- Icon 20×20, 20px from the card’s left, 16px from the top. First card’s icon color `#75EBF5`.
- Title and subtitle are one line, 16px/24px, weight 500, color `rgba(239, 246, 255, 0.97)`, 20px from the left, sitting in the bottom 24px with about 12px below it.
- Scroll buttons: 24×24 circle, fill `#17191C`, glyph 14×14, color `rgba(255, 255, 255, 0.85)`.

Recent card:

- 150×210, radius 8, background `#17191C`.
- Artwork 150×150, its own radius 0; the card radius clips it.
- Title 14px/20px weight 400, color `#E9EEF5`, `white-space: nowrap`, `overflow: hidden`, 12px from the card’s left. One line, not two.
- Meta 12px/16px weight 400, color `rgba(216, 233, 254, 0.49)`, letter-spacing 0.03px, also nowrap.
- Title top is 12px below the artwork. Meta is directly under the title.

Files toolbar:

- Heading 18px/26px, weight 500, letter-spacing −0.045px, color `rgba(225, 236, 249, 0.75)`.
- Pills height 32, radius 9999. Selected: fill `#E9EEF5`, text `#101213`, weight 500, padding `0 12px`. Unselected: fill `rgba(202, 224, 250, 0.08)`, text `#ACB5BF`, weight 500.
- Search wrap 315×32, radius 6, fill `rgba(202, 224, 250, 0.08)`. Input 14px, color `#E9EEF5`, placeholder “Search”. Border color `#E9EEF5` in the resting sample. A distinct focus ring was not observed (`outline-style: none`).
- Filter and sort: 32×32, radius 6, same wash, glyph 16×16 inset by 8px. “More” overflow pill is 32×32, radius 9999.

Table, ID E-HOME-002:

- Header and row height 56.
- Column order at 1440 and 1280: select, Title, Type, Created, Duration, spacer, kebab.
- Title cell content height inside the row is 48px at the sample y.
- Kebab glyph button about 12×24. Header text was not given a separate size in the sample; body meta uses 14/20.
- At ≤1024, Type, Duration, and select measure 0. Title and Created remain.

### 13.9 Tokens

Home-scoped. Do not write these into the global preset. ID E-HOME-006 and E-HOME-014.

| Token | Measured | Our Home value |
|---|---|---|
| `--home-bg` | `rgb(16, 18, 19)` | `#101213` |
| `--home-card` | `rgb(23, 25, 28)` | `#17191C` |
| `--home-wash` | `rgba(202, 224, 250, 0.08)` over the background | keep the alpha; composite is about `#1F2225` |
| `--home-text` | `rgba(239, 246, 255, 0.97)` | use the alpha |
| `--home-text-secondary` | `rgba(225, 236, 249, 0.75)` | use the alpha |
| `--home-text-meta` | `rgba(216, 233, 254, 0.49)` | use the alpha; contrast is 4.38:1, under 4.5 |
| `--home-text-muted` | `rgba(203, 223, 247, 0.38)` composites to about `#57606A`, **2.94:1** | do not ship this alpha. UI-1 picks the nearest neutral that is ≥4.5:1 on `#101213` and records the hex |
| `--home-chip` | `#ACB5BF` | `#ACB5BF` |
| `--home-selected` | `#E9EEF5` fill, `#101213` text | same |
| `--home-icon-accent` | `#75EBF5` on the first card icon | Learn card icon only |
| `--home-line` | search border `#E9EEF5` | `#E9EEF5` |
| Focus ring | not observed as an outline | `2px solid #E9EEF5`, offset 2px. Deliberate |
| Danger | not captured on Home | `[unverified]`. Do not invent a red until a Home error surface exists |

Global before/after, if someone later proposes copying these into `theme_presets.py`:

| Token | Today | Proposed Home value | Blast radius |
|---|---|---|---|
| `backgroundColor` | `#192542` | `#101213` | Every Streamlit page, sidebar, and any widget that inherits the theme |
| `secondaryBackgroundColor` | `#2A4467` | `#17191C` | Buttons, nav active, inputs |
| `textColor` | `#F6AD49` | near-white | All text, including Isolate and Settings |
| `primaryColor` | `#F6AD49` | `#75EBF5` | Streamlit primary widgets and focus |

That global swap is **not approved**. It would repaint the player shell and every other page. Home must override locally under the flag.

### 13.10 Type scale

Satoshi only, weights 400 and 500. Do not synthesize 600. ID E-HOME-006.

| Role | Size / line | Weight | Tracking |
|---|---|---|---|
| Action label | 16 / 24 | 500 | 0 |
| Section heading | 18 / 26 | 500 | −0.045px |
| Nav and table body | 14 / 20 | 400 | 0 |
| Pill | 14 / 20 | 500 | 0 |
| Group label | 12 / 16 | 500 | 1.5px, uppercase |
| Card meta and footer | 12 / 16 | 400 | 0.03px |
| Wordmark | 14 / 20 | 500 | 0 |

Titles in cards and rows use one line and ellipsis. No 44px page title on Home.

### 13.11 Icon inventory and our mapping

Measured icons are filled (path fill present, stroke absent) unless noted. Do not copy the vectors. ID E-HOME-007.

| Where | Measured size | Our icon | Our size |
|---|---|---|---|
| Nav row | 16 filled, white or secondary | Home, waveform, save, document, gear | 16 |
| Collapse | 16 at the logo row | Sidebar toggle | paint 16, hit 24×24 |
| Action card | 20, first card `#75EBF5` | Learn: waveform. YouTube: save. Tab: document | 20 |
| Scroll affordance | 14 inside a 24 circle | Chevron | 14 |
| Filter, sort, more | 16 inside 32 | Filter, sort, overflow | 16 |
| Row kebab | about 12×24 | Overflow | 16 inside a 32×32 hit target |
| Search | search glyph inside the field | Search | 16 |

Active nav icon is white. Inactive nav icon uses the secondary text color. Hover and pressed icon colors are `[unverified]`. A stylesheet contained a `:hover` background of `rgb(25, 228, 241)`; which control it belongs to was not tied to a node, so it is not a Home token.

### 13.12 Current Audio Tools Home

Re-measured 2026-10-21 on Streamlit 1.59.1 at `http://127.0.0.1:8501`, CSS pixels, scroll reset on `[data-testid=stMain]`. Theme file `.streamlit/config.toml` matches the computed colors. ID E-HOME-010 through E-HOME-013.

| Fact | 1440×1000 | 1280×900 | 1024×768 | 900×800 |
|---|---|---|---|---|
| Sidebar | 300×1000 | 300×900 | 300×768 | 300×800 |
| Nav row | 260×28 at x=20, radius 6, 16px. Active weight 600, fill `#2A4467` | same width | same | same |
| Header bar | 60px tall from x=300 | present | present | present |
| H1 font | 44 / 52.8, weight 700, Satoshi, `#F6AD49` | same | same | same |
| H1 box | x=380, y=112, 980×89 | 820×89 | 564×89, text not clipped | 440×89, text not clipped |
| Primary buttons | 316×74, y=239, gap 16, radius 14 | 263×74 | 177×74 | 136×74 |
| Button fill | `#2A4467`, text `#F6AD49`, border `rgba(246, 173, 73, 0.35)` | same | same | same |
| Recents | five measured, 183×74, one line of clipping inside the button | five, 151×74 | five, 100×80, about 4 text lines | five, 75×115 |
| Library row | 832×74 plus a 132×74 Practice/Analyse button | reflowed | reflowed | reflowed |
| Page horizontal scroll | no | no | no | no |
| Promo overlay | not in the DOM text | — | — | — |

The 2026-10-20 claim that 1024 clips the title and the Tab PDF card is **not** what this build does. Streamlit reflows the main column: content width is the viewport minus the 300px rail minus 80px padding on each side. The remaining failure is density, hierarchy, and the 300px rail, not a horizontal page scrollbar.

`ui/pages/home.py` sets button `min-height: 4.6rem` (74px) and radius 14px. The H1 size comes from Streamlit’s heading, not from that file. Active nav weight 600 is real; Satoshi has no 600 file, so the browser synthesizes it.

### 13.13 Gap matrix

| Element | Moises | Audio Tools now | Severity | Plan change | Phase |
|---|---|---|---|---|---|
| Rail width | 240 at all four widths | 300 | blocking | Flag CSS sets the sidebar to 240 | 1.5 |
| Page title | none; section headings 18/26 | H1 44/52.8 weight 700, box 89px tall | high | Remove the Home H1. Sections use 18/26 weight 500 | 1.5 |
| Action row | 100px cards, radius 8, icon 20, one-line label | 74px (or shorter when squeezed) equal buttons, radius 14, no icon | blocking | Three cards at the measured card spec | 1.5 |
| Recents | 150×210, art 150, nowrap title, horizontal scroll, no snap | Equal columns, 74–115px tall, text wraps to 4 lines at 1024 | high | Fixed 150×210 rail, ellipsis, scroll buttons | 1.5 |
| Files | 56px table, Title / Created, kebab | 74px buttons plus a detached action | high | 56px table | 1.5 |
| Color | neutrals, one cyan icon | every text and action `#F6AD49` on `#192542` | high | Home-scoped tokens only | 1.5 |
| Nav | 216×36, 16px filled icon, weight 400 | 260×28, no icon, active weight 600 | high | 36px rows, 16px icons, weight 400 | 1.5 |
| 1024 fit | no page scrollbar; rails clip and scroll | no page scrollbar either; columns squash | medium | Keep no page scrollbar; stop squashing recents | 1.5 |
| Header chrome | none observed on the Home surface | 60px `stHeader` | medium | Hide it under the flag | 1.5 |
| Promo | none | not present in this session | low | Keep the existing deploy-button hide. Do not treat a missing promo as a permanent guarantee | 1.5 |
| Player | not re-measured | current mixer | — | Leave it | 1.6 |

### 13.14 States

| State | Observed | Our contract |
|---|---|---|
| Active nav | wash background, near-white text | same, on Home |
| Selected pill | `#E9EEF5` / `#101213` | same, for All |
| Hover | control not tied to a computed node. `[unverified]` | background wash moves to `rgba(202, 224, 250, 0.14)` in 150ms. Do not use the untied cyan hover |
| Focus | search outline none; border already `#E9EEF5` | 2px `#E9EEF5` ring, offset 2 |
| Pressed | `[unverified]` | no scale. Wash only |
| Disabled | `[unverified]` | opacity 0.4, no pointer |
| Collapse | control exists. Click did not change the 240px rail within 350ms. Width `[unverified]` | hide rail to 0 and restore 240. Focus returns to the button |
| Filter / row menu | click did not expose a `role=menu`. Contents `[unverified]`. Destructive items were not activated | our menu in `11` §12 |
| Empty library, no results, loading, error | `[unverified]` | our copy in `11` §12 |
| Long title | one line, nowrap, hidden overflow | ellipsis |
| Reduced motion | not sampled from the OS setting | set transition-duration to 0ms |

### 13.15 Open questions

- Collapsed rail width: `[unverified]`.
- Which node uses the cyan `:hover` background: `[unverified]`.
- Menu, tooltip, toast, dialog, and paywall contents from Home: `[unverified]`. The paywall node was in the accessibility tree and was not opened.
- Sticky table header: `[unverified]`.
- Icon colors on cards after the first: `[unverified]`.
- Exact media-query pixel between 1120 and 1128: the change is bracketed; we implement 1124.

### 13.16 Keyboard and motion

Tab order was not walked. No Home-only shortcut was observed. Search focus was `outline-style: none`.

Our order, because the measured order is `[unverified]`: collapse, logo, nav, Lite/Pro, then the cards, recents, search, sort, and table rows. Enter and Space activate. Esc closes an open menu and returns focus to the opener. A click outside does the same. There is no new Home shortcut.

Motion that was measured: cards 0.15s; nav 0.2s ease and 0.28s `cubic-bezier(0.4, 0, 0.2, 1)`. Reduced motion sets those durations to 0. The Apple HIG desktop minimum hit target used as the secondary check is 20×20. The collapse glyph is 16×16, so the button is 24×24. The kebab hit target is 32×32 around a 16px glyph.
