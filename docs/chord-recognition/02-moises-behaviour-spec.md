# 02 — Moises AI chord / key / chart: observable behaviour spec

**Method:** public sources only. Official help centre, marketing pages, the in-repo
competitive snapshot taken on 2026-10-19 from the public Zendesk API and the public site
(`docs/plans/moises-parity/_work/moises-public.md`), plus a measured UI-craft pass on
Moises.app 2.0.x recorded in `docs/plans/moises-parity/10-MOISES-UI-CRAFT.md`.

**No decompilation, no private API, no account, no paywall bypass.** Where a behaviour is not
publicly observable it is marked **UNKNOWN** with a hypothesis, never stated as fact.

Confidence tags: **OBSERVED** (seen in the running app and recorded in-repo) ·
**DOCUMENTED** (official help/marketing page) · **INFERRED** (follows from two documented facts) ·
**UNKNOWN**.

Access date for every URL below: **2026-10-25**.

---

## 0. Summary of the surface

| Question | Answer | Confidence |
|---|---|---|
| Is there chord detection? | Yes, per-song, real-time, with diagrams | DOCUMENTED |
| Is there key detection? | Yes, displayed, and feeds the pitch changer | DOCUMENTED |
| Vocabulary size | 3 display levels (easy / medium / advanced) in the app; **4 label classes** (Complex Jazz / Simple Jazz / Complex Pop / Simple Pop) on the same timeline in the public API; exact symbol set not published | DOCUMENTED (levels + classes) / UNKNOWN (symbols) |
| Display modes | Bar mode and Grid mode (grid is mobile-only per the article) | DOCUMENTED |
| Sync | "in sync with the song", "synced with bars and beats" | DOCUMENTED (claim), not measurable from outside |
| Capo | Yes, shapes change, key does not | DOCUMENTED |
| Notation switch | Sharps/flats preference in Song Settings → Chords | DOCUMENTED |
| Chord chart export | **Web link + iReal Pro + MusicXML**, lyrics-aligned, sectioned, header = key/tempo/time signature, link stays transposable and editable | DOCUMENTED |
| Guitar tab | None | DOCUMENTED (absence) |
| Free tier | Chords limited to the song's first minute | DOCUMENTED |

---

## 1. Behaviour catalogue (testable specs)

Each spec is written so it can become an acceptance test: **input → expected output → how it was
observed**.

### B-01 — Real-time chord display, beat-locked
- **Input:** open a processed song, press play with Chords enabled.
- **Expected:** the current chord symbol and its diagram change as the song plays, at the moment the
  chord changes in the audio; the display never shows a chord from a different bar.
- **Observed:** "This feature detects and displays chords for any song in real-time." and "Chords and
  diagrams will display automatically in sync with the song."
  — https://help.moises.ai/hc/en-us/articles/6569274648220-How-do-I-use-Chord-Detection
- **Confidence:** DOCUMENTED. The *quantitative* lag (ms) is UNKNOWN.

### B-02 — Bar mode (linear chord row)
- **Input:** Chords → first option (mobile).
- **Expected:** chords laid out linearly with the song, one cell per chord change, following playback.
- **Observed:** "Select the first option to display the Chords in bar mode." (same article).
- **Confidence:** DOCUMENTED.

### B-03 — Grid mode (bar/beat grid)
- **Input:** Chords → "Grid".
- **Expected:** a grid of bars × beats with a chord per cell or per bar, a bar-number gutter, and the
  active beat cell filled; chords, lyrics and sections can be shown together.
- **Observed:** "Learn the complete song structure effortlessly, synced with bars and beats.
  Integrate chords, lyrics, and sections" — https://help.moises.ai/hc/en-us/articles/9570133423772-How-to-use-the-new-Chords-view-Grid-Mode
  Plus the measured UI pass: "bar-number gutters, 4 beat cells per bar, chord symbols, and a white
  active-beat cell … The current beat is a **filled cell** … the strongest state in the practice
  surface" — `docs/plans/moises-parity/10-MOISES-UI-CRAFT.md:140-151`.
