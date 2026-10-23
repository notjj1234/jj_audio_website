# Moises AI — public feature surface (as of 2026-10-19)

Competitive research snapshot. Everything below is from public sources; no accounts were used, so
nothing behind login (in-app pricing table, Studio plan limits) is verified here.

**Method.** Official marketing site + its sitemap (422 English URLs), the Zendesk help center
(112 articles pulled via the public `/api/v2/help_center` endpoint, so wording is verbatim source,
not search snippets), App Store / Google Play listings, and the official blog. Prices come from the
US App Store in-app-purchase list (the web pricing table at `studio.moises.ai/pricing` is
login-gated and renders nothing to an unauthenticated fetch).

**Confidence.** `high` = stated on an official page/help article. `medium` = marketing claim with no
documented limit, or one source only. `low` = inferred, stale, or contradicted elsewhere.

**Recurring platform shorthand.** W = web app · D = desktop app (macOS/Windows) · M = mobile
(iOS/Android) · T = iPad · TV = Apple TV / Android TV · DAW = AU/VST3/AAX plugin.

---

## 1. Stem separation

| Category | Feature | What it does | Platforms | Plan/tier or limit | Evidence URL | Conf |
|---|---|---|---|---|---|---|
| Separation | 2-stem preset | Vocals + instrumental | all | Free | https://help.moises.ai/hc/en-us/articles/29530482524316-Which-instruments-can-be-separated-on-the-Free-plan | high |
| Separation | 4-stem preset | Vocals, drums, bass, other | all | Free | https://help.moises.ai/hc/en-us/articles/29530482524316-Which-instruments-can-be-separated-on-the-Free-plan | high |
| Separation | Custom instrument picks | Choose which instruments to isolate, rest collapses into "Others" | W D M T | Premium/Pro; up to 23 targets offered (20 music + 3 multimedia) | https://help.moises.ai/hc/en-us/articles/19247459645724-How-do-I-separate-my-tracks-using-the-Custom-Upload-on-the-Mobile-App | high |
| Separation | Premium stem cap | Per-upload selection ceiling | W D M | Premium: 6 tracks incl. Others | https://help.moises.ai/hc/en-us/articles/19247459645724-How-do-I-separate-my-tracks-using-the-Custom-Upload-on-the-Mobile-App | high |
| Separation | Pro stem cap | Unlimited selection + Hi-Fi | W D M | Pro | https://help.moises.ai/hc/en-us/articles/19247459645724-How-do-I-separate-my-tracks-using-the-Custom-Upload-on-the-Mobile-App | high |
| Separation | 27 stem types | Full catalogue down to single snare / backing vocal | W D M | Pro (top tier) | https://moises.ai/features/stem-separation/ | high |
| Separation | Vocal subdivision | Combined vocals; lead + backing; male + female | W D M | Premium (lead/backing), Pro (male/female, web-first) | https://help.moises.ai/hc/en-us/articles/360010972019-Which-instruments-can-be-separated-on-the-Pro-plan | high |
| Separation | Guitar subdivision | Combined guitars; acoustic + electric; lead/rhythm (solo) | W D M | Premium/Pro | https://help.moises.ai/hc/en-us/articles/29530520103324-Which-instruments-can-be-separated-on-the-Premium-plan | high |
| Separation | Drum subdivision | Kit; kick, snare, toms, hi-hat, cymbals, other | W D M | Pro | https://help.moises.ai/hc/en-us/articles/360010972019-Which-instruments-can-be-separated-on-the-Pro-plan | high |
| Separation | Winds subdivision | Wind, woodwind, brass, reeds | W D M | Pro (brass/reeds/woodwind web-first) | https://help.moises.ai/hc/en-us/articles/360010972019-Which-instruments-can-be-separated-on-the-Pro-plan | high |
| Separation | Keys / strings | Piano, grand piano, keys, strings, percussion | W D M | Premium+ (grand piano web-first) | https://help.moises.ai/hc/en-us/articles/29530520103324-Which-instruments-can-be-separated-on-the-Premium-plan | high |
| Separation | Multimedia stems | Dialogue / soundtrack / effects split for film, TV, podcast | W D | Pro | https://moises.ai/features/multimedia-tracks/ | high |
| Separation | Automatic separation | AI picks up to 7 top-level parts without user choosing | W D | Premium/Pro (implied) | https://moises.ai/features/stem-separation/ | medium |
| Separation | Standard models | Faster separation, lower fidelity | all | Free/Premium default | https://moises.ai/features/stem-separation/ | high |
| Separation | Hi-Fi models | Larger models, better isolation, 48 kHz/24-bit | W D M | Pro only | https://moises.ai/features/hi-fi-stem-separation/ | high |
| Separation | Re-separate without re-upload | Change separation style on an existing song | W D M | Paid; Free consumes a monthly credit | https://help.moises.ai/hc/en-us/articles/6564889454236-How-can-I-change-my-song-s-track-separation-without-re-uploading | high |
| Separation | Bulk upload | Same separation settings applied to many files at once | W D | 20 files; Free limited by monthly credits | https://help.moises.ai/hc/en-us/articles/17950941743004-How-do-I-upload-multiple-files-for-track-separation | high |
| Separation | In-project stem splitting | Split an already-separated stem (e.g. drums → kick/snare) into a folder | W D | AI Studio / Studio | https://help.moises.ai/hc/en-us/articles/21745204066076-Moises-AI-Studio-Your-All-in-One-AI-Music-Creation-Platform | high |
| Separation | Vocal remover / instrumental maker | Marketing entry points onto the same separation engine | W D M | Free tier works | https://moises.ai/features/vocal-remover/ · https://moises.ai/features/instrumental-maker/ | high |
| Separation | DAW-plugin separation | Separation inside the DAW, 7 named stems | DAW | Pro only; not real-time, needs internet | https://moises.ai/features/stems-vst-plugin/ | high |
| Separation | Song tuning read/fix | Corrects detected tuning (e.g. 432 Hz material) | W D only | Premium/Pro | https://help.moises.ai/hc/en-us/articles/15757281113244-How-can-I-change-the-song-s-tuning | high |

