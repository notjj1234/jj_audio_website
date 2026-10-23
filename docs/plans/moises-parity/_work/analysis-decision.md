# Task 0 — analysis stack decision (Gate 1 evidence)

**Date:** 2026-10-19
**Status:** PASS (provisional). Zero-dependency chord/section paths selected; lyrics path measured and
approved by delegation. Real-song chord accuracy has **no labelled ground truth**, so this gate is
"usable draft" evidence, not a certified 70% score.

**Baseline:** `pytest tests/ -q` → 881 passed, 1 skipped, 0 failed (31.5 s); `ruff` clean.
The one baseline failure was the pre-existing `settings.allow_youtssube` typo in `backend/main.py:343`;
fixed to `allow_youtube` (`test_youtube_disabled` now passes). Out-of-scope baseline repair.

## 1. Reference songs

| Role | File | Duration | Notes |
|---|---|---|---|
| Clean guitar | `【TAB】Waltz for Debby - Bill Evans - FingerStyle Guitar ソロギター【タブ】.mp3` | 124.9 s | solo fingerstyle, 44.1 kHz; opening 0–45 s used as the quiet/dynamic case |
| Dense mix + vocals | `フルスピード・ボーイ.mp3` | 290.4 s | 48 kHz, Japanese vocals, full band |
| Quiet/dynamic | first 45 s of the Waltz | 45 s | RMS 0.150 intro vs 0.199 body |

Never uploaded, copied into the repo, or committed. Paths are local only.

## 2. Chord recognition

`_work/spikes/song_profile.py` (CQT chroma, beat-synchronous templates, 5-beat smoothing, then
Viterbi with a chord-change penalty and a triad prior).

### Fixture (labelled)

`eval/fixtures/chords.wav` (G 0–1.5 s, C 2–3.5 s, G 4–5.5 s): **3/3 segments correct**.

### Real songs (no labels)

| Song | Tempo | Key from chords | Chord runs | Notes |
|---|---|---|---|---|
| Waltz for Debby | 103.4 | **D / Dm** (0.544 / 0.509) | 138 / 207 beats | A-minor-7, D-sus4, A7, Dm7, Gm, Bb, F — plausible D-minor jazz palette |
| フルスピード・ボーイ | 92.3 | **C#m / F#m / E** (0.519 / 0.486 / 0.474) | 150 / 439 beats | E-maj7, A-maj7, C-maj7, G#-maj7; relative-key ambiguity |

Raw chroma key profiles said **Am for both songs** (0.97); the chord-histogram scorer fixed that to
plausible relative keys. Decision: **key comes from the chord histogram first**, raw chroma only as a
fallback when chords are empty.

Weakness: the template baseline over-labels maj7 and sus4 and still changes chord too often. Ship it as
an **editable draft** (chord editing is Phase 2), with triads preferred and a visible confidence. A
neural CRNN is not added now; it stays the fallback only if a labelled evaluation later shows <70%.

Rejected packages (audited, not installed):

| Candidate | Licence | Why rejected |
|---|---|---|
| `chord-extractor` 0.1.3 | **GPL-2.0** | bundles a **Linux x86-64 ELF** `nnls-chroma.so`; will not load on macOS |
| `autochord` 0.1.4 | Apache-2.0 | same Linux ELF `.so`; downloads weights from **Google Drive via `gdown`** (unpinned, 2021) |

## 3. Sections

`_work/spikes/song_profile.py` (beat-synchronous chroma, recurrence matrix, checkerboard novelty,
≥8 s minimum section):

| Song | Sections | First boundaries |
|---|---|---|
| Waltz | 10 | 1.0–9.8, 9.8–20.2, 20.2–38.5, 38.5–49.5, … |
| フルスピード・ボーイ | 24 | 1.3–17.8, 17.8–26.2, 26.2–46.2, 46.2–57.8, … |

Boundaries track the obvious energy/texture changes in the chroma; no ground-truth boundary file exists.
Decision: keep this algorithm; labels stay conservative (`Intro`/`Verse`/`Chorus`/`Bridge`/`Section`),
minimum 8 s, one `Full song` fallback on failure.

## 4. Lyrics

`faster-whisper 1.2.1` + `Systran/faster-whisper-small`, CTranslate2 int8, CPU. Model files downloaded
with `download_sha256_file` (urllib) to `~/.cache/audio_to_tab/analysis/faster-whisper-small`:

| File | Size | SHA256 |
|---|---|---|
| `model.bin` | 483,546,902 B | `3e305921506d8872816023e4c273e75d2419fb89b24da97b4fe7bce14170d671` |
| `config.json` | 2,370 B | `b55496ac7940a7ae47d2c01eab40edfd8701feec1229d9cce3b40014383fb828` |
| `tokenizer.json` | 2,203,239 B | `fb7b63191e9bb045082c79fd742a3106a12c99513ab30df4a0d47fa6cb6fd0ab` |
| `vocabulary.txt` | 459,861 B | `34ce3fe1c5041027b3f8d42912270993f986dbc4bb34cf27f951e34a1e453913` |

Results:

| Song | Language | Words | Time | RTF | Notes |
|---|---|---|---|---|---|
| Waltz (instrumental) | en (p=0.39) | **0** | 2.2 s | 58× | VAD correctly returned no lyrics; no hallucination |
| フルスピード・ボーイ | ja (p=0.994) | 135 | 9.3 s | 31× | all timestamps valid; speech coverage 118 s / 290 s; one 60 s segment needs display splitting |

Decision: keep `faster-whisper` small. At runtime load the **local pinned directory**; never call the
Hugging Face downloader. Split segments longer than ~8 s into display lines. If VAD coverage is <40% on
a known-vocal song, retry once without VAD. English is untested (the supplied vocal track is Japanese);
Japanese works, which is a bonus. If word timestamps are unreliable in the UI, show line-level only.

## 5. Gate 1 verdict

- **Sections:** usable navigation draft.
- **Key:** plausible from chords; raw chroma rejected as primary.
- **Chords:** plausible roots/key, noisy extensions; usable draft, editable in Phase 2.
- **Lyrics:** works (Japanese), fast, no instrumental hallucination; line splitting needed.
- **No labelled chord/boundary corpus**, so the 70% chord gate cannot be certified. The user review of
  the sample charts is the remaining check.

Proceed to Phase 1 Tasks 1–14 with these choices. No new chord dependency; only `faster-whisper` was
added, and only the pinned model above is used.