- **Confidence:** OBSERVED.
- **Note:** the help article says Grid is "for now, available only on the Mobile versions"; the
  2026-10 UI pass observed a 4-beat-cell chord chart in the desktop/web player. Both are recorded;
  treat desktop grid support as **OBSERVED in 2.0.x, not documented**.

### B-04 — Three difficulty levels (simplified ↔ full)
- **Input:** chord view setting → easy / medium / advanced.
- **Expected:** the same song yields progressively richer chord symbols/voicings; easy should bias to
  open/triad shapes, advanced may include extensions and less common voicings. The *underlying key
  and timing do not change*.
- **Observed:** "you can also set the chord view to easy, medium, or advanced"
  (help article above); "adjusting to 3 different difficulty levels … easy, medium, and advanced"
  — https://moises.ai/features/guitar-chord-finder/
- **Confidence:** DOCUMENTED (that the levels exist) / **UNKNOWN** (the exact symbol vocabulary per
  level). Hypothesis below.
- **Hypothesis (labelled):** the difficulty setting is a *display filter*, not a re-detection: one
  full-vocabulary chord track is detected, then rendered at three levels (triads only → triads +
  common 7ths → all detected qualities). Rationale: Moises markets "3 difficulty levels" as a chord
  *view* setting, the same phrasing used for capo and notation, which are display transforms.

### B-05 — Chord diagrams
- **Input:** any detected chord.
- **Expected:** a guitar chord diagram (fretboard grid, dots, open/muted marks, base-fret label for
  barre shapes) shown next to the current symbol; diagrams follow the capo setting.
- **Observed:** "Moises' web and desktop versions display the chord diagrams in sync with the songs"
  — https://moises.ai/features/guitar-chord-finder/ ; the measured pass records a shape/diagram for
  the current chord (`10-MOISES-UI-CRAFT.md:152`).
- **Confidence:** DOCUMENTED + OBSERVED.

### B-06 — Capo
- **Input:** set capo fret N (0…11 in our implementation; Moises range UNKNOWN).
- **Expected:** displayed chord *shapes* transpose down by N frets; the **sounding chord name and the
  song key stay the same**; the audio is not pitch-shifted.
- **Observed:** "input the fret number where your capo is placed. Moises will automatically adjust
  the displayed chord shapes to match the capo position without changing the song's key."
  — https://moises.ai/features/guitar-capo-mode/
- **Confidence:** DOCUMENTED.
- **Testable assertion:** with capo=N, `shape(chord) == chord transposed by −N` and
  `sounding(chord) == chord`.

### B-07 — Pitch / key change and its effect on chords
- **Input:** transpose the song by S semitones.
- **Expected:** chord names transpose by S in real time; the chart keeps working (no re-analysis
  wait).
- **Observed:** "Changing the key to match your guitar tuning or your voice range? Our Guitar Chord
  Finder reacts in real-time." — https://moises.ai/features/guitar-chord-finder/
- **Confidence:** DOCUMENTED (claim). Whether the chord *labels* are transposed from a stored track or
  re-detected is **UNKNOWN**; hypothesis: stored track + display transposition (cheap, instant).

### B-08 — Notation preference (sharps / flats)
- **Input:** Song Settings → Chords → notation.
- **Expected:** the same pitch class is spelled `A#` or `Bb` consistently across the chart; the
  underlying chord identity is unchanged.
- **Observed:** "you can change your view to simplified, add a capo, or change the notation; click on
  Song Settings > Chords" (Chord Detection article).
- **Confidence:** DOCUMENTED.

### B-09 — Key detection display
- **Input:** any processed song.
- **Expected:** a key is shown (e.g. "Dm"); it is a single tonic+mode, not a key-confidence badge; it
  is used by the pitch changer.
