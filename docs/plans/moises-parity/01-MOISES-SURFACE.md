# Moises surface — 2026-10-23

The page list is `docs/research/moises/PAGE-INVENTORY.md`. This file is the product map.

## Products in the desktop shell

Observed as menu labels and paths in `out/main/index.js` on build `261021a1gygumpb`.

| Product | Paths | Notes |
|---|---|---|
| Home | `/home` | Persisted tab used `https://studio.moises.ai/home?client=desktop`. Interior not opened. |
| Play | `/play`, `/upload/split`, `/upload/split/3` | Practice upload family. Interior not opened. |
| Player | `/player2/<id>` | One persisted tab. Interior not opened. |
| Studio | `/studio`, `/studio/new` | Icon name `sparkbars`. Marketing calls this a shared browser session. Interior not opened. |
| Mastering | `/mastering`, `/mastering/upload`, `/upload/master` | Also a plugin filename family. |
| Voice Studio | `/voice-studio`, `/voice-studio/upload` | Interior not opened. |
| Lyric Writer | `/lyrics`, `/lyrics/new`, `/lyric-writer` | Interior not opened. |

The shell itself is a window with tabs, a memory panel, updates, a tray, and a plugin server. It is not the mixer.

## Plan tiers

Public pages this scan opened do not list prices.

- Marketing FAQ on the home page still does not give the monthly count. Help articles do. Free: 5 uploads a month, and deleting a file does not give the slot back (P-S6-61, P-S6-63). Free stems are 5 minutes; Premium and Pro stems are 20 minutes (P-S6-62). These are help articles, not a captured quota response.
- Help Plans & Billing names Premium and Pro, monthly or annual, and cancel paths for Stripe, PayPal, App Store, Play Store, and Ebanx.
- Terms text from the help center says the price and feature table is on a Pricing Page available once logged in.
- AI Studio credits article: 30 seconds per credit; Free 10/month; Premium 200/month in the bullet list; Pro unlimited. Example 3 in the same article uses 100 for Premium. Product enforcement UNKNOWN.

Do not carry forward any dollar amount from older notes.

## Platforms

Desktop Windows 2.1.0 was inspected. The feed also lists an arm64 installer and a larger combined installer. Those files were not opened. Marketing says web, desktop, iPhone, iPad, and Android exist. Mobile was not installed here. Moises Live has a public page, P-S6-50, which calls it a separate desktop app that runs on-device and works offline. It was not installed. The product paths in the sitemap are listed in `PAGE-INVENTORY.md`.

## Auth

`studio.moises.ai` redirects to `/auth/login`. Providers: Google, Facebook, Apple, X, email. Signup is a separate page and was not submitted.

## What we will not pretend to have seen

Stem quality, chord editing, metronome behavior, export formats, collaboration presence, and Studio devices. See `14-RESCAN-OPEN-QUESTIONS.md`.
