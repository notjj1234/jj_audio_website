# Scope cut — the bone

**Ponytail ultra.** The request is “literally everything Moises does.” That is three products, not one:

1. a **practice player** (Play),
2. a **browser DAW with AI generation and collaboration** (Studio),
3. a **platform** (mobile, TV, VST, system-audio Live, B2B).

Building all three at once produces a shallow clone and breaks the desktop. The matrix keeps every
feature; this file decides the build order. The first release is deliberately narrow.

## The one job

> **Turn a song into a playable guitar tab and a practice mix, locally, in one flow.**

Everything in Phase 1 serves that sentence. If a feature does not make the tab better, the practice
mix better, or the flow shorter, it waits.

## The bone (Phase 1)

Six capabilities, in this order:

| # | Capability | Why it is in the bone | Reuses |
|---|---|---|---|
| 1 | **Project manifest + cached analysis** | One song = one durable project. Analysis runs once, not on every rerun. | Existing run dirs, `meta.json` |
| 2 | **Analysis artifact** — BPM, key, beats, chords, sections, lyrics | This is the parity gap. The engine already has audio; it has no musical facts. | `metronome.py`, `tempo.py`, `tuning.py`; new chord/section/lyrics modules |
| 3 | **Practice player panels** — chord chart + diagrams, sections, lyrics, tab | The current mixer plays stems; it does not teach the song. | Existing mixer iframe, `stem_mixer_component` |
| 4 | **Tab in the player** — on-screen tab + PDF | The wedge. Moises has no tab. | Existing Basic Pitch → tab → PDF pipeline |
| 5 | **Count-in + A/B loop** | The two practice controls the current player genuinely lacks. | Mixer transport, metronome |
| 6 | **Save-what-you-hear (desktop) + tab export** | A practice tool that exports a different mix is a trust bug. Web parity is P2; P2 must add an explicit “web export ignores speed/key” warning. | Desktop export paths |

**Phase 1 is done when** one real song can be imported, separated, analysed, practised with chords +
sections + tab + count-in + loop, and exported with a mix and a tab PDF that match what was heard.

Lyrics is in Phase 1 **only if** the local-model spike proves word-level timestamps inside the size and
latency budget. If it does not, Phase 1 ships without lyrics and lyrics becomes the first item of Phase
2. Do not fake it with a cloud call; that breaks the local-first promise.

**Update 2026-10-20:** the lyrics path is implemented and manually validated in the dev environment
(`faster-whisper` small, pinned local model, partial-line fallback). Packaged desktop lyrics are still
an open Phase 1.6 decision because the freeze does not collect `faster_whisper` yet and there is no
first-run model download. See `06` §Verification and `05` §Phase 1.6.

## Phase 1.5 — Home parity is part of the product, not decoration

**2026-10-21 revision.** The bullets below from 2026-10-20 described a Tyrian shell and a recomposed
player. The Home decision is now `10-MOISES-UI-CRAFT.md` §13 and `11-DESKTOP-UI-REDESIGN.md` §12:

- a Home measured against Moises: 240px rail, 100px action cards, 150×210 recents, 56px Files table;
- Home-scoped neutrals. Global Tyrian tokens and the player stay as they are until Phase 1.6;
- 1440/1280/1024/900, keyboard/focus, contrast, reduced motion;
- no new practice features, no new font or icon package, and no audio-engine changes.

This is **not** a general-purpose design system or a new app framework. It is a Home token module
plus one vanilla TypeScript Home component, reusing the existing Streamlit/Vite pattern.

## Explicitly not in Phase 1

| Cut | Why it is safe now | When, if ever |
|---|---|---|
| **Studio / DAW** (timeline, tracks, buses, clips, automation, MIDI editor, VST3) | It is a different product with a different user and a multi-year surface. The practice player does not need it. | P3, after a buy/partner/go-no-go |
| **AI stem/sample generation, voice conversion, AI mastering, Auto Mix** | Credits, model hosting, rights, and billing. None of it makes a tab. | P3, partner first |
| **Real-time collaboration, presence, chat, comments** | Requires cloud projects, auth, CRDT/OT, and a server team. Local-first is the advantage. | P3 |
| **Mobile, iPad, TV, visionOS** | Desktop is the priority; a companion app is a second product. | P3 |
| **VST/AU/AAX plugin, Moises Live-style system audio** | Separate distribution and audio-host problems. | P3 |
| **27-stem catalogue, multimedia stems** | Expensive models; guitar practice needs six stems and guitar splits. | P3 or never |
| **Chord/lyric/section editing** | Read-only + regenerate is enough to validate the workflow. Editing is polish. | P2 |
| **Setlists, queue, folders, sharing** | The local library/recents already opens songs. Setlists are convenience. | P2 (local), P3 (shared) |
| **Cloud sync, accounts, billing** | Desktop is local. Adding cloud now doubles the architecture for no practice gain. | P3, optional |
| **Batch upload** | Desktop jobs are serial by design (8–16 GB RAM). A batch UI would encourage overload. | P2, queue only |
| **Localization** | The workflow is still changing; translating it now wastes the translation. | P2 |
| **Web parity** | The user said website is a later copy. Do not split effort before the desktop is right. | P2 |