- **Observed:** "Detects song key and displays it"; the Key Detection article is also the Pitch
  Changer article — https://help.moises.ai/hc/en-us/articles/6582517238044-How-do-I-use-the-Key-Detection-with-the-Pitch-Changer
  Also recorded in the public feature table: `_work/moises-public.md:81`.
- **Confidence:** DOCUMENTED.
- **UNKNOWN:** whether relative major/minor is disambiguated by a confidence threshold, and whether
  the displayed key updates when the user edits/transposes the chart.

### B-10 — Tempo / BPM display and the speed changer
- **Input:** open a song; change speed.
- **Expected:** BPM is displayed and the metronome/speed controls follow it; the chord chart stays
  aligned when speed changes.
- **Observed:** "Detects tempo, feeds speed changer and metronome"
  — https://moises.ai/features/bpm-finder/ ; `_work/moises-public.md:87`.
- **Confidence:** DOCUMENTED.
- **UNKNOWN:** whether BPM is re-estimated after a tempo automation edit, and how the grid handles
  tempo changes (see B-11).

### B-11 — Tempo automation / variable tempo
- **Input:** change the song's tempo (per-song BPM with a click that follows the curve).
- **Expected:** the chord grid and metronome follow the tempo curve rather than a constant BPM.
- **Observed:** "Per-song BPM change with click that follows the curve"
  — https://help.moises.ai/hc/en-us/articles/6582847813148-How-do-I-change-the-song-s-tempo
- **Confidence:** DOCUMENTED.
- **Implication for us:** a constant-BPM grid is not parity; we already have a tempo curve
  (`metronome.py:bpm_curve`), but the chord stage flattens it to `click_times_1x` beat list.

### B-12 — Metronome: smart follow, subdivisions, count-in
- **Input:** enable metronome; choose 1× / 0.5× / 2×; set count-in bars.
- **Expected:** clicks land on the song's beats, accent beat 1, subdivisions subdivide; count-in plays
  N bars before the song starts and the transport holds until it finishes.
- **Observed:** "Generates a click that follows the song's tempo curve"; "1x / 0.5x / 2x click
  subdivisions"; "N clicks before playback starts" — `_work/moises-public.md:105-108`, sources:
  https://help.moises.ai/hc/en-us/articles/6582170661916-How-do-I-use-the-metronome ,
  https://help.moises.ai/hc/en-us/articles/6580752102044-How-do-I-set-up-the-count-in
- **Confidence:** DOCUMENTED.

### B-13 — Meter / time signature
- **Input:** a 3/4 song.
- **Expected:** bar lines every 3 beats; the grid shows 3 cells per bar; count-in is one 3-beat bar.
- **Observed:** "synced with bars and beats" (Grid article) — but **no article states that Moises
  detects or displays a time signature**. `_work/moises-public.md:92-93` records "chords, root key,
  time signature, tempo" for Studio only, and "no separate beat-marker editor documented" for the
  consumer app.
- **Confidence:** **UNKNOWN for the consumer app.** Hypothesis: the consumer player assumes 4/4
  unless the analysis says otherwise; Studio exposes a time signature.
- **Why it matters:** our only reference track is a jazz waltz stored as 4/4. If Moises gets this
  right on the same song, it is a visible parity gap.

### B-14 — Playback highlighting, scroll and look-ahead
- **Input:** play a long song with the chord sheet open.
- **Expected:** the current chord/beat is highlighted; the chart scrolls to keep the current position
  visible; the next chord is visible before it sounds.
- **Observed:** active beat cell is "the strongest state in the practice surface"
  (`10-MOISES-UI-CRAFT.md:150-151`, OBSERVED). Auto-scroll behaviour is **not** recorded in our notes
  and not described in any help article.
- **Confidence:** OBSERVED (highlight) / **UNKNOWN** (scroll, look-ahead distance).
- **Hypothesis:** the sheet auto-scrolls by bar and keeps ~1 bar of look-ahead, because the observed
  layout is a bar-grid rather than a chip list.

