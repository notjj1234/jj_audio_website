# Moises page inventory — 2026-10-23

A page is a distinct destination or overlay. Data-only differences are states of one page. Evidence labels: `OBSERVED` (read or seen), `INFERRED`, `UNKNOWN`.

Build: desktop **2.1.0** `261021a1gygumpb`, asar SHA-256 `e7242b3db57214f5a32ff24b4fb2e3f66d5ffabd6101381dbc4992de3d6bd284`. Shell REA: `ev_2015286d22cfc4a62451bbee9e1c1ca624e084e78ff6c80bf01cfaa20162ab93`.

Visual capture of the running desktop window is **blocked**. The primary display was in a fullscreen video. The window was restored once and left minimized. Do not treat pixel layout as measured.

## S1 — Desktop shell

Local renderer title is `Moises Studio` (`out/renderer/index.html`). CSP allows scripts only from `'self'` and connect only to `'self'`. The hosted product is not drawn by this HTML.

| ID | Page | Entry | States seen | Evidence |
|---|---|---|---|---|
| P-S1-01 | Main window | Process start. Persisted `tabs.json` had a non-maximized window. | Running, then minimized (`-32000,-32000`). Content not read. | OBSERVED process and window rect. Layout UNKNOWN. |
| P-S1-02 | Tab strip | `electronAPI.tab` | Persisted tabs: Home (`pageId` home) and one webview. Titles redacted. | OBSERVED `tabs.json` shape and preload `tab:*`. |
| P-S1-03 | Tab context menu | `tab:context-menu` | Labels in main: Duplicate Tab, Close Other Tabs, Close Tabs to the Right. | OBSERVED strings in `out/main/index.js`. Not clicked. |
| P-S1-04 | New-product menu | `tab:new-menu` | Items below in S2. | OBSERVED menu labels and paths in main. Not opened. |
| P-S1-05 | Tab preview | `tab:preview-show` / `tab:preview-hide` | Not shown. | OBSERVED channels. Behavior UNKNOWN. |
| P-S1-06 | Memory panel | `memory-panel:*`, `memory-icon:visible` | Not shown. | OBSERVED channels. Trigger UNKNOWN. |
| P-S1-07 | Titlebar window controls | `window:minimize`, `maximize`, `close`, `is-maximized` | Not clicked. | OBSERVED channels. |
| P-S1-08 | Tray menu | Strings Show Moises App, Hide Moises App, Quit Moises Desktop. | Not opened. | OBSERVED strings. |
| P-S1-09 | Application menu | Reload, reload ignoring cache, Next Tab, Previous Tab, Enable VST plugins. Accelerators Control+Tab and Control+Shift+Tab. | Not opened. | OBSERVED strings. |
| P-S1-10 | Update downloaded | `updates:downloaded`, `updates:install` | Not shown. Feed says this build is current. | OBSERVED channels and latest.yml. |
| P-S1-11 | Capture failure | Strings for addon unavailable, microphone not allowed, device-busy, rate-mismatch. | Not shown. | OBSERVED capture host and README in `app.asar.unpacked/native/capture/README.md`. |
| P-S1-12 | Download errors | Could not reveal download; file missing after complete. | Not shown. | OBSERVED strings. |

## S2 — Hosted routes inside the shell

Paths are literals in `out/main/index.js` next to the menu labels. The shell loads `https://studio.moises.ai` (and the stage host exists in the same file). Which path is appended was not watched at runtime, except the persisted session.