Notes: the Pro help article and the marketing list disagree at the margins (26 named targets vs "27 stems";
"Grand Piano web only" vs "27 everywhere"). Treat 27 as a marketing count, not a stable API contract.
There is **no** user-trainable separation model, no stem *upload* to swap a part, and no documented
"demix strength / bleed" control anywhere.

---

## 2. Audio editing

| Category | Feature | What it does | Platforms | Plan/tier or limit | Evidence URL | Conf |
|---|---|---|---|---|---|---|
| Mixer | Per-stem volume | Slider per stem, defaults to 75% on load | all | all plans | https://help.moises.ai/hc/en-us/articles/8472791352860-Welcome-to-Moises-Here-are-some-pointers-to-start-Web-Desktop | high |
| Mixer | Mute / solo | Per-stem M and S buttons | all | all plans | https://help.moises.ai/hc/en-us/articles/8472791352860-Welcome-to-Moises-Here-are-some-pointers-to-start-Web-Desktop | high |
| Mixer | Pan | Not exposed in the legacy player; pan exists only in AI-mix (per-track presence/pan/reverb) | W D (AI Studio) | Pro (AI mix) | https://help.moises.ai/hc/en-us/articles/21745204066076-Moises-AI-Studio-Your-All-in-One-AI-Music-Creation-Platform | medium |
| Mixer | Groups / buses | No group or bus routing documented in the consumer player | — | — | (absence of evidence) | low |
| Mixer | EQ / compression / FX | 18 built-in effects on a channel strip in Studio; none in the legacy player | W D | Studio | https://moises.ai/products/moises-studio/ | medium |
| Editing | Trim | Cut the song down; destructive length change | M T | all plans | https://help.moises.ai/hc/en-us/articles/9268398921116-Difference-between-Trim-and-Select-Loop | high |
| Editing | Select & Loop | Choose a region and repeat it | W D | all plans | https://help.moises.ai/hc/en-us/articles/9268398921116-Difference-between-Trim-and-Select-Loop | high |
| Editing | Timeline split / trim / copy / reverse / loop / fade | Non-destructive clip editing in Studio | W D | Studio | https://moises.ai/features/editing-track-arrangement | high |
| Editing | Automation | Per-track automation lanes | W D | Studio | https://moises.ai/products/moises-studio/ | high |
| Editing | Markers / arrangement | Chord, lyric and arrangement markers; move whole sections | W D | Studio | https://moises.ai/products/moises-studio/ | high |
| Editing | Take lanes + comping | Multiple passes per track, comp the keeper | W D | Studio | https://moises.ai/products/moises-studio/ | high |
| Editing | Versioning / undo | Version history, undo/redo, non-destructive edits | W D | Studio | https://moises.ai/features/real-time-collaboration | high |
| Editing | Stem editor | Silence / cut / crop a section of one stem, replace or save-as-copy | W D | AI Studio | https://help.moises.ai/hc/en-us/articles/21745204066076-Moises-AI-Studio-Your-All-in-One-AI-Music-Creation-Platform | high |
| Editing | Tempo automation | Per-song BPM change with click that follows the curve | all | Premium/Pro unlimited | https://help.moises.ai/hc/en-us/articles/6582847813148-How-do-I-change-the-song-s-tempo | high |
| Processing | Noise reduction / denoise | No user-facing denoise or de-reverb tool is documented (separation is marketed as leaving "no cleanup pass") | — | — | https://moises.ai/features/stem-separation/ | low |
| Processing | Amp modeler | Re-amp a guitar track by prompt, reference, or capture | W D | Studio | https://moises.ai/features/amp-modeler | high |
| Processing | Instrument hosting | 200+ built-in instrument presets; own VST3s on desktop | W D (VST3 desktop only) | Studio | https://moises.ai/products/moises-studio/ | medium |

---

## 3. Analysis

| Category | Feature | What it does | Platforms | Plan/tier or limit | Evidence URL | Conf |
|---|---|---|---|---|---|---|
| Analysis | Key detection | Detects song key and displays it | all | Free unlimited (only pitch *change* is capped) | https://help.moises.ai/hc/en-us/articles/6582517238044-How-do-I-use-the-Key-Detection-with-the-Pitch-Changer | high |
| Analysis | Chord detection | Real-time chord names + diagrams, synced to playback | all | Free: first minute; paid: unlimited | https://help.moises.ai/hc/en-us/articles/6569274648220-How-do-I-use-Chord-Detection | high |
| Analysis | Chord difficulty | Easy / medium / advanced voicings | W D; M via song settings | Premium/Pro | https://help.moises.ai/hc/en-us/articles/6569274648220-How-do-I-use-Chord-Detection | high |
| Analysis | Chord grid mode | Bar/grid layout of the whole song | M (grid), W D (bar) | all plans | https://help.moises.ai/hc/en-us/articles/9570133423772-How-to-use-the-new-Chords-view-Grid-Mode | high |
| Analysis | Capo mode | Suggests capo fret + shapes while keeping original key | M; chord settings | all plans | https://moises.ai/features/guitar-capo-mode/ | high |
| Analysis | Notation switch | Sharps/flats notation preference | M | all plans | https://help.moises.ai/hc/en-us/articles/6569274648220-How-do-I-use-Chord-Detection | medium |
| Analysis | BPM / tempo detection | Detects tempo, feeds speed changer and metronome | all | all plans | https://moises.ai/features/bpm-finder/ | high |
| Analysis | Manual BPM correction | User can override a wrong detected BPM | all | all plans | https://help.moises.ai/hc/en-us/articles/16697903875484-The-BPM-is-wrong-what-should-I-do | high |
| Analysis | Section detection | AI labels intro/verse/chorus/bridge and loops them | all | all plans; renaming is Premium+ | https://help.moises.ai/hc/en-us/articles/10138829000988-How-do-I-use-Sections | high |
| Analysis | Lyrics transcription | Word-by-word synced lyrics, editable text | all + TV | Free: first minute; paid: unlimited; 30+ languages | https://moises.ai/features/ai-audio-transcription/ | high |
| Analysis | Lyrics language pick | Choose source language before transcribing | all | all plans | https://moises.ai/features/ai-audio-transcription/ | high |
| Analysis | Chord/key detection inside Studio | Detects chords, root key, time signature, tempo for the project | W D | Studio | https://help.moises.ai/hc/en-us/articles/21745204066076-Moises-AI-Studio-Your-All-in-One-AI-Music-Creation-Platform | high |
| Analysis | Beat/bar grid | Bars and beats shown for chord grid; no separate beat-marker editor documented | M W D | all plans | https://help.moises.ai/hc/en-us/articles/9570133423772-How-to-use-the-new-Chords-view-Grid-Mode | medium |
| Analysis | Vocal pitch / melody detection | No public pitch-curve or melody-extraction view | — | — | (absence of evidence) | low |
| Analysis | Tab / fretboard diagrams | Chord diagrams only; no guitar tablature generation or export | — | — | https://moises.ai/features/guitar-chord-finder/ | low |