### B-15 — Sections / arrangement and the chord lanes
- **Input:** open a song with sections detected.
- **Expected:** section labels and boundaries are shown in a lane and in the sheet; chords are grouped
  by section.
- **Observed:** "Integrate chords, lyrics, and sections"; annotation lanes for Chords/Sections/Lyrics
  (`10-MOISES-UI-CRAFT.md:137`, OBSERVED). Public table: "Chord, lyric and arrangement markers; move
  whole sections" (Studio) — `_work/moises-public.md:66`.
- **Confidence:** DOCUMENTED + OBSERVED.

### B-16 — Stems: does muting/soloing change the chord chart?
- **Input:** mute the guitar stem, then the vocals, then solo the bass.
- **Expected (if chords are stem-independent):** identical chart. **Expected (if chords are computed
  from a harmonic stem):** unchanged too — the chart is analysed once, not live.
- **Observed:** **nothing public.** No help article, no marketing copy, no note in our own UI pass
  describes chords reacting to mute/solo. The public feature table lists chords and stem muting as
  independent features (`_work/moises-public.md:82`, `:103-108`).
- **Confidence:** **UNKNOWN.** Hypothesis: the chart is computed once at upload from the full mix (or
  from an internal harmonic reduction) and never recomputed on mute/solo; mute/solo only changes what
  you hear. This is also the only design that is cheap enough for a real-time app.
- **Testable if we ever get access:** mute all stems except drums → chart must not change.

### B-17 — Chord editing / correction
- **Input:** tap/click a chord in the chart and type a new one.
- **Expected (if supported):** the symbol is replaced and persists with the project.
- **Status:** **superseded by B-24** (second pass). Marketing copy confirms manual correction in the
  player — "edit any chord yourself" — so the earlier "no help article documents it / probably
  unsupported" reading was wrong. The *gesture* and undo behaviour remain UNKNOWN.

### B-18 — Export
- **Input:** Export → Chord Chart.
- **Expected:** a downloadable chord chart in some document format.
- **Observed (direct):** "Export dialog has Mix/Tracks/Chord Chart, MP3/WAV/FLAC/M4A/OGG,
  44.1/48 kHz, metronome/count-in" — `docs/plans/moises-parity/08-EVIDENCE-LOG.md:151` (OBSERVED).
- **Confidence:** OBSERVED (the tab exists).
- **Resolved by B-22** (second pass): the formats are web link, iReal Pro and MusicXML. The older
  in-repo note "no PDF/chart export" (`_work/moises-public.md:360`) predates the launch and is
  superseded; **PDF is still undocumented**. Read B-22, not this paragraph, for the format list.

### B-19 — Free-tier gating
- **Input:** free account, song longer than 1 minute.
- **Expected:** chords visible for 0:00–1:00 only; paid unlocks the rest.
- **Observed:** "The AI-Chord Detection is unlimited for Premium and Pro subscribers. For free
  accounts, it is limited to the song's first minute." (Chord Detection article); also
  `_work/moises-public.md:82,259`.
- **Confidence:** DOCUMENTED.
- **Note for us:** do **not** copy this cap (our AGENTS.md already forbids importing Moises quota
  behaviour).

### B-20 — Accuracy claims
- **Input:** n/a.
- **Expected:** n/a.
- **Observed marketing copy:** "The best chord detection in the market", "deciphers music with
  unmatched precision", "swiftly detected and displayed … with remarkable accuracy"
  — https://moises.ai/features/guitar-chord-finder/
- **Confidence:** MARKETING, not measured. No published WCSR/majmin numbers, no benchmark, no
  dataset. **Do not treat as a target.**

---

## 1.1 Behaviours verified on the second pass (2026-10-25)

These were fetched directly after the first catalogue was written. Two of them change the
architecture inference, so they are listed separately rather than merged above.