| ID | Page | Paths | Evidence | Interior |
|---|---|---|---|---|
| P-S2-01 | Home | `/home`, `/home/` | OBSERVED literals. Persisted tab URL was `https://studio.moises.ai/home?client=desktop`. | UNKNOWN |
| P-S2-02 | Play | `/play`, `/play/` | OBSERVED literals. Icon id `play`. | UNKNOWN |
| P-S2-03 | Play upload | `/upload/split`, `/upload/split/3` | OBSERVED literals beside Play. What `3` means is UNKNOWN. | UNKNOWN |
| P-S2-04 | Studio | `/studio`, `/studio/new` | OBSERVED literals. Menu icon file is `sparkbars`. `sparkbars` is the Studio glyph, not a separate product. | UNKNOWN |
| P-S2-05 | Mastering | `/mastering`, `/mastering/upload`, `/upload/master` | OBSERVED literals. | UNKNOWN |
| P-S2-06 | Voice Studio | `/voice-studio`, `/voice-studio/upload` | OBSERVED literals. | UNKNOWN |
| P-S2-07 | Lyric Writer | `/lyrics`, `/lyrics/new`, `/lyric-writer` | OBSERVED literals. | UNKNOWN |
| P-S2-08 | Player | `/player2/<id>` | OBSERVED as the second persisted tab. Id redacted. Not opened. | UNKNOWN |
| P-S2-09 | Auth bridge | `/auth/`, `/__/auth/` | OBSERVED literals. | UNKNOWN |
| P-S2-10 | Plugin downloads | `https://plugins.moises.ai` | OBSERVED URL. Filenames in main: `Stems.aaxplugin`, `Studio.aaxplugin`, `Studio.component`, `Studio.vst3`, `Mastering.aaxplugin`, `Mastering.component`, `Mastering.vst3`. | UNKNOWN |

## S3 — Web app, logged out

Isolated browser. No account was used.

| ID | Page | URL | Controls | Evidence |
|---|---|---|---|---|
| P-S3-01 | Login | `https://studio.moises.ai/auth/login?redirect=/` | Google, Facebook, Apple, X, Continue with email, Sign up. Email state: email, password, show password, Forgot password, Login. Quote and cookie banner present. Login was not submitted. | OBSERVED snapshot |
| P-S3-02 | Signup | `https://studio.moises.ai/auth/signup?redirect=%2F` | Same four providers, Continue with email, Terms, Privacy, Login. Copy: "Get started with your free account". Account was not created. | OBSERVED snapshot |

`/` on `studio.moises.ai` redirected to the login URL. That redirect is OBSERVED.

## S4 — Studio interior

No panel, track, device, or export inside Studio was opened. P-S2-04 is the only Studio page. Everything under it is **not discovered**.

## S5 — Mobile

**BLOCKED.** No iOS or Android package, simulator, or device on this host. Store listings appeared in `winget search` and were not installed. No pages.

## S6 — Public web

| ID | Page | URL | What was read | Evidence |
|---|---|---|---|---|
| P-S6-01 | Marketing home | `https://moises.ai/` | H1 "The Creative Suite for Musicians". Sections: Studio, Stem Separation, Video Recording, play-along, FAQ, footer. Locale list started en, es, pt, ar, nl, fr, de, it, pl, ru, sv, ja, ko, th, tr. | OBSERVED snapshot. Later the same tab was on the help center. |
| P-S6-02 | Help home | `https://help.moises.ai/hc/en-us` | Search, Upgrade, Upload, Export, Getting Started, FAQ, Plans & Billing. | OBSERVED snapshot |
| P-S6-03 | Help Getting Started | `https://help.moises.ai/hc/en-us/categories/8471338667804-Getting-Started` | Sections Mobile, Web—Desktop, iPad, Upload & Export. Article bodies not fully read. | OBSERVED fetch |
| P-S6-04 | Help Plans & Billing | `https://help.moises.ai/hc/en-us/categories/8471369565084-Plans-Billing` | Plan articles and cancel articles for Stripe, PayPal, App Store, Play Store, Ebanx. Prices not on this category page. | OBSERVED fetch |
| P-S6-05 | AI Studio credits | `https://help.moises.ai/hc/en-us/articles/21960006352796-Moises-AI-Studio-Credits` | See feature deep dive. Help text, not a product run. | OBSERVED fetch |
| P-S6-06 | robots.txt | `https://moises.ai/robots.txt` and `https://www.moises.ai/robots.txt` | Allow `/`. Sitemap `https://moises.ai/sitemap.xml`. | OBSERVED fetch |
| P-S6-07 | Sitemap | `https://moises.ai/sitemap.xml` | Direct GET 200, 544,988 bytes, 3,041 `<loc>` URLs, all on `moises.ai`. An earlier markdown fetch of the same URL returned 500. That failure is not the current result. | OBSERVED 2026-10-23 follow-up |

Locale-prefixed copies are not extra pages. Loc counts by prefix: en 405, pt 360, es 360, it 229, de 229, ja 219, fr 218, zh 98, ar 97, nl/pl/uk/th/nb/ru/cs/tr/sv/ko 75 each, zh-Hant 74, plus 2 root URLs. Help-center language codes seen earlier (hi, id, ms, pt-br, vi, zh-cn, zh-tw) are still duplicates, not extra pages.

