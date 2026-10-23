# Scan checkpoint — 2026-10-23

**Surface now:** S1 shell static analysis is done. S3 logged-out auth and S6 public help/marketing are partially captured. Logged-in product interiors are not.

**Last completed unit:** Shell JavaScript REA of `out/main`, both preloads, the capture host, and `out/renderer/index.html`. Evidence `ev_2015286d22cfc4a62451bbee9e1c1ca624e084e78ff6c80bf01cfaa20162ab93`. Preload bridges were read in full. Hosted route literals were read from `out/main/index.js`.

**Next unit:** With the primary display free of fullscreen video, restore the running Moises window (it was minimized; hwnd was the Chrome widget at `-32000,-32000`) and walk Home, Play, the open player tab, Studio, Mastering, Voice Studio, and Lyric Writer. Do not press Esc on a fullscreen video. Do not submit login, upload audio, or buy a plan.

**Open blockers:**

1. Logged-in desktop UI was not captured. The primary monitor was in a fullscreen browser video. The Moises window was restored once, landed under that video, and was then left minimized. Topmost was cleared. Do not dismiss the user's fullscreen to continue.
2. `studio.moises.ai` in the isolated browser stops at `/auth/login` and `/auth/signup`. No credentials were entered.
3. Mobile: no device, simulator, APK, or IPA on this host.
4. No HAR. Network map is static hosts plus the update feed.
5. Renderer bundle `out/renderer/assets/index-C76vPLoN.js` (1,724,942 bytes) had a literal needle scan only. REA semantic analysis was not run on it.
6. REA MCP is not connected in this Cursor session. CLI on Node 24.19.0 was used. `rea setup` was not run.
7. Sitemap direct GET is 200: 544,988 bytes, 3,041 locs. The earlier 500 was the markdown fetcher. 351 English paths and 104 help articles are still unread. Logged-in pricing is still unread.

**Do not treat as current:** Moises 2.0.3 and 2.0.18 notes, including the audify capture description and any Home pixel measurements, until they are re-seen on 2.1.0.

**Personal data:** A persisted tab title and a player id were seen in `%AppData%\Roaming\Moises\tabs.json`. They are not copied into this repo.