### B-21 — One timeline, four chord classes (the API tells us the real data model)
- **Input:** submit audio to the public Chords module.
- **Expected output:** `key` (string, e.g. `C Major`, `A minor`) and `chordMap`, a timeline where
  **each annotation carries start, end and multiple chord classes** — "Complex Jazz, Simple Jazz,
  Complex Pop, and Simple Pop" — plus bass detection.
- **Observed:** "Timeline of Chord annotations extracted from the input audio file. Each annotation
  specifies the chord's start time, end time, **and multiple Chord classes**."
  — https://developer.moises.ai/modules/transcription/chords/
- **Confidence:** DOCUMENTED.
- **Why this matters more than any other row:** the difficulty levels are not three detections and
  not a post-hoc "strip the 7ths" filter. The *annotation object itself* is poly-label: one time
  span, several simultaneous vocabularies. That is a data-model decision we can copy without
  copying any model. It also explains how "easy / medium / advanced" can switch instantly mid-play.

### B-22 — Chord chart export: link, iReal Pro, MusicXML
- **Input:** export a chord chart from a Studio project.
- **Expected output:** web link, iReal Pro file, or MusicXML file; the chart is chords-over-lyrics,
  grouped by section, with key, tempo and time signature in the header; the link is *live* —
  recipients transpose to their own key and the owner can edit the sheet on the web page.
- **Observed:** "export your detected chords into a clean chord sheet — chords aligned over the
  lyrics, organized by song section, with key, tempo, and time signature up top. Export it … as a
  web link, or as an iReal Pro or MusicXML file"; "Your bandmates open the chart in their browser
  and transpose it to their own key — no re-export, no new file."
  — https://moises.ai/features/chord-finder/
- **Confidence:** DOCUMENTED.
- **Consequence:** this **retires U7** (format was unknown) and **contradicts**
  `_work/moises-public.md:360` ("no PDF/chart export"), which was written from public pages before
  this launch. PDF is still undocumented — do not assume it.

### B-23 — The chart is a document, not a chip row
- **Expected:** the exportable artefact is lyrics-first with chords above the words, section headers,
  and a metadata header (key / tempo / time signature). The in-app strip is a *view* of that
  document.
- **Observed:** same source as B-22 ("chords aligned over the lyrics, organized by song section").
- **Confidence:** DOCUMENTED.
- **Consequence:** a chord-chip strip cannot ever be "parity". The document model has to exist
  first; the strip is one renderer of it.

### B-24 — In-player chord correction exists
- **Expected:** any chord in the player can be replaced by hand and the correction sticks for that
  song ("moving forward").
- **Observed:** "…or edit any chord yourself" and "you also have the option to manually edit chords
  so they appear correctly moving forward" — https://moises.ai/features/chord-finder/
  Plus the sync claim: "so does every chord you've detected"
  (same page, "Your chords on every device").
- **Confidence:** DOCUMENTED (existence) / UNKNOWN (gesture, undo, whether edits survive
  re-analysis or transposition).
- **Consequence:** **retires the old B-17 UNKNOWN.** Editing is a real product feature, and it
  implies server-side storage of per-song overrides. We have desktop chip editing in memory only.

### B-25 — Diagrams: real fingerings, every chord tone listed
- **Observed:** "Chord diagrams show real fingerings, adjusted for your capo position, **with every
  note in the chord listed**." — https://moises.ai/features/chord-finder/
- **Confidence:** DOCUMENTED / MARKETING (no diagram inspected).
- **Conflict:** the same page's FAQ says shapes "will" arrive "in Moises Play" (future tense), while
  the body copy and the 2.0.x UI pass both show them today. Treat present-tense as current, FAQ as
  stale copy.
- **Consequence:** chord-tone listing is table stakes for a beginner-facing chart, and it is cheap
  for us — we already know the pitch classes; we just never show them.

### B-26 — Free-tier limits, as documented
- **Observed:** chords "for the first minute of each song"; transpose "limited to 2 semitones";
  count-in "up to 4 clicks" free vs 16 paid; metronome limited to the first minute.
  — chord-finder FAQ; Key help article; Count-in help article.