English sitemap paths: 405 unique. Feature and product paths below each have a row. The other 351 English paths (blog, newsroom, legal, campaigns, and the rest) are discovered and not opened. Help Center `articles.json` reports 112 English articles. Eight article bodies are rows here. The other 104 are discovered and not read.

| ID | Path | Body this follow-up |
|---|---|---|
| P-S6-08 | `/features/` | Sitemap loc only |
| P-S6-09 | `/features/ai-audio-transcription/` | Sitemap loc only |
| P-S6-10 | `/features/ai-mastering/` | Sitemap loc only |
| P-S6-11 | `/features/ai-studio-creators` | Sitemap loc only |
| P-S6-12 | `/features/ai-studio-music-creation` | Sitemap loc only |
| P-S6-13 | `/features/ai-voice-models/` | Sitemap loc only |
| P-S6-14 | `/features/amp-modeler` | Sitemap loc only |
| P-S6-15 | `/features/audio-speed-changer/` | Sitemap loc only |
| P-S6-16 | `/features/band-collaborative-setlist/` | Sitemap loc only |
| P-S6-17 | `/features/bpm-finder/` | Sitemap loc only |
| P-S6-18 | `/features/chord-finder` | GET 200. Title "Chord Finder — AI chord detection for any song". Stripped text has chord and capo. It has neither `guitar tab` nor `tablature`. |
| P-S6-19 | `/features/editing-track-arrangement` | Sitemap loc only |
| P-S6-20 | `/features/guitar-capo-mode/` | GET 200. Title "Guitar Capo Mode". Stripped text has chord and capo. It has neither `guitar tab` nor `tablature`. |
| P-S6-21 | `/features/guitar-chord-finder/` | Sitemap loc only |
| P-S6-22 | `/features/hi-fi-stem-separation/` | Sitemap loc only |
| P-S6-23 | `/features/instrumental-maker/` | Sitemap loc only |
| P-S6-24 | `/features/karaoke-backing-tracks/` | Sitemap loc only |
| P-S6-25 | `/features/key-detector/` | Sitemap loc only |
| P-S6-26 | `/features/lyric-writer/` | Sitemap loc only |
| P-S6-27 | `/features/metronome-online/` | Sitemap loc only |
| P-S6-28 | `/features/multimedia-tracks/` | Sitemap loc only |
| P-S6-29 | `/features/multitrack-recording` | Sitemap loc only |
| P-S6-30 | `/features/music-cutter/` | Sitemap loc only |
| P-S6-31 | `/features/pitch-changer-shifter/` | Sitemap loc only |
| P-S6-32 | `/features/real-time-collaboration` | Sitemap loc only |
| P-S6-33 | `/features/song-key-finder/` | Sitemap loc only |
| P-S6-34 | `/features/song-parts/` | Sitemap loc only |
| P-S6-35 | `/features/stem-generation` | Sitemap loc only |
| P-S6-36 | `/features/stem-separation` | Sitemap loc only |
| P-S6-37 | `/features/stems-vst-plugin/` | Sitemap loc only |
| P-S6-38 | `/features/video-recording` | Sitemap loc only |
| P-S6-39 | `/features/video-recording-desktop` | Sitemap loc only |
| P-S6-40 | `/features/vocal-remover/` | Sitemap loc only |
| P-S6-41 | `/features/vocal-stems/` | Sitemap loc only |
| P-S6-42 | `/features/voice-recorder/` | Sitemap loc only |
| P-S6-43 | `/products/` | Sitemap loc only |
| P-S6-44 | `/products/app-for-ipad/` | Sitemap loc only |
| P-S6-45 | `/products/integrations` | Sitemap loc only |
| P-S6-46 | `/products/integrations/fender-studio-pro` | Sitemap loc only |
| P-S6-47 | `/products/integrations/soundcloud` | Sitemap loc only |
| P-S6-48 | `/products/integrations/universal-audio-luna` | Sitemap loc only |
| P-S6-49 | `/products/live` | Sitemap loc only |
| P-S6-50 | `/products/live/` | GET 200. Title "Moises Live: Real-Time Audio Control for All Your Apps". Page says it is desktop-only, "runs entirely on-device", and "works offline". Marketing copy, not a run. |
| P-S6-51 | `/products/moises-app-android-ios/` | Sitemap loc only |
| P-S6-52 | `/products/moises-app-download/` | Sitemap loc only |
| P-S6-53 | `/products/moises-app-for-mac/` | Sitemap loc only |
| P-S6-54 | `/products/moises-app-for-pc/` | Sitemap loc only |
| P-S6-55 | `/products/moises-app/` | Sitemap loc only |
| P-S6-56 | `/products/moises-desktop-app/` | Sitemap loc only |
| P-S6-57 | `/products/moises-studio` | Sitemap loc only |
| P-S6-58 | `/products/moises-web-app/` | Sitemap loc only |
| P-S6-59 | `/products/software-for-musicians/` | Sitemap loc only |
| P-S6-60 | `/business-api/` | GET 200. Title "AI Audio Models to Power Your Music Business \| Music AI". Not an API reference. |
| P-S6-61 | Help: Free separation | Article `29530482524316`, updated 2026-10-23. Free plan: 2-stem preset or 4-stem preset, 5 uploads per month, files up to 5 minutes. Individual instruments need Premium or Pro. Help text, not a quota response. |
| P-S6-62 | Help: maximum file length | Article `360010855680`, updated 2026-10-15. Free stems 5 minutes. Free metronome, chords, and lyrics: first minute. Premium and Pro stems 20 minutes. Those three features unlimited on Premium and Pro. Mastering by reference 20 minutes on Premium and Pro. Points at `https://studio.moises.ai/pricing/`. |
| P-S6-63 | Help: 5-upload counter | Article `360010972039`, updated 2026-10-23. Free plan 5 files per month. Deleting a file does not restore the slot. Counter resets each calendar month. |
| P-S6-64 | Help: mastering length | Article `360013858400`, updated 2026-10-05. Mastering on Free, Premium, and Pro. Export of all mastered files is Pro. Premium can export the Reference track. Free 5 minutes, Premium and Pro 20 minutes. Web or desktop only. |
| P-S6-65 | Help: Premium instruments | Article `29530520103324`, updated 2026-10-17. Up to 5 instruments per upload. Guitar group is Guitars, or Acoustic and Electric, or Lead and Rhythm, not all three. Lists vocals, bass, guitars, piano, keys, winds, drums, strings. |
| P-S6-66 | Help: Pro instruments | Article `360010972019`, updated 2026-10-20. Adds female and male vocals, brass, reeds, woodwind, percussion, kick, snare, toms, hi-hat, cymbals. Dialogue, soundtrack, and effects "available in Play". Some of those are described as web-only for now. |
| P-S6-67 | Help: Pro reasons | Article `10523828567196`, updated 2026-10-22. Voice Studio export, WAV 48 kHz / 24-bit, VST plugin "8 stems on every track uploaded", and a Hi-Fi model sentence. Help text, not a run. |

