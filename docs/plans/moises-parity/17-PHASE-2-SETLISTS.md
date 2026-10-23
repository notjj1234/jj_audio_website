# Phase 2 slice — local setlists

A setlist is a named list of songs already on this computer. Sharing, links, and collaborative setlists stay out.

## Tasks

1. `ui/setlists.py` loads and saves `setlists.json`. Create, add, and remove. A song appears once, in the order it was added. A blank name becomes "Setlist".
2. Home shows one pill per setlist, a New setlist button, and Add to setlist on a song. The browser receives setlist ids and song tokens, never file paths.
3. Rebuild the Home frontend with `scripts/dev.ps1 home-build`.

## Tests

- `tests/test_setlists.py`

## Rollback

Delete `ui/setlists.py` and the Home setlist pills. Leave the library table as it is.

Out of scope: the website player and the batch queue.
