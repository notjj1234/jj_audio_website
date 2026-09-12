/** Shared Isolate / Tab PDF track labels. Honesty copy must stay in one place. */

export const TRACK_OPTIONS = {
  vocals_demucs: { label: "Vocals (Demucs)", stem: "vocals" },
  drums_demucs: { label: "Drums (Demucs)", stem: "drums" },
  bass_demucs: { label: "Bass (Demucs)", stem: "bass" },
  other_demucs: { label: "Other (Demucs)", stem: "other" },
  piano_demucs: { label: "Piano (Demucs 6-stem — heavy bleed)", stem: "piano" },
  guitar_demucs_6s: {
    label: "Guitar (Demucs 6-stem, weaker — other instruments still bleed in)",
    stem: "guitar",
  },
  guitar_roformer: {
    label: "Guitar (BS-RoFormer, better, slower — residual bleed remains)",
    stem: "guitar",
  },
  guitar_roformer_refine: {
    label:
      "Guitar (BS-RoFormer + MelBand refine, best, slowest — residual bleed remains)",
    stem: "guitar",
  },
  vocals_instrumental_demucs: {
    label: "Vocals & instrumental (Demucs 2-stem)",
    stem: "vocals",
  },
} as const;

export type TrackOptionId = keyof typeof TRACK_OPTIONS;

export const GUITAR_TRACK_OPTION_IDS = new Set<TrackOptionId>([
  "guitar_demucs_6s",
  "guitar_roformer",
  "guitar_roformer_refine",
]);

export const DEMUCS_STEM_CHECKBOX_IDS: TrackOptionId[] = [
  "vocals_demucs",
  "drums_demucs",
  "bass_demucs",
  "piano_demucs",
  "other_demucs",
];

export const VOCALS_INSTRUMENTAL_OPTION_ID: TrackOptionId = "vocals_instrumental_demucs";
export const DEFAULT_TRACK_OPTIONS: TrackOptionId[] = ["vocals_demucs", "guitar_demucs_6s"];

export const HOSTED_FILE_ONLY_NOTE =
  "Upload an audio file. YouTube ingest is desktop-only for now.";