---

## 4. Practice

| Category | Feature | What it does | Platforms | Plan/tier or limit | Evidence URL | Conf |
|---|---|---|---|---|---|---|
| Practice | Speed change | Time-stretch playback without pitch change | all | Free ±10% (one article) / 20% (another); paid unlimited | https://help.moises.ai/hc/en-us/articles/6582847813148-How-do-I-change-the-song-s-tempo | high |
| Practice | Pitch shift | Transpose in semitone steps, real time | all | Free ±2 semitones; paid unlimited | https://help.moises.ai/hc/en-us/articles/6582517238044-How-do-I-use-the-Key-Detection-with-the-Pitch-Changer | high |
| Practice | Smart metronome | Generates a click that follows the song's tempo curve | all | Free: first minute; paid unlimited | https://help.moises.ai/hc/en-us/articles/6582170661916-How-do-I-use-the-metronome | high |
| Practice | Metronome modes | 1x / 0.5x / 2x click subdivisions | W D M | Premium/Pro | https://help.moises.ai/hc/en-us/articles/6582170661916-How-do-I-use-the-metronome | high |
| Practice | Metronome export | Bounce the click as its own track | all | paid | https://help.moises.ai/hc/en-us/articles/360017813099-How-do-I-export-the-Metronome | high |
| Practice | Count-in | N clicks before playback starts | all | Free 4; paid up to 16 | https://help.moises.ai/hc/en-us/articles/6580752102044-How-do-I-set-up-the-count-in | high |
| Practice | Section looping | Loop one or several detected sections | all | all plans | https://help.moises.ai/hc/en-us/articles/10138829000988-How-do-I-use-Sections | high |
| Practice | Select & loop | Arbitrary region loop, not just detected sections | W D | all plans | https://help.moises.ai/hc/en-us/articles/9268398921116-Difference-between-Trim-and-Select-Loop | high |
| Practice | Play-along mixer | Mute your instrument, solo the part you learn | all | all plans | https://moises.ai/features/stem-separation/ | high |
| Practice | Setlists | Group songs for practice, rehearsal, lessons, gigs | all + TV | all plans | https://moises.ai/features/band-collaborative-setlist/ | high |
| Practice | Collaborative setlist | Shared setlist link, members adjust their own mix | W iOS Android | up to 7 people incl. owner | https://moises.ai/features/band-collaborative-setlist/ | high |
| Practice | Queue / play-all | Auto-advance through ready songs | M | all plans | https://help.moises.ai/hc/en-us/articles/6311848422556-How-to-get-my-songs-to-play-in-a-queue-Mobile-only | high |
| Practice | Video recording | Record video over a library track or from scratch, auto-synced | M only | all plans (Free/Premium/Pro) | https://help.moises.ai/hc/en-us/articles/21169867017116-Video-recording-on-Mobile | high |
| Practice | Smart sync correction | Aligns performance to backing track; manual sync nudge | M | all plans | https://help.moises.ai/hc/en-us/articles/21169867017116-Video-recording-on-Mobile | high |
| Practice | Voice/instrument recorder | One-tap idea capture, then run the usual tools on it | M W D | all plans | https://moises.ai/features/voice-recorder/ | high |
| Practice | Curated content | Artist/educator setlists (Berklee, Eloy Casagrande, guitar exercises, "Moises Collection") | all | all plans | https://moises.ai/blog/latest/improvements-latest-releases | medium |
| Practice | TV practice mode | Lyrics + chords + setlists on the big screen | TV | all plans | https://help.moises.ai/hc/en-us/articles/8581469810844-Where-can-I-use-Moises | high |

Conflict: free speed limit is stated as both "20% speed change" (tempo article) and "up to -10/+10"
(welcome article). Both are current help-center articles; the stricter number is the safer assumption.

---

## 5. AI studio / generation

