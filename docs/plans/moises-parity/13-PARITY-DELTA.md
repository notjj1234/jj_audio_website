# Parity delta versus the archived matrix

Archive: `docs/plans/moises-parity/_work/archive-pre-rescan-2026-10-23/plans-moises-parity/03-FEATURE-MATRIX.md`.

Every old id 1–153 is in exactly one bucket.

## CONFIRMED

Narrow scope only.

| IDs | What was re-seen |
|---|---|
| 5 | `import:consume` exists on the webview bridge |
| 85 | Home route and a persisted `studio.moises.ai/home?client=desktop` tab |
| 110 | `/studio` and `/studio/new` exist. The timeline was not opened. |
| 120 | Windows desktop 2.1.0 build `261021a1gygumpb` |
| 124 | Plugin filenames and `plugin:install` |
| 125 | Public Live page P-S6-50. The app was not installed. |
| 128 | The shell's Home is a hosted URL. Our MPS gate is still 12 GB. |
| 133 | Help text states 5 uploads a month and the 5-minute / first-minute split. Not a quota response. |

## CORRECTED

Certainty only, unless the note says a fact changed. Decisions in `04` did not flip.

IDs: 1–4, 6–84, 86–109, 111–119, 121–123, 126–127, 129–132, 134–153.

Count: 4 + 79 + 24 + 9 + 3 + 2 + 4 + 20 = 145. Plus 8 confirmed = 153.

Correction: the Moises behavior in the archived cell was not executed on 2.1.0. Keep the decision. Do not quote stem counts, prices, or mixer laws from that cell as current.

Additional fact corrections that are not those rows:

| Topic | Was | Now |
|---|---|---|
| Capture addon | audify in the 2.0.3 teardown | Custom `capture.node` (RtAudio 6.0.1) per the shipped README. Process string `MoisesAudioCapture` remains. |
| Build | 2.0.3 and 2.0.18 | 2.1.0 `261021a1gygumpb`, feed-current on 2026-10-23 |
| Studio icon | not named sparkbars | `sparkbars` is the icon id beside the Studio paths |
| Prices | older notes may cite public prices | Not on the pages opened. Logged-in pricing page not opened. |
| Credits | not in the old matrix as a measured quota | Help article re-fetched 2026-10-23: 30s per credit; Free 10; Premium 200 in the list and 100 in example 3 |
| Sitemap | recorded as HTTP 500 | Direct GET 200, 544,988 bytes, 3,041 locs. The 500 was the markdown fetcher. |
| Free tier | "FAQ has no number" | Help articles P-S6-61 and P-S6-63 state 5 uploads a month. P-S6-62 states 5-minute stems and a first-minute analysis cap. |
| Guitar tab on the public site | open | Chord Finder and Capo Mode pages have no `guitar tab` or `tablature` string. The player is still unopened. |
| `/business-api/` | treated as a possible API spec | The URL returns a Music AI marketing page (P-S6-60). |

## NEW

| ID | Capability | Evidence | Decision |
|---|---|---|---|
| N1 | Memory panel and memory icon | F-019–F-027 | never clone; keep our memory gate |
| N2 | `sparkbars` icon id | main string beside `/studio` | never as its own feature |
| N3 | WASAPI/ASIO capture utility | capture host and README | later, not the practice wedge |
| N4 | Login providers Google, Facebook, Apple, X, email | P-S3-01 | later, only if we add accounts |
| N5 | Marketed video recording | P-S6-01 | never for this product |
| N6 | AI Studio credit help text | P-S6-05 | never add credits |
| N7 | `studio-stage.moises.ai` and `studio1` IndexedDB directory | main literal; directory name | unknown; do not build |

## REMOVED

None. No archived capability was shown to be gone.
