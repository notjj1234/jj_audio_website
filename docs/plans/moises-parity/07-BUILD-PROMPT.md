# Build prompt — paste into a fresh session

You are implementing Phase 1.6 in `C:\Users\orall\Documents\GitHub\jj_audio_website`.

Read, in order:

1. `docs/plans/moises-parity/15-PHASE-1.6-PLAN.md`
2. `docs/plans/moises-parity/10-MOISES-UI-CRAFT.md` §1.3 and §2.5
3. `ui/stem_mixer_component/frontend/src/main.ts` from the `root.innerHTML` template

Home is done. Do not rebuild it. `AUDIO_TOOLS_UI_V2=0` must keep the old Home.

Constraints:

- Follow `15` task by task. The practice sheet moves below `.mixer-stage`. Speed and Key become a popover. Master stays with the stems.
- Pixels in `10` are our spec, not Moises 2.1.0 parity.
- Do not edit `pan.ts` or `web/src/mixer/pan.ts`. Do not change `setPracticeRate`, `startCountIn`, or `startSources`.
- Do not raise `MPS_MIN_RAM_GB` (12.0 in `src/audio_to_tab/hardware.py`).
- Do not unify Desktop Interface Lite with hosted `lite`.
- Desktop isolation stays serial.
- Rebuild the mixer with the existing script. Do not hand-edit hashed `frontend/build/` output.
- Check 1440, 1280, 1024, and 900.
- Do not commit, push, or open a PR unless this conversation asks for it.
- Do not log into Moises, upload audio, or buy a plan.

Done means: the tests named in `15` pass, and the stem list is above the practice sheet at those four widths.
