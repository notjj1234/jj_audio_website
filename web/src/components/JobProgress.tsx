import type { JobResponse } from "../api";

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
        {job.status} · {job.stage}
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