| Category | Feature | What it does | Platforms | Plan/tier or limit | Evidence URL | Conf |
|---|---|---|---|---|---|---|
| Studio | Moises Studio | Browser DAW: record, arrange, edit, separate, generate, collaborate | W D | Free to start; paid tiers vary (limits not public) | https://moises.ai/products/moises-studio/ | high |
| Generation | Stem generation | Generates drums, bass, guitar, keys, strings, "others" to fit the project | W D M | 1 credit = 30 s; Free 10, Premium 200, Pro unlimited credits/mo | https://moises.ai/features/stem-generation/ | high |
| Generation | Presets | 55 genre presets across 5 instrument types | W D | paid credits | https://moises.ai/products/moises-studio/ | medium |
| Generation | Custom prompt | Text description of the part to generate | W D | paid credits | https://moises.ai/features/stem-generation/ | high |
| Generation | Reference audio | Match style from an uploaded reference clip | W D | paid credits | https://moises.ai/features/stem-generation/ | high |
| Generation | Creative-control dial | How tightly the part follows the existing track | W D | paid credits | https://moises.ai/features/stem-generation/ | high |
| Generation | Section regenerate | Re-roll just a selected region, or fill a gap/transition | W D | paid credits | https://help.moises.ai/hc/en-us/articles/21745204066076-Moises-AI-Studio-Your-All-in-One-AI-Music-Creation-Platform | high |
| Generation | Audio **or MIDI** return | Generated parts can come back as audio or MIDI | W D | paid credits | https://moises.ai/products/moises-studio/ | medium |
| Generation | Sample generation | Text-described one-shot or loop, in project key/tempo, MIDI alongside | W D | paid credits | https://moises.ai/products/moises-studio/ | medium |
| Generation | Chord-guided generation | Project chord lane conditions the generated harmony | W D | Pro (chords in AI Studio) | https://help.moises.ai/hc/en-us/articles/21745204066076-Moises-AI-Studio-Your-All-in-One-AI-Music-Creation-Platform | high |
| Voice | Voice conversion | Recasts vocal timbre, keeps pitch/timing/phrasing | W D | 40+ voices; Free/Premium can process, **export is Pro** | https://help.moises.ai/hc/en-us/articles/14531895291932-What-s-new-on-Voice-Studio | high |
| Voice | Voice matching | Ranks which voice models suit an uploaded take | W D | Pro | https://help.moises.ai/hc/en-us/articles/15232485539228-How-do-I-use-Voice-Studio | high |
| Voice | Custom voice model | Train a private model on your own voice in minutes | W D | Studio; rights attestation required | https://moises.ai/products/moises-studio/ | medium |
| Mixing | Auto-mix | AI mix across 20 genre styles | W D | Studio | https://moises.ai/products/moises-studio/ | medium |
| Mixing | AI mix controls | Per-track presence, pan, reverb before bouncing | W D | AI Studio | https://help.moises.ai/hc/en-us/articles/21745204066076-Moises-AI-Studio-Your-All-in-One-AI-Music-Creation-Platform | high |
| Mixing | AI mastering | Auto / Advanced / Reference modes | W D | process on all plans; **export Pro only** | https://help.moises.ai/hc/en-us/articles/360013615140-What-is-AI-Mastering | high |
| Mixing | Advanced mastering | Target loudness, ceiling, intensity, low/high cut | W D | Pro to export (WAV/FLAC/MP3) | https://help.moises.ai/hc/en-us/articles/15232321661852-How-do-I-use-Advanced-Mastering | high |
| Writing | Lyric writer | Rhyme, mood and syllable-count line suggestions | W D | Free/Premium/Pro; fair-use caps | https://moises.ai/features/lyric-writer/ | high |
| Guitar | Amp modeler | Prompt / reference / captured amp tone on a guitar track | W D | Studio; TONE3000 + .nam imports | https://moises.ai/features/amp-modeler | high |
| Guitar | TONE3000 library | 700k+ community NAM captures and IRs inside the amp effect | W D | Studio | https://moises.ai/blog/latest/tone3000-amp-modeler-moises-studio/ | high |
| Absent | Text-to-song | No full-song text-to-music generator; generation is part-level and conditioned on your audio | — | — | https://help.moises.ai/hc/en-us/articles/21894428062108-Do-s-and-Don-ts-of-AI-Studio-Prompt-Engineering | high |
| Absent | Artist-name prompting | Blocked by ToS and not recognised by models | — | — | https://help.moises.ai/hc/en-us/articles/21894257114396-Can-I-prompt-AI-Studio-with-an-artist-or-song-name-e-g-make-a-beat-like-famous-artist | high |

Naming caution: "AI Studio" (Oct 2025) and "Moises Studio" (Sep 2026) are described with overlapping
feature sets (stem generation, voice conversion, chords, in-browser editing). Treat Studio as the
successor surface, and old help-center "AI Studio" articles as the same engine.

---

## 6. Projects, library, cloud, collaboration

