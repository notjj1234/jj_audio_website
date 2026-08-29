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
  // Legacy artifacts only — default isolate path no longer emits these.
  lead_guitar: "Lead (legacy)",
  rhythm_guitar: "Rhythm (legacy)",
  guitar1: "Guitar 1",
  guitar2: "Guitar 2",
};

const SEPARATION_PRESETS = {
  full_band: {
    label: "Full band — Vocals, Drums, Bass, Guitar (4 tracks)",
    model: "htdemucs_6s",
    two_stems: null as string | null,
    emit_stems: ["vocals", "drums", "bass", "guitar"] as string[],
    fold_other_into_guitar: true,
  },
  essential: {
    label: "Essential tracks — Vocals, Drums, Bass, Other (4 tracks)",
    model: "htdemucs",
    two_stems: null,
    emit_stems: ["vocals", "drums", "bass", "other"] as string[],
    fold_other_into_guitar: true,
  },
  vocals_music: {
    label: "Vocals & music — Vocals, Instrumental (2 tracks)",
    model: "htdemucs",
    two_stems: "vocals",
    emit_stems: null as string[] | null,
    fold_other_into_guitar: true,
  },
} as const;

type PresetId = keyof typeof SEPARATION_PRESETS;

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

export function IsolatePage() {
  const [file, setFile] = useState<File | null>(null);
  const [preset, setPreset] = useState<PresetId>("full_band");
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

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!file) {
      setError("Choose an audio file");
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

    const presetCfg = SEPARATION_PRESETS[preset];
    const body: Record<string, unknown> = {
      upload_id: "",
      model: presetCfg.model,
      processing_mode: processingMode,
    };
    if (presetCfg.two_stems) {
      body.two_stems = presetCfg.two_stems;
    }
    if (presetCfg.emit_stems) {
      body.emit_stems = [...presetCfg.emit_stems];
    }
    body.fold_other_into_guitar = presetCfg.fold_other_into_guitar;
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

  return (
    <div>
      <h1>Isolate</h1>
      <p className="lede">
        Separate stems with Demucs. Pick tracks, an optional section, and a processing mode.
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

        <label className="field">
          Tracks to separate
          <select
            value={preset}
            onChange={(e) => setPreset(e.target.value as PresetId)}
            aria-label="Tracks to separate"
          >
            {(Object.keys(SEPARATION_PRESETS) as PresetId[]).map((id) => (
              <option key={id} value={id}>
                {SEPARATION_PRESETS[id].label}
              </option>
            ))}
          </select>
        </label>

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
        <button type="submit" disabled={busy}>
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