## Counts

| Surface | Discovered | Classified | Unresolved interior |
|---|---:|---:|---|
| S1 | 12 | 12 | Visual states of all 12 |
| S2 | 10 | 10 | All hosted interiors except the login redirect |
| S3 | 2 | 2 | Logged-in app |
| S4 | 0 beyond P-S2-04 | 0 | Whole DAW |
| S5 | 0 | 0 | Surface blocked |
| S6 | 522 | 67 | 455 public URLs or articles not opened. See the arithmetic under the table. |
| **Total** | **546** | **91** | Interiors and the 455 public items |

S6 discovered = 405 English sitemap paths + 112 help articles + 5 already-listed meta pages (help home, two categories, robots, sitemap) = 522. Classified S6 rows = P-S6-01 through P-S6-67 = 67. 522 − 67 = 455. App pages stay 12 + 10 + 2 = 24. 522 + 24 = 546 discovered. 67 + 24 = 91 classified.

English paths classified = home + 35 features + 17 products + `/business-api/` = 54. 405 − 54 = 351 English paths without a body. Help articles classified = credits plus the seven new articles = 8. 112 − 8 = 104 articles unread. 351 + 104 = 455.

✅ [S6] pages 67/522 classified, functions unchanged, blocked still S4 interior, S5, and logged-in S3