| Category | Feature | What it does | Platforms | Plan/tier or limit | Evidence URL | Conf |
|---|---|---|---|---|---|---|
| Library | Song library | All processed songs in one list, searchable | all + TV | all plans | https://help.moises.ai/hc/en-us/articles/8472791352860-Welcome-to-Moises-Here-are-some-pointers-to-start-Web-Desktop | high |
| Library | Search | Finds songs, including purchased iTunes files on device | M T | all plans | https://help.moises.ai/hc/en-us/articles/8472822785180-Welcome-to-Moises-Here-are-some-pointers-to-start-iPad-App | high |
| Library | Multi-select | Bulk organise songs/setlists | W D M | all plans | https://moises.ai/blog/latest/improvements-latest-releases | medium |
| Library | Setlists | Named collections for gigs/lessons | all | all plans | https://moises.ai/features/band-collaborative-setlist/ | high |
| Library | Folders | No user-facing folder tree documented; "folder" appears only as a UI grouping for split stems | — | — | https://help.moises.ai/hc/en-us/articles/21745204066076-Moises-AI-Studio-Your-All-in-One-AI-Music-Creation-Platform | low |
| Cloud | Cross-device library | Upload once, open on any signed-in device | all | all plans | https://help.moises.ai/hc/en-us/articles/12538853396764-Will-my-changes-show-up-on-all-devices | high |
| Cloud | Edit sync | Key/speed/etc. edits are stored **per device** and do not sync | all | all plans | https://help.moises.ai/hc/en-us/articles/12538853396764-Will-my-changes-show-up-on-all-devices | high |
| Cloud | Delete song | Permanent removal from library and backend, no recovery | all | all plans | https://help.moises.ai/hc/en-us/articles/9324322083996-If-I-delete-a-song-is-it-deleted-from-Moises-database | high |
| Cloud | Storage quota | No published GB/project cap; fair-use processing caps instead | all | see fair use | https://help.moises.ai/hc/en-us/articles/5968943445404-Acceptable-Use-and-Fair-Usage-Policy | high |
| Collab | Studio sessions | Shared live session, one link, no file handoff | W D | Free to join; host plan varies | https://moises.ai/products/moises-studio/ | high |
| Collab | Roles | Admin / Editor / Listener per collaborator | W D | Studio | https://moises.ai/features/real-time-collaboration | high |
| Collab | Live presence | Cursors, quick chat, follow mode, live edits | W D | Studio | https://moises.ai/features/real-time-collaboration | high |
| Collab | Version history | Per-session versioning + undo/redo | W D | Studio | https://moises.ai/features/real-time-collaboration | high |
| Collab | Offline resilience | Keeps working through a disconnect, syncs on reconnect | W D | Studio | https://moises.ai/products/moises-studio/ | medium |
| Collab | Setlist sharing | Private by default; owner flips to collaborative and shares a link; push notifications | W iOS Android | 7 people | https://help.moises.ai/hc/en-us/articles/12731092152476-How-do-I-enhance-my-music-Setlists-through-collaboration | high |

---

## 7. Export

| Category | Feature | What it does | Platforms | Plan/tier or limit | Evidence URL | Conf |
|---|---|---|---|---|---|---|
| Export | Mixdown | Bounce the current mix as one file | all | all plans | https://help.moises.ai/hc/en-us/articles/360013691720-How-do-I-export-my-file | high |
| Export | Stems | Export selected stems or all | all | all plans (Hi-Fi quality gated) | https://help.moises.ai/hc/en-us/articles/360013691720-How-do-I-export-my-file | high |
| Export | Per-stem export | Ellipsis next to a track → export that one | M | all plans | https://help.moises.ai/hc/en-us/articles/360013691720-How-do-I-export-my-file | high |
| Export | Mobile formats | MP3, M4A | M T | all plans | https://help.moises.ai/hc/en-us/articles/360013691720-How-do-I-export-my-file | high |
| Export | Desktop/web formats | MP3, M4A, WAV | W D | WAV = Premium/Pro | https://help.moises.ai/hc/en-us/articles/360013691720-How-do-I-export-my-file | high |
| Export | Extra formats (marketing) | FLAC and OGG also listed for stems | W D | Pro | https://moises.ai/features/stem-separation/ | medium |
| Export | Pro WAV spec | 48 kHz / 24-bit WAV | W D | Pro | https://help.moises.ai/hc/en-us/articles/10523828567196-Reasons-to-Subscribe-to-the-Moises-Pro-Plan | high |
| Export | High-rate claim | "Lossless quality at up to 192 kHz" | W D | unspecified | https://moises.ai/features/stem-separation/ | low |
| Export | Mastering export | Mastered file download | W D | Pro (Premium may export reference track); Free cannot export | https://help.moises.ai/hc/en-us/articles/360013858400-What-is-the-maximum-file-size-for-mastering | high |
| Export | Metronome track | Click bounced as audio | all | paid | https://help.moises.ai/hc/en-us/articles/360017813099-How-do-I-export-the-Metronome | high |
| Export | MIDI | Generated parts as MIDI | W D | Studio | https://moises.ai/products/moises-studio/ | medium |
| Export | DAW project files | DAWproject and Ableton Live Set export | W D | Studio | https://moises.ai/products/moises-studio/ | high |
| Export | Plugin hand-off | Drag separated stems straight into the DAW timeline | DAW | Pro | https://moises.ai/features/stems-vst-plugin/ | high |
| Export | Video | Video is recorded/shared on mobile; no desktop video export documented | M | all plans | https://moises.ai/features/video-recording/ | high |
| Export | Watermark | None documented on any export | — | — | (absence of evidence) | medium |
| Export | PDF / tab | No PDF, chart or tab export | — | — | (absence of evidence) | low |

Conflict: help center consistently says mobile = MP3/M4A and desktop = +WAV; the stem-separation page
adds FLAC and OGG and a 192 kHz ceiling that no help article supports. Take help-center values as the
contract and marketing as aspiration.

---

## 8. Platforms & integrations

