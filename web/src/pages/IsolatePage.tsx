import { useMemo, useState, type FormEvent } from "react";
import * as api from "../api";
import { JobProgress } from "../components/JobProgress";
import { StemMixer } from "../components/StemMixer";
import type { StemInfo } from "../mixer/engine";

const STEM_LABELS: Record<string, string> = {
  vocals: "Vocals",
  drums: "Drums",
  bass: "Bass",
  other: "Other",
  guitar: "Guitar",
  piano: "Piano",
  lead_guitar: "Lead",
  rhythm_guitar: "Rhythm",
  guitar1: "Guitar 1",
  guitar2: "Guitar 2",
};

const AUDIO_KINDS = new Set(Object.keys(STEM_LABELS));

export function IsolatePage() {
  const [file, setFile] = useState<File | null>(null);
  const [quality, setQuality] = useState("fast");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [job, setJob] = useState<api.JobResponse | null>(null);
  const [stopWatch, setStopWatch] = useState<(() => void) | null>(null);

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

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!file) {
      setError("Choose an audio file");
      return;
    }
    setBusy(true);
    setError(null);
    stopWatch?.();
    try {
      const up = await api.uploadAudio(file);
      const created = await api.createIsolateJob({
        upload_id: up.upload_id,
        model: "htdemucs_6s",
        quality,
        device: "cpu",
      });
      setJob(created);
      const stop = api.watchJob(created.id, setJob);
      setStopWatch(() => stop);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <h1>Isolate</h1>
      <p className="lede">
        Separate stems with Demucs. Default quality is fast for public servers.
      </p>
      <form className="stack" onSubmit={onSubmit}>
        <label className="field">
          Audio file
          <input
            type="file"
            accept=".mp3,.wav,.flac,.m4a,audio/*"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </label>
        <label className="field">
          Quality
          <select value={quality} onChange={(e) => setQuality(e.target.value)}>
            <option value="fast">Fast</option>
            <option value="balanced">Balanced</option>
            <option value="high">High</option>
            <option value="extreme">Extreme</option>
          </select>
        </label>
        {error && <p className="error">{error}</p>}
        <button type="submit" disabled={busy}>
          {busy ? "Starting…" : "Start isolation"}
        </button>
      </form>

      <div style={{ marginTop: "1.5rem" }}>
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
        <>
          <div className="artifacts" style={{ marginTop: "1rem" }}>
            {job.artifacts.zip && (
              <a href={job.artifacts.zip} download>
                Download all stems (ZIP)
              </a>
            )}
            {Object.entries(job.artifacts)
              .filter(([k]) => k !== "zip" && k !== "guitar_split_diagnostics")
              .map(([kind, url]) => (
                <a key={kind} href={url} download>
                  {STEM_LABELS[kind] ?? kind}
                </a>
              ))}
          </div>
          {stems.length > 0 && <StemMixer stems={stems} />}
        </>
      )}
    </div>
  );
}
