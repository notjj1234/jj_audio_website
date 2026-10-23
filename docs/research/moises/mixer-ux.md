# Mixer and player — 2026-10-23

No mixer was measured on Moises 2.1.0.

The local renderer bundle does not contain `player2`, `guitar`, or `chord` in a literal scan, and its HTML cannot call the network. The player the persisted session had open is a hosted `studio.moises.ai/player2/` view. That view was not displayed. Pan law, solo law, fader scale, stem count, and transport behavior are **UNKNOWN** for this build.

The 2026-10-21 Home pixel tables in `docs/plans/moises-parity/10-MOISES-UI-CRAFT.md` were not remeasured. They are not a 2.1.0 observation.

Our own mixer laws stay ours. Do not import a Moises curve from the archived 2.0.3 literal scan. That scan did not establish a curve either.

Shell interactions that wrap the hosted player, and that were read from the preload rather than clicked:

- Tab create, close, activate, reorder, duplicate, close others, close right, context menu, preview.
- `desktop:pause-playback` from the host into the page.
- Capture open/close for a live input, separate from stem faders.

Memory panel channels exist. What they show was not seen.
