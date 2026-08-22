import { useState, type FormEvent } from "react";
import * as api from "../api";
import { JobProgress } from "../components/JobProgress";
import { ProcessingModeSelect } from "../components/ProcessingModeSelect";

export function TabPage() {
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("Guitar Tab");
  const [processingMode, setProcessingMode] = useState("auto");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [job, setJob] = useState<api.JobResponse | null>(null);
  const [stopWatch, setStopWatch] = useState<(() => void) | null>(null);

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
      const created = await api.createTabJob({
        upload_id: up.upload_id,
        title,
        separate_stems: true,
        processing_mode: processingMode,
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
      <h1>Tab PDF</h1>
      <p className="lede">
        Upload a track, wait for the job to finish, then download the PDF.
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
          Title
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </label>
        <ProcessingModeSelect value={processingMode} onChange={setProcessingMode} />
        {error && <p className="error">{error}</p>}
        <button type="submit" disabled={busy}>
          {busy ? "Starting…" : "Create tab job"}
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

      {job?.status === "succeeded" && job.artifacts.pdf && (
        <div className="results-card" style={{ marginTop: "1rem" }}>
          <h2 className="section-heading">Your files</h2>
          <div className="artifacts">
            <a className="btn" href={job.artifacts.pdf} download>
              Download PDF
            </a>
            {job.artifacts.midi && (
              <a className="btn secondary" href={job.artifacts.midi} download>
                Download MIDI
              </a>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
