import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import * as api from "../api";
import { JobProgress } from "../components/JobProgress";
import { ProcessingModeSelect } from "../components/ProcessingModeSelect";
import { StemMixer } from "../components/StemMixer";
import type { StemInfo } from "../mixer/engine";

const MIN_REGION_SEC = 5;

const STEM_LABELS: Record<string, string> = {
  vocals: "Vocals",
  drums: "Drums",
  bass: "Bass",
  other: "Other",
  guitar: "Guitar",
  piano: "Piano",
  lead_guitar: "Lead (legacy)",
  rhythm_guitar: "Rhythm (legacy)",
  guitar1: "Guitar 1",
  guitar2: "Guitar 2",
};

const TRACK_OPTIONS = {
  vocals_demucs: { label: "Vocals (Demucs)", stem: "vocals" },
  drums_demucs: { label: "Drums (Demucs)", stem: "drums" },
  bass_demucs: { label: "Bass (Demucs)", stem: "bass" },
  other_demucs: { label: "Other (Demucs)", stem: "other" },
  piano_demucs: { label: "Piano (Demucs 6-stem)", stem: "piano" },
  guitar_demucs_6s: { label: "Guitar (Demucs 6-stem, weaker)", stem: "guitar" },
  guitar_roformer: { label: "Guitar (BS-RoFormer, better, slower)", stem: "guitar" },
  guitar_roformer_refine: {
    label: "Guitar (BS-RoFormer + MelBand refine, best, slowest)",
    stem: "guitar",
  },
  vocals_instrumental_demucs: {
    label: "Vocals & instrumental (Demucs 2-stem)",
    stem: "vocals",
  },
} as const;

type TrackOptionId = keyof typeof TRACK_OPTIONS;

const GUITAR_TRACK_OPTION_IDS = new Set<TrackOptionId>([
  "guitar_demucs_6s",
  "guitar_roformer",
  "guitar_roformer_refine",
]);

const DEMUCS_STEM_CHECKBOX_IDS: TrackOptionId[] = [
  "vocals_demucs",
  "drums_demucs",
  "bass_demucs",
  "piano_demucs",
  "other_demucs",
];

const VOCALS_INSTRUMENTAL_OPTION_ID: TrackOptionId = "vocals_instrumental_demucs";
const DEFAULT_TRACK_OPTIONS: TrackOptionId[] = ["vocals_demucs", "guitar_demucs_6s"];

const ROFORMER_DOWNLOAD_CAVEAT =
  "Downloads ~700 MB BS-RoFormer-SW weights on first use, then a guitar specialist (~45 MB). Much slower on CPU. Community weights have no stated license — use accordingly.";
const ROFORMER_MIXED_STEMS_NOTE =
  "All stems are separated in one BS-RoFormer pass; unselected stems are discarded.";
const TRACKS_PICKER_HELP =
  "Pick the stems you want. Guitar can use Demucs (faster) or BS-RoFormer (better quality, much slower on CPU).";

type ResolvedTrackSelection = {
  model: string;
  two_stems: string | null;
  emit_stems: string[];
  fold_other_into_guitar: boolean;
  guitar_refine: boolean;
  caveat: string;
};

function trackSelectionCaveat(optionIds: string[], usesRoformer: boolean): string {
  const parts: string[] = [];
  if (usesRoformer) {
    parts.push(ROFORMER_DOWNLOAD_CAVEAT);
    if (optionIds.some((id) => !GUITAR_TRACK_OPTION_IDS.has(id as TrackOptionId))) {
      parts.push(ROFORMER_MIXED_STEMS_NOTE);
    }
  }
  return parts.join(" ");
}

