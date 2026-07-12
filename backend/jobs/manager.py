"""In-memory job manager with WebSocket pub/sub."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.contracts import JobEvent, JobStatus


@dataclass
class JobRecord:
    id: str
    status: JobStatus = JobStatus.pending
    stage: str = "pending"
    message: str = ""
    error: str | None = None
    artifacts: dict[str, str] = field(default_factory=dict)
    upload_path: str | None = None
    youtube_url: str | None = None
    title: str = "Guitar Tab"
    separate_stems: bool = True
    max_duration_sec: float = 90.0
    mix_aware_filtering: bool = True
    tempo_bpm_override: float | None = None
    onset_threshold: float = 0.5
    frame_threshold: float = 0.3
    subscribers: list[asyncio.Queue] = field(default_factory=list)


class JobManager:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.uploads_dir = data_dir / "uploads"
        self.jobs_dir = data_dir / "jobs"
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self._jobs: dict[str, JobRecord] = {}

    def save_upload(self, filename: str, content: bytes) -> tuple[str, Path]:
        upload_id = str(uuid.uuid4())
        dest = self.uploads_dir / upload_id / filename
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        return upload_id, dest

    def create_job(
        self,
        *,
        upload_id: str | None = None,
        upload_path: Path | None = None,
        youtube_url: str | None = None,
        title: str = "Guitar Tab",
        separate_stems: bool = True,
        max_duration_sec: float = 90.0,
        mix_aware_filtering: bool = True,
        tempo_bpm_override: float | None = None,
        onset_threshold: float = 0.5,
        frame_threshold: float = 0.3,
    ) -> JobRecord:
        job_id = str(uuid.uuid4())
        if upload_id and not upload_path:
            candidates = list((self.uploads_dir / upload_id).iterdir())
            upload_path = candidates[0] if candidates else None

        job = JobRecord(
            id=job_id,
            upload_path=str(upload_path) if upload_path else None,
            youtube_url=youtube_url,
            title=title,
            separate_stems=separate_stems,
            max_duration_sec=max_duration_sec,
            mix_aware_filtering=mix_aware_filtering,
            tempo_bpm_override=tempo_bpm_override,
            onset_threshold=onset_threshold,
            frame_threshold=frame_threshold,
        )
        self._jobs[job_id] = job
        (self.jobs_dir / job_id).mkdir(parents=True, exist_ok=True)
        return job

    def get(self, job_id: str) -> JobRecord | None:
        return self._jobs.get(job_id)

    def job_output_dir(self, job_id: str) -> Path:
        return self.jobs_dir / job_id

    async def subscribe(self, job_id: str) -> asyncio.Queue:
        job = self._jobs[job_id]
        q: asyncio.Queue = asyncio.Queue()
        job.subscribers.append(q)
        return q

    def unsubscribe(self, job_id: str, q: asyncio.Queue) -> None:
        job = self._jobs.get(job_id)
        if job and q in job.subscribers:
            job.subscribers.remove(q)

    async def emit(self, job_id: str, stage: str, message: str, status: JobStatus | None = None) -> None:
        job = self._jobs[job_id]
        job.stage = stage
        job.message = message
        if status:
            job.status = status
        event = JobEvent(
            job_id=job_id,
            stage=stage,
            message=message,
            status=job.status,
            artifacts=dict(job.artifacts),
        )
        for q in list(job.subscribers):
            await q.put(event)

    def set_artifacts(self, job_id: str, artifacts: dict[str, str]) -> None:
        self._jobs[job_id].artifacts = artifacts

    def set_failed(self, job_id: str, error: str) -> None:
        job = self._jobs[job_id]
        job.status = JobStatus.failed
        job.error = error

    def set_succeeded(self, job_id: str) -> None:
        self._jobs[job_id].status = JobStatus.succeeded