| Category | Feature | What it does | Platforms | Plan/tier or limit | Evidence URL | Conf |
|---|---|---|---|---|---|---|
| Platform | Web app | Full studio in the browser, no install | W | all plans | https://moises.ai/products/moises-web-app/ | high |
| Platform | Desktop app | Native macOS/Windows app; adds WAV, mastering, plugins | D | all plans | https://moises.ai/products/moises-desktop-app/ | high |
| Platform | Mobile app | Play-along, metronome, recording, video | iOS Android | all plans | https://moises.ai/products/moises-app/ | high |
| Platform | iPad app | Tablet layout, keyboard shortcuts, trim | T | all plans | https://moises.ai/products/app-for-ipad/ | high |
| Platform | TV apps | Lyrics, chords, setlists on Apple TV / Android TV | TV | all plans | https://help.moises.ai/hc/en-us/articles/8581469810844-Where-can-I-use-Moises | high |
| Platform | visionOS | App Store lists Apple Vision compatibility | Vision | all plans | https://apps.apple.com/us/app/moises-the-musicians-app/id1515796612 | medium |
| Plugin | AU / VST3 / AAX | Stems plugin installed by the desktop app | DAW | Pro | https://help.moises.ai/hc/en-us/articles/11228246270876-How-do-I-set-up-Moises-Stems-on-a-DAW | high |
| Plugin | DAW coverage | Documented setups for Ableton, Logic, Pro Tools, Reaper; marketing adds Studio One/FL | DAW | Pro | https://moises.ai/features/stems-vst-plugin/ | high |
| Plugin | Not real-time | One-shot separation request, internet required | DAW | Pro | https://moises.ai/features/stems-vst-plugin/ | high |
| Integration | Fender Studio Pro | Native Moises separation, backing-track generation, voice conversion in the DAW | Fender Studio Pro 8.1+ | paid Fender users | https://moises.ai/products/integrations/fender-studio-pro/ | high |
| Integration | Universal Audio LUNA | Moises lyric transcription + chord detection inside LUNA, no extra cost | macOS/Windows LUNA | any paid LUNA user | https://moises.ai/products/integrations/universal-audio-luna/ | high |
| Integration | Moises Live | Real-time vocal/instrument control over any system audio | macOS, Windows (Mac listed on product page; help article still says "Mac coming soon") | free with account | https://moises.ai/products/live/ | high |
| Integration | TONE3000 | NAM capture library inside Amp Modeler | W D | Studio | https://moises.ai/blog/latest/tone3000-amp-modeler-moises-studio/ | high |
| Integration | Cloud import | Google Drive / iCloud / Files picker on mobile | M T | all plans | https://help.moises.ai/hc/en-us/articles/360017712459-I-cannot-access-the-files-on-my-Google-Drive | high |
| Integration | URL import | Paste a public URL instead of uploading a file | W D M | all plans | https://moises.ai/features/voice-recorder/ | medium |
| Integration | Streaming links | Spotify/Apple Music URLs rejected (DRM/licensing) | — | — | https://help.moises.ai/hc/en-us/articles/18322457396508-How-do-streaming-services-work-and-why-can-t-we-accept-their-URL-links-on-Moises | high |
| Integration | Dropbox | Not mentioned anywhere; unverified | — | — | — | low |
| API | Public consumer API | None. Business access via Music AI platform/sales | — | B2B contract | https://help.moises.ai/hc/en-us/articles/15320373339676-How-do-I-make-B2B-and-API-purchases | high |
| Plugin | Chrome extension | No current official extension found (legacy product, unlisted) | — | — | — | low |

---

## 9. Account, plans, quotas

| Category | Feature | What it does | Platforms | Plan/tier or limit | Evidence URL | Conf |
|---|---|---|---|---|---|---|
| Plans | Free | Limited monthly processing, core practice tools | all | 5 uploads/mo, 5 min/file, 2- or 4-stem only | https://help.moises.ai/hc/en-us/articles/360010972039-I-m-a-Free-user-and-I-can-t-upload-more-than-5-songs | high |
| Plans | Premium | Unlimited uploads, wider stems, longer files | all | 20 min/file, 6-track custom separation, unlimited metronome/chords/lyrics | https://help.moises.ai/hc/en-us/articles/9410960985628-Reasons-to-subscribe-to-the-Moises-Premium-Plan | high |
| Plans | Pro | Top separation quality + pro exports + plugins | all | 27 stems, Hi-Fi, WAV 48/24, voice export, DAW plugin, priority queue | https://help.moises.ai/hc/en-us/articles/10523828567196-Reasons-to-Subscribe-to-the-Moises-Pro-Plan | high |
| Quota | Uploads reset | Free counter is calendar-month, deleting does not refund | all | 5/mo | https://help.moises.ai/hc/en-us/articles/360010972039-I-m-a-Free-user-and-I-can-t-upload-more-than-5-songs | high |
| Quota | Fair use — processing | Guideline before abnormal-use review | all | ~14 tracks/day, 420/month | https://help.moises.ai/hc/en-us/articles/5968943445404-Acceptable-Use-and-Fair-Usage-Policy | high |
| Quota | Fair use — lyrics | Lyric writer caps | W D | 300 lyrics or 150k words / 30 days | https://help.moises.ai/hc/en-us/articles/5968943445404-Acceptable-Use-and-Fair-Usage-Policy | high |
| Quota | Fair use — voice | Voice Studio caps | W D | 200 tracks or 480 min / 30 days | https://help.moises.ai/hc/en-us/articles/5968943445404-Acceptable-Use-and-Fair-Usage-Policy | high |
| Quota | Fair use — generation | Stem generation caps | W D | 30,000 generated minutes / 30 days | https://help.moises.ai/hc/en-us/articles/5968943445404-Acceptable-Use-and-Fair-Usage-Policy | high |
| Quota | AI credits | Metered generation | W D M | 1 credit = 30 s; Free 10, Premium 200, Pro unlimited; unused expire monthly | https://help.moises.ai/hc/en-us/articles/21960006352796-Moises-AI-Studio-Credits | high |
| Rights | Output ownership | User keeps uploads and outputs, commercial use allowed with rights | all | all plans | https://help.moises.ai/hc/en-us/articles/23877386138140-Who-owns-the-output-and-music-I-create-with-Moises | high |
| Rights | Training opt-out | Uploads are not used to train shared models | all | all plans | https://moises.ai/ | high |
| Billing | Payment rails | Stripe, PayPal, App Store, Play Store, Ebanx | all | — | https://help.moises.ai/hc/en-us/articles/360013884080-What-happens-if-I-cancel-my-subscription | medium |
| Billing | Cancellation effect | Library stays; paid-only separations and edits lock the day after | all | — | https://help.moises.ai/hc/en-us/articles/360013884080-What-happens-if-I-cancel-my-subscription | high |
| Billing | Refunds | Case-by-case eligibility check | all | — | https://help.moises.ai/hc/en-us/articles/12750007338780-How-can-I-check-if-I-m-eligible-for-a-refund | medium |

