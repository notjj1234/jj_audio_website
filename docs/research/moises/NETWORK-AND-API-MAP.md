# Network and API map — 2026-10-23

No HAR, cookie, or response body from a logged-in session was saved. Hosts below are literals or responses this scan fetched. A no-match is not proof a host is unused.

## Hosts observed

| Host | How | Auth seen | Notes |
|---|---|---|---|
| `studio.moises.ai` | Literal in main; persisted Home tab; browser navigation | Login wall at `/auth/login` | Product origin for Home, Play, Studio, Mastering, Voice Studio, Lyric Writer, player |
| `studio-stage.moises.ai` | Literal in main | Not requested | Stage host. Use UNKNOWN. |
| `plugins.moises.ai` | Literal in main | Not requested | Plugin payload host |
| `download.todesktop.com` | `app-update.yml` channel `latest`, provider `generic`, url `https://download.todesktop.com/220410vabqjud82` | None | `latest.yml` returned 2.1.0 / `261021a1gygumpb` / release `2026-10-21T12:53:06.324Z` |
| `moises.ai` | Browser | None | Marketing |
| `www.moises.ai` | `robots.txt` | None | Same robots body as the apex |
| `help.moises.ai` | Browser and fetch | None | Zendesk-style help |
| Sentry ingest | Literal in main | DSN not recorded | `@sentry/electron` is a dependency. Calls not captured. |
| `moises.com`, `*.moises.ai`, `*.moises.com`, `*.moises.localhost` | Allow-list strings in main | Not requested | INFERRED as navigation allow-list from surrounding strings. Enforcement not watched. |

## Desktop IPC

The channel list is `FUNCTION-INVENTORY.md`. REA: 68 literal channels, 0 dynamic, 54/54 renderer transmissions paired, 0 sender-validation observations. Static pairing is not a runtime security verdict.

## Capture utility

`out/main/audio-capture-host.js` is a utility using `process.parentPort`. Parent messages: `devices`, `open`, `close`, `watch`. Child replies include `devices`, `opened`, `closed`, `failed`, `devices-changed`. PCM posts use `t: "pcm"` with `frame`, `hostTime`, `samples`, and optional `lost`. Default API on Windows is WASAPI. ASIO is compiled for `win32-x64` and is used only when asked by name. Error codes in that file: `addon-unavailable`, `unknown-api`, `device-busy`, `device-not-found`, `rate-mismatch`, `device-lost`, `driver-error`.

The shipped README says the addon is RtAudio 6.0.1 with Moises patches, replacing audify. That README is OBSERVED text. This scan did not open a capture stream.

## Auth

Logged-out buttons: Google, Facebook, Apple, X, email. Endpoints behind those buttons were not captured. Signup and login URLs are in `PAGE-INVENTORY.md`.

## Not observed

WebSocket, SSE, upload URL, separation API, quota response, feature-flag payload, and billing API were not observed. Help articles describe credits and plans; those numbers are help text, not captured responses.
