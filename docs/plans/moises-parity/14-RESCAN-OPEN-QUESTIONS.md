# Open questions — closed or blocked, 2026-10-23

Each row is CLOSED or BLOCKED. BLOCKED rows name the evidence that would close them and whether they block Phase 1.6.

Phase 1.6 may proceed on our player spec. It must not copy a Moises mixer law.

| Question | Status | Blocks 1.6? | Evidence |
|---|---|---|---|
| What does Home, Play, and the player show on 2.1.0? | BLOCKED | No, if the implementer uses `10` §1.3 and §2.5 as our spec. Yes, if the task is to copy a Moises pixel or mixer law. | A walk of P-S2-01, P-S2-02, and P-S2-08 with redacted screenshots. The display was left alone. Do not press Esc. |
| Does the hosted player generate guitar tab? | BLOCKED | No. Our tab view already exists at `main.ts` 2678 and the Tab tab at line 3083. | Open one hosted player and record whether a tab view exists. |
| Studio panels, devices, exports | BLOCKED | No. Studio is Phase 3. | A logged-in throwaway Studio project. No invites. |
| Mastering, Voice, Lyrics behavior and limits | BLOCKED | No. Those routes are Phase 3. | Open each route and record controls. Help text already lists some limits in P-S6-64 through P-S6-67. Enforcement was not captured. |
| Real prices | BLOCKED | No. | Read `studio.moises.ai/pricing/` while logged in. Do not purchase. |
| Whether the free tier really stops at 5 uploads and 5 minutes | BLOCKED | No. Help text is recorded. Enforcement is not. | A quota response. Do not upload private audio to force it. |
| Which Premium credit number is real, 200 or 100? | BLOCKED | No. We are not adding credits. | A quota response or the logged-in balance. Both numbers are in article `21960006352796`. |
| The 11 bridge members REA counted beyond the 68 named methods | BLOCKED | No. Phase 1.6 does not use the Electron bridge. | Re-run REA and project the member names. |
| Renderer bundle behavior | BLOCKED | No. The local bundle is shell chrome. The player we will edit is ours. | `analyze-javascript-application` on `out/renderer/assets/index-C76vPLoN.js` with a raised node cap. |
| Plugin server hash mismatch | BLOCKED | No. | Hash the unpacked exe outside the asar reader and compare it to the declared digest. Bytes stay untrusted. |
| `studio1.moises.ai` | BLOCKED | No. | A navigation that uses that host, or proof it is absent from current main. |
| Mobile apps | BLOCKED | No. | An IPA, APK, or a device you provide. |
| Authenticated API shapes | BLOCKED | No. | A capture with auth headers removed. |
| Home pixels versus our 1.5 spec | CLOSED | No. | `10-MOISES-UI-CRAFT.md` states the numbers are our spec. `06-PHASE-1-PLAN.md` records the 2026-10-23 check of our Home at 1440, 1280, 1024, and 900. |
| Sitemap URL denominator | CLOSED | No. | Direct GET 200, 3,041 locs, 405 English paths. 351 English paths and 104 help articles stay a counted remainder in `PAGE-INVENTORY.md`. |
| Does Moises Live actually run offline? | BLOCKED | No. Live is a separate app. | Install it and capture a session with the network disabled. Marketing page P-S6-50 says on-device and offline. That is not a run. |
| Pan, solo, and fader laws inside Moises | BLOCKED | Yes for copying them. No for keeping our law. | A measured Moises player. Until then, `ui/stem_mixer_component/frontend/src/pan.ts` lines 1–20 stay the law. `15-PHASE-1.6-PLAN.md` forbids editing that file. |