- **Confidence:** DOCUMENTED, but contradicted by App Store copy claiming free chord detection and
  click track without a cap. **Record the conflict; do not average it.**
- **Note for us:** we copy none of these caps (`AGENTS.md` already forbids importing Moises quotas).

### B-27 — Sections: auto-detected, downbeat-aligned, default names, Premium rename
- **Observed:** "automatically detects and isolates different song sections, such as Intros, Verses,
  Choruses, and Bridges", "downbeat precision"; default names "intro, chorus, verse"; "Editing names
  is only available for Premium users."
  — https://moises.ai/features/song-parts/ ,
  https://help.moises.ai/hc/en-us/articles/10138829000988-How-do-I-use-Sections
- **Confidence:** DOCUMENTED.
- **Consequence:** section boundaries are claimed to snap to downbeats. If our meter is wrong on a
  waltz (H10), our section boundaries inherit that error.

---

## 2. What the catalogue implies for our implementation

| Moises behaviour | Our current state | Gap |
|---|---|---|
| Chord + diagram in sync | symbol + diagram, 10 Hz, no scroll | **follow/scroll missing** |
| Bar mode | chip strip, no bar cells | layout gap |
| Grid mode with active beat cell | none | **biggest visual gap** |
| **One timeline, several label classes** | one flat vocabulary, one symbol per event | **data-model gap — blocks easy/medium/advanced** |
| easy / medium / advanced | one vocabulary, no levels | display gap (needs B-21 model first) |
| Capo keeps key | implemented (`capoDiagramSymbol`) | parity ✅ |
| Notation sharps/flats | desktop only (`spelling`) | web parity gap |
| Key display | shown, with confidence | parity ✅ (we show more) |
| Tempo curve follows song | metronome has a curve; chords flatten it to beats | partial |
| 3/4 support | meter defaults to 4 | **bug** |
| **Chord chart as a document** (lyrics over chords, sectioned, header) | none — strip only | **gap** |
| **Chart export** (link / iReal Pro / MusicXML) | none | gap; MusicXML is the cheap first step |
| **Chord editing** | desktop chip input (in-memory only) | partial, not persisted |
| **Per-song overrides synced across devices** | none | gap (needs storage we do not have) |
| Chord tones listed per chord | quality is in the symbol only | cheap win |

---

## 3. UNKNOWN list (each with a hypothesis, clearly labelled)

| # | Unknown | Status after the second pass | Hypothesis (not fact) | How we could resolve it legitimately |
|---|---|---|---|---|
| U1 | Exact chord vocabulary per difficulty level | **partly resolved** — API names 4 classes (Complex Jazz / Simple Jazz / Complex Pop / Simple Pop) but not their symbol sets | simple pop ≈ triads + sus/add9; complex pop adds 7ths, slash; simple jazz = 7ths with root-position only; complex jazz adds 9/11/13, alterations, inversions | screen-record a jazz standard and a pop song, transcribe symbols from all three levels |
| U2 | Whether slash chords / inversions are ever shown | open — API advertises **bass detection**, which is the prerequisite for slash chords | shown in complex classes only | same capture, pick a song with obvious bass inversions |
| U3 | Chord update latency | open | ≤1 video frame at 60 Hz | high-speed screen capture against a click track |
| U4 | Whether the chart auto-scrolls and with what look-ahead | open | scrolls by bar, ~1 bar look-ahead | same capture, long song |
| U5 | Whether chords are computed from the mix or a stem | open; marketing says "separate … first, resulting in cleaner … detection" which describes a *user workflow*, not a per-stem detector | computed once from the full mix; mute/solo never recomputes | mute all stems except drums → chart must not change |
| U6 | Time-signature handling | **revised** — a time signature appears in the chart header and in Studio detection, so the product models it; whether the *player* detects 3/4 is still open | detected per song, displayed, not user-editable outside Studio | run a known 3/4 song and count grid cells per bar |
| U7 | Chord-chart export format | **resolved** — web link, iReal Pro, MusicXML (B-22). PDF still undocumented | — | — |
| U8 | Whether key display updates after transposition | open | displayed key is the sounding key and transposes with the audio | transpose +12 and read the key chip |
| U9 | Whether chord edits persist across devices | **revised** — marketing says detected chords sync across devices; per-song *edits* still unstated | edits are server-side per song and sync | edit on web, open on mobile |
| U10 | No-chord / silence handling | open | last chord held rather than "N" | observe an intro with no harmony |
| U11 | Whether "advanced" re-detects or re-voices | **strongly narrowed** by B-21: multiple classes ship in *one* annotation, so it is one pass | re-render from one poly-label timeline | compare easy vs advanced timing; identical boundaries ⇒ one pass |
| U12 | Free transpose cap: 2 semitones vs "unlimited" | **conflict, unresolved** — Key help says 2 semitones; a release note says pitch shifting is free for everyone | the release note predates or postdates a pricing change | log in to a free account and press + three times |
| U13 | Whether chord diagrams can be non-guitar (piano/uke) | open | guitar only | inspect the level/diagram control |