function resolveTrackSelection(optionIds: string[]): ResolvedTrackSelection {
  const ids = optionIds.filter((id): id is TrackOptionId => id in TRACK_OPTIONS);
  if (ids.length === 0) {
    throw new Error("Pick at least one track to separate.");
  }

  const guitarPicks = ids.filter((id) => GUITAR_TRACK_OPTION_IDS.has(id));
  if (guitarPicks.length > 1) {
    throw new Error("Pick only one guitar option.");
  }

  if (ids.includes(VOCALS_INSTRUMENTAL_OPTION_ID)) {
    if (ids.length > 1) {
      throw new Error("Vocals & instrumental cannot combine with other tracks.");
    }
    return {
      model: "htdemucs",
      two_stems: "vocals",
      emit_stems: ["vocals"],
      fold_other_into_guitar: true,
      guitar_refine: false,
      caveat: "",
    };
  }

  const emit: string[] = [];
  const customStems: string[] = [];
  for (const oid of ids) {
    const stem = TRACK_OPTIONS[oid].stem;
    if (!emit.includes(stem)) emit.push(stem);
    if (!customStems.includes(stem)) customStems.push(stem);
  }

  const usesRoformer =
    guitarPicks.length === 1 &&
    (guitarPicks[0] === "guitar_roformer" || guitarPicks[0] === "guitar_roformer_refine");
  const guitarRefine = guitarPicks[0] === "guitar_roformer_refine";

  let model: string;
  if (usesRoformer) {
    model = "bs_roformer_sw";
  } else if (customStems.includes("guitar") || customStems.includes("piano")) {
    model = "htdemucs_6s";
  } else {
    model = "htdemucs";
  }

  return {
    model,
    two_stems: null,
    emit_stems: emit,
    fold_other_into_guitar: !customStems.includes("other"),
    guitar_refine: guitarRefine,
    caveat: trackSelectionCaveat(ids, usesRoformer),
  };
}

const AUDIO_KINDS = new Set(Object.keys(STEM_LABELS));

