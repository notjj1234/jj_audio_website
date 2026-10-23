# Roadmap — 2026-10-23

Order is unchanged in intent. The evidence under it changed. Do not start Studio work to "catch 2.1.0".

| Phase | Exit | Why this order |
|---|---|---|
| 1 — practice core | Code for analysis display, count-in, loop, and tab in the player is already in the tree. This scan did not re-run the three-song checklist. | The wedge is tab plus a local player. That stays ahead of a DAW. |
| 1.5 — Home shell | Done. Our Home matched `11` §12 at 1440, 1280, 1024, and 900 on 2026-10-23. The check used our spec, not a Moises 2.1.0 remeasure. | The shell is what people see first. |
| 1.6 — player craft | `15-PHASE-1.6-PLAN.md`. Layout and empty states only. Installer model download is not in that plan. | After Home, so the practice screen is not restyled twice. |
| 2 — practice depth | Chord edit, capo, setlists, web player, batch as a queue. | Only after the desktop player is the daily tool. |
| 3 — other products | Studio, voice, mastering, generation, plugins, sync, mobile. Go/no-go, not a default build. | Moises already splits these into other routes. We should too. |

Dependencies: Home can still fall back with `AUDIO_TOOLS_UI_V2=0`. That check passed on 2026-10-23. Phase 1.6 does not change the pan law, the MPS gate, or isolation. Next code is `15-PHASE-1.6-PLAN.md`.

Risk: treating 2026-10-21 screenshots as 2.1.0 parity. Mitigation is the banner on `10` and `11`.

Rollback: env flag `AUDIO_TOOLS_UI_V2=0`.
