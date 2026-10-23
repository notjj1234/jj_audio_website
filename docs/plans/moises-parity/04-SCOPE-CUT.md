# Scope cut — 2026-10-23

Every matrix row has one of now / next / later / never. `now` means already in the tree or the immediate gate. `next` is the following build. Decisions did not drop the tab wedge or the local-first rule.

| Rows | Decision | Why |
|---|---|---|
| 1–6, 11–14, 20, 23–27, 30–33, 35–42, 44–49, 54, 56–57, 59, 63–66, 69, 72–75, 78–80, 85, 90, 93, 98, 120, 128–129, 132, 135–137 | now | Already the practice core, or a Phase 1 item the code still shows (count-in, tab PDF import, Home flag, 12 GB gate). Web leftovers inside these numbers stay next if `03` says the web cell is partial. |
| 141–144, 149–153 | next | Home shell craft. Pixels in `10` are not confirmed on Moises 2.1.0. Build them as our Home spec, or remeasure first. See `06`. |
| 7–9, 15–18, 22, 28–29, 34, 43, 50–53, 55, 58, 62, 67–68, 71, 76–77, 86–88, 94, 121–122, 130–131, 145–148 | later | Real practice-adjacent work: editing, capo, batch, web parity, filters, player visual polish. Not this build. |
| 16, 21, 70, 81, 89, 91–92, 95–97, 99–119, 124–125, 134 | later | Studio, generation, voice, mastering, plugins, sync, capture. Separate product. Revisit only after the practice player is the one we ship. |
| 10, 19, 60–61, 82–84, 123 (TV/visionOS), 126–127, 133, 138–140 | never | DRM imports, non-music stems, vocal-pitch and drum-tab products, video export, watermarks, export time limits, B2B deals, a public API, artificial quotas, artist-name prompting, full text-to-song, a social feed. |
| N1 memory panel | never | Their low-memory chrome. We keep the 12 GB gate instead of cloning a panel we did not see. |
| N2 sparkbars | never | Not a product. It is the Studio icon id. |
| N5 video-recording marketing | never | Not the guitar-practice job. Our picture sync, if it stays, is the local player, not a social camera. |
| N6 credit accounting | never | Do not add generation credits. |

Row numbers are `03-FEATURE-MATRIX.md`. N-rows are `13-PARITY-DELTA.md`.

Rollback for anything in `next`: `AUDIO_TOOLS_UI_V2=0` keeps the old Home (`ui/design_tokens.py`).