function formatTime(sec: number): string {
  if (!isFinite(sec) || sec < 0) sec = 0;
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function formatRegionLabel(startSec: number, endSec: number): string {
  return `${formatTime(startSec)}–${formatTime(endSec)}`;
}

function isDiagnosticKind(kind: string): boolean {
  return kind.endsWith("_diagnostics");
}

function readAdvancedOpen(): boolean {
  try {
    const v = sessionStorage.getItem("isolate_advanced_open");
    return v === null ? true : v === "1";
  } catch {
    return true;
  }
}

type GuitarTrackChoice = "none" | TrackOptionId;

export function IsolatePage() {
  const [file, setFile] = useState<File | null>(null);
  const [demucsChecked, setDemucsChecked] = useState<Record<TrackOptionId, boolean>>({
    vocals_demucs: true,
    drums_demucs: false,
    bass_demucs: false,
    piano_demucs: false,
    other_demucs: false,
    guitar_demucs_6s: false,
    guitar_roformer: false,
    guitar_roformer_refine: false,
    vocals_instrumental_demucs: false,
  });
  const [guitarTrack, setGuitarTrack] = useState<GuitarTrackChoice>("guitar_demucs_6s");
  const [vocalsInstrumentalOnly, setVocalsInstrumentalOnly] = useState(false);
  const [processingMode, setProcessingMode] = useState("balanced");
  const [capabilities, setCapabilities] = useState<api.SystemCapabilities | null>(null);
  const [duration, setDuration] = useState<number | null>(null);
  const [useRegion, setUseRegion] = useState(false);
  const [regionStart, setRegionStart] = useState(0);
  const [regionEnd, setRegionEnd] = useState(30);
  const [advancedOpen, setAdvancedOpen] = useState(readAdvancedOpen);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [job, setJob] = useState<api.JobResponse | null>(null);
  const [jobList, setJobList] = useState<api.JobResponse[]>([]);
  const [stopWatch, setStopWatch] = useState<(() => void) | null>(null);
  const [clipLabel, setClipLabel] = useState<string | null>(null);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const previewStopRef = useRef<(() => void) | null>(null);
  const objectUrlRef = useRef<string | null>(null);

  const trackOptions = useMemo((): TrackOptionId[] => {
    if (vocalsInstrumentalOnly) {
      return [VOCALS_INSTRUMENTAL_OPTION_ID];
    }
    const options = DEMUCS_STEM_CHECKBOX_IDS.filter((id) => demucsChecked[id]);
    if (guitarTrack !== "none") {
      options.push(guitarTrack);
    }
    return options;
  }, [demucsChecked, guitarTrack, vocalsInstrumentalOnly]);

  const resolved = useMemo((): ResolvedTrackSelection => {
    try {
      return resolveTrackSelection(trackOptions);
    } catch {
      return resolveTrackSelection(DEFAULT_TRACK_OPTIONS);
    }
  }, [trackOptions]);

  const pickerError = useMemo(() => {
    try {
      resolveTrackSelection(trackOptions);
      return null;
    } catch (err) {
      return err instanceof Error ? err.message : String(err);
    }
  }, [trackOptions]);

  useEffect(() => {
    let cancelled = false;
    api
      .getSystemCapabilities()
      .then((c) => {
        if (!cancelled) setCapabilities(c);
      })
      .catch(() => {
        /* fallback modes used by ProcessingModeSelect */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const refresh = () => {
      api
        .listJobs({ kind: "isolate", limit: 10 })
        .then((rows) => {
          if (!cancelled) setJobList(rows);
        })
        .catch(() => {
          /* ignore */
        });
    };
    refresh();
    const t = window.setInterval(refresh, 3000);
    return () => {
      cancelled = true;
      window.clearInterval(t);
    };
  }, [job?.id, job?.status]);

  useEffect(() => {
    previewStopRef.current?.();
    previewStopRef.current = null;
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = null;
    }
    if (!file) {
      setDuration(null);
      setRegionStart(0);
      setRegionEnd(30);
      return;
    }
    const url = URL.createObjectURL(file);
    objectUrlRef.current = url;
    const audio = new Audio(url);
    audioRef.current = audio;
    const onMeta = () => {
      const d = audio.duration;
      if (!isFinite(d) || d <= 0) {
        setDuration(null);
        return;
      }
      setDuration(d);
      const end = Math.min(d, Math.max(MIN_REGION_SEC, 30));
      setRegionStart(0);
      setRegionEnd(end);
    };
    audio.addEventListener("loadedmetadata", onMeta);
    audio.load();
    return () => {
      audio.removeEventListener("loadedmetadata", onMeta);
      previewStopRef.current?.();
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current);
        objectUrlRef.current = null;
      }
    };
  }, [file]);

  const selectedMode = useMemo(() => {
    const modes = capabilities?.modes ?? [];
    const picked = modes.find((m) => m.id === processingMode);
    if (picked) return picked;
    if (processingMode === "auto") {
      return modes.find((m) => m.id === "balanced") ?? modes.find((m) => m.id === "fast_cpu");
    }
    return modes.find((m) => m.id === processingMode);
  }, [capabilities, processingMode]);

  const regionLength = useRegion ? Math.max(0, regionEnd - regionStart) : null;
  const modeCap = selectedMode?.max_duration_sec ?? null;
  const regionOverCap =
    useRegion && regionLength !== null && modeCap !== null && regionLength > modeCap;

  const regionLabel =
    useRegion && duration !== null ? formatRegionLabel(regionStart, regionEnd) : null;

  function onAdvancedToggle(open: boolean) {
    setAdvancedOpen(open);
    try {
      sessionStorage.setItem("isolate_advanced_open", open ? "1" : "0");
    } catch {
      /* ignore */
    }
  }

  function shortenEndToCap() {
    if (modeCap === null) return;
    setRegionEnd(Math.min(duration ?? regionEnd, regionStart + modeCap));
  }

  function previewRegion() {
    const audio = audioRef.current;
    if (!audio || !useRegion) return;
    previewStopRef.current?.();
    audio.currentTime = regionStart;
    void audio.play();
    const stopAtEnd = () => {
      if (audio.currentTime >= regionEnd - 0.05) {
        audio.pause();
        audio.removeEventListener("timeupdate", stopAtEnd);
        previewStopRef.current = null;
      }
    };
    audio.addEventListener("timeupdate", stopAtEnd);
    previewStopRef.current = () => {
      audio.pause();
      audio.removeEventListener("timeupdate", stopAtEnd);
    };
  }

  function toggleDemucsStem(id: TrackOptionId, checked: boolean) {
    setDemucsChecked((prev) => ({ ...prev, [id]: checked }));
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!file) {
      setError("Choose an audio file");
      return;
    }
    if (pickerError) {
      setError(pickerError);
      return;
    }
    if (useRegion) {
      if (duration === null) {
        setError("Could not read audio length — turn off section mode or try another file");
        return;
      }
      if (regionStart >= regionEnd) {
        setError("Start must be before end");
        return;
      }
      if (regionEnd - regionStart < MIN_REGION_SEC) {
        setError(`Section must be at least ${MIN_REGION_SEC} seconds`);
        return;
      }
      if (regionEnd > duration + 0.05) {
        setError("End time exceeds file length");
        return;
      }
    }

    setBusy(true);
    setError(null);
    stopWatch?.();
    setClipLabel(useRegion && regionLabel ? regionLabel : null);

    const body: Record<string, unknown> = {
      upload_id: "",
      model: resolved.model,
      processing_mode: processingMode,
      emit_stems: [...resolved.emit_stems],
      fold_other_into_guitar: resolved.fold_other_into_guitar,
    };
    if (resolved.two_stems) {
      body.two_stems = resolved.two_stems;
    }
    if (resolved.guitar_refine) {
      body.guitar_refine = true;
    }
    if (useRegion) {
      body.start_sec = regionStart;
      body.end_sec = regionEnd;
    }

    try {
      const up = await api.uploadAudio(file);
      body.upload_id = up.upload_id;
      const created = await api.createIsolateJob(body);
      setJob(created);
      const stop = api.watchJob(created.id, setJob);
      setStopWatch(() => stop);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setClipLabel(null);
    } finally {
      setBusy(false);
    }
  }

  const stems: StemInfo[] = useMemo(() => {
    if (!job || job.status !== "succeeded") return [];
    return Object.entries(job.artifacts)
      .filter(([kind]) => AUDIO_KINDS.has(kind))
      .map(([id, url]) => ({
        id,
        label: STEM_LABELS[id] ?? id,
        url,
      }));
  }, [job]);

  const downloadArtifacts = job?.artifacts
    ? Object.entries(job.artifacts).filter(
        ([kind]) => kind !== "zip" && !isDiagnosticKind(kind)
      )
    : [];

  const guitarRadioOptions: { id: GuitarTrackChoice; label: string }[] = [
    { id: "none", label: "No guitar" },
    ...Array.from(GUITAR_TRACK_OPTION_IDS).map((id) => ({
      id,
      label: TRACK_OPTIONS[id].label,
    })),
  ];

  return (
    <div>
      <h1>Isolate</h1>
      <p className="lede">
        Separate stems. Pick labeled tracks (Demucs or BS-RoFormer for guitar), an optional
        section, and a processing mode.
      </p>
      <form
        className={`stack${job ? " stack-secondary" : ""}`}
        onSubmit={onSubmit}
      >
        <label className="field">
          Audio file
          <input
            type="file"
            accept=".mp3,.wav,.flac,.m4a,audio/*"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </label>

        <fieldset className="field">
          <legend>Tracks to separate</legend>
          <p className="hint">{TRACKS_PICKER_HELP}</p>
          <label className="field">
            <input
              type="checkbox"
              checked={vocalsInstrumentalOnly}
              onChange={(e) => setVocalsInstrumentalOnly(e.target.checked)}
            />{" "}
            {TRACK_OPTIONS[VOCALS_INSTRUMENTAL_OPTION_ID].label}
          </label>
          {!vocalsInstrumentalOnly && (
            <>
              <div className="stack" style={{ marginTop: "0.5rem" }}>
                {DEMUCS_STEM_CHECKBOX_IDS.map((id) => (
                  <label key={id} className="field">
                    <input
                      type="checkbox"
                      checked={demucsChecked[id]}
                      onChange={(e) => toggleDemucsStem(id, e.target.checked)}
                    />{" "}
                    {TRACK_OPTIONS[id].label}
                  </label>
                ))}
              </div>
              <fieldset className="field" style={{ marginTop: "0.75rem" }}>
                <legend>Guitar</legend>
                {guitarRadioOptions.map(({ id, label }) => (
                  <label key={id} className="field">
                    <input
                      type="radio"
                      name="guitar_track"
                      checked={guitarTrack === id}
                      onChange={() => setGuitarTrack(id)}
                    />{" "}
                    {label}
                  </label>
                ))}
              </fieldset>
            </>
          )}
          {pickerError ? <p className="error">{pickerError}</p> : null}
          {resolved.caveat ? <p className="hint">{resolved.caveat}</p> : null}
        </fieldset>

        <fieldset className="field" disabled={!file}>
          <legend>Section</legend>
          {!file ? (
            <span className="hint">Upload a file to choose a section or preview audio.</span>
          ) : (
            <>
              {duration !== null ? (
                <span className="hint">
                  Length: {formatTime(duration)} ({duration.toFixed(1)} s)
                </span>
              ) : (
                <span className="hint">Length: unknown — full file will be processed.</span>
              )}
              <label className="field">
                <input
                  type="checkbox"
                  checked={useRegion}
                  onChange={(e) => setUseRegion(e.target.checked)}
                />{" "}
                Isolate only a section
              </label>
              {objectUrlRef.current && (
                <audio controls src={objectUrlRef.current} style={{ width: "100%" }} />
              )}
              {useRegion && duration !== null && (
                <>
                  <label className="field">
                    Start ({formatTime(regionStart)})
                    <input
                      type="range"
                      min={0}
                      max={duration}
                      step={1}
                      value={regionStart}
                      onChange={(e) => {
                        const next = Number(e.target.value);
                        setRegionStart(next);
                        if (regionEnd <= next + MIN_REGION_SEC) {
                          setRegionEnd(Math.min(duration, next + MIN_REGION_SEC));
                        }
                      }}
                    />
                  </label>
                  <label className="field">
                    End ({formatTime(regionEnd)})
                    <input
                      type="range"
                      min={MIN_REGION_SEC}
                      max={duration}
                      step={1}
                      value={regionEnd}
                      onChange={(e) => {
                        const next = Number(e.target.value);
                        setRegionEnd(next);
                        if (regionStart >= next - MIN_REGION_SEC) {
                          setRegionStart(Math.max(0, next - MIN_REGION_SEC));
                        }
                      }}
                    />
                  </label>
                  <span className="hint">
                    {regionLabel} ({(regionEnd - regionStart).toFixed(0)} s)
                  </span>
                  <button type="button" className="secondary" onClick={previewRegion}>
                    Preview section
                  </button>
                  {regionOverCap && selectedMode && (
                    <p className="error">
                      {selectedMode.label} allows up to {modeCap} s per job. Shorten the section
                      or choose a different mode.
                      <button
                        type="button"
                        className="secondary"
                        style={{ marginLeft: "0.5rem" }}
                        onClick={shortenEndToCap}
                      >
                        Shorten end to {modeCap} s
                      </button>
                    </p>
                  )}
                </>
              )}
            </>
          )}
        </fieldset>

        <ProcessingModeSelect value={processingMode} onChange={setProcessingMode} />

        <details
          open={advancedOpen}
          onToggle={(e) => onAdvancedToggle((e.target as HTMLDetailsElement).open)}
        >
          <summary>Advanced options</summary>
          <p className="hint">
            Processing mode above sets quality and device on the server. Use this panel to review
            host limits before starting a long section.
          </p>
        </details>

        {error && <p className="error">{error}</p>}
        <button type="submit" disabled={busy || Boolean(pickerError)}>
          {busy ? "Starting…" : "Start isolation"}
        </button>
      </form>

      <div style={{ marginTop: "1.5rem" }}>
        {jobList.length > 0 && (
          <div className="results-card" style={{ marginBottom: "1rem" }}>
            <h2 className="section-heading">Job queue</h2>
            <p className="hint">
              Jobs run one at a time. Queuing several songs means a long wait and high
              CPU/RAM use — this is not parallel Demucs.
            </p>
            <ul className="stack" style={{ listStyle: "none", padding: 0 }}>
              {jobList.map((j) => (
                <li key={j.id} style={{ marginBottom: "0.35rem" }}>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => {
                      stopWatch?.();
                      setJob(j);
                      if (!["succeeded", "failed", "cancelled"].includes(j.status)) {
                        const stop = api.watchJob(j.id, setJob);
                        setStopWatch(() => stop);
                      }
                    }}
                  >
                    {j.status} — {j.message || j.stage || j.id.slice(0, 8)}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
        {clipLabel && job && (
          <p className="hint">
            <strong>Clip {clipLabel}</strong>
          </p>
        )}
        <JobProgress
          job={job}
          onCancel={
            job && !["succeeded", "failed", "cancelled"].includes(job.status)
              ? () => void api.cancelJob(job.id).then(setJob)
              : undefined
          }
        />
      </div>

      {job?.status === "succeeded" && (
        <div className="results-card" style={{ marginTop: "1rem" }}>
          <h2 className="section-heading">
            Your files
            {clipLabel && (
              <span className="hint" style={{ marginLeft: "0.5rem", fontWeight: "normal" }}>
                Clip {clipLabel}
              </span>
            )}
          </h2>
          <div className="artifacts">
            {job.artifacts.zip && (
              <a className="btn" href={job.artifacts.zip} download>
                Download all stems (ZIP)
              </a>
            )}
            {downloadArtifacts.map(([kind, url]) => (
              <a key={kind} className="btn secondary" href={url} download>
                Download {STEM_LABELS[kind] ?? kind}
              </a>
            ))}
          </div>
          {stems.length > 0 && <StemMixer stems={stems} />}
        </div>
      )}
    </div>
  );
}
