# Stage A — reference songs (local only)

These files are **not** copied into the repo and must never be committed. The paths below are
the user's local files; hashes identify exactly what was measured.

| Role | Path | Duration | SHA256 |
|---|---|---|---|
| Clean solo guitar | `/Users/JJ/Downloads/reference audio files/【TAB】Waltz for Debby - Bill Evans - FingerStyle Guitar ソロギター【タブ】.mp3` | 124.9 s | `58e5ac0166f7d0c07347ff005a13804983d760bf99877882bae96190e590bbbc` |
| Dense mix + Japanese vocals | `/Users/JJ/Downloads/reference audio files/フルスピード・ボーイ.mp3` | 290.4 s | `5d4f30cce88d0bd2a4d2f96c86a23911561f3eb08b3329a267def8092fb371b1` |
| Quiet/dynamic | first 45 s of the Waltz | 45 s | derived from row 1 |

The third case is an excerpt, not a third file: the Waltz opens at RMS ≈ 0.150 and settles at
≈ 0.199, which is the quiet-intro/dynamic case the plan asks for. The full-band track covers the
dense-mix and vocal cases.

## Commands

```bash
# chord / key / beat / section profile
.venv311/bin/python docs/plans/moises-parity/_work/spikes/song_profile.py \
  "<waltz path>" "<full-speed path>"

# lyrics (pinned local model, no Hugging Face downloader)
.venv311/bin/python docs/plans/moises-parity/_work/spikes/lyrics_spike.py \
  "<waltz path>" "<full-speed path>"
```

Results and decisions are recorded in `../analysis-decision.md`.