---

## 10. Pricing snapshot (US App Store IAP, 2026-10-19)

| Tier | Monthly | Annual | Notes |
|---|---|---|---|
| Free | $0 | — | 5 uploads/mo, 5-min files, 2/4-stem, first-minute metronome/chords/lyrics, ±2 semitones, ±10–20% speed, 4-click count-in, no WAV, no mastered export |
| Premium | $5.99 | $39.99 | Unlimited uploads, 20-min files, 6-track custom separation, unlimited analysis/practice tools |
| Pro | $29.99 | not listed in US store | 27 stems, Hi-Fi, 48/24 WAV, voice export, DAW plugin, priority processing, unlimited Studio credits |

Source: https://apps.apple.com/us/app/moises-the-musicians-app/id1515796612 (in-app purchase list).
Web pricing (`https://studio.moises.ai/billing/pricing/`) is login-gated and could not be verified;
web checkout often differs from store pricing after tax/regional pricing. Treat the table as
indicative, not authoritative.

---

## 11. Technical clues

| Clue | Detail | Source |
|---|---|---|
| Model families | "Standard" (fast) and "Hi-Fi" (larger, slower, Pro-only); no public model names/versions | https://moises.ai/features/stem-separation/ |
| Stem count | "27 stem types" marketing vs 23 selectable targets (20 music + 3 multimedia) in the mobile help article | https://help.moises.ai/hc/en-us/articles/19247459645724-How-do-I-separate-my-tracks-using-the-Custom-Upload-on-the-Mobile-App |
| Processing audio spec | 48 kHz / 24-bit for Hi-Fi and Pro WAV export | https://moises.ai/features/hi-fi-stem-separation/ |
| Claimed export ceiling | "up to 192 kHz" (unverified, conflicts with 48 kHz docs) | https://moises.ai/features/stem-separation/ |
| Duration ceilings | Free 5 min; paid 20 min; mastering same; AI Studio 30 s per credit | https://help.moises.ai/hc/en-us/articles/360010855680-What-is-the-maximum-file-length |
| Accepted inputs | Audio: MP3, AAC, AIFC, OGG, WMA, AIFF, FLAC, WAV. Video: MP4, M4V, MOV, MKV, M4R, M4A, FLV, MPEG, WEBM | https://help.moises.ai/hc/en-us/articles/360013289060-Accepted-Play-file-formats |
| Inference model | Cloud-only; no offline processing, plugin needs internet | https://help.moises.ai/hc/en-us/articles/9173509988124-Is-it-possible-to-use-Moises-offline |
| Real-time path | Moises Live processes system audio locally, low-latency ("lag-free" claim), presets Music (vocals/guitars/other) and Speech (vocals/other) | https://moises.ai/products/live/ |
| Live unauthenticated | Slider snapped to 25/50/75/100% until an account is connected (free) | https://help.moises.ai/hc/en-us/articles/20126450906908-Moises-Live |
| Plugin formats | AU, VST3, AAX; installed via desktop app; Pro only; one-shot, not real-time | https://help.moises.ai/hc/en-us/articles/11228246270876-How-do-I-set-up-Moises-Stems-on-a-DAW |
| Voice models | 40+ voices, artist-licensed, trained at ≥48/96 kHz, royalty-free for commercial use, resale prohibited | https://help.moises.ai/hc/en-us/articles/15232485539228-How-do-I-use-Voice-Studio |
| Generation scale | 55 genre presets × 5 instrument types; 200+ instrument presets; 18 channel-strip FX; 20 auto-mix genres | https://moises.ai/products/moises-studio/ |
| Amp capture format | Neural Amp Modeler `.nam` plus TONE3000 library of 700k+ captures/IRs | https://moises.ai/blog/latest/tone3000-amp-modeler-moises-studio/ |
| Project interchange | DAWproject and Ableton Live Set export (Studio) | https://moises.ai/products/moises-studio/ |
| Company scale claim | 2M+ minutes of audio processed daily (Music AI corporate) | https://developer.moises.ai/ |

---

## 12. Recent changes (last ~12 months)

| Date | Change | Source |
|---|---|---|
| 2026-10-01 | TONE3000 library + `.nam` import built into Studio's Amp Modeler | https://moises.ai/blog/latest/tone3000-amp-modeler-moises-studio/ |
| 2026-09-01 | Moises Studio launch: browser/desktop collaborative DAW, real-time sessions, roles, multitrack recording, 27 stems, stem generation, voice conversion, amp modeler, auto-mix | https://moises.ai/blog/latest/introducing-moises-studio |
| 2026-06-09 | Fender Studio Pro 8.1 ships native Moises integration (separation, backing tracks, 40 voices) | https://moises.ai/blog/latest/fender-studio-pro-moises-daw-integration |
| 2026-03-11 | "Moises Design Hub" terms published — press/partner media-asset portal, not a music feature | https://help.moises.ai/hc/en-us/articles/26059680736284-Moises-Design-Hub-Terms |
| 2026 (undated) | Universal Audio LUNA gets Moises lyrics + chord detection free for paid LUNA users | https://moises.ai/products/integrations/universal-audio-luna/ |
| 2025-10-17 | Video Recording (mobile), AI Stem Generation, AI Studio DAW, chords in AI Studio, Voice Conversion | https://moises.ai/blog/latest/improvements-latest-releases |
| 2025-08-26 | Fair-use policy revision: 14/day, 420/mo, lyric/voice/generation caps | https://help.moises.ai/hc/en-us/articles/5968943445404-Acceptable-Use-and-Fair-Usage-Policy |
| 2025-04-30 | Moises Live EULA published (real-time desktop app) | https://help.moises.ai/hc/en-us/articles/19834093643292-Moises-Live-End-User-License-Agreement |