**Rule for this project:** none of U1–U11 may be quoted as fact in a design review. They are
hypotheses to test, not requirements copied from a competitor.

---

## 4. Sources actually fetched for this document

| URL | What it established |
|---|---|
| https://help.moises.ai/hc/en-us/articles/6569274648220-How-do-I-use-Chord-Detection | real-time chords, easy/medium/advanced, bar mode, grid mode, notation, capo, free 1-minute cap |
| https://help.moises.ai/hc/en-us/articles/9570133423772-How-to-use-the-new-Chords-view-Grid-Mode | grid mode, "synced with bars and beats", chords+lyrics+sections |
| https://moises.ai/features/guitar-capo-mode/ | capo shapes change, key does not |
| https://moises.ai/features/guitar-chord-finder/ | 3 difficulty levels, real-time key reaction, diagrams on web/desktop, marketing accuracy claims |
| https://help.moises.ai/hc/en-us/articles/6582517238044-How-do-I-use-the-Key-Detection-with-the-Pitch-Changer | key detection display (via `_work/moises-public.md:81`) |
| https://help.moises.ai/hc/en-us/articles/6582170661916-How-do-I-use-the-metronome | smart metronome (via `_work/moises-public.md:105`) |
| https://help.moises.ai/hc/en-us/articles/6580752102044-How-do-I-set-up-the-count-in | count-in (via `_work/moises-public.md:108`) |
| https://help.moises.ai/hc/en-us/articles/6582847813148-How-do-I-change-the-song-s-tempo | tempo curve + click follows it (via `_work/moises-public.md:70`) |
| https://moises.ai/features/bpm-finder/ | BPM detection (via `_work/moises-public.md:87`) |
| https://developer.moises.ai/modules/transcription/chords/ | **`key` + `chordMap` with multiple chord classes (Complex Jazz / Simple Jazz / Complex Pop / Simple Pop) and bass detection** |
| https://moises.ai/features/chord-finder/ | chart export (link / iReal Pro / MusicXML), lyrics-aligned sectioned chart, time signature in header, per-note listing, in-player chord editing, cross-device sync, free 1-minute cap |
| https://moises.ai/features/song-parts/ | downbeat-aligned auto sections, default section names |

In-repo observation records (no external fetch):
`docs/plans/moises-parity/10-MOISES-UI-CRAFT.md:135-190` (measured 2.0.x player geometry and
interaction), `docs/plans/moises-parity/08-EVIDENCE-LOG.md:149-152` (export dialog, player surface),
`docs/plans/moises-parity/_work/moises-public.md:81-108,239-259,350-392` (public feature + plan
matrix built from the Zendesk API on 2026-10-19).