## Why these cuts are safe

- **The matrix still covers everything.** Nothing is dropped from the product map. “Defer” is a
  scheduling decision, not a denial.
- **Moises' own split proves the sequence.** Play is the consumer practice tool; Studio is a separate
  beta. They share a brand, not a screen. We should copy the split, not the brand.
- **Our advantage is structural, not feature-count.** Local processing, no upload, no monthly
  separation cap, no first-minute gate, YouTube ingest, and tab. Adding a DAW does not strengthen any
  of those.
- **The existing mixer is already ahead in places.** Pan, group rows, synced picture, speed/key without
  a free-tier cap, and desktop export formats are already there. Rebuilding them would be motion, not
  progress.
- **The export mismatch is the only Phase 1 bug that can invalidate the whole promise.** Fix it before
  adding panels.

## Buy / partner / build decisions (for P3, not now)

| Capability | Default decision | Why |
|---|---|---|
| Browser DAW engine | **Buy/partner/integrate** (evaluate OpenDAW and commercial SDKs) | Moises' own Studio bundle references OpenDAW. Building a DAW from scratch is years. |
| Stem/sample generation | **Partner** | Model training and hosting are not our differentiator. |
| Voice conversion | **Partner**, rights-first | Consent, artist rights, and safety are heavier than the model. |
| AI mastering | **Partner or defer** | Commodity; not the wedge. |
| Real-time collaboration | **Buy** (CRDT/audio infra) or defer | A distributed-systems product on its own. |
| Mobile app | **Build later**, share the analysis/player schema | The engine and JSON contract are portable. |
| VST plugin | **Build later** or partner | Distribution/signing/support is a separate business. |

## Success metrics for the bone

- **Flow:** import → separated → analysed → practising in under one action after separation; no
  configuration required for the default path.
- **Trust:** exported mix matches playback (pan, speed, key, mute/solo, master).
- **Wedge:** every completed project offers a tab PDF and an on-screen tab; no Moises import needed.
- **Local:** analysis and playback work with the network off after models are installed.
- **Speed:** analysis adds no more than ~1× the separation time on the reference machine; it is cached
  and never blocks the mixer from opening.
- **Quality:** chords/sections/lyrics are “useful draft” quality, editable later; tab is at least as good
  as today's Tab PDF page.
- **Craft (Phase 1.5):** at 1024×768 the primary action and recent songs are visible without clipping;
  the library is scannable as a table; the player has one transport center and a stable practice
  surface; no Streamlit promo/default chrome is visible; keyboard-only use is possible; all text meets
  4.5:1. This is a gate, not a vibe.

## Risks and stop conditions

| Risk | Mitigation / stop condition |
|---|---|
| Chord model is inaccurate or too heavy | Spike first. If no local model hits the accuracy/latency budget, ship BPM/key/sections/tab and defer chords. Do not ship a random-chord panel. |
| Lyrics model bloats the installer or needs HF downloads | Use a pinned local model + SHA256 `urllib` download. If size > budget, defer lyrics. Never add `huggingface_hub` (repo invariant). |
| Analysis makes the 8 GB Mac unusable | Run it in the serial worker, after separation, with a “skip analysis” option. Never in the Streamlit thread. |
| Tab quality on full-band mixes is poor | Always transcribe the isolated guitar stem, not the mix; show confidence/empty state. |
| Mixer iframe becomes a second app | Keep the audio engine, state model, pan/solo laws, and wake hooks. Phase 1.5 may restyle and recompose the chrome, but it does not create a second player or a new component framework. |
| UI craft becomes a redesign rabbit hole | Bounded to the screens in `10`/`11`; no new features, no web/backend, no engine. The 1024/900 gates are pass/fail. If Gate 0 fails, use the documented native-Home fallback. |
| Web/desktop drift | Fix desktop export parity in P1; keep the analysis JSON schema shared. Port the UI and fix web export in P2, including the “web export ignores speed/key” warning. |
| Scope creep back to “everything” | This file is the contract. A new feature needs a matrix row and a phase; it does not jump the queue. |

## If the user insists on Studio now

Do not start coding a DAW. Do this instead:

1. Run the P3 decision spike: licence/terms for OpenDAW, a commercial SDK quote, and a 2-week
   prototype that opens a project, plays a stem, and exports a mix.
2. Write a one-page go/no-go with cost, headcount, and time.
3. Only then add Studio to the roadmap.

That is the lazy path that still answers the ambition. Building it blind is the expensive path.
