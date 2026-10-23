# Coverage ledger — 2026-10-23

Arithmetic a reviewer can re-add. Definitions match `PAGE-INVENTORY.md` and `FUNCTION-INVENTORY.md`.

## Pages

| Surface | Discovered | Classified | Unresolved interior |
|---|---:|---:|---:|
| S1 shell | 12 | 12 | 12 |
| S2 hosted routes | 10 | 10 | 10 |
| S3 logged-out web | 2 | 2 | 0 of those two pages; logged-in web not discovered |
| S4 Studio panels beyond the route | 0 | 0 | blocked, not discovered |
| S5 mobile | 0 | 0 | blocked |
| S6 public | 522 | 67 | 455 sitemap paths and help articles not opened |
| **Sum** | **546** | **91** | |

App pages stay 12+10+2 = 24. Public discovered = 405 English sitemap paths + 112 help articles + 5 meta pages = 522. 24+522 = 546. Classified = 24+67 = 91. Unresolved public = 522−67 = 455. The 3,041 sitemap locs include locale copies; those copies are not extra pages. Locale counts are in `PAGE-INVENTORY.md`.

## Functions

| Tier | Discovered | Classified | Runtime-executed | Blocker |
|---|---:|---:|---:|---|
| T1 shell and webview bridge methods | 68 | 68 | 0 | Window not walked |
| T2 named channels inside those methods, plus hosts F-069–F-076 | 76 | 76 | 1 (update feed) | No HAR |
| T3 shell syntax tokens in the five parsed JS files | 563 | 563 files parsed; names not listed | n/a | |
| T3 renderer bundle tokens | 3885 | 0 semantic | n/a | REA not run on that file |
| T3 node_modules files outside the selection | 6510 | 0 | n/a | Inventory only |
| Bridge members REA counted but this read did not name | 11 | 0 | n/a | Summary view has a count only |

Token check: 414+37+9+79+24 = 563.

REA cross-check on `ev_2015286d22cfc4a62451bbee9e1c1ca624e084e78ff6c80bf01cfaa20162ab93`: literal channels 68, exposed members 79, parsed JavaScript files 5, text bytes read 79019. Byte check: 66147+5211+659+4105+1961+936 = 79019.

## Planning close, same day

Counts were not changed by writing `15-PHASE-1.6-PLAN.md`.

Re-add: 12+10+2 = 24. 405+112+5 = 522. 24+522 = 546. 67+24 = 91. 522−67 = 455. 405−54 = 351. 112−8 = 104. 351+104 = 455.

## Gates this ledger can support

Pages discovered have rows. T1 and T2 rows exist, with static chains and a runtime blocker. T3 modules have a discovered count and an analyzed count. Logged-in product behavior is not covered. That is an open scan, not a finished product census.
