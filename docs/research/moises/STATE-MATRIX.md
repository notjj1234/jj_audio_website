# State matrix — 2026-10-23

Empty, loading, error, paywall, permission, and offline states. "Not shown" means the page was not opened, not that the state does not exist.

| Page | Empty | Loading | Error | Paywall | Permission | Offline |
|---|---|---|---|---|---|---|
| P-S1-01 Main window | Not shown | String `Loading...` in main | Not shown | Not shown | Not shown | Not shown |
| P-S1-11 Capture | n/a | n/a | Addon unavailable, device-busy, rate-mismatch, device-not-found, device-lost, driver-error | Not shown | Microphone string in main | Not shown |
| P-S1-12 Downloads | Not shown | `.crdownload` string | Reveal failed; file missing | Not shown | Not shown | Not shown |
| P-S2-* hosted | Not shown | Not shown | Not shown | Not shown | Not shown | Not shown |
| P-S3-01 Login | n/a | Page reached `complete` | Not submitted | Not shown | n/a | Not tested |
| P-S3-02 Signup | n/a | Rendered | Not submitted | Copy says free account. Limits UNKNOWN here. | n/a | Not tested |
| P-S6-01 Marketing | n/a | Rendered | n/a | Home FAQ still gives no count. Help articles P-S6-61 and P-S6-63 state 5 uploads a month. Prices were not on that FAQ. | n/a | Not tested |
| P-S6-07 Sitemap | n/a | Direct GET 200, 3,041 locs | The earlier markdown fetch returned 500. A later direct GET succeeded. | n/a | n/a | n/a |
| P-S6-50 Live marketing | n/a | GET 200 | n/a | n/a | n/a | Page says the product works offline. Not installed, so that state was not tested. |

Persisted shell state that was read: `tabs.json` version 1, one window, two tabs, `activeIndex` 1, not maximized. Song title and id are omitted.
