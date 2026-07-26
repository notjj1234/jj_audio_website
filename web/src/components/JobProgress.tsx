import type { JobResponse, JobStatus } from "../api";

const STATUS_LABELS: Record<JobStatus, string> = {
  pending: "Pending",
  running: "Running",
  succeeded: "Succeeded",
  failed: "Failed",
  cancelled: "Cancelled",
};

function humanizeStage(stage: string): string {
  if (!stage) return "";
  const words = stage.replace(/[_-]+/g, " ").trim().split(/\s+/);
  return words
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export function JobProgress({
  job,
  onCancel,
}: {
  job: JobResponse | null;
  onCancel?: () => void;
}) {
  if (!job) return null;
  const done = ["succeeded", "failed", "cancelled"].includes(job.status);
  return (
    <div className="progress">
      <div className="stage">
        {STATUS_LABELS[job.status] ?? job.status}
        {job.stage ? ` — ${humanizeStage(job.stage)}` : ""}
      </div>
      <p>{job.message}</p>
      {job.error && <p className="error">{job.error}</p>}
      {!done && onCancel && (
        <button type="button" className="danger" onClick={onCancel}>
          Cancel
        </button>
      )}
    </div>
  );
}
