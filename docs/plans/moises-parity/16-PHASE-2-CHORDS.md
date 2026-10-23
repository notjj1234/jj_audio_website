# Phase 2 slice — chord edit and capo

The practice sheet already draws chord chips, the current chord name, and a fixed "No capo" label. This slice adds two controls. It does not restyle the player from Phase 1.6.

Chosen behavior: type a new symbol on one chord chip. Capo is a fret from 0 to 11. Fret 0 reads "No capo". Any other fret reads "Capo N". The chord name on the chip and on the current-chord line stays the sounding name. The diagram uses the shape you would finger with that capo, which is the name transposed down by N frets.

## Tasks

1. Pure helpers in `ui/stem_mixer_component/frontend/src/analysis.ts`: `replaceChordSymbol`, `capoDiagramSymbol`, `capoLabel`.
2. In `main.ts`, an input on each chord chip and `<select id="chord-capo">` in the existing capo spot. Edits stay on that song if the parent sends the original analysis again.
3. Rebuild with `scripts/dev.ps1 mixer-build`.

## Tests

- `tests/test_stem_mixer_component.py::test_capo_and_chord_edit_rules` runs the helpers.
- `tests/test_stem_mixer_component.py::test_chord_chip_is_editable_and_capo_has_a_control` checks the sheet markup.

## Rollback

Remove the three helpers, the chip input, and `#chord-capo`. Restore the chord chip button and the fixed "No capo" text.

Out of scope: setlists, the website player, and the batch queue.