App Store release notes for the same period are boilerplate ("under the hood improvements"), versions
2.132 → 2.150 between May and Oct 2026 — i.e. ~2-week cadence, no feature detail. Source:
https://apps.apple.com/us/app/moises-the-musicians-app/id1515796612

---

## 13. Defensively inferred (not documented)

Clearly labelled guesses — do not cite as fact.

- **Studio plan limits.** Studio markets "start a session free" and says collaborators need no paid
  plan, but no page states project count, session length, or storage caps. Likely: free sessions are
  watermarked by tool limits (credits, export) rather than by seat count.
- **Separation backend is shared.** The 27-stem list, "Hi-Fi" naming and 48 kHz spec are identical
  across app, Studio and the DAW plugin; almost certainly one inference service with tier gating.
- **Chord/key engine is shared** across app, Studio, LUNA and Fender Studio Pro; the LUNA deal is
  explicitly "technology powered by Moises".
- **"18 built-in effects"** are counted, never named. Assume a standard channel strip (EQ, comp,
  reverb, delay, saturation) but verify in-app before planning parity.
- **Auto-mix "20 genre styles"** likely maps to preset EQ/comp/pan curves, not a learned mixer.
- **Custom voice model training** is advertised as "in minutes"; unclear whether it is Pro-only or
  credit-metered. The help center's Voice Studio articles predate custom training.
- **Video recording length** is unstated; App Store review complaints and the "share to socials"
  framing suggest short-form (tens of seconds to a few minutes), not full-song 4K.
- **Offline.** Marketing says cloud-first; mobile caches downloaded songs for playback. Assume:
  playback offline = yes (cached), any processing/generation = no.
- **MIDI export scope.** "Audio or MIDI" appears only in Studio marketing; the consumer app's MIDI
  story (if any) is undocumented.
- **Grand Piano, male/female vocals, brass/reeds/woodwind, percussion** are flagged "web only for
  now" in help articles — a mobile parity gap that is likely closing silently.

---

## 14. Unknown / not public

- Storage quotas (GB per plan) and retention policy for inactive libraries.
- Studio: max collaborators per session, project count, session duration, file-size caps.
- Whether Studio/AI Studio is bundled into Premium/Pro or billed separately (web pricing is gated).
- Model names, versions, architectures, and any published quality benchmarks (SDR/museval).
- Latency figures for Moises Live and for the web player's time-stretch.
- Whether a denoise/de-reverb or "cleanup" tool exists (only marketed as separation quality).
- Public API docs, rate limits, and pricing for the Music AI platform.
- Accessibility conformance (VoiceOver/TalkBack coverage, WCAG/VPAT, Dynamic Type).
- Chrome extension / browser-extension status.
- Dropbox or OneDrive direct integration (only Google Drive/iCloud/Files are evidenced).
- Commercial-use terms for **AI-generated** parts beyond "you own your outputs"; copyright status is
  explicitly left to local law.
- Refund policy specifics, education/nonprofit pricing, family plans.

---

## 15. Where Moises is weak (parity opportunities for us)

Short, evidence-based read across the tables above:

1. **No tablature.** Chords, capo and diagrams exist; no tab generation and no PDF/chart export —
   the single clearest gap versus a guitar-first product.
2. **No pan/EQ/comp in the practice player.** The legacy mixer is volume + mute/solo only; real
   channel strips live in Studio, behind a different surface.
3. **Analysis is display-only.** Key/chord/BPM/sections are detected but there is no beat-grid editor,
   no pitch curve, no melody/MIDI extraction in the consumer app.
4. **Per-device edit state.** Key/speed tweaks do not sync across devices — a real workflow papercut.
5. **First-minute gating** on metronome/chords/lyrics makes the free tier feel like a demo, while
   speed/pitch are capped separately (±10–20%, ±2 semitones) with inconsistent published numbers.
6. **No denoise / de-reverb**, despite marketing "no cleanup pass" separation.
7. **Offline is playback-only**, and the plugin is explicitly not real-time.

---

## 16. Source conflicts (both values recorded, unresolved)

| Topic | Value A | Value B | Which to trust |
|---|---|---|---|
| Free speed change | ±10 (welcome article) | 20% (tempo article) | Assume the stricter ±10% until tested in-app |
| Custom separation cap, Premium | 6 tracks incl. Others (mobile custom-upload article) | "up to 5 instruments per upload" (Premium instruments article) | 5 may exclude the implicit "Others"; verify |
| Export formats | MP3/M4A mobile, +WAV desktop (help center) | +FLAC, +OGG, "up to 192 kHz" (stem-separation page) | Help center is the safer contract |
| Plugin stem count | 7 (plugin page: vocals, keys, drums, guitar, bass, strings, other) | "8 stems on every track" (Pro plan article) | 7 is the documented named list |
| Offline use | "Cannot be used offline" (offline article) | "songs must be downloaded again to play offline" (storage article) | Processing needs internet; cached playback works |
| Moises Live on macOS | Product page has a Mac download | Help article says "Mac coming soon" | Product page is newer |
| Minimum iOS | iOS 16 (help: minimum requirements) | iOS 17 (current App Store listing) | App Store |
| Minimum macOS | macOS 11 Big Sur, M1+ (help) | macOS 14, M1+ (App Store Mac listing) | App Store |
| "27 stems" | 27 stem types (marketing) | 23 selectable (20 music + 3 multimedia) | 23 selectable, 27 marketing |
| Studio's relationship to AI Studio | AI Studio = desktop/web AI DAW (Oct 2025) | Moises Studio = collaborative studio (Sep 2026) | Same lineage; Studio is the current surface |

Where a number mattered for planning (free caps, file lengths, export specs) the table above uses the
help-center value, since marketing pages are revised for launches and help articles track the shipped
product.

